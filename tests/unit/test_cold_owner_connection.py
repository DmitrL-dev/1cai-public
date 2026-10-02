# Controlled Source verifiers only. All facts/budgets below are synthetic fixture
# values, never Root Editor/ABI/rights/budget admission. No native adapter exists.
from threading import RLock
from time import monotonic_ns
import pytest
import json
from scripts.verification import cold_owner_connection as m

class FilledThenInterrupted(BaseException):
    pass

class Port(m._ControlledIOPort):
    def __init__(self):
        self.primary = FilledThenInterrupted()
        self.completed = False
        self.closes = []
        self.cancels = 0
        self.submits = 0
        self.polls = 0
        self.interrupt_submit = True
        self.ambiguous_close = True
        self.on_close = None
    def submit(self, token, bundle):
        self.submits += 1
        bundle.stable_outputs['filled_before_interrupt'] = True
        if self.interrupt_submit:
            raise self.primary
    def cancel(self, token, bundle):
        self.cancels += 1
        return 'ERROR_NOT_FOUND'  # no completion/closure inference
    def poll_completion(self, token, bundle):
        self.polls += 1
        return m._Completion(token, bundle) if self.completed else None
    def close_slot(self, slot):
        self.closes.append(slot)
        if self.on_close is not None:
            self.on_close()
        if self.ambiguous_close and len(self.closes) == 2:
            raise FilledThenInterrupted()  # ambiguous effect; never retry this slot
        return True

def controlled_session(port=None):
    # Deliberately small synthetic Source-fixture storage, not a runtime cap.
    now = monotonic_ns(); end = now + 60 * 1000000000
    port, role, instance = port if port is not None else Port(), object(), object()
    policy = m._IOPolicy(object(), object(), 8, 16, 1, 64, end, end, end, end)
    bundle = m._IOBundle({}, object(), bytearray(16),
                         (m._CloseSlot(object()), m._CloseSlot(object())), 64)
    editor = m._EditorEntry(1, object(), object(), object(), role, object())
    endpoint = m._EndpointContract(1, instance, role, object(), object(), object(), object())
    lease = m._OperationLease(1, instance, policy, bundle, port)
    owner = m._RootConnectionSession(1, editor, endpoint, lease, root_gate=RLock())
    owner._controlled_port = port
    fields = (owner._held_editor_entry, owner._connection_endpoint_contract, owner._retained_operation_lease)
    return owner, fields, port, bundle

def test_unknown_or_wire_contract_never_dispatches():
    owner, fields, port, bundle = controlled_session()
    for missing in range(3):
        supplied = list(fields); supplied[missing] = None
        with pytest.raises(m.ColdOwnerRefusal, match='DAILY_ROOT_EDITOR_OWNER_REQUIRED'):
            m.register_operation_before_dispatch(owner, *supplied)
    wire = {'accepted': True, 'role': 'extension-host', 'pid': 123, 'nonce': 'marker'}
    with pytest.raises(m.ColdOwnerRefusal, match='DAILY_ROOT_EDITOR_OWNER_REQUIRED'):
        m.register_operation_before_dispatch(owner, wire, fields[1], fields[2])
    # Even issued tokens cannot turn a missing literal policy into a dispatch.
    lease = owner._records[fields[2]]; lease.policy = m._IOPolicy()
    with pytest.raises(m.ColdOwnerRefusal, match='DAILY_ROOT_EDITOR_OWNER_REQUIRED'):
        m.register_operation_before_dispatch(owner, *fields)
    assert owner._operation is None and bundle.stable_outputs == {}
    assert port.cancels == 0 and port.closes == []
    assert owner.snapshot()['kernel_authority'] is False and owner.snapshot()['ready'] is False

