"""Real Rust/HTTP selected-module occurrence lifecycle and disclosure guards."""
import hashlib
import json
import sys
import threading
import time
from urllib.parse import urlencode

import pytest
from rentgen_core import gui, gui_occurrences
from test_local_gui import post, request, running, upload, prepare
from test_rust_input_workflow import binary, zip_bytes
from test_metadata_three_way_materialize import PATH as XML_PATH, xml

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux GUI qualification')
PATH = 'CommonModules/Shared/Ext/Module.bsl'


def imported(server, text='aaa\r\n😀a\ra\na'):
    raw = b'\xef\xbb\xbf' + text.encode()
    job, outcome = upload(server, zip_bytes({XML_PATH: xml(), PATH: raw}))
    assert outcome['status'] == 'ready', outcome
    return {'job': job, 'input_sha256': outcome['result']['input']['input_sha256'],
            'path': PATH, 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'query': 'a', 'offset': 0}


def start(server, payload):
    status, result = post(server, '/api/occurrences-start', payload)
    assert status == 201, result
    assert {k: result[k] for k in payload} == payload
    return {k: result[k] for k in ('job', 'occurrence', 'input_sha256')}


def poll(server, selector):
    status, raw, _ = request(server, '/api/occurrences?' + urlencode(selector))
    return status, json.loads(raw)


def wait(server, selector):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        status, result = poll(server, selector)
        assert status == 200, result
        if result['status'] != 'searching':
            return result
        time.sleep(.01)
    pytest.fail('occurrences did not terminate')


def test_exact_positions_pagination_and_old_source_compatible(running):
    app, server, _ = running
    binding = imported(server)
    result = wait(server, start(server, binding))
    assert result['status'] == 'ready', result
    data = result['result']
    assert [(hit['line'], hit['column']) for hit in data['occurrences']] == [(1,1),(1,2),(1,3),(2,2),(3,1),(4,1)]
    assert data['page']['total'] == 6 and data['coverage']['complete']
    assert data['input_ref']['raw_sha256'] == binding['raw_sha256']
    assert request(server, '/api/source?' + urlencode({'job': binding['job'], 'path': PATH}))[0] == 200
    app.occurrence_worker.join(5)
    binding = imported(server, 'a' * 450)
    first = wait(server, start(server, binding))['result']
    assert len(first['occurrences']) == 200 and first['page']['total'] == 450
    app.occurrence_worker.join(5)
    second = wait(server, start(server, {**binding, 'offset': 200}))['result']
    assert second['occurrences'][0]['column'] == 201 and second['page']['total'] == 450


@pytest.mark.parametrize('change', [dict(raw_sha256='0'*64),dict(input_sha256='0'*64),dict(path='../Module.bsl'),dict(path='unknown.bsl'),dict(query=''),dict(offset=True),dict(offset=1)])
def test_rejects_unbound_or_invalid_start(running, change):
    app, server, _ = running
    binding = imported(server)
    assert post(server, '/api/occurrences-start', {**binding, **change})[0] == 400
    assert app.occurrence is None


def block_read(monkeypatch):
    entered, proceed, children = threading.Event(), threading.Event(), []
    original = gui_occurrences.search_source_occurrences
    def delayed(*args, **kwargs):
        entered.set()
        assert proceed.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(gui_occurrences, 'search_source_occurrences', delayed)
    return entered, proceed


@pytest.mark.parametrize('action', ['cancel', 'import', 'ordinary_search', 'close'])
def test_inflight_cancellation_and_invalidation_return_no_rows(running, monkeypatch, action):
    app, server, _ = running
    binding = imported(server)
    entered, proceed = block_read(monkeypatch)
    selector = start(server, binding)
    assert entered.wait(5)
    try:
        if action == 'cancel':
            assert post(server, '/api/occurrences-cancel', selector)[0] == 200
        elif action == 'import':
            prepare(server)
        elif action == 'ordinary_search':
            status, _ = post(server, '/api/search-start', {'job':binding['job'],'input_sha256':binding['input_sha256'],'query':'','kind':'modules'})
            assert status == 201
        else:
            app.begin_close()
    finally:
        proceed.set()
    app.occurrence_worker.join(5)
    assert not app.occurrence_worker.is_alive()
    assert app.occurrence.result is None and app.occurrence.status == 'cancelled'


