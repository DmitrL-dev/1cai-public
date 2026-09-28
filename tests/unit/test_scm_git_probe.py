"""Diagnostic contracts; these never accept a LocalService or stock Git worker."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/verification/scm_git_probe_service.py'


def api():
    assert SCRIPT.is_file(), 'Verification-only Git measurement module is missing'
    spec = importlib.util.spec_from_file_location('scm_git_probe_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def roots(tmp_path):
    selected, other = tmp_path / 'selected', tmp_path / 'other'
    selected.mkdir()
    other.mkdir()
    return selected, other


def result_files(tmp_path, stdout=b'', stderr=b'', code=0, **flags):
    result = {'exit_code': code, 'timed_out': False, 'output_limit_exceeded': False,
              'process_error': None, **flags}
    for name, data in (('stdout', stdout), ('stderr', stderr)):
        path = tmp_path / name
        path.write_bytes(data)
        result[name] = {'path': str(path), 'size_bytes': len(data),
                        'sha256': hashlib.sha256(data).hexdigest()}
    return result


def test_default_environment_removes_inherited_git_overrides_and_simulation():
    env = api().probe_environment({'PATH': 'observed path', 'SystemRoot': r'C:\Windows',
        'GIT_TEST_ASSUME_DIFFERENT_OWNER': '1', 'GIT_CONFIG_COUNT': '1',
        'git_config_key_0': 'safe.directory', 'GIT_CONFIG_VALUE_0': '*', 'GIT_DIR': 'foreign'})
    assert env == {'PATH': 'observed path', 'SystemRoot': r'C:\Windows',
                   'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0', 'GIT_NO_LAZY_FETCH': '1'}


def test_isolated_configuration_is_separate_and_does_not_modify_the_default(tmp_path):
    module = api()
    config = tmp_path / 'empty-global'
    config.write_bytes(b'')
    inherited = {'PATH': 'observed', 'GIT_CONFIG_GLOBAL': 'foreign'}
    default = module.probe_environment(inherited)
    isolated = module.probe_environment(inherited, isolated_global=config)
    assert inherited == {'PATH': 'observed', 'GIT_CONFIG_GLOBAL': 'foreign'}
    assert 'GIT_CONFIG_NOSYSTEM' not in default and 'GIT_CONFIG_GLOBAL' not in default
    assert isolated['GIT_CONFIG_NOSYSTEM'] == '1' and isolated['GIT_CONFIG_GLOBAL'] == str(config)
    assert config.read_bytes() == b''


def test_isolation_rejects_nonempty_or_absent_global_config(tmp_path):
    module = api()
    config = tmp_path / 'global'
    config.write_bytes(b'[safe]\n directory = *\n')
    with pytest.raises(ValueError):
        module.probe_environment({}, isolated_global=config)
    with pytest.raises(ValueError):
        module.probe_environment({}, isolated_global=tmp_path / 'absent')


def test_trust_is_reset_exact_selected_root_and_kept_out_of_environment(tmp_path):
    module = api()
    selected, other = roots(tmp_path)
    git = Path(sys.executable).resolve()
    for repo in (selected, other):
        argv = module.probe_command(git, repo, trusted_root=selected)
        assert argv == (str(git), '--no-pager', '-c', 'core.fsmonitor=false',
            '-c', 'safe.directory=', '-c', 'safe.directory=' + str(selected),
            '-C', str(repo), 'rev-parse', '--show-toplevel', 'HEAD^{commit}')
    default = module.probe_command(git, selected)
    assert not any('safe.directory' in part for part in default)
    assert not any('safe.directory' in value for value in module.probe_environment({}).values())


@pytest.mark.parametrize('unsafe', ['*', '/*', '../selected', 'selected\nforeign'])
def test_command_refuses_wildcard_relative_and_control_paths(tmp_path, unsafe):
    module = api()
    selected, _ = roots(tmp_path)
    with pytest.raises(ValueError):
        module.probe_command(Path(sys.executable).resolve(), selected, trusted_root=unsafe)


def test_command_refuses_other_or_foreign_trust_root(tmp_path):
    module = api()
    selected, other = roots(tmp_path)
    foreign = tmp_path / 'foreign'
    foreign.mkdir()
    for trusted in (other, foreign):
        with pytest.raises(ValueError):
            module.probe_command(Path(sys.executable).resolve(), selected, trusted_root=trusted)


def test_capture_retains_raw_bytes_and_checks_exclusive_evidence_paths(tmp_path):
    module = api()
    command = (sys.executable, '-I', '-c', 'import sys;sys.stdout.buffer.write(b"ok\\xff");sys.stderr.write("raw error")')
    result = module.capture(command, dict(os.environ), tmp_path, 'probe')
    assert result['exit_code'] == 0 and not result['timed_out'] and not result['output_limit_exceeded']
    assert result['argv'] == list(command)
    assert Path(result['stdout']['path']).read_bytes() == b'ok\xff'
    assert Path(result['stderr']['path']).read_bytes() == b'raw error'
    for stream in ('stdout', 'stderr'):
        raw = Path(result[stream]['path']).read_bytes()
        assert result[stream]['sha256'] == hashlib.sha256(raw).hexdigest()
        assert result[stream]['size_bytes'] == len(raw)
    with pytest.raises(FileExistsError):
        module.capture(command, dict(os.environ), tmp_path, 'probe')
    with pytest.raises(ValueError):
        module.capture(command, dict(os.environ), tmp_path, '../foreign')


def test_capture_timeout_terminates_and_reaps_the_same_child(tmp_path):
    module = api()
    result = module.capture((sys.executable, '-I', '-c', 'import time;time.sleep(30)'),
                            dict(os.environ), tmp_path, 'timeout', timeout=0.15)
    assert result['timed_out'] and result['exit_code'] != 0 and result['child_reaped']
    assert result['duration_seconds'] < 5


def test_capture_overflow_is_bounded_and_never_owner_evidence(tmp_path):
    module = api()
    result = module.capture((sys.executable, '-I', '-c',
        'import sys;sys.stdout.buffer.write(b"x"*1000000);sys.stdout.flush()'),
        dict(os.environ), tmp_path, 'overflow', output_limit=1024)
    assert result['output_limit_exceeded'] and result['child_reaped']
    assert result['stdout']['size_bytes'] <= 1024 and result['stderr']['size_bytes'] <= 1024
    assert module.classify_probe(result, tmp_path, 'a' * 40) == 'output_limit'


def test_success_requires_exact_root_and_expected_commit(tmp_path):
    module = api()
    selected, _ = roots(tmp_path)
    result = result_files(tmp_path, (str(selected) + '\n' + 'a' * 40 + '\n').encode())
    assert module.classify_probe(result, selected, 'a' * 40) == 'accepted'
    assert module.classify_probe(result, selected, 'b' * 40) == 'identity_mismatch'
    assert module.classify_probe(result, tmp_path, 'a' * 40) == 'identity_mismatch'


def test_foreign_owner_refusal_requires_actual_git_diagnostic_and_root(tmp_path):
    module = api()
    selected, other = roots(tmp_path)
    error = ("fatal: detected dubious ownership in repository at '" + str(selected) + "'\n").encode()
    result = result_files(tmp_path, stderr=error, code=128)
    assert module.classify_probe(result, selected, 'a' * 40) == 'foreign_owner_refused'
    assert module.classify_probe(result, other, 'a' * 40) == 'command_failed'


@pytest.mark.parametrize('error', [b'fatal: not a git repository', b'Access denied', b'git not found'])
def test_generic_errors_do_not_prove_foreign_owner_refusal(tmp_path, error):
    module = api()
    result = result_files(tmp_path, stderr=error, code=128)
    assert module.classify_probe(result, tmp_path, 'a' * 40) == 'command_failed'


def test_tampered_raw_result_cannot_be_classified_as_success(tmp_path):
    module = api()
    result = result_files(tmp_path, (str(tmp_path) + '\n' + 'a' * 40).encode())
    Path(result['stdout']['path']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='evidence'):
        module.classify_probe(result, tmp_path, 'a' * 40)


def test_owned_raw_evidence_hardlinks_remain_rejected(tmp_path):
    module = api()
    result = result_files(tmp_path, (str(tmp_path) + '\n' + 'a' * 40).encode())
    os.link(result['stdout']['path'], tmp_path / 'raw-alias')
    with pytest.raises(ValueError, match='path type'):
        module.classify_probe(result, tmp_path, 'a' * 40)


def test_real_current_user_git_probe_is_read_only_and_trust_does_not_persist(tmp_path):
    module = api()
    git = shutil.which('git')
    assert git is not None, 'Git required for this local command contract'
    git = Path(git).resolve()
    selected, _ = roots(tmp_path)
    empty = tmp_path / 'global-empty'
    empty.write_bytes(b'')
    env = module.probe_environment(os.environ, isolated_global=empty)

    def run(*args):
        return subprocess.run([str(git), *args], env=env, cwd=selected,
            stdin=subprocess.DEVNULL, capture_output=True, timeout=10, check=True).stdout

    run('init', '-q', '--template=', '--initial-branch=main')
    (selected / 'input.txt').write_bytes(b'owned current-user Git fixture\n')
    run('add', 'input.txt')
    run('-c', 'user.name=Diagnostic Test', '-c', 'user.email=probe@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', 'owned fixture')
    commit = run('rev-parse', 'HEAD').decode().strip()

    def inventory():
        return {p.relative_to(selected).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in selected.rglob('*') if p.is_file()}

    before = inventory()
    result = module.capture(module.probe_command(git, selected, trusted_root=selected),
                             env, tmp_path, 'real-selected')
    assert module.classify_probe(result, selected, commit) == 'accepted'
    scoped = module.capture((str(git), '-c', 'safe.directory=', '-c', 'safe.directory=' + str(selected),
        'config', '--get-all', 'safe.directory'), env, tmp_path, 'scoped-config')
    assert scoped['exit_code'] == 0
    assert Path(scoped['stdout']['path']).read_text('utf-8').splitlines() == ['', str(selected)]
    after = module.capture((str(git), 'config', '--get-all', 'safe.directory'), env, tmp_path, 'next-config')
    assert after['exit_code'] == 1 and Path(after['stdout']['path']).read_bytes() == b''
    assert inventory() == before and empty.read_bytes() == b''


def prepared_inputs(tmp_path, monkeypatch):
    from rentgen_core.service_entry import load_config
    module = api()
    work = tmp_path / ('rg-scm-' + 'a' * 12)
    runtime, fixture = work / 'runtime', work / 'fixture'
    executable = runtime / 'python.exe'
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b'owned test interpreter metadata')
    installed = runtime / 'Lib/site-packages/scm_git_probe_service.py'
    installed.parent.mkdir(parents=True)
    installed.write_bytes(SCRIPT.read_bytes())
    monkeypatch.setattr(module, '__file__', str(installed))
    monkeypatch.setattr(sys, 'executable', str(executable))
    data = fixture / 'localservice/data'
    (data / 'observer-profile').mkdir(parents=True)
    output = data / 'git-probe'
    output.mkdir()
    registry = data / 'registry.sqlite3'
    registry.write_bytes(b'owned diagnostic fixture metadata; DB not accessed')
    scanner = fixture / 'bsl-scan.exe'
    scanner.write_bytes(b'owned unused scanner metadata')
    config_path = fixture / 'localservice/service.json'
    config_path.write_text(json.dumps({'schema': 1, 'service_name': 'Rentgen.CI.' + 'a' * 12,
        'registry': str(registry), 'profile': str(data / 'observer-profile'), 'project': str(uuid4()),
        'scanner': str(scanner), 'interval_seconds': 5, 'max_cycles': None}), 'utf-8')
    config = load_config(config_path)
    probe = fixture / 'git-probe'
    repositories = {}
    for name in ('selected', 'other'):
        repo = probe / 'source' / name
        (repo / '.git/refs/heads').mkdir(parents=True)
        (repo / '.git/HEAD').write_bytes(b'ref: refs/heads/main\n')
        (repo / '.git/refs/heads/main').write_bytes(('a' * 40 + '\n').encode())
        (repo / '.git/config').write_bytes(b'')
        repositories[name] = {'root': str(repo), 'commit': 'a' * 40,
            'owner_sid': 'S-1-5-32-544', 'files': {
                path.relative_to(repo).as_posix(): {'size_bytes': path.stat().st_size,
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in repo.rglob('*') if path.is_file()}}
    empty = probe / 'empty-global.cfg'
    empty.write_bytes(b'')
    inputs = {'schema': 1, 'workdir': str(work), 'service_name': config.service_name,
        'project': config.project, 'config_sha256': hashlib.sha256(config_path.read_bytes()).hexdigest(),
        'module_sha256': hashlib.sha256(installed.read_bytes()).hexdigest(),
        'repositories': repositories, 'empty_global_sha256': hashlib.sha256(b'').hexdigest()}
    sidecar = probe / 'inputs.json'
    sidecar.write_text(json.dumps(inputs), 'utf-8')
    return module, config, config_path, sidecar, inputs, output


def test_fixed_probe_inputs_bind_runtime_module_config_and_repositories(tmp_path, monkeypatch):
    module, config, path, sidecar, inputs, output = prepared_inputs(tmp_path, monkeypatch)
    loaded = module.load_inputs(config, path)
    assert loaded['document'] == inputs and loaded['output'] == output
    assert loaded['selected'] == Path(inputs['repositories']['selected']['root'])
    assert loaded['other'] == Path(inputs['repositories']['other']['root'])
    assert loaded['empty_global'] == sidecar.parent / 'empty-global.cfg'


@pytest.mark.parametrize('changed', ['service_name', 'project', 'module_sha256', 'config_sha256', 'workdir'])
def test_probe_inputs_refuse_changed_bindings_before_measurement(tmp_path, monkeypatch, changed):
    module, config, path, sidecar, inputs, _ = prepared_inputs(tmp_path, monkeypatch)
    inputs[changed] = 'unbound changed value'
    sidecar.write_text(json.dumps(inputs), 'utf-8')
    with pytest.raises(ValueError):
        module.load_inputs(config, path)


def test_probe_inputs_refuse_changed_repository_and_nonempty_global(tmp_path, monkeypatch):
    module, config, path, sidecar, inputs, _ = prepared_inputs(tmp_path, monkeypatch)
    head = Path(inputs['repositories']['selected']['root']) / '.git/HEAD'
    original = head.read_bytes()
    head.write_bytes(b'changed')
    with pytest.raises(ValueError):
        module.load_inputs(config, path)
    head.write_bytes(original)
    (sidecar.parent / 'empty-global.cfg').write_bytes(b'[safe]\n directory=*\n')
    with pytest.raises(ValueError):
        module.load_inputs(config, path)


def test_probe_inputs_refuse_missing_sidecar_and_preexisting_output(tmp_path, monkeypatch):
    module, config, path, sidecar, _, output = prepared_inputs(tmp_path, monkeypatch)
    (output / 'retained.json').write_bytes(b'old result')
    with pytest.raises(ValueError):
        module.load_inputs(config, path)
    (output / 'retained.json').unlink()
    sidecar.unlink()
    with pytest.raises(ValueError):
        module.load_inputs(config, path)


def test_probe_inputs_refuse_escaped_trust_root_and_linked_source(tmp_path, monkeypatch):
    module, config, path, sidecar, inputs, _ = prepared_inputs(tmp_path, monkeypatch)
    selected = inputs['repositories']['selected']['root']
    inputs['repositories']['selected']['root'] = str(tmp_path)
    sidecar.write_text(json.dumps(inputs), 'utf-8')
    with pytest.raises(ValueError):
        module.load_inputs(config, path)
    inputs['repositories']['selected']['root'] = selected
    sidecar.write_text(json.dumps(inputs), 'utf-8')
    source = Path(selected) / '.git/HEAD'
    os.link(source, tmp_path / 'foreign-alias')
    with pytest.raises(ValueError):
        module.load_inputs(config, path)


def fake_capture(module, monkeypatch, *, default='accepted', selected_error=False):
    calls = []
    def invoke(command, environment, output, label, **bounds):
        calls.append((tuple(command), dict(environment), label))
        if label == 'git-version':
            stdout, stderr, code = b'git version 2.51.2.windows.1\n', b'', 0
        else:
            root = Path(command[command.index('-C') + 1])
            accepted = label == 'trusted-selected' or (label == 'default-env' and default == 'accepted')
            stdout = (str(root) + '\n' + 'a' * 40 + '\n').encode() if accepted else b''
            stderr = b'' if accepted else ("fatal: detected dubious ownership in repository at '" + str(root) + "'\n").encode()
            code = 0 if accepted else 128
            if selected_error and label == 'trusted-selected':
                stdout, stderr, code = b'', b'Access denied', 128
        result = {'argv': list(command), 'exit_code': code, 'timed_out': False,
                  'output_limit_exceeded': False, 'process_error': None, 'child_reaped': True}
        for stream, raw in (('stdout', stdout), ('stderr', stderr)):
            path = output / (label + '-' + stream + '.raw')
            path.write_bytes(raw)
            result[stream] = {'path': str(path), 'size_bytes': len(raw),
                             'sha256': hashlib.sha256(raw).hexdigest()}
        return result
    monkeypatch.setattr(module, 'capture', invoke)
    monkeypatch.setattr(module, 'current_identity', lambda: 'S-1-5-19', raising=False)
    return calls


@pytest.mark.parametrize('default', ['accepted', 'foreign_owner_refused'])
def test_worker_keeps_default_and_isolated_cases_separate_and_waits_for_stop(tmp_path, monkeypatch, default):
    module, config, path, _, _, output = prepared_inputs(tmp_path, monkeypatch)
    calls = fake_capture(module, monkeypatch, default=default)
    worker = module.ProbeWorker(config, path)
    worker.tick()
    result = json.loads((output / 'result.json').read_text('utf-8'))
    assert result['ownership_pattern_verified']
    assert result['cases']['default-env']['classification'] == default
    assert {name: item['classification'] for name, item in result['cases'].items() if name != 'default-env'} == {
        'isolated-default': 'foreign_owner_refused', 'trusted-selected': 'accepted',
        'isolated-other': 'foreign_owner_refused', 'isolated-after': 'foreign_owner_refused'}
    assert 'GIT_CONFIG_NOSYSTEM' not in calls[1][1]
    assert all(env['GIT_CONFIG_NOSYSTEM'] == '1' for _, env, _ in calls[2:])
    assert all(not result[name] for name in ('diagnostic_accepted', 'native_git_scm_accepted',
        'continuous_git_accepted', 'production_trust_policy_selected', 'full_product_ready', 'production_deployment'))
    assert not (output / 'closed.json').exists()
    worker.tick()
    assert len(calls) == 6
    worker.close()
    worker.close()
    assert json.loads((output / 'closed.json').read_text('utf-8'))['closed']


def test_worker_preserves_failed_measurement_and_never_relabels_generic_error(tmp_path, monkeypatch):
    module, config, path, _, _, output = prepared_inputs(tmp_path, monkeypatch)
    fake_capture(module, monkeypatch, selected_error=True)
    worker = module.ProbeWorker(config, path)
    with pytest.raises(RuntimeError):
        worker.tick()
    result = json.loads((output / 'result.json').read_text('utf-8'))
    assert result['cases']['trusted-selected']['classification'] == 'command_failed'
    assert not result['ownership_pattern_verified'] and not result['diagnostic_accepted']
    assert result['failure']
    worker.close()


def test_worker_rejects_non_localservice_sid_before_any_git_child(tmp_path, monkeypatch):
    module, config, path, _, _, output = prepared_inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(module, 'current_identity', lambda: 'S-1-5-21-123', raising=False)
    monkeypatch.setattr(module, 'capture', lambda *a, **k: pytest.fail('Git must not run with wrong token'))
    worker = module.ProbeWorker(config, path)
    with pytest.raises(RuntimeError):
        worker.tick()
    result = json.loads((output / 'result.json').read_text('utf-8'))
    assert result['process']['token_user_sid'] == 'S-1-5-21-123' and not result['cases']
    assert not result['diagnostic_accepted']


def test_main_dispatches_only_fixed_service_entry_and_never_allows_console(tmp_path, monkeypatch):
    import rentgen_core.service_entry as entry
    module, _, path, _, _, _ = prepared_inputs(tmp_path, monkeypatch)
    calls = []
    class FakeService:
        def __init__(self, config_path, *, worker_factory):
            calls.append((config_path, worker_factory))
        def run(self):
            return SimpleNamespace(exit_code=0)
    monkeypatch.setattr(entry, 'NativeService', FakeService)
    assert module.main(['--service', '--config', str(path)]) == 0
    assert len(calls) == 1 and calls[0][0] == path and callable(calls[0][1])
    assert module.main(['--console', '--config', str(path)]) == 2
    assert module.main(['--service', '--config', str(tmp_path / 'foreign.json')]) == 2
    assert len(calls) == 1
