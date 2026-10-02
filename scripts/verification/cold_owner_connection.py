"""One Root-private retained IO seam. Real transport remains unadmitted.

Nothing in this module discovers an Editor, opens a pipe, binds a peer, calls
Core/SDK/model, or creates a READY/loading/native grant. Private records are
created in the Root process; serialized dictionaries cannot recreate them.
"""
from dataclasses import dataclass
from threading import Lock
from time import monotonic_ns
import json
import re

_COLD_REFUSAL = 'DAILY_ROOT_EDITOR_OWNER_REQUIRED'

class ColdOwnerRefusal(RuntimeError):
    pass

@dataclass(frozen=True)
class _EditorEntry:
    generation: int
    held_entry: object
    cold_group: object
    identity_token: object
    role_manifest_ref: object = None
    current_lifecycle_ref: object = None

@dataclass(frozen=True)
class _EndpointContract:
    generation: int
    instance_token: object
    role_manifest_ref: object = None
    ABI_ref: object = None
    ACL_ref: object = None
    trusted_handoff_ref: object = None
    handle_transfer_policy_ref: object = None

@dataclass(frozen=True)
class _IOPolicy:
    fact_ref: object = None
    completion_collector_ref: object = None
    frame_bytes: object = None
    aggregate_bytes: object = None
    queue_slots: object = None
    retained_storage_bytes: object = None
    connect_until_ns: object = None
    hello_until_ns: object = None
    cancel_until_ns: object = None
    closure_until_ns: object = None

@dataclass(frozen=True)
class _FrameContract:
    generation: int
    run_nonce: str
    request_id: str
    bindings_sha256: str

@dataclass
class _FrameStorage:
    # Verifier-only complete bytes; no native readable-buffer/ABI assertion.
    capacity_bytes: int
    inbound: object = None
    sealed: bool = False
    refusal: object = None

@dataclass
class _FrameExchange:
    contract: object
    storage: object
    policy: object
    capacity_bytes: int
    attempted: bool = False
    error: object = None
    summary: object = None

@dataclass
class _CloseSlot:
    # Stable Root-owned output storage; never a foreign numeric HANDLE argument.
    storage: object
    close_state: str = 'held'

@dataclass
class _IOBundle:
    stable_outputs: object
    overlapped: object
    buffer: object
    close_slots: tuple
    storage_bytes: object = None

@dataclass
class _OperationLease:
    generation: int
    instance_token: object
    policy: object
    bundle: object
    closure_owner: object
    consumed: bool = False

@dataclass(frozen=True)
class _Completion:
    # Root collector output, matched by object identity, not a wire receipt.
    operation_token: object
    bundle: object

@dataclass
class _Operation:
    token: object
    lease: object
    generation: int
    bundle: object
    port: object = None
    phase: str = 'REGISTERED'
    revoked: bool = False
    submit_attempted: bool = False
    submit_exited: bool = False
    completion_seen: bool = False
    cancel_attempted: bool = False
    primary_error: object = None
    cleanup_error: object = None
    application: object = None

class _RootConnectionSession:
    """Private Root construction only, not a public caller authority factory.

    The controlled port below is for two Source verifiers only. No production
    adapter is installed by this slice, even if all three private tokens exist.
    Underscore names are not a Python sandbox; Root must keep these objects out
    of caller/JSON/extension APIs. Actual role/rights/budgets remain Root facts.
    """
    def __init__(self, generation, editor=None, endpoint=None, lease=None, *, root_gate=None):
        if type(generation) is not int or generation < 1:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        if root_gate is None:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        self.generation = generation
        self.gate, self.io_gate = root_gate, Lock()  # SAME Root owner/revoke gate, not a new authority
        self._terminal_reason = None
        self._operation = None
        self._controlled_port = None
        self._records = {}
        self._held_editor_entry = self._retain(editor)
        self._connection_endpoint_contract = self._retain(endpoint)
        self._retained_operation_lease = self._retain(lease)

    def _retain(self, record):
        if record is None:
            return None
        token = object()
        self._records[token] = record
        return token

    def _operation_for(self, token):
        value = self._operation
        if value is None or token is not value.token:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        return value

    def snapshot(self):
        with self.gate:
            op = self._operation
            return {'scope': 'retained-connection-contract-only',
                    'state': None if op is None else op.phase,
                    'revoked': self._terminal_reason is not None,
                    'completion_pending': op is not None and op.phase != 'CLOSED',
                    'kernel_authority': False, 'ready': False,
                    'model_loading_allowed': False, 'native_allowed': False,
                    'loading_grant': None, 'native_grant': None}