@pytest.mark.parametrize('mutation', ['permission', 'source_row', 'job', 'archive_hash'])
def test_revalidation_after_actual_json_serialization(running, monkeypatch, mutation):
    app, server, _ = running
    binding = imported(server)
    selector = start(server, binding)
    assert wait(server, selector)['status'] == 'ready'
    ctx = app.config.context()
    original = gui.json.dumps
    changed = []
    def dumps(value, *args, **kwargs):
        result = original(value, *args, **kwargs)
        if isinstance(value,dict) and value.get('occurrence') == selector['occurrence'] and value.get('status') == 'ready' and not changed:
            changed.append(True)
            if mutation == 'permission':
                with ctx.state.transaction(ctx.principal, write=True) as tx:
                    tx._connection.execute("DELETE FROM membership_permissions WHERE permission='analysis:run'")
            elif mutation == 'source_row':
                app.current.result['modules'].clear()
            elif mutation == 'job':
                app.current = None
            else:
                app.current.sha256 = '0'*64
        return result
    monkeypatch.setattr(gui.json, 'dumps', dumps)
    status, value = poll(server, selector)
    assert changed and status == (403 if mutation == 'permission' else 400)
    assert 'result' not in value


@pytest.mark.parametrize('action', ['revoke', 'cancel', 'replace_archive'])
def test_actual_rust_child_reaped_after_mid_io_denial(running, monkeypatch, action):
    app, server, _ = running
    binding = imported(server)
    ctx = app.config.context()
    entered, proceed, children = threading.Event(), threading.Event(), []
    original = gui.RustInputSession.open_import
    def opened(session, *args):
        result = original(session, *args)
        if threading.current_thread().name == 'rentgen-gui-occurrences':
            children.append(session.process)
            entered.set()
            assert proceed.wait(5)
        return result
    monkeypatch.setattr(gui.RustInputSession, 'open_import', opened)
    selector = start(server, binding)
    assert entered.wait(5)
    try:
        if action == 'revoke':
            with ctx.state.transaction(ctx.principal, write=True) as tx:
                tx._connection.execute("DELETE FROM membership_permissions WHERE permission='analysis:run'")
        elif action == 'cancel':
            assert post(server, '/api/occurrences-cancel', selector)[0] == 200
        else:
            # Rust owns immutable bytes already: pathname replacement must not
            # change the source evidence returned from this accepted import.
            app.current.path.write_bytes(b'changed after Rust import')
    finally:
        proceed.set()
    app.occurrence_worker.join(5)
    assert not app.occurrence_worker.is_alive()
    assert children and all(child.poll() is not None for child in children)
    if action == 'replace_archive':
        assert app.occurrence.status == 'ready'
        assert app.occurrence.result['input_ref']['raw_sha256'] == binding['raw_sha256']
        # A subsequent page must reopen/rehash and reject the changed file.
        second = start(server, binding)
        assert wait(server, second)['status'] == 'error'
    else:
        assert app.occurrence.result is None and app.occurrence.status in {'error','cancelled'}


def test_cancel_ready_clears_retrievable_occurrences(running):
    app, server, _ = running
    binding = imported(server)
    selector = start(server, binding)
    assert wait(server, selector)['status'] == 'ready'
    assert post(server, '/api/occurrences-cancel', selector) == (200, {'status':'cancelled','cancel_requested':True})
    status, value = poll(server, selector)
    assert status == 200 and value['status'] == 'cancelled' and 'result' not in value
    assert app.occurrence.result is None
