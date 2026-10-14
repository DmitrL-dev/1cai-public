"""Read-only inventory of three explicitly assigned ZIP roles, never a merge."""
from dataclasses import dataclass, field
import json
from pathlib import Path
import secrets
import threading
import time

from .errors import CoreError
from .gui_comparison import _id, _hash, validate_filename
from .rust_input import RustInputSession
from .three_zip_inventory import classify_entries, page_entries

MAX_UPLOAD = 16 * 1024**2
ZIP_SLOTS = 6  # primary current/pending, comparison current/pending, Base/Upstream


def fail(code):
    raise CoreError(code, 'Three ZIP inventory could not complete the request')


@dataclass
class Role:
    role: str
    path: Path
    filename: str | None = None
    upload: str | None = None
    sha256: str = ''
    status: str = 'missing'
    created_at: float = 0
    handler_active: bool = False
    cancel: threading.Event = field(default_factory=threading.Event)


@dataclass
class Plan:
    id: str
    current: object
    current_sha256: str
    roles: dict
    status: str = 'awaiting_inputs'
    error: str | None = None
    rows: tuple = ()
    counts: dict | None = None
    coverage: dict | None = None
    page: str | None = None
    valid: bool = True
    worker_active: bool = False
    cancel: threading.Event = field(default_factory=threading.Event)


