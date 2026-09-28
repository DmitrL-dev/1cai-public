"""Diagnostic contracts; these never accept a LocalService or stock Git worker."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

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
