"""Four controlled Source families; no DLL/WinAPI/Node/process execution here."""
from dataclasses import replace
import ctypes as C
import json
import os
from pathlib import Path
import pytest
from scripts.verification import cold_owner_pipe as m
from scripts.verification.cold_owner_connection import _FrameContract

class Clock:
    value = 1
    def __call__(self):
        return self.value

def policy():
    return m.ProbePolicy(4096, 8200, 2*1024*1024, 64*1024*1024,
                         10_000, 20_000, 30_000, 40_000,
                         object(), object(), object())

def packet(extra=None):
    value = {'schema':'rentgen-owner-bootstrap-observation/1','type':'BOOTSTRAP',
             'run_nonce':'a'*32,'connection_generation':1,'sequence':1,
             'request_id':'b'*32,'bindings_sha256':'c'*64}
    if extra:
        value.update(extra)
    raw = json.dumps(value, separators=(',',':')).encode('ascii')
    return len(raw).to_bytes(4,'big') + raw

class Fake(m.SinkBackend):
    """Native sink contract simulator; values are artificial, not OS proof."""
    def __init__(self, image):
        self.image = image
        self.next_handle = 10
        self.calls = []
        self.source = packet()
        self.at = 0
        self.ops = {}
        self.written = bytearray()
        self.peer = 101
        self.alive = True
        self.stall = False
        self.late_done = False
        self.before_close = None
        self.pipe_handle = None
        self.fault_create = None
        self.fault_close = None
        self.probe = None

    def invoke(self, call):
        self.calls.append(call)
        out = call.out
        out.entered = 1
        out.done = out.ok = 1
        op = call.code
        if op in (m.CREATE_JOB,m.CREATE_EVENT,m.CREATE_SD,m.CREATE_PIPE,m.DUP_JOB):
            self.next_handle += 1
            out.h1 = self.next_handle
            if op == m.CREATE_PIPE:
                self.pipe_handle = out.h1
            if op == m.CREATE_JOB and self.fault_create is not None:
                assert self.probe.resources[-1].call is call  # registered BEFORE effect
                raise self.fault_create  # a valid, completed sink survives P
        elif op == m.CREATE_PROCESS:
            out.h1, out.h2 = 41, 42
        elif op == m.SET_JOB:
            pass
        elif op == m.JOB_LIMITS:
            out.value, out.extra, out.birth = m.FLAGS, 1, 64*1024*1024
        elif op == m.JOB_PIDS:
            out.value = out.extra = 1 if self.alive else 0
            out.birth = 101 if self.alive else 0
        elif op == m.MEMBER:
            out.value = 1
        elif op == m.IDENTITY:
            out.value, out.birth, out.extra = 101, 777, 258 if self.alive else 0
            out.image = self.image
        elif op == m.PEER_PID:
            out.value = self.peer
        elif op == m.RESUME:
            out.value = 1
        elif op in (m.CONNECT,m.READ,m.WRITE):
            out.ok, out.error = 0, m.PENDING
            self.ops[int(call.args.p)] = call
        elif op == m.RESULT:
            original = self.ops[int(call.args.p)]
            if self.stall and not self.late_done:
                out.ok, out.error = 0, m.INCOMPLETE
            elif original.code == m.READ:
                count = min(int(original.args.count), 97, len(self.source)-self.at)
                data = self.source[self.at:self.at+count]
                self.at += count
                buffer = (C.c_ubyte * count).from_address(int(original.args.q))
                buffer[:] = data
                out.value = count
            elif original.code == m.WRITE:
                count = min(83, int(original.args.count))
                self.written.extend(bytes((C.c_ubyte * count).from_address(int(original.args.q))))
                out.value = count
        elif op == m.CANCEL:
            out.ok, out.error = 0, 1168  # not-found: never terminal
        elif op in (m.TERMINATE_PROCESS,m.TERMINATE_JOB):
            self.alive = False
        elif op == m.PROCESS_WAIT:
            out.value, out.extra = (258, 259) if self.alive else (0, 0)
        elif op in (m.CLOSE,m.LOCAL_FREE):
            if self.fault_close is not None:
                out.done = 0  # ambiguity cannot be retried numerically
                raise self.fault_close
            if call.args.a == self.pipe_handle:
                self.alive = False
            if self.before_close is not None:
                self.before_close()

