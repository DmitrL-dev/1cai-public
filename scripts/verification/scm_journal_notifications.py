"""Owned Windows directory notifications: scheduling hints, never journal evidence.

No journal file is opened. The caller arms before START and proves the retained
journal only after its service process has stopped and been reaped.

Observation is bounded to 45 seconds. OS cancellation is drained synchronously
and has no hard wall-clock guarantee; the existing qualification job timeout
remains the outer bound. No pending asynchronous storage is intentionally freed.
"""
import ctypes
from ctypes import wintypes as W
import os
from pathlib import Path
import struct
import time


BUFFER_BYTES = 16384
TARGET = 'git-journal.json'


def rename_count(data):
    """Strictly decode one completed FILE_NOTIFY_INFORMATION buffer."""
    if not data or len(data) > BUFFER_BYTES:
        raise RuntimeError('Directory notification overflow or invalid size')
    offset = count = 0
    while True:
        if len(data) - offset < 12:
            raise RuntimeError('Truncated directory notification header')
        next_offset, action, size = struct.unpack_from('<III', data, offset)
        end = offset + 12 + size
        if action not in range(1, 6) or not size or size % 2 or end > len(data):
            raise RuntimeError('Malformed directory notification')
        try:
            name = data[offset + 12:end].decode('utf-16-le', errors='strict')
        except UnicodeDecodeError as exc:
            raise RuntimeError('Invalid directory notification name') from exc
        if '\x00' in name or '/' in name or '\\' in name:
            raise RuntimeError('Unexpected directory notification path')
        count += action == 5 and name == TARGET
        if next_offset == 0:
            # The final record may include up to three DWORD alignment bytes.
            if len(data) - end > 3:
                raise RuntimeError('Unexpected directory notification tail')
            return count
        if next_offset % 4 or next_offset < 12 + size or offset + next_offset >= len(data):
            raise RuntimeError('Invalid directory notification offset')
        if next_offset - (12 + size) > 3:
            raise RuntimeError('Invalid directory notification padding')
        offset += next_offset


def _validate_parent(worker, path):
    path = Path(path)
    root = worker.ROOT
    worker.require(path == root/'localservice/data/observer-profile'/TARGET,
                   'Unowned journal notification path')
    parent = path.parent
    worker.require(root.is_absolute() and parent.resolve(strict=True) == parent,
                   'Journal notification parent is not canonical')
    current = root
    for part in ('', *parent.relative_to(root).parts):
        if part:
            current /= part
        info = current.lstat()
        worker.require(current.is_dir() and not info.st_file_attributes & 0x400,
                       'Journal notification ancestor is missing or reparse')
    return parent


class _Overlapped(ctypes.Structure):
    _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                ('Offset', W.DWORD), ('OffsetHigh', W.DWORD), ('hEvent', W.HANDLE)]


