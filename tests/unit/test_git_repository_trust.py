"""Explicit Git root permissions; real current-user Git, no LocalService claim."""
from dataclasses import FrozenInstanceError
import hashlib
import importlib
from pathlib import Path
import subprocess

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.git_observer import GitObservation, observe_git, require_ancestor
from rentgen_diagnostics.git_bsl_analyzer import BslGitAnalyzer
from test_git_bsl_analyzer import FakeAdapter, git, repository


def api():
    return importlib.import_module('rentgen_core._git_policy')


def test_permission_is_frozen_and_keeps_one_canonical_root(tmp_path):
    trust = api().GitRepositoryTrust(tmp_path.resolve())
    assert trust.repository == tmp_path.resolve()
    with pytest.raises(FrozenInstanceError):
        trust.repository = tmp_path.parent


@pytest.mark.parametrize('bad', ['relative', 'missing', 'parent_alias', 'wildcard', 'question',
    'control', 'interpolation', 'file', 'not_path'])
def test_invalid_permission_root_is_refused(tmp_path, bad):
    path = {'relative': Path('relative'), 'missing': tmp_path / 'missing',
        'parent_alias': tmp_path / '..' / tmp_path.name, 'wildcard': tmp_path / '*',
        'question': tmp_path / '?', 'control': tmp_path / 'bad\npath',
        'interpolation': tmp_path / '%(prefix)', 'file': tmp_path / 'file.txt',
        'not_path': str(tmp_path)}[bad]
    (tmp_path / 'file.txt').touch()
    with pytest.raises(CoreError) as error:
        api().GitRepositoryTrust(path)
    assert error.value.code == 'GIT_TRUST_CONTEXT'


def test_environment_removes_all_git_overrides_independent_of_case():
    original = {'PATH': 'unchanged', 'Ordinary': 'keep', 'GIT_DIR': 'foreign',
        'git_config_count': '1', 'Git_Config_Key_0': 'safe.directory',
        'gIt_CONFIG_VALUE_0': '*', 'git_test_assume_different_owner': '1',
        'GIT_NO_REPLACE_OBJECTS': '0', 'GIT_OPTIONAL_LOCKS': '1'}
    before = dict(original)
    env = api().git_environment(original)
    assert original == before
    assert env == {'PATH': 'unchanged', 'Ordinary': 'keep', 'GIT_OPTIONAL_LOCKS': '0',
        'GIT_TERMINAL_PROMPT': '0', 'GIT_NO_LAZY_FETCH': '1', 'GIT_NO_REPLACE_OBJECTS': '1'}


def test_default_command_adds_no_repository_exception(tmp_path):
    root = tmp_path.resolve()
    assert api().git_command(root, 'rev-parse', 'HEAD') == [
        'git', '--no-pager', '-c', 'core.fsmonitor=false', '-C', str(root), 'rev-parse', 'HEAD']


def test_explicit_command_resets_inherited_list_then_names_exact_root(tmp_path):
    root = tmp_path.resolve()
    trust = api().GitRepositoryTrust(root)
    assert api().git_command(root, 'rev-parse', 'HEAD', trust=trust) == [
        'git', '--no-pager', '-c', 'core.fsmonitor=false', '-c', 'safe.directory=',
        '-c', 'safe.directory=' + str(root), '-C', str(root), 'rev-parse', 'HEAD']


@pytest.mark.parametrize('operation', ['observe', 'ancestor', 'analyzer'])
@pytest.mark.parametrize('target', ['parent', 'nested', 'other'])
def test_wrong_root_refused_before_any_child(tmp_path, monkeypatch, operation, target):
    root = tmp_path / 'selected'
    root.mkdir()
    other, nested = tmp_path / 'other', root / 'nested'
    other.mkdir()
    nested.mkdir()
    trust = api().GitRepositoryTrust(root.resolve())
    destination = {'parent': tmp_path, 'nested': nested, 'other': other}[target]
    monkeypatch.setattr(subprocess, 'Popen', lambda *args, **kwargs: pytest.fail('foreign root launched Git'))
    with pytest.raises(CoreError) as error:
        if operation == 'observe': observe_git(destination, trust=trust)
        elif operation == 'ancestor': require_ancestor(destination, 'a' * 40, 'b' * 40, trust=trust)
        else:
            BslGitAnalyzer(FakeAdapter(), lambda: None, git_trust=trust)(
                GitObservation(str(destination.resolve()), 'a' * 40, 'refs/heads/main'))
    assert error.value.code == 'GIT_TRUST_CONTEXT'


def inventory(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob('*') if path.is_file()}


def test_real_observation_and_ancestry_do_not_persist_exception(repository, monkeypatch):
    trust = api().GitRepositoryTrust(repository.resolve())
    original = inventory(repository)
    calls, run = [], subprocess.Popen
    def capture(command, **kwargs):
        calls.append((command, kwargs['env']))
        return run(command, **kwargs)
    monkeypatch.setattr(subprocess, 'Popen', capture)
    observation = observe_git(repository, trust=trust)
    require_ancestor(repository, observation.commit, observation.commit, trust=trust)
    assert observation.repository == str(repository.resolve()) and len(calls) == 7
    assert all(command[4:8] == ['-c', 'safe.directory=', '-c', 'safe.directory=' + str(repository)]
        and env['GIT_NO_REPLACE_OBJECTS'] == '1' for command, env in calls)
    assert inventory(repository) == original
    monkeypatch.setattr(subprocess, 'Popen', run)
    assert observe_git(repository) == observation


def test_real_analyzer_propagates_permission_to_probe_tree_and_blob(repository, monkeypatch):
    trust = api().GitRepositoryTrust(repository.resolve())
    observed = observe_git(repository, trust=trust)
    expected_blob = subprocess.check_output(['git', '-C', str(repository), 'cat-file',
        'blob', observed.commit + ':Module.bsl'])
    original = inventory(repository)
    calls, run = [], subprocess.Popen
    def capture(command, **kwargs):
        calls.append(command)
        return run(command, **kwargs)
    monkeypatch.setattr(subprocess, 'Popen', capture)
    adapter = FakeAdapter()
    result = BslGitAnalyzer(adapter, lambda: None, git_trust=trust)(observed)
    assert result.complete and adapter.calls[0][0] == expected_blob
    assert {'ls-tree', 'cat-file'} <= {command[10] for command in calls}
    assert all(command[4:8] == ['-c', 'safe.directory=', '-c', 'safe.directory=' + str(repository)] for command in calls)
    assert inventory(repository) == original


@pytest.mark.parametrize('explicit', [False, True])
def test_replacement_refs_cannot_change_analyzed_blob_under_original_commit(repository, explicit):
    original_commit = git(repository, 'rev-parse', 'HEAD')
    original_blob = subprocess.check_output(['git', '-C', str(repository), 'cat-file',
        'blob', original_commit + ':Module.bsl'])
    original_bytes = (repository / 'Module.bsl').read_bytes()
    (repository / 'Module.bsl').write_bytes(original_bytes + b'// replacement tree\n')
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'replacement')
    replacement = git(repository, 'rev-parse', 'HEAD')
    git(repository, 'reset', '--hard', original_commit)
    git(repository, 'replace', original_commit, replacement)
    trust = api().GitRepositoryTrust(repository.resolve()) if explicit else None
    observation = observe_git(repository, trust=trust)
    assert observation.commit == original_commit
    adapter = FakeAdapter()
    report = BslGitAnalyzer(adapter, lambda: None, git_trust=trust)(observation)
    assert report.complete and adapter.calls[0][0] == original_blob
    assert git(repository, 'replace', '-l') == original_commit