def require_connection_contract(owner_session, held_editor_entry,
                                connection_endpoint_contract, retained_operation_lease):
    if type(owner_session) is not _RootConnectionSession:
        raise ColdOwnerRefusal(_COLD_REFUSAL)
    owner = owner_session
    with owner.gate:
        expected = (owner._held_editor_entry, owner._connection_endpoint_contract,
                    owner._retained_operation_lease)
        supplied = (held_editor_entry, connection_endpoint_contract, retained_operation_lease)
        if any(a is None or a is not b for a, b in zip(supplied, expected)):
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        if owner._terminal_reason is not None:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        editor, endpoint, lease = (owner._records[token] for token in supplied)
        if type(editor) is not _EditorEntry or type(endpoint) is not _EndpointContract or type(lease) is not _OperationLease:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        if any(type(v.generation) is not int or v.generation != owner.generation for v in (editor, endpoint, lease)):
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        required = (editor.held_entry, editor.cold_group, editor.identity_token,
                    editor.role_manifest_ref, editor.current_lifecycle_ref,
                    endpoint.instance_token, endpoint.role_manifest_ref, endpoint.ABI_ref,
                    endpoint.ACL_ref, endpoint.trusted_handoff_ref, endpoint.handle_transfer_policy_ref,
                    lease.closure_owner)
        if any(value is None for value in required):
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        if editor.role_manifest_ref is not endpoint.role_manifest_ref or lease.instance_token is not endpoint.instance_token:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        policy, bundle = lease.policy, lease.bundle
        if type(policy) is not _IOPolicy or policy.fact_ref is None or policy.completion_collector_ref is None:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        caps = (policy.frame_bytes, policy.aggregate_bytes, policy.queue_slots, policy.retained_storage_bytes)
        ends = (policy.connect_until_ns, policy.hello_until_ns, policy.cancel_until_ns, policy.closure_until_ns)
        if any(type(value) is not int or value <= 0 for value in caps + ends):
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        if not policy.frame_bytes <= policy.aggregate_bytes <= policy.retained_storage_bytes:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        if not monotonic_ns() < policy.connect_until_ns <= policy.hello_until_ns <= policy.cancel_until_ns <= policy.closure_until_ns:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        if type(bundle) is not _IOBundle or any(value is None for value in (bundle.stable_outputs, bundle.overlapped, bundle.buffer)):
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        if type(bundle.storage_bytes) is not int or not 0 < bundle.storage_bytes <= policy.retained_storage_bytes:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        if type(bundle.close_slots) is not tuple or not bundle.close_slots:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        if any(type(slot) is not _CloseSlot or slot.storage is None or slot.close_state != 'held' for slot in bundle.close_slots):
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        if len({id(slot) for slot in bundle.close_slots}) != len(bundle.close_slots) or len({id(slot.storage) for slot in bundle.close_slots}) != len(bundle.close_slots) or lease.consumed is not False:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        return lease

def register_operation_before_dispatch(owner, held_editor_entry, connection_endpoint_contract,
                                       retained_operation_lease, *, application_contract=None):
    lease = require_connection_contract(owner, held_editor_entry, connection_endpoint_contract,
                                        retained_operation_lease)
    with owner.gate:
        application = (None if application_contract is None else
                       _app_prepare(owner, lease, application_contract))
        if owner._terminal_reason is not None or owner._operation is not None or lease.consumed or monotonic_ns() >= lease.policy.connect_until_ns:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        if application is not None and monotonic_ns() >= application.policy.connect_until_ns:
            raise ColdOwnerRefusal(_COLD_REFUSAL)
        token = object()
        op = _Operation(token, lease, owner.generation, lease.bundle)
        op.application = application
        owner._operation = op  # retains every output/event/OVERLAPPED/buffer BEFORE any submit
        lease.consumed = True
        return token