def probe(tmp_path):
    clock = Clock()
    image = os.path.normcase(str((tmp_path/'known-node.exe').resolve()))
    fake = Fake(image)
    p = m.PipeProbe(fake, policy(), _FrameContract(1,'a'*32,'b'*32,'c'*64),
                    clock=clock, pause=lambda _:None)
    fake.probe = p
    return p, fake, clock

def seeded(p, fake):
    # Exactly one operation/lease; native effects are exclusively Fake.invoke.
    p.expected_image = fake.image
    p.consumed = True
    p.job = p._create(m.CREATE_JOB)
    p.pipe = p._create(m.CREATE_PIPE)
    call = m.Call(m.CREATE_PROCESS)
    p.process = p._resource(call)
    p.thread = p._resource(call, field='h2')
    p.calls.append(call)
    fake.invoke(call)
    p.phase = 'IN_FLIGHT'

def test_owned_refusal_partial_io_one_lease_and_old_completion_gate(tmp_path):
    p, fake, _ = probe(tmp_path)
    seeded(p, fake)
    token, lease = p.token, p.lease
    p.exchange_refusal()
    reply = bytes(fake.written)
    decoded = json.loads(reply[4:])
    assert int.from_bytes(reply[:4],'big') == len(reply)-4
    assert decoded['type'] == 'REFUSAL' and decoded['sequence'] == 2
    assert decoded['code'] == 'DAILY_ROOT_EDITOR_OWNER_REQUIRED'
    assert decoded['request_id'] == 'b'*32
    assert p.token is token and p.lease is lease
    assert p.snapshot()['EditorRole'] is False and p.snapshot()['ready'] is False
    assert p.cleanup_step() is True
    assert all(io.terminal and io.buffer is None and io.ov is None for io in p.ios)
    assert all(r.state == 'closed' for r in p.resources)
    calls = len(fake.calls)
    assert p.cleanup_step() is True and len(fake.calls) == calls
    with pytest.raises(m.PipeRefusal):
        p.exchange_refusal()
    assert len(fake.calls) == calls
    # No _Completion is created/passed into the old retained-connection dispatcher.

def test_kernel_peer_and_wire_cannot_create_editor_authority(tmp_path):
    for wrong_peer, extra in ((202,None),(None,{'claimed_pid':101,'peer_bound':1})):
        p, fake, _ = probe(tmp_path)
        seeded(p, fake)
        if wrong_peer is not None:
            fake.peer = wrong_peer  # correct wire/nonce/image/Job is insufficient
        if extra is not None:
            fake.source = packet(extra)
        with pytest.raises((m.PipeRefusal, RuntimeError)):
            p.exchange_refusal()
        assert p.revoked and p.reply is None and not p.refusal_exchanged
        assert not any(c.code == m.WRITE for c in fake.calls)
        state = p.snapshot()
        assert state['EditorRole'] is state['peer_bound'] is state['ready'] is False
        assert state['initializer'] == state['runner'] == state['Core'] == 0

def test_cancel_not_found_late_completion_and_original_closure_budget(tmp_path):
    p, fake, clock = probe(tmp_path)
    seeded(p, fake)
    fake.stall = True
    io = p._start_io(m.READ, 4)
    held = io.buffer
    p.revoke()
    assert p.cleanup_step() is False
    assert io.cancel_attempted and io.cancel_call.out.error == 1168
    assert not io.terminal and io.buffer is held
    assert not any(c.code == m.CLOSE for c in fake.calls)
    fake.late_done = True
    assert p.poll_io(io, cleanup=True) is True
    assert p.revoked and not p.refusal_exchanged and io.buffer is held
    # The view cannot renew the original absolute closure end.
    p.policy = replace(p.policy, closure_until_ns=100_000)
    assert p.cleanup_step() is False  # known own process stop, then reap on next step
    fake.before_close = lambda:setattr(clock,'value',p._captured_policy.closure_until_ns)
    assert p.cleanup_step() is False
    assert any(r.state == 'closed' for r in p.resources)
    assert any(r.state != 'closed' for r in p.resources)
    assert io.buffer is held and not p.closed