class _DirectoryRead:
    """One overlapped read at a time, owning all storage until completion."""
    def __init__(self, native, parent):
        if os.name != 'nt':
            raise RuntimeError('Windows required for directory notifications')
        self.kernel = native.kernel
        self.directory = self.event = None
        self.pending = False
        self.buffer = ctypes.create_string_buffer(BUFFER_BYTES)
        self.overlapped = _Overlapped()
        signatures = (
            ('CreateFileW', [W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE], W.HANDLE),
            ('CreateEventW', [ctypes.c_void_p,W.BOOL,W.BOOL,W.LPCWSTR], W.HANDLE),
            ('ResetEvent', [W.HANDLE], W.BOOL),
            ('ReadDirectoryChangesW', [W.HANDLE,ctypes.c_void_p,W.DWORD,W.BOOL,W.DWORD,
                ctypes.POINTER(W.DWORD),ctypes.POINTER(_Overlapped),ctypes.c_void_p], W.BOOL),
            ('WaitForSingleObject', [W.HANDLE,W.DWORD], W.DWORD),
            ('GetOverlappedResult', [W.HANDLE,ctypes.POINTER(_Overlapped),ctypes.POINTER(W.DWORD),W.BOOL], W.BOOL),
            ('CancelIoEx', [W.HANDLE,ctypes.POINTER(_Overlapped)], W.BOOL),
            ('CloseHandle', [W.HANDLE], W.BOOL),
            ('GetFinalPathNameByHandleW', [W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD], W.DWORD),
            ('GetFileInformationByHandleEx', [W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD], W.BOOL),
        )
        for name, args, result in signatures:
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = args, result
        try:
            # FILE_LIST_DIRECTORY only. Share all; never block atomic replacement.
            self.directory = self.kernel.CreateFileW(str(parent), 1, 7, None, 3,
                                                     0x02000000 | 0x40000000 | 0x00200000, None)
            if self.directory in (None, ctypes.c_void_p(-1).value):
                self.directory = None
                self._error('CreateFileW directory')
            resolved = ctypes.create_unicode_buffer(32768)
            size = self.kernel.GetFinalPathNameByHandleW(self.directory, resolved, len(resolved), 0)
            if not size or size >= len(resolved) or resolved.value != '\\\\?\\' + str(parent):
                raise RuntimeError('Opened notification directory binding differs')
            attributes = (W.DWORD * 2)()
            self._check(self.kernel.GetFileInformationByHandleEx(self.directory, 9,
                        ctypes.byref(attributes), ctypes.sizeof(attributes)), 'Directory attributes')
            if not attributes[0] & 0x10 or attributes[0] & 0x400:
                raise RuntimeError('Opened notification parent is not a non-reparse directory')
            self.event = self.kernel.CreateEventW(None, True, False, None)
            self._check(self.event, 'CreateEventW')
            self.overlapped.hEvent = self.event
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _error(operation):
        raise OSError(ctypes.get_last_error(), operation)

    def _check(self, value, operation):
        if not value:
            self._error(operation)

    def arm(self):
        if self.pending:
            raise RuntimeError('Directory notification read already pending')
        self.overlapped = _Overlapped()
        self.overlapped.hEvent = self.event
        self._check(self.kernel.ResetEvent(self.event), 'ResetEvent')
        self._check(self.kernel.ReadDirectoryChangesW(self.directory, self.buffer, BUFFER_BYTES,
                    False, 1, None, ctypes.byref(self.overlapped), None), 'ReadDirectoryChangesW')
        self.pending = True

    def poll(self, milliseconds):
        result = self.kernel.WaitForSingleObject(self.event, milliseconds)
        if result == 258:
            return None
        if result != 0:
            self._error('WaitForSingleObject')
        transferred = W.DWORD()
        success = self.kernel.GetOverlappedResult(self.directory, ctypes.byref(self.overlapped),
                                                  ctypes.byref(transferred), False)
        code = 0 if success else ctypes.get_last_error()
        if code == 996:  # IO_INCOMPLETE must retain the async storage.
            raise RuntimeError('Signaled directory notification remains incomplete')
        self.pending = False
        if not success:
            raise OSError(code, 'Directory notification completion')
        if not transferred.value or transferred.value > BUFFER_BYTES:
            raise RuntimeError('Directory notification overflow')
        return self.buffer.raw[:transferred.value]

    def close(self):
        try:
            if self.pending:
                cancelled = self.kernel.CancelIoEx(self.directory, ctypes.byref(self.overlapped))
                cancel_error = 0 if cancelled else ctypes.get_last_error()
                transferred = W.DWORD()
                # CancelIoEx only requests cancellation. Drain before releasing
                # OVERLAPPED/buffer. Never treat ERROR_NOT_FOUND as completion.
                success = self.kernel.GetOverlappedResult(self.directory,
                    ctypes.byref(self.overlapped), ctypes.byref(transferred), True)
                code = 0 if success else ctypes.get_last_error()
                self.pending = False
                if code not in (0, 995):
                    raise OSError(code, 'Drain directory notification')
                if cancel_error not in (0, 1168):
                    raise OSError(cancel_error, 'CancelIoEx')
        finally:
            close_error = None
            for field in ('event', 'directory'):
                handle = getattr(self, field)
                if handle is not None:
                    setattr(self, field, None)
                    if not self.kernel.CloseHandle(handle) and close_error is None:
                        close_error = OSError(ctypes.get_last_error(), 'Close ' + field)
            if close_error is not None:
                raise close_error