def dispatch_registered_operation(owner, operation_token):
    # No real IPC adapter/role/right/budget admission is installed by this file.
    # This denial also prevents a controlled lifecycle from becoming a product backend.
    with owner.gate:
        owner._operation_for(operation_token)
    raise ColdOwnerRefusal('OWNER_TRANSPORT_NOT_ADMITTED')
class _ControlledIOPort:
    """Source-verifier interface only; no WINAPI implementation or ABI declarations.

    submit fills only the retained bundle. cancel is a request, not completion.
    poll_completion is nonblocking and returns None or an exact _Completion.
    close_slot closes only one exact Root-owned slot; bool false means a known
    refusal, while exception/non-bool means unknown and forbids numeric retry.
    """
    def submit(self, operation_token, bundle):
        raise NotImplementedError
    def cancel(self, operation_token, bundle):
        raise NotImplementedError
    def poll_completion(self, operation_token, bundle):
        raise NotImplementedError
    def close_slot(self, slot):
        raise NotImplementedError

def _dispatch_for_controlled_verifier(owner, operation_token):
    # Never called by the product dispatch path. A fixture does not create authority.
    if not owner.io_gate.acquire(blocking=False):
        return False
    try:
        with owner.gate:
            op = owner._operation_for(operation_token)
            port = owner._controlled_port
            if not isinstance(port, _ControlledIOPort) or port is not op.lease.closure_owner:
                raise ColdOwnerRefusal(_COLD_REFUSAL)
            if (op.phase != 'REGISTERED' or type(op.bundle) is not _IOBundle
                    or op.bundle is not op.lease.bundle or op.submit_attempted
                    or op.revoked or owner._terminal_reason is not None):
                raise ColdOwnerRefusal(_COLD_REFUSAL)
            if op.application is not None:
                app = op.application
                try:
                    storage, policy = _app_before_submit(owner, op, app)
                    now = monotonic_ns()
                    # The controlled clock may reenter, revoke or replace a view.
                    if app.storage is not storage or app.policy is not policy:
                        raise ColdOwnerRefusal(_APP_REFUSED)
                    _app_before_submit(owner, op, app)
                    if now >= policy.connect_until_ns:
                        owner._terminal_reason = 'expired'; op.revoked = True
                        raise ColdOwnerRefusal(_COLD_REFUSAL)
                except BaseException as original:
                    # Refuse locally before any submit marker or port effect.
                    op.revoked = True
                    if owner._terminal_reason is None:
                        owner._terminal_reason = 'application_submit_refused'
                    if type(app) is _FrameExchange:
                        app.attempted = True
                        if app.error is None:
                            app.error = original
                    raise
            elif monotonic_ns() >= _operation_policy(op).connect_until_ns:
                owner._terminal_reason = 'expired'; op.revoked = True
                raise ColdOwnerRefusal(_COLD_REFUSAL)
            op.port = port; op.submit_attempted = True; op.phase = 'IN_FLIGHT'
        try:
            port.submit(op.token, op.bundle)  # outside the short owner gate
            return True
        except BaseException as original:
            with owner.gate:
                if op.primary_error is None:
                    op.primary_error = original
                op.revoked = True
                if owner._terminal_reason is None:
                    owner._terminal_reason = 'submit_failed'
            raise  # cleanup/diagnostic errors cannot replace this original exception
        finally:
            with owner.gate:
                op.submit_exited = True
                op.phase = 'COMPLETION_PENDING'
    finally:
        owner.io_gate.release()

_APP_SCHEMA = 'rentgen-owner-bootstrap-observation/1'
_APP_REFUSED = 'OWNER_APPLICATION_FRAME_REFUSED'
_APP_KEYS = {'schema', 'type', 'run_nonce', 'connection_generation',
             'sequence', 'request_id', 'bindings_sha256'}