def test_interrupted_submit_cancel_late_completion_and_unknown_close(monkeypatch):
    owner, fields, port, bundle = controlled_session()
    token = m.register_operation_before_dispatch(owner, *fields)
    with pytest.raises(m.ColdOwnerRefusal, match='OWNER_TRANSPORT_NOT_ADMITTED'):
        m.dispatch_registered_operation(owner, token)
    assert bundle.stable_outputs == {}  # real dispatch did not reach even the fixture
    with pytest.raises(FilledThenInterrupted) as caught:
        m._dispatch_for_controlled_verifier(owner, token)
    assert caught.value is port.primary and owner._operation.primary_error is port.primary
    assert bundle.stable_outputs['filled_before_interrupt'] is True
    assert owner._operation.bundle is bundle and owner._operation.phase == 'COMPLETION_PENDING'
    assert m.request_cancel_or_revoke(owner, token, 'owner_loss') is False
    assert port.cancels == 1 and m.observe_completion_and_settle(owner, token) is False
    assert port.closes == [] and bundle.overlapped is not None and bundle.buffer is not None
    port.completed = True  # normal late completion permits cleanup only
    assert m.observe_completion_and_settle(owner, token) is False
    assert bundle.close_slots[0].close_state == 'closed'
    assert bundle.close_slots[1].close_state == 'closing_unknown'
    assert m.observe_completion_and_settle(owner, token) is False
    assert len(port.closes) == 2  # no numeric/slot resurrection after unknown close
    assert owner._operation.primary_error is port.primary
    assert owner._operation.bundle is bundle and bundle.buffer is not None
    snap = owner.snapshot()
    assert snap['revoked'] is True and snap['completion_pending'] is True
    assert snap['kernel_authority'] is False and snap['ready'] is False
    assert snap['loading_grant'] is None and snap['native_grant'] is None
    # Settlement before the first submit permanently retires that dispatch.
    unsent, fields2, port2, buffer2 = controlled_session()
    unsent_token = m.register_operation_before_dispatch(unsent, *fields2)
    assert m.observe_completion_and_settle(unsent, unsent_token) is False
    with pytest.raises(m.ColdOwnerRefusal, match='DAILY_ROOT_EDITOR_OWNER_REQUIRED'):
        m._dispatch_for_controlled_verifier(unsent, unsent_token)
    assert port2.submits == 0 and len(port2.closes) == 2
    assert buffer2.close_slots[1].close_state == 'closing_unknown'
    assert unsent._operation.bundle is buffer2 and buffer2.buffer is not None

    clean_port = Port(); clean_port.ambiguous_close = False
    settled, fields3, port3, buffer3 = controlled_session(clean_port)
    settled_token = m.register_operation_before_dispatch(settled, *fields3)
    assert m.observe_completion_and_settle(settled, settled_token) is True
    assert m.observe_completion_and_settle(settled, settled_token) is True
    assert settled._operation.phase == 'CLOSED' and settled._operation.bundle is None
    assert buffer3.buffer is None and len(port3.closes) == 2
    with pytest.raises(m.ColdOwnerRefusal, match='DAILY_ROOT_EDITOR_OWNER_REQUIRED'):
        m._dispatch_for_controlled_verifier(settled, settled_token)
    assert port3.submits == 0 and len(port3.closes) == 2

    # Absolute deadlines are synthetic, deterministic, distinct, and never renewed.
    clock = [1000]
    monkeypatch.setattr(m, 'monotonic_ns', lambda: clock[0])
    def timed_operation():
        fixture_port = Port(); fixture_port.interrupt_submit = False
        fixture_port.ambiguous_close = False
        session, fixture_fields, fixture_port, storage = controlled_session(fixture_port)
        lease = session._records[fixture_fields[2]]
        lease.policy = m._IOPolicy(object(), object(), 8, 16, 1, 64, 2000, 3000, 4000, 5000)
        operation = m.register_operation_before_dispatch(session, *fixture_fields)
        assert m._dispatch_for_controlled_verifier(session, operation) is True
        return session, operation, fixture_port, storage

    timed, timed_token, timed_port, timed_buffer = timed_operation()
    clock[0] = 4000
    assert m.request_cancel_or_revoke(timed, timed_token, 'expired') is False
    assert timed_port.cancels == 0
    clock[0] = 5000
    timed_port.completed = True
    assert m.observe_completion_and_settle(timed, timed_token) is False
    assert timed_port.polls == 0 and timed_port.closes == []
    assert timed_buffer.buffer is not None and timed._operation.bundle is timed_buffer
    assert timed.snapshot()['revoked'] is True

    # A close begun within budget may report its outcome, but no next slot starts.
    clock[0] = 1000
    closing, closing_token, closing_port, closing_buffer = timed_operation()
    closing_port.completed = True
    closing_port.on_close = lambda: clock.__setitem__(0, 5000)
    clock[0] = 4500
    assert m.observe_completion_and_settle(closing, closing_token) is False
    assert len(closing_port.closes) == 1 and closing_port.polls == 1
    assert closing_buffer.close_slots[0].close_state == 'closed'
    assert closing_buffer.close_slots[1].close_state == 'held'
    assert closing_buffer.buffer is not None and closing._operation.bundle is closing_buffer
    assert m.observe_completion_and_settle(closing, closing_token) is False
    assert len(closing_port.closes) == 1 and closing_port.polls == 1


