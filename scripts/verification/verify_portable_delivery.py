"""Install the exact candidate wheel and verify Linux CLI and local GUI delivery.

Creates only new synthetic inputs under the explicit output directory. No model,
network downloads, project import, live apply or existing user profile is used.
"""
if not __debug__:
    raise RuntimeError('Delivery verification requires assertions; do not use Python -O')

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time
from urllib.parse import urlencode, urlsplit
import venv
import zipfile


def snapshot(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def bootstrap(child, timeout=15):
    """Consume the session-bearing startup privately; never include it in errors."""
    raw = bytearray()
    deadline = time.monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        selector.register(child.stdout, selectors.EVENT_READ)
        while raw.count(b'\n') < 2:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise AssertionError('Installed GUI readiness timed out')
            chunk = os.read(child.stdout.fileno(), 4096)
            if not chunk or len(raw) + len(chunk) > 8192:
                raise AssertionError('Installed GUI exited or emitted invalid startup')
            raw.extend(chunk)
    try:
        url = raw.splitlines()[1].decode('utf-8')
        parts = urlsplit(url)
        assert (parts.scheme == 'http' and parts.hostname == '127.0.0.1'
                and parts.port and parts.path == '/' and not parts.query
                and not parts.username and not parts.password
                and re.fullmatch(r'[A-Za-z0-9_-]{43}', parts.fragment))
    except (AssertionError, UnicodeError, ValueError, IndexError):
        raise AssertionError('Installed GUI emitted invalid private bootstrap') from None
    return f'http://127.0.0.1:{parts.port}', parts.fragment


def gui_delivery(python, core, core_hash, common, project, archive, wheel, workspace, output):
    """Run the installed console entry point, real HTTP/Rust and packaged assets."""
    before = snapshot(workspace)
    temporary = output / 'gui-temp'
    temporary.mkdir()
    env = {key: value for key, value in os.environ.items() if key not in {'PYTHONPATH', 'PYTHONHOME'}}
    env.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', TMPDIR=str(temporary))
    command = [str(python), '-I', str(python.with_name('rentgen-gui')), *map(str, common),
               '--project', project, '--input-core', str(core), '--input-core-sha256', core_hash]
    child = subprocess.Popen(command, cwd=workspace, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        origin, token = bootstrap(child)
        port = urlsplit(origin).port

        def request(path, method='GET', body=None, authenticated=True, expected=200, origin_header=None):
            headers = {'Origin': origin if origin_header is None else origin_header}
            if authenticated:
                headers['X-Rentgen-Session'] = token
            if isinstance(body, dict):
                body = json.dumps(body).encode()
                headers['Content-Type'] = 'application/json'
            elif body is not None:
                headers['Content-Type'] = 'application/zip'
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=20)
            try:
                connection.request(method, path, body, headers)
                response = connection.getresponse()
                raw = response.read(4 * 1024**2 + 1)
                assert len(raw) <= 4 * 1024**2 and response.status == expected, 'Installed GUI HTTP contract failed'
                assert response.getheader('Cache-Control') == 'no-store'
                assert "frame-ancestors 'none'" in response.getheader('Content-Security-Policy', '')
                assert response.getheader('Access-Control-Allow-Origin') is None
                return raw
            finally:
                connection.close()

        with zipfile.ZipFile(wheel) as package:
            assets = {name.removeprefix('rentgen_core/gui_assets/'): package.read(name)
                      for name in package.namelist() if name.startswith('rentgen_core/gui_assets/') and not name.endswith('/')}
        assert {'index.html', 'app.js', 'app.css', 'comparison.js', 'threeway.js', 'occurrences.js'} <= assets.keys(), 'GUI assets missing from installed wheel'
        assert all('/' not in name for name in assets), 'Unexpected GUI asset path'
        for name, expected in assets.items():
            raw = request('/' if name == 'index.html' else '/' + name, authenticated=False)
            assert raw == expected, 'HTTP asset differs from accepted wheel bytes'
            assert token.encode() not in raw, 'Session token leaked into static content'
        assert json.loads(request('/api/session', authenticated=False, expected=401)) == {'error': 'UNAUTHORIZED'}
        assert json.loads(request('/api/session', origin_header='https://example.invalid', expected=401)) == {'error': 'UNAUTHORIZED'}
        session = json.loads(request('/api/session'))
        assert session['platform'] == 'experimental-linux'
        job = json.loads(request('/api/import-start', 'POST', {'filename': 'installed.zip'}, expected=201))['job']
        request('/api/import?' + urlencode({'job': job}), 'PUT', archive.read_bytes(), expected=202)
        deadline = time.monotonic() + 20
        while True:
            result = json.loads(request('/api/job?' + urlencode({'job': job})))
            if result['status'] not in {'awaiting_upload', 'uploading', 'analyzing'}:
                break
            assert time.monotonic() < deadline, 'Installed GUI Rust import timed out'
            time.sleep(.02)
        assert result['status'] == 'ready', 'Installed GUI Rust import failed'
        report = result['result']
        assert report['counts']['metadata_objects'] == 1 and report['counts']['modules'] == 1
        assert report['input']['input_sha256'] == hashlib.sha256(archive.read_bytes()).hexdigest()
        module = report['modules'][0]['input_ref']
        source = json.loads(request('/api/source?' + urlencode({'job': job, 'path': module['relative_path']})))
        assert source['input_ref']['raw_sha256'] == module['raw_sha256']
        assert hashlib.sha256(source['text'].encode()).hexdigest() == module['raw_sha256']
        assert source['text'] == 'Procedure Demo()\nEndProcedure\n'
        receipt = {'console_entry_point': True, 'isolated_installed_package': True,
                   'static_assets_equal_wheel': len(assets), 'unauthenticated_refused': True,
                   'foreign_origin_refused': True, 'http_rust_import': True,
                   'hash_bound_source_read': True, 'loopback_only': True}
    finally:
        if child.poll() is None:
            child.send_signal(signal.SIGINT)
        try:
            _, stderr = child.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate(timeout=5)
            raise AssertionError('Installed GUI failed to stop cleanly') from None
        assert child.returncode == 0 and not stderr, 'Installed GUI process failed or emitted stderr'
    assert snapshot(workspace) == before, 'Installed GUI changed synthetic project or input files'
    assert not any(temporary.iterdir()), 'Installed GUI left owned temporary files'
    receipt.update(project_and_inputs_unchanged=True, graceful_shutdown=True, temporary_files_removed=True)
    return receipt


def verify(wheel, binary, output, expected_version):
    wheel, binary, output = wheel.resolve(strict=True), binary.resolve(strict=True), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment = output / 'environment'
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / 'bin/python'
    subprocess.run([str(python), '-m', 'pip', 'install', '--no-index', '--no-deps', str(wheel)], check=True, capture_output=True, text=True, timeout=60)
    core = output / 'rentgen-input-core'
    shutil.copyfile(binary, core); core.chmod(0o700)
    core_hash = hashlib.sha256(core.read_bytes()).hexdigest()
    workspace = output / 'work'; workspace.mkdir()
    probe = subprocess.run([str(python), '-I', '-c', 'import importlib.metadata,json,rentgen_core,sys;from pathlib import Path;print(json.dumps({"version":importlib.metadata.version("rentgen-core"),"installed":Path(rentgen_core.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())}))'], cwd=workspace, capture_output=True, text=True, check=True, timeout=15)
    assert json.loads(probe.stdout) == {'version': expected_version, 'installed': True}
    checks = []
    def cli(*args, expected=0):
        result = subprocess.run([str(python), '-I', '-m', 'rentgen_core', *map(str, args)], cwd=workspace, capture_output=True, text=True, timeout=30)
        assert result.returncode == expected and not result.stderr, (result.stdout, result.stderr)
        value = json.loads(result.stdout); checks.append({'command': args[0], 'exit': result.returncode})
        return value
    profile = workspace / 'private/identity.json'
    registry = workspace / 'registry.sqlite3'
    source = workspace / 'source'; source.mkdir(); (source / 'untouched.bsl').write_bytes(b'Unchanged();\n')
    cli('identity-init', '--identity-profile', profile)
    common = ['--registry', registry, '--identity-profile', profile]
    cli('registry-init', *common)
    project = cli('project-register', *common, '--source-root', source, '--state-root', workspace / 'state', '--name', 'Installed portable qualification')['result']['project_id']
    archive = workspace / 'export.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as target:
        target.writestr('Catalogs/Products.xml', '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"><Catalog uuid="11111111-1111-4111-8111-111111111111"><Properties><Name>Products</Name></Properties><ChildObjects/></Catalog></MetaDataObject>')
        target.writestr('CommonModules/Shared/Ext/Module.bsl', 'Procedure Demo()\nEndProcedure\n')
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    args = ['export-analyze', *common, '--project', project, '--archive', archive, '--archive-sha256', archive_hash, '--input-core', core, '--input-core-sha256', core_hash]
    report = cli(*args)['result']
    assert report['counts']['metadata_objects'] == 1 and report['counts']['modules'] == 1
    assert cli(*args)['result'] == report
    assert cli('project-head', *common, '--project', project)['result']['snapshot'] is None
    assert (source / 'untouched.bsl').read_bytes() == b'Unchanged();\n'
    refused = cli('capture', *common, '--project', project, expected=2)
    assert refused['error']['code'] == 'CAPABILITY_UNAVAILABLE'
    gui = gui_delivery(python, core, core_hash, common, project, archive, wheel, workspace, output)
    receipt = {'schema': 1, 'scope': 'experimental Linux installed CLI and read-only GUI import; not Windows/macOS or full Linux qualification', 'version': expected_version, 'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(), 'binary_sha256': core_hash, 'checks': checks, 'counts': report['counts'], 'gui': gui, 'source_unchanged': True, 'project_head_unchanged': True}
    (output / 'acceptance.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-version', required=True)
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Experimental Linux delivery qualification only')
    verify(args.wheel, args.binary, args.output, args.expected_version)


if __name__ == '__main__':
    main()