def _app_prepare(owner, lease, contract):
    storage, policy = lease.bundle.buffer, lease.policy
    if (type(contract) is not _FrameContract
            or type(contract.generation) is not int
            or not 1 <= contract.generation <= 2**53 - 1
            or contract.generation != owner.generation
            or any(type(value) is not str or re.fullmatch(pattern, value) is None
                   for value, pattern in ((contract.run_nonce, r'[a-f0-9]{32}'),
                                          (contract.request_id, r'[a-f0-9]{32}'),
                                          (contract.bindings_sha256, r'[a-f0-9]{64}')))):
        raise ColdOwnerRefusal(_APP_REFUSED)
    if (type(policy) is not _IOPolicy
            or any(type(value) is not int or value <= 0 for value in
                   (policy.frame_bytes, policy.aggregate_bytes,
                    policy.retained_storage_bytes, policy.queue_slots))
            or policy.queue_slots != 1 or policy.frame_bytes > 65536
            or policy.aggregate_bytes > 131080 or policy.retained_storage_bytes > 196620
            or not policy.frame_bytes <= policy.aggregate_bytes <= policy.retained_storage_bytes
            or type(storage) is not _FrameStorage
            or type(storage.capacity_bytes) is not int
            or not 0 < storage.capacity_bytes <= lease.bundle.storage_bytes
            or storage.inbound is not None or storage.sealed is not False
            or storage.refusal is not None):
        raise ColdOwnerRefusal(_APP_REFUSED)
    return _FrameExchange(contract, storage, policy, storage.capacity_bytes)

def _operation_policy(op):
    app = op.application
    return app.policy if type(app) is _FrameExchange else op.lease.policy

def _app_retire(op):
    app = op.application
    if type(app) is _FrameExchange and app.storage is not None:
        # Called only after successful existing all-own-slots settlement.
        # Detach owned packet diagnostics, preserving the same first error object.
        # The original submit P and its diagnostics belong to the old lifecycle.
        error = app.error
        if isinstance(error, BaseException) and error is not op.primary_error:
            BaseException.__dict__['__traceback__'].__set__(error, None)
            BaseException.__dict__['__context__'].__set__(error, None)
            BaseException.__dict__['__cause__'].__set__(error, None)
        app.storage.inbound = None
        app.storage.refusal = None
        app.storage.sealed = False
        app.storage = None  # captured policy/scalar summary/first error identity only

def _app_bound(owner, op, app, bundle, lease):
    if (type(app) is not _FrameExchange or op.application is not app
            or owner._operation is not op or type(lease) is not _OperationLease
            or lease is not op.lease or type(bundle) is not _IOBundle
            or bundle is not op.bundle or bundle is not lease.bundle
            or lease.policy is not app.policy
            or type(app.storage) is not _FrameStorage
            or bundle.buffer is not app.storage
            or type(app.storage.capacity_bytes) is not int
            or app.storage.capacity_bytes != app.capacity_bytes
            or any(type(value) is not int or value != app.contract.generation
                   for value in (owner.generation, op.generation, lease.generation))):
        raise ColdOwnerRefusal(_APP_REFUSED)
    return app.storage

def _app_before_submit(owner, op, app):
    storage = _app_bound(owner, op, app, op.bundle, op.lease)
    policy = app.policy  # the exact immutable policy captured at registration
    if (type(policy) is not _IOPolicy or app.attempted is not False
            or app.error is not None or op.phase != 'REGISTERED'
            or op.submit_attempted is not False or op.submit_exited is not False
            or op.completion_seen is not False or op.revoked is not False
            or owner._terminal_reason is not None
            or type(op.bundle.storage_bytes) is not int
            or not 0 < app.capacity_bytes <= op.bundle.storage_bytes <= policy.retained_storage_bytes
            or storage.inbound is not None or storage.sealed is not False
            or storage.refusal is not None):
        raise ColdOwnerRefusal(_APP_REFUSED)
    return storage, policy

def _app_live(owner, op):
    if (owner._terminal_reason is not None or op.revoked is not False
            or op.phase != 'COMPLETION_PENDING' or op.submit_attempted is not True
            or op.submit_exited is not True or op.completion_seen is not False):
        raise ColdOwnerRefusal(_APP_REFUSED)

def _app_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ColdOwnerRefusal(_APP_REFUSED)
        value[key] = item
    return value

def _app_number(value):
    if re.fullmatch(r'0|[1-9][0-9]*', value) is None:
        raise ColdOwnerRefusal(_APP_REFUSED)
    return int(value)

def _app_noninteger(value):
    raise ColdOwnerRefusal(_APP_REFUSED)