# Controlled bytes/clock/port only; no IPC/native/model admission.
def _packet(changes=None, text=None):
    value = {'schema':'rentgen-owner-bootstrap-observation/1','type':'BOOTSTRAP',
             'run_nonce':'a'*32,'connection_generation':1,'sequence':1,
             'request_id':'b'*32,'bindings_sha256':'c'*64}
    value.update(changes or {})
    body = (json.dumps(value,separators=(',',':')) if text is None else text).encode()
    return len(body).to_bytes(4,'big')+body

class FramePort(Port):
    def __init__(self, frame):
        super().__init__(); self.frame = frame
        self.interrupt_submit = self.ambiguous_close = False
    def submit(self, token, bundle):
        bundle.buffer.inbound = self.frame; bundle.buffer.sealed = True
        super().submit(token,bundle)

def app_session(monkeypatch, frame=None, *, submit=True, interrupt=False, capacity=4096):
    clock = [1000]; monkeypatch.setattr(m,'monotonic_ns',lambda:clock[0])
    port = FramePort(_packet() if frame is None else frame); port.interrupt_submit = interrupt
    owner,fields,port,bundle = controlled_session(port); lease = owner._records[fields[2]]
    policy = m._IOPolicy(object(),object(),1024,4096,1,4096,2000,3000,4000,5000)
    lease.policy = policy; storage = m._FrameStorage(capacity)
    bundle.buffer,bundle.storage_bytes = storage,4096
    contract = m._FrameContract(1,'a'*32,'b'*32,'c'*64)
    token = m.register_operation_before_dispatch(owner,*fields,application_contract=contract)
    assert port.submits == 0
    if submit:
        if interrupt:
            with pytest.raises(FilledThenInterrupted) as caught:
                m._dispatch_for_controlled_verifier(owner,token)
            assert caught.value is port.primary
        else: assert m._dispatch_for_controlled_verifier(owner,token) is True
    return clock,owner,token,lease,bundle,storage,port,policy

def frame_observe(parts):
    _,owner,token,lease,bundle,_,_,_ = parts
    return m._observe_application_frame_for_controlled_verifier(owner,token,bundle,lease)

def frame_false(owner):
    snap = owner.snapshot()
    for key in ('kernel_authority','ready','model_loading_allowed','native_allowed'):
        assert snap[key] is False
    assert snap['loading_grant'] is None and snap['native_grant'] is None

