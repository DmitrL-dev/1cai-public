"""Portable protocol/lifetime contracts; native diagnostic is Windows-only."""
import ctypes
import importlib.util
from pathlib import Path
import struct
from types import SimpleNamespace

import pytest


@pytest.fixture
def api():
    path = Path(__file__).resolve().parents[2]/'scripts/verification/scm_journal_notifications.py'
    spec = importlib.util.spec_from_file_location('journal_notifications_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(name='git-journal.json', action=5, *, more=False):
    name = name.encode('utf-16-le')
    size = 12 + len(name)
    padded = (size + 3) // 4 * 4
    return struct.pack('<III', padded if more else 0, action, len(name)) + name + (b'\0' * (padded-size) if more else b'')


def test_exact_rename_only_and_multi_record(api):
    data = record(more=True) + record('GIT-JOURNAL.JSON', more=True) + record(action=3, more=True) + record()
    assert api.rename_count(data) == 2
    assert api.rename_count(record('git-journal.json.tmp')) == 0


@pytest.mark.parametrize('data', [b'', b'\0'*11, b'\0'*16385,
    struct.pack('<III', 0, 5, 3)+b'abc', record()[:-1], record()+b'xxxx',
    struct.pack('<III', 13, 5, 2)+b'ab'+record(),
    struct.pack('<III', 1000, 5, 2)+b'ab', record('x/y'), record('x\\y'),
    record('x\0y'), record(action=6), struct.pack('<III', 0, 5, 2)+b'\x00\xd8'])
def test_malformed_overflow_truncation_rejected(api, data):
    with pytest.raises(RuntimeError):
        api.rename_count(data)


class FakeRead:
    def __init__(self, events, clock, packets):
        self.events, self.clock, self.packets = events, clock, packets
    def arm(self): self.events.append('arm')
    def poll(self, milliseconds):
        self.events.append(('poll', milliseconds))
        self.clock[0] += milliseconds/1000
        return self.packets.pop(0) if self.packets else None
    def close(self): self.events.append('close')


def setup_hint(api, monkeypatch, packets):
    events, clock = [], [0.0]
    monkeypatch.setattr(api, '_validate_parent', lambda worker,path: path.parent)
    monkeypatch.setattr(api.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(api, '_DirectoryRead', lambda native,parent: FakeRead(events,clock,packets))
    return api.JournalRenameHint(None, None, Path('git-journal.json')), events, clock


def test_arm_before_start_and_three_renames_are_hint_only(api, monkeypatch):
    hint, events, _ = setup_hint(api,monkeypatch,[record(),record(action=3),record(),record()])
    with hint:
        events.append('service_start')
        result = hint.wait(lambda: events.append('alive'))
    assert events[:2] == ['arm','service_start']
    assert result['rename_new_name_count'] == 3
    assert result['kind'] == 'directory_rename_scheduling_hint'
    assert events[-1] == 'close'
    assert events.count('arm') == 4


def test_timeout_unchanged_deadline_and_cleanup(api, monkeypatch):
    hint, events, clock = setup_hint(api,monkeypatch,[record(),record()])
    with pytest.raises(RuntimeError, match='Timed out'):
        with hint:
            hint.wait(lambda: None)
    assert clock[0] == 45
    assert events[-1] == 'close'
    assert all(event[1] <= 250 for event in events if isinstance(event,tuple))


@pytest.mark.parametrize('failure', ['liveness', 'malformed', 'overflow'])
def test_error_closes_without_retries(api, monkeypatch, failure):
    packets = [b'bad' if failure == 'malformed' else b'']
    hint, events, _ = setup_hint(api,monkeypatch,packets)
    def alive():
        if failure == 'liveness': raise RuntimeError('dead service')
    with pytest.raises(RuntimeError):
        with hint: hint.wait(alive)
    assert events.count('arm') == 1
    assert events[-1] == 'close'


class Kernel:
    def __init__(self, error, *, cancel=True, complete=False, close_fail=False):
        self.events=[]; self.error=error; self.cancel=cancel; self.complete=complete; self.close_fail=close_fail
    def CancelIoEx(self,*args): self.events.append('cancel'); return self.cancel
    def GetOverlappedResult(self,*args):
        assert args[-1] is True
        self.events.append('drain'); return self.complete
    def CloseHandle(self, handle): self.events.append(('close',handle)); return not self.close_fail


@pytest.mark.parametrize('cancel,complete,code', [(True,False,995),(False,True,1168),(True,True,0)])
def test_cancel_drain_race_then_both_handles(api, monkeypatch, cancel, complete, code):
    monkeypatch.setattr(ctypes,'get_last_error',lambda:code,raising=False)
    read = api._DirectoryRead.__new__(api._DirectoryRead)
    read.kernel = Kernel(code,cancel=cancel,complete=complete)
    read.directory,read.event,read.pending,read.overlapped = 1,2,True,api._Overlapped()
    read.close()
    assert read.kernel.events == ['cancel','drain',('close',2),('close',1)]
    assert not read.pending and read.directory is None and read.event is None
    read.close()
    assert len(read.kernel.events) == 4


def test_completed_io_error_still_closes(api, monkeypatch):
    monkeypatch.setattr(ctypes,'get_last_error',lambda:5,raising=False)
    read = api._DirectoryRead.__new__(api._DirectoryRead)
    read.kernel = Kernel(5)
    read.directory,read.event,read.pending,read.overlapped = 1,2,True,api._Overlapped()
    with pytest.raises(OSError,match='Drain'):
        read.close()
    assert read.kernel.events[-2:] == [('close',2),('close',1)]


def test_close_failure_does_not_skip_other_handle(api, monkeypatch):
    monkeypatch.setattr(ctypes,'get_last_error',lambda:5,raising=False)
    read = api._DirectoryRead.__new__(api._DirectoryRead)
    read.kernel = Kernel(5,close_fail=True)
    read.directory,read.event,read.pending = 1,2,False
    with pytest.raises(OSError): read.close()
    assert read.kernel.events == [('close',2),('close',1)]


def test_refuses_wrong_owned_path_before_open(api, tmp_path):
    def require(value,message):
        if not value: raise RuntimeError(message)
    worker=SimpleNamespace(ROOT=tmp_path,require=require)
    with pytest.raises(RuntimeError, match='Unowned'):
        api._validate_parent(worker,tmp_path/'other/git-journal.json')


@pytest.mark.skipif(__import__('os').name != 'nt', reason='Actual Windows API diagnostic')
def test_actual_windows_transport_and_cancel(api):
    api.diagnostic()


def test_notification_padding_is_not_filename_data(api):
    first = bytearray(record("x", more=True))
    first[-2:] = b'\xaa\xbb'  # Native alignment padding has no defined contents.
    assert api.rename_count(bytes(first)+record()) == 1


@pytest.mark.parametrize('count', [0, 16385])
def test_native_overflow_marks_io_completed_before_cleanup(api, count):
    class Completion:
        def WaitForSingleObject(self,*args): return 0
        def GetOverlappedResult(self,handle,overlapped,transferred,wait):
            transferred._obj.value = count
            return True
    read = api._DirectoryRead.__new__(api._DirectoryRead)
    read.kernel,read.pending,read.directory,read.event = Completion(),True,1,2
    read.overlapped = api._Overlapped()
    with pytest.raises(RuntimeError,match='overflow'): read.poll(250)
    assert not read.pending


def test_spurious_signal_preserves_pending_read_for_cancel(api, monkeypatch):
    class Completion:
        def WaitForSingleObject(self,*args): return 0
        def GetOverlappedResult(self,*args): return False
    monkeypatch.setattr(ctypes,'get_last_error',lambda:996,raising=False)
    read = api._DirectoryRead.__new__(api._DirectoryRead)
    read.kernel,read.pending,read.directory,read.event = Completion(),True,1,2
    read.overlapped = api._Overlapped()
    with pytest.raises(RuntimeError,match='incomplete'): read.poll(250)
    assert read.pending


def test_arm_failure_closes_transport(api, monkeypatch):
    hint, events, _ = setup_hint(api,monkeypatch,[])
    def fail(self):
        self.events.append('arm_fail')
        raise OSError('arm failed')
    monkeypatch.setattr(FakeRead,'arm',fail)
    with pytest.raises(OSError): hint.__enter__()
    assert events == ['arm_fail','close']
    assert hint.read is None


def test_late_completion_does_not_extend_deadline(api, monkeypatch):
    hint, events, clock = setup_hint(api,monkeypatch,[])
    def late(self,milliseconds):
        clock[0] = 45
        return record(more=True)+record(more=True)+record()
    monkeypatch.setattr(FakeRead,'poll',late)
    with pytest.raises(RuntimeError,match='Timed out'):
        with hint: hint.wait(lambda:None)
    assert events[-1] == 'close'


def test_native_arm_is_readonly_filename_filter_and_fixed_buffer(api):
    class Arm:
        def ResetEvent(self,event): assert event == 2; return True
        def ReadDirectoryChangesW(self,handle,buffer,size,subtree,filter_,bytes_,overlapped,callback):
            assert (handle,size,subtree,filter_,bytes_,callback) == (1,16384,False,1,None,None)
            assert overlapped._obj.Internal == 0 and overlapped._obj.hEvent == 2
            return True
    read = api._DirectoryRead.__new__(api._DirectoryRead)
    read.kernel,read.pending,read.directory,read.event = Arm(),False,1,2
    read.buffer = ctypes.create_string_buffer(16384)
    read.overlapped = api._Overlapped()
    read.overlapped.Internal = 123
    read.arm()
    assert read.pending
    with pytest.raises(RuntimeError,match='already pending'): read.arm()


def test_nonreparse_ancestors_checked_without_touching_journal(api, monkeypatch, tmp_path):
    parent = tmp_path/'localservice/data/observer-profile'
    parent.mkdir(parents=True)
    paths=[]
    original_lstat=Path.lstat
    def fake_lstat(path,*args,**kwargs):
        paths.append(path)
        if path == parent/'git-journal.json': raise AssertionError('Journal accessed')
        value = original_lstat(path,*args,**kwargs)
        return SimpleNamespace(st_file_attributes=0x400 if path == parent else 0,
                               st_mode=value.st_mode)
    def require(value,message):
        if not value: raise RuntimeError(message)
    monkeypatch.setattr(Path,'lstat',fake_lstat)
    with pytest.raises(RuntimeError,match='reparse'):
        api._validate_parent(SimpleNamespace(ROOT=tmp_path,require=require), parent/'git-journal.json')
    assert parent/'git-journal.json' not in paths


def test_hint_cannot_reuse_completed_notifications(api, monkeypatch):
    hint, _, _ = setup_hint(api,monkeypatch,[record(more=True)+record(more=True)+record()])
    with hint:
        hint.wait(lambda:None)
        with pytest.raises(RuntimeError,match='Invalid'): hint.wait(lambda:None)
    with pytest.raises(RuntimeError,match='reused'): hint.__enter__()