def _app_decode(data, contract, policy):
    if (type(data) is not bytes or len(data) < 5
            or len(data) > policy.aggregate_bytes):
        raise ColdOwnerRefusal(_APP_REFUSED)
    length = int.from_bytes(data[:4], 'big')
    if length < 1 or length > policy.frame_bytes or len(data) != length + 4:
        raise ColdOwnerRefusal(_APP_REFUSED)
    try:
        value = json.loads(data[4:].decode('utf-8'), object_pairs_hook=_app_pairs,
                           parse_int=_app_number, parse_float=_app_noninteger,
                           parse_constant=_app_noninteger)
    except (ValueError, UnicodeError):
        raise ColdOwnerRefusal(_APP_REFUSED) from None
    if (type(value) is not dict or set(value) != _APP_KEYS
            or any(type(item) not in (str, int) for item in value.values())
            or value['schema'] != _APP_SCHEMA or value['type'] != 'BOOTSTRAP'
            or type(value['sequence']) is not int or value['sequence'] != 1
            or type(value['connection_generation']) is not int
            or value['connection_generation'] != contract.generation
            or value['run_nonce'] != contract.run_nonce
            or value['request_id'] != contract.request_id
            or value['bindings_sha256'] != contract.bindings_sha256):
        raise ColdOwnerRefusal(_APP_REFUSED)

def _app_refusal(app, incoming_bytes):
    expected = app.contract
    text = json.dumps({'schema': _APP_SCHEMA, 'type': 'REFUSAL',
                       'run_nonce': expected.run_nonce,
                       'connection_generation': expected.generation, 'sequence': 2,
                       'request_id': expected.request_id,
                       'bindings_sha256': expected.bindings_sha256, 'code': _COLD_REFUSAL},
                      ensure_ascii=True, separators=(',', ':'))
    size = len(text) + 4
    if (len(text) > app.policy.frame_bytes
            or incoming_bytes + size > app.policy.aggregate_bytes
            or incoming_bytes + size > app.capacity_bytes):
        raise ColdOwnerRefusal(_APP_REFUSED)
    return len(text).to_bytes(4, 'big') + text.encode('ascii')

def _observe_application_frame_for_controlled_verifier(owner, operation_token,
                                                     selected_bundle, selected_lease):
    if type(owner) is not _RootConnectionSession:
        raise ColdOwnerRefusal(_APP_REFUSED)
    if not owner.io_gate.acquire(blocking=False):
        return False
    op = app = primary = None
    try:
        with owner.gate:
            op = owner._operation_for(operation_token)
            app = op.application
            if op.primary_error is not None:
                raise op.primary_error
            storage = _app_bound(owner, op, app, selected_bundle, selected_lease)
            if app.error is not None:
                raise app.error
            _app_live(owner, op)
            if app.attempted:
                raise ColdOwnerRefusal(_APP_REFUSED)
            now = monotonic_ns()
            _app_bound(owner, op, app, selected_bundle, selected_lease)
            _app_live(owner, op)
            if now >= app.policy.hello_until_ns:
                raise ColdOwnerRefusal(_APP_REFUSED)
            if (storage.sealed is not True or type(storage.inbound) is not bytes
                    or len(storage.inbound) > app.capacity_bytes
                    or storage.refusal is not None):
                raise ColdOwnerRefusal(_APP_REFUSED)
            app.attempted = True
            data = storage.inbound
        _app_decode(data, app.contract, app.policy)
        reply = _app_refusal(app, len(data))
        with owner.gate:
            storage = _app_bound(owner, op, app, selected_bundle, selected_lease)
            now = monotonic_ns()
            _app_bound(owner, op, app, selected_bundle, selected_lease)
            _app_live(owner, op)
            if (now >= app.policy.hello_until_ns or storage.inbound is not data
                    or storage.sealed is not True or storage.refusal is not None):
                raise ColdOwnerRefusal(_APP_REFUSED)
            op.revoked = True
            owner._terminal_reason = 'application_refusal'
            storage.refusal = reply
            app.summary = (len(data), len(reply))
        return {'scope': 'controlled-application-frame-only', 'type': 'REFUSAL',
                'native_completion': False, 'kernel_authority': False, 'ready': False,
                'loading_grant': None, 'native_grant': None}
    except BaseException as original:
        primary = original
        try:
            with owner.gate:
                if (type(app) is _FrameExchange and owner._operation is op
                        and op.application is app):
                    app.attempted = True
                    if app.error is None:
                        app.error = original
                    op.revoked = True
                    if owner._terminal_reason is None:
                        owner._terminal_reason = 'application_failed'
        except BaseException:
            pass
        raise
    finally:
        try:
            owner.io_gate.release()
        except BaseException:
            if primary is not None:
                raise primary
            raise