def test_pre_effect_refusal_persisted_creation_output_and_primary_P(tmp_path):
    p, fake, _ = probe(tmp_path)
    with pytest.raises(m.PipeRefusal):
        m.PipeProbe(fake, replace(policy(), ABI_ref=None), p.contract, clock=p.clock)
    assert fake.calls == []
    seeded(p, fake)
    calls = len(fake.calls)
    p.policy = replace(p.policy, job_bytes=128*1024*1024)
    with pytest.raises(m.PipeRefusal):
        p._start_io(m.READ, 4)
    assert len(fake.calls) == calls
    # Original P survives a retained native creation and unknown-close F.
    q, native, _ = probe(tmp_path)
    primary, secondary = KeyboardInterrupt('primary'), RuntimeError('cleanup')
    native.fault_create, native.fault_close = primary, secondary
    def interrupted_setup(_):
        q.consumed = True
        q._create(m.CREATE_JOB)
    q.setup_fixture = interrupted_setup
    with pytest.raises(KeyboardInterrupt) as got:
        q.run({})
    assert got.value is primary and q.primary is primary and q.secondary is secondary
    assert q.resources[0].handle() is not None
    assert q.resources[0].state == 'closing_unknown'
    before = len(native.calls)
    assert q.cleanup_step() is False and len(native.calls) == before


@pytest.mark.parametrize('change', ['revoke', 'replacement', 'connect_expiry', 'hello_expiry'])
def test_late_io_authority_change_after_event_refuses_before_new_io(tmp_path, change):
    p, fake, clock = probe(tmp_path)
    seeded(p, fake)
    original_invoke = fake.invoke
    def changed_after_event(call):
        original_invoke(call)
        if call.code == m.CREATE_EVENT:
            if change == 'revoke':
                p.revoke()
            elif change == 'replacement':
                p.policy = replace(p.policy, job_bytes=128*1024*1024)
            elif change == 'connect_expiry':
                clock.value = p._captured_policy.connect_until_ns
            else:
                clock.value = p._captured_policy.hello_until_ns
    fake.invoke = changed_after_event
    kind = m.CONNECT if change == 'connect_expiry' else m.READ
    with pytest.raises(m.PipeRefusal):
        p._start_io(kind, 0 if kind == m.CONNECT else 4)
    assert not any(call.code in (m.CONNECT, m.READ, m.WRITE) for call in fake.calls)


def test_wait_at_issue_gate_cannot_cross_original_closure_end(tmp_path):
    p, fake, clock = probe(tmp_path)
    seeded(p, fake)
    original_gate = p.gate
    class DelayedGate:
        def __enter__(self):
            original_gate.__enter__()
            clock.value = p._captured_policy.closure_until_ns
            return self
        def __exit__(self, *args):
            return original_gate.__exit__(*args)
    p.gate = DelayedGate()
    before = len(fake.calls)
    with pytest.raises(m.PipeRefusal):
        p._invoke(m.JOB_PIDS, a=p.job.handle())
    assert len(fake.calls) == before

def test_issued_native_producer_retains_slots_before_entered_publication(tmp_path):
    p, fake, _ = probe(tmp_path)
    seeded(p, fake)
    original_invoke = fake.invoke
    held_resources = tuple(p.resources)
    observed = []
    def delayed_publication(call):
        if call.code == m.JOB_LIMITS:
            # The backend producer exists, but its native output is still zero.
            # Reentrant cleanup models Root's observation while it has not returned.
            assert call.out.entered == 0
            before = len(fake.calls)
            assert p.cleanup_step() is False
            assert len(fake.calls) == before
            assert all(resource.state == 'held' for resource in held_resources)
            observed.append(call)
        original_invoke(call)
    fake.invoke = delayed_publication
    with pytest.raises(m.PipeRefusal):
        p._invoke(m.JOB_LIMITS, a=p.job.handle())
    assert len(observed) == 1 and p.revoked and not p.closed
    assert not any(call.code in (m.CLOSE, m.LOCAL_FREE) for call in fake.calls)
    assert observed[0].out.entered == observed[0].out.done == 1
    assert observed[0].issued and observed[0].producer_ended
    assert p.snapshot()['issued_producers_pending'] == 0
    assert p.snapshot()['EditorRole'] is p.snapshot()['ready'] is False