class ThreewayWorkspace:
    def _init_threeway(self):
        self.threeway = None
        self.threeway_worker = None

    def _zip_slots(self):
        paths = {item.path for item in (self.current, self.pending, self.comparison_current,
                                        self.comparison_pending) if item is not None}
        if self.threeway:
            paths.update(role.path for role in self.threeway.roles.values())
        return paths

    def _reserve_zip_slots(self, count, *, excluding=()):
        # Logical reservations count full 16 MiB slots, including empty/pending
        # paths. All callers hold the workspace lock and reserve before writes.
        if len(self._zip_slots() - set(excluding)) + count > ZIP_SLOTS:
            fail('GUI_RESOURCE_LIMIT')

    def _threeway_current(self, job_id, sha256):
        if not _id(job_id) or not _hash(sha256):
            fail('THREEWAY_NOT_AVAILABLE')
        job = self.current
        if self.closed or job is None or job.status != 'ready' or job.id != job_id or job.sha256 != sha256:
            fail('THREEWAY_NOT_AVAILABLE')
        return job

    def _get_threeway(self, plan_id, *, valid=True):
        item = self.threeway
        if not _id(plan_id) or item is None or item.id != plan_id or (valid and not item.valid):
            fail('THREEWAY_NOT_AVAILABLE')
        if self._threeway_current(item.current.id, item.current_sha256) is not item.current:
            fail('THREEWAY_NOT_AVAILABLE')
        return item

    def _threeway_active(self, item):
        return item.worker_active or any(role.handler_active for role in item.roles.values())

    def _threeway_clear_files(self, item):
        if self._threeway_active(item):
            return
        for role in item.roles.values():
            role.path.unlink(missing_ok=True)
        # Keep cancelled role metadata for status/recovery, but no inventories.
        item.rows, item.counts, item.coverage, item.page = (), None, None, None

    def _invalidate_threeway(self):
        if self.threeway:
            item = self.threeway
            item.valid = False
            item.cancel.set()
            item.rows, item.counts, item.coverage, item.page = (), None, None, None
            for role in item.roles.values():
                role.cancel.set()
            item.status, item.error = 'cancelled', 'CANCELLED'
            self._threeway_clear_files(item)

    def start_threeway(self, job_id, sha256):
        self.config.authorize()
        with self.lock:
            current = self._threeway_current(job_id, sha256)
            if (self.pending and self.pending.status in {'awaiting_upload','uploading','analyzing'}) or self._comparison_busy():
                fail('BUSY')
            old = self.threeway
            if old and (self._threeway_active(old) or (self.threeway_worker and self.threeway_worker.is_alive())):
                self._invalidate_threeway()
                fail('BUSY')
            self._invalidate_threeway()
            excluded = [role.path for role in old.roles.values()] if old else []
            self._reserve_zip_slots(2, excluding=excluded)
            roles = {name: Role(name, Path(self.temp.name)/(secrets.token_hex(16)+'.zip'))
                     for name in ('base','upstream')}
            item = Plan(secrets.token_hex(16), current, sha256, roles)
            self.threeway = item
            return self._threeway_status(item)

    def _threeway_status(self, item):
        for role in item.roles.values():
            if role.status == 'awaiting_upload' and time.monotonic() - role.created_at >= 30:
                self._abandon_threeway_role(item, role, 'UPLOAD_TIMEOUT')
                role.cancel.set()
        roles = {'current': {'filename': item.current.filename, 'sha256': item.current_sha256,
                             'status': 'ready', 'upload': None}}
        for name, role in item.roles.items():
            roles[name] = {'filename': role.filename, 'sha256': role.sha256 or None,
                           'status': role.status, 'upload': role.upload}
        result = {'plan': item.id, 'job': item.current.id, 'current_sha256': item.current_sha256,
                  'status': item.status, 'error': item.error, 'roles': roles}
        if item.status == 'ready':
            result.update(counts=item.counts, coverage=item.coverage)
        return result

    def validate_threeway_status(self, result):
        item = self._get_threeway(result['plan'])
        if self._threeway_status(item) != result:
            fail('THREEWAY_NOT_AVAILABLE')

    def threeway_status(self, plan_id):
        self.config.authorize()
        with self.lock:
            return self._threeway_status(self._get_threeway(plan_id))

    def recover_threeway(self, job_id, sha256):
        self.config.authorize()
        with self.lock:
            current = self._threeway_current(job_id, sha256)
            item = self.threeway
            if item and item.valid and item.current is current and item.current_sha256 == sha256:
                return self._threeway_status(item)
            return {'plan': None, 'job': job_id, 'current_sha256': sha256, 'status': 'none'}

    def reserve_threeway_upload(self, plan_id, role_name, filename):
        self.config.authorize()
        validate_filename(filename)
        if type(role_name) is not str or role_name not in {'base','upstream'}:
            fail('INVALID_REQUEST')
        with self.lock:
            item = self._get_threeway(plan_id)
            if item.cancel.is_set():
                fail('CANCELLED')
            if self._threeway_active(item) or (self.threeway_worker and self.threeway_worker.is_alive()):
                fail('BUSY')
            for other in item.roles.values():
                if other.status == 'awaiting_upload':
                    if time.monotonic() - other.created_at < 30:
                        fail('BUSY')
                    other.status = 'error'
                    other.cancel.set()
                    other.path.unlink(missing_ok=True)
            role = item.roles[role_name]
            # Replacement never owns old+new files simultaneously. The previous
            # body handler and Rust worker are already quiescent above.
            role.path.unlink(missing_ok=True)
            self._reserve_zip_slots(0)
            role.filename, role.upload = filename, secrets.token_hex(16)
            role.sha256, role.status, role.created_at = '', 'awaiting_upload', time.monotonic()
            role.cancel = threading.Event()
            item.status, item.error = 'awaiting_inputs', None
            item.rows, item.counts, item.coverage, item.page = (), None, None, None
            return {'plan': item.id, 'upload': role.upload, 'role': role_name, 'status': role.status}

    def _get_threeway_upload(self, plan_id, upload_id):
        item = self._get_threeway(plan_id)
        if not _id(upload_id):
            fail('THREEWAY_NOT_AVAILABLE')
        role = next((role for role in item.roles.values() if role.upload == upload_id), None)
        if role is None:
            fail('THREEWAY_NOT_AVAILABLE')
        return item, role

    def _threeway_authorize(self, item):
        self.config.authorize()
        with self.lock:
            if self.closed or item.cancel.is_set():
                fail('CANCELLED')
            if self._get_threeway(item.id) is not item:
                fail('THREEWAY_NOT_AVAILABLE')

    def _threeway_entries(self, path, sha256, authorize):
        with RustInputSession(self.config.input_core, self.config.input_core_sha256,
                              authorize=authorize) as session:
            manifest = session.open_import(path, sha256)
            return session.entries(manifest)

    def _start_threeway_analysis(self, item, role):
        with self.lock:
            self._threeway_authorize(item)
            if role.cancel.is_set() or role.status != 'uploading':
                fail('CANCELLED')
            role.status, item.status, item.worker_active = 'analyzing', 'analyzing', True
            self.threeway_worker = threading.Thread(target=self._run_threeway, args=(item, role),
                                                   name='rentgen-gui-threeway', daemon=False)
            self.threeway_worker.start()

    def _abandon_threeway_role(self, item, role, code):
        with self.lock:
            role.status = 'cancelled' if item.cancel.is_set() or role.cancel.is_set() or self.closed else 'error'
            item.status, item.error = role.status, 'CANCELLED' if role.status == 'cancelled' else code
            item.rows, item.counts, item.coverage, item.page = (), None, None, None
            if not role.handler_active and not item.worker_active:
                role.path.unlink(missing_ok=True)

    def _run_threeway(self, item, role):
        try:
            with self.io_lock:
                authorize = lambda: self._threeway_authorize(item)
                authorize()
                # Validate the newly supplied safe ZIP, without XML/native claims.
                self._threeway_entries(role.path, role.sha256, authorize)
                with self.lock:
                    authorize()
                    role.status = 'ready'
                    complete = all(side.status == 'ready' for side in item.roles.values())
                if complete:
                    current = self._threeway_entries(item.current.path, item.current_sha256, authorize)
                    base = self._threeway_entries(item.roles['base'].path, item.roles['base'].sha256, authorize)
                    upstream = self._threeway_entries(item.roles['upstream'].path, item.roles['upstream'].sha256, authorize)
                    rows, counts, coverage = classify_entries(base, current, upstream, checkpoint=authorize)
                    del base, current, upstream
                    authorize()
                    with self.lock:
                        authorize()
                        item.rows, item.counts, item.coverage = rows, counts, coverage
                        item.status, item.error = 'ready', None
                else:
                    with self.lock:
                        authorize()
                        item.status, item.error = 'awaiting_inputs', None
        except Exception as error:
            self._abandon_threeway_role(item, role, error.code if isinstance(error, CoreError) else 'INTERNAL_ERROR')
        finally:
            with self.lock:
                item.worker_active = False
                if item.cancel.is_set():
                    self._threeway_clear_files(item)
                elif role.status == 'error' and not role.handler_active:
                    role.path.unlink(missing_ok=True)

    def cancel_threeway(self, plan_id):
        self.config.authorize()
        with self.lock:
            item = self._get_threeway(plan_id, valid=False)
            item.cancel.set()
            for role in item.roles.values():
                role.cancel.set()
                if role.status != 'missing':
                    role.status = 'cancelled'
            item.status, item.error = 'cancelled', 'CANCELLED'
            item.rows, item.counts, item.coverage, item.page = (), None, None, None
            self._threeway_clear_files(item)
            return {'plan': item.id, 'status': 'cancelled', 'cancel_requested': True}

    def _threeway_binding(self, item):
        return {'plan': item.id, 'job': item.current.id, 'current_sha256': item.current_sha256,
                'base_sha256': item.roles['base'].sha256, 'upstream_sha256': item.roles['upstream'].sha256}

    def _threeway_ready(self, plan_id, base_sha256, current_sha256, upstream_sha256):
        item = self._get_threeway(plan_id)
        if (item.cancel.is_set() or item.status != 'ready'
                or any(not _hash(value) for value in (base_sha256,current_sha256,upstream_sha256))
                or (base_sha256,current_sha256,upstream_sha256) !=
                   (item.roles['base'].sha256,item.current_sha256,item.roles['upstream'].sha256)):
            fail('THREEWAY_NOT_AVAILABLE')
        return item

    def threeway_page(self, plan_id, base_sha256, current_sha256, upstream_sha256, offset, action):
        self.config.authorize()
        with self.lock:
            item = self._threeway_ready(plan_id, base_sha256, current_sha256, upstream_sha256)
            result = page_entries(item.rows, offset, action, checkpoint=lambda: self._threeway_authorize(item))
            item.page = secrets.token_hex(16)
            result['page']['id'] = item.page
            return {**self._threeway_binding(item), **result, 'counts': item.counts, 'coverage': item.coverage}

    def validate_threeway_page(self, result):
        item = self._threeway_ready(result['plan'],result['base_sha256'],result['current_sha256'],result['upstream_sha256'])
        if item.page != result['page']['id']:
            fail('THREEWAY_NOT_AVAILABLE')


