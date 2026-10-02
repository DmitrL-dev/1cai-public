# Controlled Source verifiers only. All facts/budgets below are synthetic fixture
# values, never Root Editor/ABI/rights/budget admission. No native adapter exists.
from threading import RLock
from time import monotonic_ns
import pytest
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