@pytest.mark.parametrize('when', ['issue', 'result'])
@pytest.mark.parametrize('change', ['replacement', 'revoke'])
def test_clock_mutation_inside_gate_is_checked_before_issue_or_return(tmp_path, when, change):
    p, fake, _ = probe(tmp_path)
    seeded(p, fake)
    original_clock = p.clock
    calls = 0
    def changing_clock():
        nonlocal calls
        calls += 1
        if calls == (1 if when == 'issue' else 2):
            if change == 'replacement':
                p.policy = replace(p.policy, job_bytes=128*1024*1024)
            else:
                p.revoke()
        return original_clock()
    p.clock = changing_clock
    before = len(fake.calls)
    with pytest.raises(m.PipeRefusal):
        p._invoke(m.JOB_PIDS, a=p.job.handle())
    assert len(fake.calls) - before == (0 if when == 'issue' else 1)
    assert p.snapshot()['EditorRole'] is p.snapshot()['ready'] is False

# Source-only append proposal for Root's test_cold_owner_pipe.py.
# Reuses its existing probe/seeded/replace/pytest/m definitions.
# No changes to Root's working file and no execution by this author.

def test_absolute_connect_end_refuses_before_new_event_or_connect(tmp_path):
    p, fake, clock = probe(tmp_path)
    seeded(p, fake)
    original_policy = p._captured_policy
    clock.value = original_policy.connect_until_ns
    assert clock.value < original_policy.hello_until_ns
    before = len(fake.calls)
    with pytest.raises(m.PipeRefusal):
        p._start_io(m.CONNECT)
    assert len(fake.calls) == before
    assert not any(call.code in (m.CREATE_EVENT, m.CONNECT) for call in fake.calls)
    assert p._captured_policy is original_policy
    assert p.snapshot()['EditorRole'] is p.snapshot()['ready'] is False


def test_policy_replaced_while_waiting_for_issue_gate_refuses_before_query(tmp_path):
    p, fake, _ = probe(tmp_path)
    seeded(p, fake)
    original_policy, original_gate = p._captured_policy, p.gate
    class ReplacedGate:
        def __enter__(self):
            original_gate.__enter__()
            p.policy = replace(original_policy, job_bytes=128*1024*1024)
            return self
        def __exit__(self, *args):
            return original_gate.__exit__(*args)
    p.gate = ReplacedGate()
    before = len(fake.calls)
    with pytest.raises(m.PipeRefusal):
        p._invoke(m.JOB_LIMITS, a=p.job.handle())
    assert len(fake.calls) == before
    assert p._captured_policy is original_policy and p.policy is not original_policy
    assert all(resource.state == 'held' for resource in p.resources)


def test_producer_finish_F_cannot_replace_persisted_native_primary_P(tmp_path):
    p, fake, _ = probe(tmp_path)
    primary, secondary = KeyboardInterrupt('native primary'), RuntimeError('finish gate')
    fake.fault_create = primary
    original_gate = p.gate
    class FinishFaultGate:
        entries = 0
        def __enter__(self):
            self.entries += 1
            if self.entries == 2:
                raise secondary  # Native producer has raised P; finish publication fails.
            return original_gate.__enter__()
        def __exit__(self, *args):
            return original_gate.__exit__(*args)
    p.gate = FinishFaultGate()
    def interrupted_setup(_):
        p.consumed = True
        p._create(m.CREATE_JOB)
    p.setup_fixture = interrupted_setup
    with pytest.raises(KeyboardInterrupt) as got:
        p.run({})
    assert got.value is primary and p.primary is primary and p.secondary is secondary
    assert p.resources[0].handle() is not None
    assert p.resources[0].state == 'held' and not p.closed
    before = len(fake.calls)
    assert p.cleanup_step() is False and len(fake.calls) == before
    assert not any(call.code in (m.CLOSE, m.LOCAL_FREE) for call in fake.calls)