class JournalRenameHint:
    def __init__(self, native, worker, path):
        self.native, self.worker, self.path = native, worker, Path(path)
        self.read = None
        self.used = False
        self.waited = False

    def __enter__(self):
        if self.used:
            raise RuntimeError('Journal notification hint cannot be reused')
        self.used = True
        parent = _validate_parent(self.worker, self.path)
        self.read = _DirectoryRead(self.native, parent)
        try:
            self.read.arm()
        except BaseException:
            self.close()
            raise
        return self

    def wait(self, check_alive, seconds=45):
        if self.read is None or self.waited or not 0 < seconds <= 45:
            raise RuntimeError('Invalid journal notification wait')
        self.waited = True
        start = time.monotonic()
        deadline = start + seconds
        count = 0
        while True:
            check_alive()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('Timed out: journal rename scheduling hint')
            data = self.read.poll(min(250, max(0, int(remaining * 1000))))
            if time.monotonic() >= deadline:
                raise RuntimeError('Timed out: journal rename scheduling hint')
            if data is None:
                continue
            count += rename_count(data)
            if count >= 3:
                check_alive()
                return {'kind': 'directory_rename_scheduling_hint',
                        'rename_new_name_count': count, 'elapsed_seconds': time.monotonic() - start}
            self.read.arm()

    def close(self):
        if self.read is not None:
            read, self.read = self.read, None
            read.close()

    def __exit__(self, *_):
        self.close()


def diagnostic():
    """Synthetic ordinary-user Windows check, with no SCM or product access."""
    import json
    import tempfile
    from types import SimpleNamespace

    if os.name != 'nt':
        raise RuntimeError('Diagnostic requires actual Windows')
    def require(value, message):
        if not value:
            raise RuntimeError(message)
    native = SimpleNamespace(kernel=ctypes.WinDLL('kernel32', use_last_error=True))
    with tempfile.TemporaryDirectory(prefix='rg-rename-diagnostic-') as temporary:
        root = Path(temporary).resolve(strict=True)
        parent = root/'localservice/data/observer-profile'
        parent.mkdir(parents=True)
        target = parent/TARGET
        worker = SimpleNamespace(ROOT=root, require=require)
        # Closing an armed, never-completed read exercises actual cancellation.
        with JournalRenameHint(native, worker, target):
            pass
        try:
            with JournalRenameHint(native, worker, target) as idle:
                idle.wait(lambda: None, seconds=0.05)
        except RuntimeError as exc:
            if str(exc) != 'Timed out: journal rename scheduling hint':
                raise
        else:
            raise RuntimeError('Empty notification wait did not time out')
        written = 0
        def publish_one():
            nonlocal written
            if written < 3:
                candidate = parent/f'owned-{written}.tmp'
                candidate.write_bytes(b'qualification diagnostic only\n')
                os.replace(candidate, target)
                written += 1
        with JournalRenameHint(native, worker, target) as hint:
            result = hint.wait(publish_one, seconds=5)
        require(written == 3, 'Synthetic diagnostic did not publish three renames')
        # No target read is needed to establish notification transport behavior.
    print(json.dumps({'diagnostic': 'windows-owned-directory-notifications',
                      'hint': result, 'cleanup': 'completed',
                      'checked': ['pending_cancel', 'timeout_cancel', 'rename_completion'],
                      'native_acceptance': False}))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnostic', action='store_true', required=True)
    parser.parse_args()
    diagnostic()