def dispatch_threeway(handler, path):
    app = handler.server.workspace
    if handler.command == 'GET' and path in {'/api/threeway','/api/threeway-current','/api/threeway-page'}:
        with app.lock:
            if path == '/api/threeway':
                q=handler._query({'plan'});result=app.threeway_status(q['plan'])
                validate=lambda: app.validate_threeway_status(result)
            elif path == '/api/threeway-current':
                q=handler._query({'job','input_sha256'});result=app.recover_threeway(q['job'],q['input_sha256'])
                validate=lambda: app.validate_threeway_status(result) if result['plan'] else app._threeway_current(q['job'],q['input_sha256'])
            else:
                q=handler._query({'plan','base_sha256','current_sha256','upstream_sha256','offset','action'})
                if not q['offset'].isascii() or not q['offset'].isdigit() or len(q['offset'])>5:
                    fail('INVALID_QUERY_OPTIONS')
                result=app.threeway_page(q['plan'],q['base_sha256'],q['current_sha256'],q['upstream_sha256'],int(q['offset']),q['action'])
                validate=lambda: app.validate_threeway_page(result)
            handler._json(result,validate=validate)
        return True
    if handler.command == 'POST' and path in {'/api/threeway-start','/api/threeway-upload-start','/api/threeway-cancel'}:
        if handler.headers.get_all('Content-Type') != ['application/json']:
            fail('INVALID_REQUEST')
        payload=json.loads(handler._body(4096))
        required={'job','input_sha256'} if path=='/api/threeway-start' else {'plan','role','filename'} if path=='/api/threeway-upload-start' else {'plan'}
        if type(payload) is not dict or set(payload)!=required:
            fail('INVALID_REQUEST')
        with app.lock:
            if path=='/api/threeway-start':
                result=app.start_threeway(payload['job'],payload['input_sha256'])
                validate=lambda: app.validate_threeway_status(result)
            elif path=='/api/threeway-upload-start':
                result=app.reserve_threeway_upload(payload['plan'],payload['role'],payload['filename'])
                validate=lambda: app._get_threeway_upload(result['plan'],result['upload'])
            else:
                result=app.cancel_threeway(payload['plan'])
                validate=lambda: app._get_threeway(result['plan'],valid=False)
            handler._json(result,status=200 if path.endswith('-cancel') else 201,validate=validate)
        return True
    if handler.command=='PUT' and path=='/api/threeway-upload':
        if handler.headers.get_all('Content-Type') != ['application/zip']:
            fail('INVALID_UPLOAD')
        q=handler._query({'plan','upload'});length=handler._length(MAX_UPLOAD)
        with app.lock:
            item,role=app._get_threeway_upload(q['plan'],q['upload'])
            if role.status=='awaiting_upload' and time.monotonic()-role.created_at>=30:
                app._abandon_threeway_role(item,role,'UPLOAD_TIMEOUT')
                role.cancel.set()
                fail('UPLOAD_TIMEOUT')
            if item.cancel.is_set() or role.cancel.is_set() or role.status!='awaiting_upload':
                fail('CANCELLED')
            if app._threeway_active(item):
                fail('BUSY')
            app._reserve_zip_slots(0)
            role.handler_active=True
            role.status,item.status='uploading','uploading'
        try:
            handler._upload_bytes(role,length,lambda side: app._start_threeway_analysis(item,side),
                                  lambda side,code: app._abandon_threeway_role(item,side,code))
            with app.lock:
                handler._json({'plan':item.id,'upload':role.upload,'role':role.role},status=202,
                              validate=lambda: app._get_threeway_upload(item.id,role.upload))
        finally:
            with app.lock:
                role.handler_active=False
                if item.cancel.is_set():
                    app._threeway_clear_files(item)
                elif role.status=='error' and not item.worker_active:
                    role.path.unlink(missing_ok=True)
        return True
    return False