def test_application_identity_once_and_retirement(monkeypatch):
    parts = app_session(monkeypatch)
    _,owner,token,lease,bundle,storage,port,policy = parts
    result = frame_observe(parts); reply = storage.refusal
    assert result['native_completion'] is False and result['ready'] is False
    assert int.from_bytes(reply[:4],'big') == len(reply)-4
    assert json.loads(reply[4:]) == {'schema':'rentgen-owner-bootstrap-observation/1',
        'type':'REFUSAL','run_nonce':'a'*32,'connection_generation':1,'sequence':2,
        'request_id':'b'*32,'bindings_sha256':'c'*64,'code':'DAILY_ROOT_EDITOR_OWNER_REQUIRED'}
    assert owner._operation.bundle is bundle is lease.bundle
    assert owner._operation.application.policy is policy
    assert owner._operation.completion_seen is False and port.polls == 0 and port.closes == []
    assert m.observe_completion_and_settle(owner,token) is False
    assert storage.inbound is not None and storage.refusal is reply
    with pytest.raises(m.ColdOwnerRefusal): frame_observe(parts)
    error = owner._operation.application.error
    assert storage.refusal is reply and port.submits == 1
    summary = owner._operation.application.summary; port.completed = True
    assert m.observe_completion_and_settle(owner,token) is True
    assert m.observe_completion_and_settle(owner,token) is True
    assert owner._operation.application.storage is None
    assert owner._operation.application.summary == summary
    assert owner._operation.application.error is error
    assert storage.inbound is None and storage.refusal is None and bundle.buffer is None
    assert len(port.closes) == 2; frame_false(owner)
    for kind in ('lease','bundle','storage','unsent'):
        parts = app_session(monkeypatch,submit=kind != 'unsent')
        _,owner,token,lease,bundle,storage,port,_ = parts
        bt,bb,bl = token,bundle,lease
        if kind == 'lease': bl = type(lease)(**vars(lease))
        elif kind == 'bundle': bb = type(bundle)(**vars(bundle))
        elif kind == 'storage': bundle.buffer = m._FrameStorage(4096)
        with pytest.raises(m.ColdOwnerRefusal):
            m._observe_application_frame_for_controlled_verifier(owner,bt,bb,bl)
        assert storage.refusal is None; frame_false(owner)

def test_application_frame_shape_and_bounds(monkeypatch):
    text = _packet()[4:].decode()
    variants = [_packet({key:'d'*length}) for key,length in
                [('run_nonce',32),('request_id',32),('bindings_sha256',64)]]
    variants += [_packet({'connection_generation':True}),_packet({'sequence':2}),
        _packet({'peer_bound':True}),_packet({'type':'REFUSAL'}),
        _packet(text=text.replace('"schema":','"\\u0073chema":"shadow","schema":')),
        _packet(text=text.replace('"sequence":1','"sequence":1e0')),
        bytes([0,0,0,1,255]),bytes(4),(1025).to_bytes(4,'big'),
        _packet()[:-1],_packet()+bytes([0])]
    for data in variants:
        parts = app_session(monkeypatch,data)
        _,owner,_,_,_,storage,port,_ = parts
        with pytest.raises(m.ColdOwnerRefusal): frame_observe(parts)
        assert storage.refusal is None and storage.inbound is data
        assert owner._operation.completion_seen is False and port.closes == []
        frame_false(owner)
    parts = app_session(monkeypatch,capacity=len(_packet()))
    with pytest.raises(m.ColdOwnerRefusal): frame_observe(parts)
    assert parts[5].refusal is None and parts[6].closes == []

def test_application_cancel_and_original_policy(monkeypatch):
    decode = m._app_decode
    for reason in ('cancel','hello'):
        parts = app_session(monkeypatch)
        clock,owner,token,lease,bundle,storage,port,_ = parts
        def changed(data,contract,policy):
            decode(data,contract,policy)
            if reason == 'cancel': m.request_cancel_or_revoke(owner,token,'owner_loss')
            else: clock[0] = 3000
        monkeypatch.setattr(m,'_app_decode',changed)
        with pytest.raises(m.ColdOwnerRefusal): frame_observe(parts)
        assert storage.refusal is None and storage.inbound is not None
        assert owner._operation.completion_seen is False and port.closes == []
    monkeypatch.setattr(m,'_app_decode',decode)
    parts = app_session(monkeypatch)
    clock,owner,token,lease,bundle,storage,port,policy = parts
    later = m._IOPolicy(object(),object(),1024,4096,1,4096,9000,9000,9000,9000)
    lease.policy = later
    with pytest.raises(m.ColdOwnerRefusal): frame_observe(parts)
    assert owner._operation.application.policy is policy
    clock[0] = 4000
    assert m.request_cancel_or_revoke(owner,token,'expired') is False and port.cancels == 0
    clock[0] = 5000; port.completed = True
    assert m.observe_completion_and_settle(owner,token) is False
    assert port.polls == 0 and port.closes == [] and storage.inbound is not None
    parts = app_session(monkeypatch,submit=False)
    clock,owner,token,lease,bundle,storage,port,_ = parts
    lease.policy = later; clock[0] = 2000
    with pytest.raises(m.ColdOwnerRefusal): m._dispatch_for_controlled_verifier(owner,token)
    assert port.submits == 0
    parts = app_session(monkeypatch)
    clock,owner,token,lease,bundle,storage,port,_ = parts
    port.completed = True; clock[0] = 4500
    def first_close():
        lease.policy = later; clock[0] = 5000
    port.on_close = first_close
    assert m.observe_completion_and_settle(owner,token) is False
    assert len(port.closes) == 1 and port.polls == 1
    assert owner._operation.application.storage is storage and storage.inbound is not None
    assert m.observe_completion_and_settle(owner,token) is False and len(port.closes) == 1
    frame_false(owner)

