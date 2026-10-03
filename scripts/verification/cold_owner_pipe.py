"""Root-private negative pipe probe. Import has no WinAPI/DLL/process effects.
Requires a separately reviewed/pinned output-sink shim. Never a product backend.
All Native result slots are owned before calls; call-return != IO completion.
"""
from dataclasses import dataclass, field
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from threading import Lock, RLock, Thread, Event
from time import monotonic_ns, sleep

from .cold_owner_connection import (
    _FrameContract, _FrameExchange, _FrameStorage, _app_decode, _app_refusal,
)

class PipeRefusal(RuntimeError):
    pass

def need(value, code):
    if not value:
        raise PipeRefusal(code)

# Private Source ceilings, not measured OS budgets or Editor-role facts.
MAX_CALLS, CLEANUP_RESERVE, MAX_IO, MAX_FRAME = 320, 64, 16, 4096
CREATE_JOB, SET_JOB, JOB_LIMITS, JOB_PIDS, MEMBER = 1, 2, 3, 4, 5
CREATE_SD, LOCAL_FREE, CREATE_PIPE, CREATE_EVENT = 6, 7, 8, 9
CREATE_PROCESS, RESUME, IDENTITY, PEER_PID = 10, 11, 12, 13
CONNECT, READ, WRITE, RESULT, CANCEL = 14, 15, 16, 17, 18
CLOSE, TERMINATE_JOB, TERMINATE_PROCESS, PROCESS_WAIT, DUP_JOB = 19, 20, 21, 22, 23
FLAGS = 0x2000 | 0x8 | 0x200
PENDING, INCOMPLETE, ABORTED, PIPE_CONNECTED = 997, 996, 995, 535
TERMINAL_IO_ERRORS = frozenset((ABORTED, 109, 38))
INVALID = C.c_void_p(-1).value

class NativeArgs(C.Structure):
    _fields_ = [('a', C.c_void_p), ('b', C.c_void_p), ('p', C.c_void_p),
                ('q', C.c_void_p), ('count', C.c_uint32), ('flags', C.c_uint32),
                ('number', C.c_uint64), ('path', C.c_wchar_p), ('command', C.c_wchar_p),
                ('environment', C.c_wchar_p), ('cwd', C.c_wchar_p)]

class NativeOut(C.Structure):
    _fields_ = [('entered', C.c_uint32), ('done', C.c_uint32),
                ('ok', C.c_uint32), ('error', C.c_uint32),
                ('h1', C.c_void_p), ('h2', C.c_void_p),
                ('value', C.c_uint32), ('extra', C.c_uint32),
                ('birth', C.c_uint64), ('image', C.c_wchar * 1024)]

class Overlapped(C.Structure):
    _fields_ = [('internal', C.c_size_t), ('internal_high', C.c_size_t),
                ('offset', C.c_uint32), ('offset_high', C.c_uint32),
                ('event', C.c_void_p)]

@dataclass(frozen=True)
class ProbePolicy:
    frame_bytes: int
    aggregate_bytes: int
    retained_storage_bytes: int
    job_bytes: int
    connect_until_ns: int
    hello_until_ns: int
    cancel_until_ns: int
    closure_until_ns: int
    ABI_ref: object
    ACL_ref: object
    admission_ref: object

    def validate(self, now):
        nums = (self.frame_bytes, self.aggregate_bytes, self.retained_storage_bytes,
                self.job_bytes, self.connect_until_ns, self.hello_until_ns,
                self.cancel_until_ns, self.closure_until_ns)
        need(all(type(v) is int and v > 0 for v in nums), 'PROBE_POLICY')
        need(1 <= self.frame_bytes <= MAX_FRAME and
             self.frame_bytes <= self.aggregate_bytes <= 2 * (MAX_FRAME + 4),
             'PROBE_BYTE_LIMITS')
        required = (MAX_CALLS + CLEANUP_RESERVE) * (C.sizeof(NativeArgs) + C.sizeof(NativeOut))
        required += MAX_IO * (self.frame_bytes + C.sizeof(Overlapped)) + 2 * (self.frame_bytes + 4) + 131072
        need(required <= self.retained_storage_bytes <= 16 * 1024 * 1024,
             'PROBE_STORAGE_LIMIT')
        need(self.job_bytes <= 512 * 1024 * 1024, 'PROBE_JOB_CEILING')
        need(now < self.connect_until_ns <= self.hello_until_ns <=
             self.cancel_until_ns <= self.closure_until_ns <= now + 30_000_000_000,
             'PROBE_FROZEN_ENDS')
        need(all(v is not None for v in (self.ABI_ref, self.ACL_ref, self.admission_ref)),
             'PROBE_UNADMITTED')

