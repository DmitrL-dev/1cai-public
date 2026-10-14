"""Selected-module literal navigation with temporary, existing-row authority."""
from dataclasses import dataclass, field
import json
import re
import secrets
import threading

from .errors import CoreError
from .source_search import validate_source_query
from .source_occurrences import search_source_occurrences, validate_occurrence_offset


def fail(code):
    raise CoreError(code, 'Selected module occurrences are not available')


@dataclass
class Occurrence:
    id: str
    job: object
    reference: dict
    query: str
    offset: int
    status: str = 'searching'
    error: str | None = None
    result: dict | None = None
    valid: bool = True
    cancel: threading.Event = field(default_factory=threading.Event)

    def binding(self):
        return {'occurrence': self.id, 'job': self.job.id,
                'input_sha256': self.reference['input_sha256'],
                'path': self.reference['relative_path'], 'raw_sha256': self.reference['raw_sha256'],
                'query': self.query, 'offset': self.offset}


class OccurrenceWorkspace:
    def _init_occurrences(self):
        self.occurrence = None
        self.occurrence_worker = None

    def _invalidate_occurrences(self):
        # Called with workspace lock held. Preserve an unreaped worker handle.
        if self.occurrence:
            self.occurrence.valid = False
            self.occurrence.cancel.set()
            self.occurrence.result = None
            if self.occurrence.status == 'ready':
                self.occurrence.status = 'cancelled'
                self.occurrence.error = 'CANCELLED'

    def _get_occurrence(self, job_id, occurrence_id, sha256, *, valid=True):
        item = self.occurrence
        if (type(occurrence_id) is not str or re.fullmatch(r'[0-9a-f]{32}', occurrence_id) is None
                or item is None or item.id != occurrence_id or item.job.id != job_id
                or item.reference['input_sha256'] != sha256 or (valid and not item.valid)):
            fail('SOURCE_NOT_AVAILABLE')
        # Row authority is still owned by the current import/search page, never
        # created by the occurrence query itself. Recheck on every disclosure.
        self.validate_source(job_id, item.reference['relative_path'], item.reference)
        return item

    def start_occurrences(self, job_id, sha256, path, raw_sha256, query, offset=0):
        self.config.authorize()
        validate_source_query(query)
        validate_occurrence_offset(offset)
        if (type(path) is not str or not path.lower().endswith(('.bsl', '.os', '.bsp'))
                or type(raw_sha256) is not str or re.fullmatch(r'[0-9a-f]{64}', raw_sha256) is None):
            fail('INVALID_QUERY_OPTIONS')
        with self.lock:
            job = self._search_job(job_id, sha256)
            _, reference = self._source_reference(job_id, path)
            if reference['raw_sha256'] != raw_sha256:
                fail('SOURCE_NOT_AVAILABLE')
            if self.pending and self.pending.status in {'awaiting_upload', 'uploading', 'analyzing'}:
                fail('BUSY')
            if self.search_worker and self.search_worker.is_alive():
                fail('BUSY')
            if self.occurrence_worker and self.occurrence_worker.is_alive():
                self._invalidate_occurrences()
                fail('BUSY')
            self._invalidate_occurrences()
            item = Occurrence(secrets.token_hex(16), job, dict(reference), query, offset)
            self.occurrence = item
            self.occurrence_worker = threading.Thread(target=self._run_occurrences, args=(item,),
                                                     name='rentgen-gui-occurrences', daemon=False)
            self.occurrence_worker.start()
            return item.binding()

    def _run_occurrences(self, item):
        try:
            with self.io_lock:
                with self.lock:
                    if self.closed or item.cancel.is_set():
                        fail('CANCELLED')
                    self._get_occurrence(item.job.id, item.id, item.reference['input_sha256'])
                result = search_source_occurrences(self.config.context(), archive=item.job.path,
                    archive_sha256=item.reference['input_sha256'], input_core=self.config.input_core,
                    input_core_sha256=self.config.input_core_sha256, reference=item.reference,
                    query=item.query, offset=item.offset, cancelled=item.cancel.is_set)
                self.config.authorize()
                with self.lock:
                    if self.closed or item.cancel.is_set():
                        fail('CANCELLED')
                    self._get_occurrence(item.job.id, item.id, item.reference['input_sha256'])
                    item.result = result
                    item.status = 'ready'
        except Exception as error:
            with self.lock:
                item.error = ('CANCELLED' if item.cancel.is_set() or self.closed else
                              error.code if isinstance(error, CoreError) else 'INTERNAL_ERROR')
                item.status = 'cancelled' if item.error == 'CANCELLED' else 'error'
                item.result = None

    def occurrence_status(self, job_id, occurrence_id, sha256):
        self.config.authorize()
        with self.lock:
            item = self._get_occurrence(job_id, occurrence_id, sha256)
            result = {**item.binding(), 'status': item.status, 'error': item.error}
            if item.status == 'ready':
                result['result'] = item.result
            return result

    def cancel_occurrences(self, job_id, occurrence_id, sha256):
        self.config.authorize()
        with self.lock:
            self._search_job(job_id, sha256)
            item = self.occurrence
            if occurrence_id is None:
                if item is None or item.job.id != job_id or item.reference['input_sha256'] != sha256:
                    return {'status': 'cancelled', 'cancel_requested': False}
            else:
                item = self._get_occurrence(job_id, occurrence_id, sha256, valid=False)
            item.cancel.set()
            item.result = None
            if item.status == 'ready':
                item.status = 'cancelled'
                item.error = 'CANCELLED'
            return {'status': item.status, 'cancel_requested': True}


def dispatch_occurrences(handler, path):
    app = handler.server.workspace
    if handler.command == 'GET' and path == '/api/occurrences':
        query = handler._query({'job', 'occurrence', 'input_sha256'})
        with app.lock:
            validate = lambda: app._get_occurrence(query['job'], query['occurrence'], query['input_sha256'])
            result = app.occurrence_status(query['job'], query['occurrence'], query['input_sha256'])
            handler._json(result, validate=validate)
        return True
    if handler.command != 'POST' or path not in {'/api/occurrences-start', '/api/occurrences-cancel'}:
        return False
    if handler.headers.get_all('Content-Type') != ['application/json']:
        fail('INVALID_REQUEST')
    payload = json.loads(handler._body(4096))
    start = path.endswith('-start')
    required = ({'job', 'input_sha256', 'path', 'raw_sha256', 'query', 'offset'} if start else
                {'job', 'input_sha256', 'occurrence'})
    if type(payload) is not dict or set(payload) != required:
        fail('INVALID_REQUEST')
    with app.lock:
        if start:
            result = app.start_occurrences(payload['job'], payload['input_sha256'], payload['path'],
                                           payload['raw_sha256'], payload['query'], payload['offset'])
            validate = lambda: app._get_occurrence(result['job'], result['occurrence'], result['input_sha256'])
            handler._json(result, status=201, validate=validate)
        else:
            result = app.cancel_occurrences(payload['job'], payload['occurrence'], payload['input_sha256'])
            handler._json(result, validate=lambda: app._search_job(payload['job'], payload['input_sha256']))
    return True