def test_application_completion_and_primary_separation(monkeypatch):
    parts = app_session(monkeypatch,interrupt=True)
    _,owner,token,lease,bundle,storage,port,_ = parts
    with pytest.raises(FilledThenInterrupted) as caught: frame_observe(parts)
    assert caught.value is port.primary and owner._operation.primary_error is port.primary
    port.poll_completion = lambda token,bundle:{'schema':'PASS','completed':True}
    assert m.observe_completion_and_settle(owner,token) is False and port.closes == []
    assert owner._operation.application.storage is storage and storage.inbound is not None
    def cancel_error(token,bundle): raise FilledThenInterrupted()
    port.cancel = cancel_error
    assert m.request_cancel_or_revoke(owner,token,'stop') is False
    port.poll_completion = lambda token,bundle:m._Completion(token,bundle)
    port.ambiguous_close = True
    assert m.observe_completion_and_settle(owner,token) is False
    assert storage.inbound is not None and owner._operation.application.storage is storage
    assert m.observe_completion_and_settle(owner,token) is False and len(port.closes) == 2
    assert owner._operation.application.error is port.primary
    assert owner._operation.primary_error is port.primary; frame_false(owner)

# Two P2 controls: run against old Source54 as RED2, then amended Source as GREEN8.
def test_application_failed_decode_retirement_drops_owned_diagnostics(monkeypatch):
    data = bytes([0, 0, 0, 1, 255])  # valid framing, invalid UTF8
    parts = app_session(monkeypatch, data)
    _, owner, token, _, bundle, storage, port, _ = parts
    with pytest.raises(m.ColdOwnerRefusal) as caught:
        frame_observe(parts)
    error = caught.value; app = owner._operation.application
    assert app.error is error and error.__traceback__ is not None
    context = error.__context__
    assert isinstance(context, UnicodeDecodeError) and context.object == data[4:]
    error.__cause__ = context  # exercise both owned diagnostic links
    traceback = error.__traceback__
    assert storage.inbound is data and app.storage is storage
    assert m.observe_completion_and_settle(owner, token) is False
    assert app.error is error and error.__traceback__ is traceback
    assert error.__context__ is context and error.__cause__ is context

    # A known refusal permits later closure, without premature diagnostic release.
    port.completed = True; original_close = port.close_slot
    def known_refusal(slot):
        port.closes.append(slot)
        return False
    port.close_slot = known_refusal
    assert m.observe_completion_and_settle(owner, token) is False
    assert app.storage is storage and storage.inbound is data
    assert error.__traceback__ is traceback and error.__context__ is context
    port.close_slot = original_close
    assert m.observe_completion_and_settle(owner, token) is True
    assert app.error is error  # same object, only owned raw diagnostic roots retired
    assert error.__traceback__ is None  # old Source54 fails here: packet still retained
    assert error.__context__ is None and error.__cause__ is None
    assert app.storage is None and storage.inbound is None and storage.refusal is None
    assert bundle.buffer is None and owner._operation.phase == 'CLOSED'
    assert m.observe_completion_and_settle(owner, token) is True
    frame_false(owner)

    # Ambiguous closure remains pending and keeps storage/diagnostic evidence.
    parts = app_session(monkeypatch, data)
    _, owner, token, _, bundle, storage, port, _ = parts
    with pytest.raises(m.ColdOwnerRefusal) as caught:
        frame_observe(parts)
    error = caught.value; traceback = error.__traceback__; context = error.__context__
    port.completed = True; port.ambiguous_close = True
    assert m.observe_completion_and_settle(owner, token) is False
    assert bundle.close_slots[1].close_state == 'closing_unknown'
    assert owner._operation.application.storage is storage and storage.inbound is data
    assert owner._operation.application.error is error
    assert error.__traceback__ is traceback and error.__context__ is context
    assert m.observe_completion_and_settle(owner, token) is False and len(port.closes) == 2

    # Original submit P identity and diagnostics remain untouched even on success.
    parts = app_session(monkeypatch, interrupt=True)
    _, owner, token, _, _, storage, port, _ = parts
    with pytest.raises(FilledThenInterrupted) as caught:
        frame_observe(parts)
    primary = caught.value; traceback = primary.__traceback__
    context, cause = primary.__context__, primary.__cause__
    port.completed = True; port.ambiguous_close = False
    assert m.observe_completion_and_settle(owner, token) is True
    assert owner._operation.primary_error is primary
    assert owner._operation.application.error is primary
    assert primary.__traceback__ is traceback
    assert primary.__context__ is context and primary.__cause__ is cause
    assert owner._operation.application.storage is None and storage.inbound is None
    frame_false(owner)

