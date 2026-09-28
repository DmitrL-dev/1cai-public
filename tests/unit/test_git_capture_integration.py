"""Command error mappings and actual committed Git listing/blob overflow."""
import subprocess

import pytest

from rentgen_core import git_observer
from rentgen_core._git_capture import GitOutputLimitExceeded
from rentgen_core.errors import CoreError
from rentgen_diagnostics import git_bsl_analyzer
from test_git_bsl_analyzer import FakeAdapter, git, repository
from test_git_repository_trust import inventory


@pytest.mark.parametrize('operation', ['probe', 'ancestor', 'analyzer'])
@pytest.mark.parametrize('failure', ['limit', 'timeout', 'os'])
def test_capture_failure_keeps_command_specific_core_code(repository, monkeypatch, operation, failure):
    def unavailable(command, **kwargs):
        if failure == 'limit':
            raise GitOutputLimitExceeded(kwargs['max_stdout'], b'x')
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(command, kwargs['timeout'], output=b'')
        raise OSError('injected spawn failure')

    module = git_bsl_analyzer if operation == 'analyzer' else git_observer
    monkeypatch.setattr(module, 'capture_git', unavailable)
    with pytest.raises(CoreError) as error:
        if operation == 'probe':
            git_observer.observe_git(repository)
        elif operation == 'ancestor':
            git_observer.require_ancestor(repository, 'a' * 40, 'b' * 40)
        else:
            git_bsl_analyzer.BslGitAnalyzer._run(repository, 'rev-parse', 'HEAD')
    expected = {'probe': 'GIT_PROBE_FAILED', 'ancestor': 'GIT_ANCESTRY_FAILED',
        'analyzer': 'GIT_ANALYZER_LIMIT' if failure == 'limit' else 'GIT_ANALYZER_FAILED'}
    assert error.value.code == expected[operation]


def test_actual_oversized_committed_blob_refuses_before_bsl_and_preserves_repo(repository):
    (repository / 'Module.bsl').write_bytes(b'/' * (git_bsl_analyzer.MAX_FILE + 1))
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'oversized committed module')
    observation = git_observer.observe_git(repository)
    original = inventory(repository)
    adapter = FakeAdapter()
    with pytest.raises(CoreError) as error:
        git_bsl_analyzer.BslGitAnalyzer(adapter, lambda: None)(observation)
    assert error.value.code == 'GIT_ANALYZER_LIMIT' and adapter.calls == []
    assert inventory(repository) == original


def test_actual_tree_listing_uses_its_stream_bound_before_bsl(repository, monkeypatch):
    observation = git_observer.observe_git(repository)
    original = inventory(repository)
    adapter = FakeAdapter()
    # Reduce the fixed production bound for a small real-tree overflow fixture.
    monkeypatch.setattr(git_bsl_analyzer, 'MAX_TREE', 4)
    with pytest.raises(CoreError) as error:
        git_bsl_analyzer.BslGitAnalyzer(adapter, lambda: None)(observation)
    assert error.value.code == 'GIT_ANALYZER_LIMIT' and adapter.calls == []
    assert inventory(repository) == original