def request_cancel_or_revoke(owner, operation_token, reason):
    with owner.gate:
        op = owner._operation_for(operation_token)
        op.revoked = True
        if owner._terminal_reason is None:
            owner._terminal_reason = reason if type(reason) is str and reason else _COLD_REFUSAL
    # A busy/ambiguous submit remains retained. No wait occurs under the owner gate.
    if not owner.io_gate.acquire(blocking=False):
        return False
    try:
        with owner.gate:
            if not op.submit_attempted or op.completion_seen or op.cancel_attempted:
                return False
            port = op.port
            if port is None or not op.submit_exited:
                return False
            if monotonic_ns() >= _operation_policy(op).cancel_until_ns:
                return False  # expired cancellation budget does not settle the IO
            op.cancel_attempted = True
        try:
            port.cancel(op.token, op.bundle)  # even false/not-found is only a request result
        except BaseException as error:
            with owner.gate:
                if op.cleanup_error is None:
                    op.cleanup_error = error
        return False  # cancellation never constitutes closed/completed/PASS
    finally:
        owner.io_gate.release()

def observe_completion_and_settle(owner, operation_token):
    if not owner.io_gate.acquire(blocking=False):
        return False
    try:
        with owner.gate:
            op = owner._operation_for(operation_token)
            if op.phase == 'CLOSED':
                return True
            if monotonic_ns() >= _operation_policy(op).closure_until_ns:
                op.revoked = True
                if owner._terminal_reason is None:
                    owner._terminal_reason = 'expired'
                return False  # keep pending storage; never renew the budget
            if monotonic_ns() >= _operation_policy(op).hello_until_ns:
                op.revoked = True
                if owner._terminal_reason is None:
                    owner._terminal_reason = 'expired'
            if op.submit_attempted and not op.submit_exited:
                return False
            port = op.port if op.submit_attempted else owner._controlled_port
            if not isinstance(port, _ControlledIOPort) or port is not op.lease.closure_owner:
                return False
        if op.submit_attempted and not op.completion_seen:
            try:
                completion = port.poll_completion(op.token, op.bundle)
            except BaseException as error:
                with owner.gate:
                    if op.cleanup_error is None:
                        op.cleanup_error = error
                return False
            if type(completion) is not _Completion or completion.operation_token is not op.token or completion.bundle is not op.bundle:
                return False
        with owner.gate:
            # Never un-revoke or bind. A normal late completion is cleanup only.
            op.completion_seen = True; op.phase = 'OBSERVED_COMPLETION'
        for slot in op.bundle.close_slots:
            with owner.gate:
                if slot.close_state == 'closed':
                    continue
                if slot.close_state != 'held':
                    return False
                if monotonic_ns() >= _operation_policy(op).closure_until_ns:
                    op.revoked = True
                    if owner._terminal_reason is None:
                        owner._terminal_reason = 'expired'
                    return False  # no new slot close after the frozen deadline
                slot.close_state = 'closing_unknown'  # tombstone BEFORE the native-close seam
            try:
                outcome = port.close_slot(slot)  # exact own slot, outside the owner gate
            except BaseException as error:
                with owner.gate:
                    if op.cleanup_error is None:
                        op.cleanup_error = error
                return False  # stable storage/tombstone retained; no numeric retry
            with owner.gate:
                if type(outcome) is not bool:
                    return False
                if not outcome:
                    slot.close_state = 'held'  # known refusal; exactly held slot may be retried
                    return False
                slot.close_state = 'closed'; slot.storage = None
        with owner.gate:
            _app_retire(op)
            op.bundle.stable_outputs = None
            op.bundle.overlapped = None
            op.bundle.buffer = None
            op.lease.bundle = None; op.bundle = None; op.phase = 'CLOSED'
        return True  # settled resource state only; not READY/peer/authority/native permission
    finally:
        owner.io_gate.release()