@dataclass
class Call:
    code: int
    args: object = field(default_factory=NativeArgs)
    out: object = field(default_factory=NativeOut)
    refs: tuple = ()
    attempted: bool = False
    issued: bool = False
    producer_ended: bool = False
    issued_until_ns: int = 0

@dataclass
class Resource:
    call: object
    field: str = 'h1'
    kind: str = 'handle'
    state: str = 'held'
    close_call: object = None

    def handle(self):
        return getattr(self.call.out, self.field)

@dataclass
class IO:
    token: object
    event: object
    ov: object
    buffer: object
    requested: int
    kind: int
    start: object = None
    poll: object = None
    terminal: bool = False
    succeeded: bool = False
    count: int = 0
    cancel_attempted: bool = False
    cancel_call: object = None

class SinkBackend:
    """Root-private effect interface; controlled tests implement only this ABI."""
    def invoke(self, call):
        raise NotImplementedError

def pinned_file(ref, limit):
    need(type(ref) is dict and set(ref) == {'path', 'bytes', 'sha256'}, 'PIN_SHAPE')
    p = Path(ref['path'])
    need(p.is_absolute() and type(ref['bytes']) is int and 0 < ref['bytes'] <= limit,
         'PIN_PATH_SIZE')
    need(type(ref['sha256']) is str and re.fullmatch('[a-f0-9]{64}', ref['sha256']),
         'PIN_DIGEST')
    with p.open('rb') as stream:
        raw = stream.read(limit + 1)
    need(len(raw) == ref['bytes'] and hashlib.sha256(raw).hexdigest() == ref['sha256'],
         'PIN_BYTES')
    return raw

class ShimBackend(SinkBackend):
    def __init__(self, dll_ref, *, policy, admission_ref, clock=monotonic_ns):
        need(type(policy) is ProbePolicy, 'NATIVE_SHIM_POLICY')
        policy.validate(clock())  # BEFORE DLL loading/ABI call
        need(admission_ref is policy.admission_ref and os.name == 'nt' and C.sizeof(C.c_void_p) == 8,
             'NATIVE_SHIM_NOT_ADMITTED')
        pinned_file(dll_ref, 4 * 1024 * 1024)
        # Loading the newly built DLL is a separate Root-admitted effect.
        self.dll = C.WinDLL(str(Path(dll_ref['path']).resolve()))
        self.call = self.dll.cp_call
        self.call.argtypes = [C.c_uint32, C.POINTER(NativeArgs), C.POINTER(NativeOut)]
        self.call.restype = None
        abi = self.dll.cp_abi
        abi.argtypes, abi.restype = [C.POINTER(C.c_uint32)], None
        self.abi = (C.c_uint32 * 6)()
        abi(self.abi)  # data-only sizes/version; retained output
        need(tuple(self.abi) == (1, 8, C.sizeof(NativeArgs), C.sizeof(NativeOut),
                                C.sizeof(Overlapped), 2), 'NATIVE_SHIM_ABI')

    def invoke(self, call):
        self.call(call.code, C.byref(call.args), C.byref(call.out))