def test_application_pre_submit_binding_budget_and_reentrant_clock_refuse(monkeypatch):
    for kind in ('storage', 'policy', 'capacity', 'reservation',
                 'clock_storage', 'clock_cancel', 'clock_policy'):
        parts = app_session(monkeypatch, submit=False)
        clock, owner, token, lease, bundle, storage, port, policy = parts
        later = m._IOPolicy(object(), object(), 1024, 4096, 1, 4096,
                            9000, 9000, 9000, 9000)
        if kind == 'storage':
            bundle.buffer = m._FrameStorage(4096)
        elif kind == 'policy':
            lease.policy = later
        elif kind == 'capacity':
            storage.capacity_bytes = 4097
        elif kind == 'reservation':
            bundle.storage_bytes = 1
        else:
            fired = [False]
            def changed_clock():
                if not fired[0]:
                    fired[0] = True
                    if kind == 'clock_storage':
                        bundle.buffer = m._FrameStorage(4096)
                    elif kind == 'clock_policy':
                        lease.policy = later
                    else:
                        m.request_cancel_or_revoke(owner, token, 'clock_owner_loss')
                return clock[0]
            monkeypatch.setattr(m, 'monotonic_ns', changed_clock)
        with pytest.raises(m.ColdOwnerRefusal):
            m._dispatch_for_controlled_verifier(owner, token)
        # Old Source54 submits for the first otherwise-valid replacement instead.
        op = owner._operation
        assert port.submits == 0 and port.cancels == 0 and port.polls == 0
        assert port.closes == [] and bundle.stable_outputs == {}
        assert storage.inbound is None and storage.refusal is None
        assert op.phase == 'REGISTERED' and op.submit_attempted is False
        assert op.revoked is True and owner._terminal_reason is not None
        assert op.application.policy is policy and op.application.storage is storage
        assert op.application.error is not None
        first = op.application.error
        # Restoration cannot renew a terminal application operation.
        lease.policy = policy; bundle.buffer = storage
        storage.capacity_bytes = 4096; bundle.storage_bytes = 4096
        monkeypatch.setattr(m, 'monotonic_ns', lambda: clock[0])
        with pytest.raises(m.ColdOwnerRefusal):
            m._dispatch_for_controlled_verifier(owner, token)
        assert port.submits == 0 and op.application.error is first
        assert m.request_cancel_or_revoke(owner, token, 'again') is False
        assert port.cancels == 0 and op.application.policy is policy
        frame_false(owner)