class PipeProbe:
    def __init__(self, backend, policy, contract, *, clock=monotonic_ns, pause=sleep):
        need(isinstance(backend, SinkBackend) and type(policy) is ProbePolicy, 'PROBE_TYPES')
        need(type(contract) is _FrameContract and type(contract.generation) is int and
             1 <= contract.generation <= 2**53 - 1, 'PROBE_CONTEXT')
        need(all(type(v) is str and re.fullmatch(p, v) for v, p in (
            (contract.run_nonce, '[a-f0-9]{32}'), (contract.request_id, '[a-f0-9]{32}'),
            (contract.bindings_sha256, '[a-f0-9]{64}'))), 'PROBE_CONTEXT')
        policy.validate(clock())  # all caps/refs before any native effect
        self.backend, self.policy, self.contract = backend, policy, contract
        self._captured_policy = policy
        self.clock, self.pause = clock, pause
        self.gate, self.io_gate = RLock(), Lock()
        self.token, self.lease = object(), object()
        self.calls, self.resources, self.ios = [], [], []
        self.job = self.process = self.thread = self.pipe = self.watch_job = None
        self.watch_thread = None
        self.watch_done = Event()
        self.revoked = self.consumed = self.closed = False
        self.primary = self.secondary = None
        self.inbound = self.reply = None
        self.identity = None
        self.expected_image = None
        self.process_exit = None
        self.phase = 'REGISTERED'
        self.refusal_exchanged = False
        self._cleanup_started = False

    def _same_policy(self):
        need(self.policy is self._captured_policy, 'POLICY_REPLACED')
        return self._captured_policy

    def _dispatch(self, call, *, cleanup=False, deadline=None):
        # Issuance is atomic with Root revocation; native calls remain OUTSIDE
        # this short gate (apart from the existing explicit stop/resume gate).
        # Issued producers retain their slots even before native entered=1.
        primary = None
        try:
            with self.gate:
                now = self.clock()
                policy = self._captured_policy if cleanup else self._same_policy()
                need(not self.closed, 'PROBE_CLOSED')
                if deadline is None:
                    deadline = ('closure_until_ns' if cleanup else
                                'connect_until_ns' if self.phase == 'REGISTERED' else
                                'hello_until_ns')
                need(deadline in ('connect_until_ns', 'hello_until_ns',
                                  'cancel_until_ns', 'closure_until_ns'), 'ISSUE_END')
                end = min(policy.closure_until_ns, getattr(policy, deadline))
                need(now < end, 'CLOSURE_EXPIRED' if
                     deadline == 'closure_until_ns' else 'ISSUE_EXPIRED')
                need(cleanup or (not self.revoked and
                     self.phase in ('REGISTERED', 'IN_FLIGHT')), 'ISSUE_REVOKED')
                cap = MAX_CALLS + CLEANUP_RESERVE if cleanup else MAX_CALLS
                need(not call.issued and len(self.calls) < cap, 'NATIVE_CALL_LIMIT')
                self.calls.append(call)  # retained args/out/refs BEFORE issuance
                call.issued_until_ns = end
                call.issued = call.attempted = True
            self.backend.invoke(call)  # may block; no owner gate held here
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                with self.gate:
                    call.producer_ended = True  # invocation returned or raised
            except BaseException as finish_error:
                if self.secondary is None:
                    self.secondary = finish_error
                if primary is None:
                    raise
                # Keep the original P; a failed finish publication stays pending.
        # A revoked/expired issued result is retained for cleanup only.
        with self.gate:
            now = self.clock()
            if not cleanup:
                self._same_policy()
                need(not self.revoked and not self.closed, 'ISSUED_RESULT_REVOKED')
            need(now < call.issued_until_ns, 'ISSUED_RESULT_EXPIRED')
        return call

    def _invoke(self, code, *, cleanup=False, refs=(), deadline=None, **fields):
        call = Call(code, refs=tuple(refs))
        for key, value in fields.items():
            setattr(call.args, key, value)
        return self._dispatch(call, cleanup=cleanup, deadline=deadline)

    def _producers_settled(self):
        with self.gate:
            return not any((c.issued and not c.producer_ended) or
                           (c.out.entered == 1 and c.out.done != 1)
                           for c in self.calls)

    @staticmethod
    def _ok(call):
        need(call.out.entered == 1 and call.out.done == 1 and call.out.ok == 1,
             'NATIVE_CALL_FAILED')
        return call.out

    def _resource(self, call, *, field='h1', kind='handle'):
        resource = Resource(call, field, kind)
        self.resources.append(resource)  # stable output slot, not a detached number
        return resource

    def _create(self, code, *, kind='handle', **fields):
        # Register even a HANDLE-returning creation BEFORE invoke, using C output sink.
        call = Call(code)
        for key, value in fields.items():
            setattr(call.args, key, value)
        resource = self._resource(call, kind=kind)
        self._dispatch(call)
        self._ok(call)
        need(resource.handle() not in (None, 0, INVALID), 'CREATE_HANDLE')
        return resource

    def _live(self):
        out = self._ok(self._invoke(IDENTITY, a=self.process.handle()))
        proof = (int(out.value), int(out.birth), os.path.normcase(os.path.abspath(out.image)), int(out.extra))
        need(proof[0] > 0 and proof[1] > 0 and proof[3] == 258 and
             self.expected_image is not None and proof[2] == self.expected_image, 'HELD_NOT_LIVE')
        need(self._ok(self._invoke(MEMBER, a=self.job.handle(),
                                 b=self.process.handle())).value == 1, 'NOT_OWN_JOB')
        group = self._ok(self._invoke(JOB_PIDS, a=self.job.handle()))
        need(group.value == group.extra == 1 and int(group.birth) == proof[0],
             'INCOMPLETE_JOB')
        limits = self._ok(self._invoke(JOB_LIMITS, a=self.job.handle()))
        need(limits.value == FLAGS and limits.extra == 1 and
             limits.birth == self._same_policy().job_bytes, 'JOB_LIMITS_CHANGED')
        if self.identity is None:
            self.identity = proof[:3]
        need(proof[:3] == self.identity, 'HELD_IDENTITY_CHANGED')
        return proof[0]

    def _peer(self):
        before = self._live()
        peer = self._ok(self._invoke(PEER_PID, a=self.pipe.handle())).value
        after = self._live()
        need(peer == before == after, 'PIPE_PEER_MISMATCH')
        # This is ONLY the exact-created fixture client; Editor role stays false.

    def _watch(self):
        try:
            while not self.watch_done.wait(.01):
                if self.clock() >= self._captured_policy.hello_until_ns:
                    self.revoke()
                    self._invoke(TERMINATE_JOB, cleanup=True, a=self.watch_job.handle())
                    return
        except BaseException as error:
            if self.secondary is None:
                self.secondary = error
            self.revoke()
        # Thread remains in ledger until joined; close its duplicate only afterwards.

    def setup_fixture(self, spec):
        policy = self._same_policy()
        need(self.clock() < policy.connect_until_ns and not self.consumed and
             not self.revoked, 'PROBE_PRE_EFFECT_REFUSAL')
        need(type(spec) is dict and set(spec) == {
            'node', 'client', 'bridge', 'bootstrap', 'config', 'report', 'cwd', 'environment',
            'pipe_name', 'logon_sid', 'expected_sddl'}, 'FIXTURE_SPEC')
        for key, limit in (('node', 128 * 1024 * 1024), ('client', 65536),
                           ('bridge', 65536), ('bootstrap', 65536), ('config', 8192)):
            pinned_file(spec[key], limit)
        need(all(Path(spec[k]).is_absolute() for k in ('report', 'cwd')), 'FIXTURE_PATH')
        name, sid = spec['pipe_name'], spec['logon_sid']
        need(type(name) is str and re.fullmatch(r'\\\\\.\\pipe\\rentgen-refusal-[a-f0-9]{32}', name),
             'LOCAL_PIPE_NAME')
        need(type(sid) is str and re.fullmatch(r'S-1-5-5-[0-9]+-[0-9]+', sid), 'LOGON_SID')
        # Same-logon fixture Node/libuv opens GENERIC_READ|GENERIC_WRITE. This GA
        # ACE is allowed ONLY for this negative fixture; no trusted endpoint claim.
        sddl = 'D:P(A;;GA;;;' + sid + ')'
        need(spec['expected_sddl'] == sddl, 'EXPLICIT_DACL')
        cfg = json.loads(pinned_file(spec['config'], 8192))
        expected = {'generation': self.contract.generation,
                    'run_nonce': self.contract.run_nonce, 'request_id': self.contract.request_id,
                    'bindings_sha256': self.contract.bindings_sha256}
        need(cfg.get('expected') == expected and cfg.get('pipe_name') == name and
             cfg.get('bridge') == spec['bridge'] and cfg.get('bootstrap') == spec['bootstrap'] and
             cfg.get('report') == spec['report'] and
             cfg.get('schema') == 'rentgen-root-pipe-refusal-client/1' and
             type(cfg.get('client_window_ms')) is int and 100 <= cfg['client_window_ms'] <= 5000,
             'CLIENT_CONFIG_BINDING')
        need(type(spec['environment']) is dict and set(spec['environment']) == {'SYSTEMROOT', 'TEMP', 'TMP'} and
             all(type(k) is str and type(v) is str and k and '=' not in k and
                 '\0' not in k + v for k, v in spec['environment'].items()), 'FIXTURE_ENV')
        with self.gate:
            need(not self.consumed and not self.revoked, 'LEASE_REUSED')
            self.consumed = True
        need(spec['environment']['TEMP'] == spec['environment']['TMP'] == spec['cwd'],
             'OWNED_TEMP_ONLY')
        self.expected_image = os.path.normcase(str(Path(spec['node']['path']).resolve()))
        self.job = self._create(CREATE_JOB)
        self._ok(self._invoke(SET_JOB, a=self.job.handle(), number=policy.job_bytes))
        limits = self._ok(self._invoke(JOB_LIMITS, a=self.job.handle()))
        empty = self._ok(self._invoke(JOB_PIDS, a=self.job.handle()))
        need(limits.value == FLAGS and limits.extra == 1 and limits.birth == policy.job_bytes
             and empty.value == empty.extra == 0, 'JOB_BEFORE_CREATE')
        self.watch_job = self._create(DUP_JOB, a=self.job.handle())
        self.watch_thread = Thread(target=self._watch, name='Root-pipe-refusal-stop', daemon=False)
        self.watch_thread.start()
        descriptor = self._create(CREATE_SD, kind='local', path=sddl)
        self.pipe = self._create(CREATE_PIPE, a=descriptor.handle(), path=name,
                                 count=policy.frame_bytes)
        # Process output h1/h2 are both pre-registered in the SAME retained sink.
        command = subprocess.list2cmdline([spec['node']['path'], spec['client']['path'],
                                           spec['config']['path'],
                                           str(spec['config']['bytes']), spec['config']['sha256']])
        environment = '\0'.join(k + '=' + v for k, v in
                                sorted(spec['environment'].items(), key=lambda p: p[0].upper())) + '\0\0'
        need(len(command) < 8192 and len(environment) < 8192, 'CREATE_TEXT_BOUNDS')
        mutable_command, mutable_environment = C.create_unicode_buffer(command), C.create_unicode_buffer(environment)
        call = Call(CREATE_PROCESS, refs=(spec, mutable_command, mutable_environment))
        call.args.a = self.job.handle()  # JOB_LIST assignment at birth; no unassigned orphan gap
        call.args.path = spec['node']['path']
        call.args.command = C.cast(mutable_command, C.c_wchar_p)
        call.args.environment, call.args.cwd = C.cast(mutable_environment, C.c_wchar_p), spec['cwd']
        self.process = self._resource(call)
        self.thread = self._resource(call, field='h2')
        self._dispatch(call, deadline='connect_until_ns')
        self._ok(call)
        need(self.process.handle() and self.thread.handle(), 'PROCESS_OUTPUTS')
        self._live()
        # Short stop/resume gate; no owner IO is awaited under it.
        with self.gate:
            need(not self.revoked and self.clock() < policy.connect_until_ns, 'NO_LATE_RESUME')
            resumed = self._invoke_unlocked_resume()
            need(resumed == 1 and not self.revoked, 'PRIMARY_RESUME_COUNT')
            self.phase = 'IN_FLIGHT'

    def _invoke_unlocked_resume(self):
        call = Call(RESUME)
        call.args.a = self.thread.handle()
        self._dispatch(call, deadline='connect_until_ns')
        return self._ok(call).value

    def _start_io(self, kind, amount=0, data=None):
        policy = self._same_policy()
        end = policy.connect_until_ns if kind == CONNECT else policy.hello_until_ns
        need(not self.revoked and not self.closed and self.clock() < end and
             len(self.ios) < MAX_IO and not any(not io.terminal for io in self.ios),
             'IO_PRE_EFFECT_REFUSAL')
        event = self._create(CREATE_EVENT)
        ov = Overlapped()
        ov.event = event.handle()
        buffer = C.create_string_buffer(data, len(data)) if data is not None else C.create_string_buffer(amount)
        io = IO(self.token, event, ov, buffer, len(data) if data is not None else amount, kind)
        self.ios.append(io)  # BEFORE connect/read/write; retain buffer/OVERLAPPED/event
        call = Call(kind, refs=(io, ov, buffer))
        call.args.a = self.pipe.handle()
        call.args.p = C.addressof(ov)
        call.args.q = C.addressof(buffer)
        call.args.count = io.requested
        io.start = call  # retained even when fresh issuance refuses
        self._dispatch(call, deadline='connect_until_ns' if kind == CONNECT else
                       'hello_until_ns')
        self._classify_start(io)
        return io

    def _classify_start(self, io):
        if not io.start.issued:
            # A refused issuance whose producer has ended never started native IO.
            if io.start.producer_ended:
                io.terminal = True
            return
        if not io.start.producer_ended:
            return
        out = io.start.out
        if out.entered != 1 or out.done != 1:
            return  # unknown call output never treated as completion
        if io.kind == CONNECT and (out.ok == 1 or out.error == PIPE_CONNECTED):
            io.terminal = io.succeeded = True
            return
        if out.ok != 1 and out.error != PENDING:
            io.terminal = True
            return
        # Read/write, including immediate success: query exact bytes with GOR(FALSE).

    def poll_io(self, io, *, cleanup=False):
        need(io in self.ios and io.token is self.token, 'IO_IDENTITY')
        self._classify_start(io)
        if io.terminal:
            return True
        if not io.start.producer_ended or io.start.out.entered != 1 or io.start.out.done != 1:
            return False
        call = self._invoke(RESULT, cleanup=cleanup, a=self.pipe.handle(),
                            p=C.addressof(io.ov), refs=(io,),
                            deadline='closure_until_ns' if cleanup else
                            'connect_until_ns' if io.kind == CONNECT else 'hello_until_ns')
        io.poll = call
        out = call.out
        if out.entered != 1 or out.done != 1:
            return False
        if out.ok == 1:
            need(0 <= out.value <= io.requested or io.kind == CONNECT, 'IO_COUNT')
            io.terminal, io.succeeded = True, True
            io.count = 0 if io.kind == CONNECT else int(out.value)
        elif out.error in TERMINAL_IO_ERRORS:
            io.terminal = True
        return io.terminal

    def _await(self, io):
        end = self._captured_policy.connect_until_ns if io.kind == CONNECT else self._captured_policy.hello_until_ns
        while True:
            if self.revoked or self.clock() >= end:
                self.revoke()
                raise PipeRefusal('IO_DEADLINE')
            if self.poll_io(io):
                break
            self.pause(.01)
        need(not self.revoked and self.clock() < end and io.succeeded, 'IO_REFUSED')
        if io.kind != CONNECT:
            need(io.count > 0, 'IO_ZERO_PROGRESS')
        return bytes(io.buffer[:io.count])

    def _read_exact(self, amount):
        chunks, remaining = [], amount
        while remaining:
            part = self._await(self._start_io(READ, remaining))
            chunks.append(part)
            remaining -= len(part)
        return b''.join(chunks)

    def exchange_refusal(self):
        need(self.io_gate.acquire(blocking=False), 'EXCHANGE_BUSY')
        try:
            return self._exchange_refusal()
        except BaseException as primary:
            if self.primary is None:
                self.primary = primary
            self.revoke()
            raise
        finally:
            self.io_gate.release()

    def _exchange_refusal(self):
        need(self.phase == 'IN_FLIGHT' and self.consumed and not self.revoked, 'PROBE_PHASE')
        self._await(self._start_io(CONNECT))
        self._peer()
        prefix = self._read_exact(4)
        length = int.from_bytes(prefix, 'big')
        need(0 < length <= self._captured_policy.frame_bytes, 'FRAME_LENGTH')
        inbound = prefix + self._read_exact(length)
        _app_decode(inbound, self.contract, self._captured_policy)
        app = _FrameExchange(self.contract, _FrameStorage(self._captured_policy.aggregate_bytes),
                             self._captured_policy, self._captured_policy.aggregate_bytes)
        reply = _app_refusal(app, len(inbound))
        self._peer()
        with self.gate:
            now = self.clock()
            policy = self._same_policy()
            need(not self.revoked and not self.closed and
                 now < policy.hello_until_ns, 'NO_LATE_REPLY')
            self.inbound, self.reply = inbound, reply
        at = 0
        while at < len(self.reply):
            io = self._start_io(WRITE, data=self.reply[at:])
            self._await(io)
            at += io.count
        self._peer()
        with self.gate:
            now = self.clock()
            policy = self._same_policy()
            need(not self.revoked and not self.closed and
                 now < policy.hello_until_ns, 'NO_LATE_REFUSAL')
            self.refusal_exchanged = True
            self.revoke()
        return self.snapshot()

    def revoke(self):
        with self.gate:
            self.revoked = True
            if not self.closed:
                self.phase = 'CLOSURE_PENDING'

    def _cancel(self, io):
        self._classify_start(io)
        if io.terminal or io.cancel_attempted or not io.start.producer_ended:
            return
        if self.clock() >= self._captured_policy.cancel_until_ns:
            return
        io.cancel_attempted = True  # BEFORE cancel; no repeated cancel after throw
        io.cancel_call = self._invoke(CANCEL, cleanup=True, a=self.pipe.handle(),
                                      p=C.addressof(io.ov), refs=(io,),
                                      deadline='cancel_until_ns')
        # BOOL/error only describes the cancellation request. Never terminal here.

    def _close(self, resource):
        if resource.state == 'closed':
            return True
        if resource.state != 'held':
            return False
        handle = resource.handle()
        if handle in (None, 0, INVALID):
            if resource.call.out.entered == 0 or resource.call.out.done == 1:
                resource.state = 'closed'
                return True
            return False
        resource.state = 'closing_unknown'  # tombstone before effect
        call = Call(LOCAL_FREE if resource.kind == 'local' else CLOSE)
        call.args.a = handle
        resource.close_call = call
        try:
            self._dispatch(call, cleanup=True, deadline='closure_until_ns')
        finally:
            # A completed C sink can prove closure despite a Python return exception.
            if call.out.entered == call.out.done == call.out.ok == 1:
                resource.state = 'closed'
        return resource.state == 'closed'

    def cleanup_step(self):
        if not self.io_gate.acquire(blocking=False):
            return False
        try:
            return self._cleanup_step()
        finally:
            self.io_gate.release()

    def _cleanup_step(self):
        if self.closed:
            return True
        self.revoke()
        try:
            if self.clock() >= self._captured_policy.closure_until_ns or not self._producers_settled():
                return False
            for io in self.ios:
                if not io.terminal:
                    self._cancel(io)
                    if not self.poll_io(io, cleanup=True):
                        return False
            # Native call-return unknown (including watchdog) retains ALL resources.
            if not self._producers_settled():
                return False
            self.watch_done.set()
            if self.watch_thread is not None:
                self.watch_thread.join(0)
                if self.watch_thread.is_alive():
                    return False
            if self.refusal_exchanged:
                # End the server side only after every IO is terminal. This lets
                # the known Node fixture observe close and exit naturally.
                protected = (self.process, self.thread, self.job, self.watch_job)
                for resource in reversed(self.resources):
                    if not any(resource is v for v in protected):
                        if self.clock() >= self._captured_policy.closure_until_ns or not self._close(resource):
                            return False
            if self.process is not None and self.process.handle():
                wait = self._ok(self._invoke(PROCESS_WAIT, cleanup=True, a=self.process.handle()))
                if wait.value == 258:
                    if self.refusal_exchanged:
                        return False
                    if not self._cleanup_started:
                        self._cleanup_started = True
                        # Stop only the retained own-created child; Job association was at birth.
                        self._invoke(TERMINATE_PROCESS, cleanup=True, a=self.process.handle())
                        if self.job is not None and self.job.handle():
                            self._invoke(TERMINATE_JOB, cleanup=True, a=self.job.handle())
                    return False
                need(wait.value == 0, 'REAP_PENDING')
                self.process_exit = int(wait.extra)
            if self.job is not None and self.job.handle():
                group = self._ok(self._invoke(JOB_PIDS, cleanup=True, a=self.job.handle()))
                need(group.value == group.extra == 0, 'JOB_REAP_PENDING')
            for resource in reversed(self.resources):
                if self.clock() >= self._captured_policy.closure_until_ns or not self._close(resource):
                    return False
            # Only after native calls/IO/thread/process/Job/handles have settled.
            for io in self.ios:
                io.buffer = io.ov = None
            for call in self.calls:
                call.refs = ()
                call.args = NativeArgs()  # discard completed pointer/string aliases
            self.inbound = self.reply = None
            self.closed, self.phase = True, 'CLOSED'
            return True
        except BaseException as error:
            if self.secondary is None:
                self.secondary = error
            return False

    def run(self, spec):
        try:
            self.setup_fixture(spec)
            self.exchange_refusal()
            while not self.cleanup_step():
                need(self.clock() < self._captured_policy.closure_until_ns, 'OWNER_PENDING')
                self.pause(.01)
            need(self.process_exit == 0, 'FIXTURE_EXIT_NOT_ZERO')
            return self.snapshot()
        except BaseException as primary:
            if self.primary is None:
                self.primary = primary
            try:
                self.cleanup_step()
            except BaseException:
                pass
            raise  # never replace original P with diagnostic/stop/close F

    def snapshot(self):
        return {'scope': 'one-owned-fixture-pipe-refusal-only', 'phase': self.phase,
                'lease_consumed': self.consumed, 'revoked': self.revoked,
                'refusal_exchanged': self.refusal_exchanged, 'closed': self.closed,
                'fixture_exit_code': self.process_exit,
                'native_io_calls': len(self.ios),
                'native_io_pending': sum(not io.terminal for io in self.ios),
                'issued_producers_pending': sum(c.issued and not c.producer_ended
                                               for c in self.calls),
                'strict_native_postrevoke_barrier': False,
                'unknown_closes': sum(r.state == 'closing_unknown' for r in self.resources),
                'owned_handles_pending': sum(r.state != 'closed' for r in self.resources),
                'EditorRole': False, 'peer_bound': False, 'ready': False,
                'initializer': 0, 'runner': 0, 'Core': 0, 'model': 0, 'onec': 0,
                'loading_grant': None, 'native_grant': None,
                'global_RSS_measured': False, 'production_backend': False}

if __name__ == '__main__':
    raise PipeRefusal('ROOT_PRIVATE_ADAPTER_NO_AUTO_EXECUTION')
