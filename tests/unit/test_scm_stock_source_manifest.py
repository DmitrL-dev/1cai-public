"""Exact owned source manifest contracts; real Git, no SCM/BSL acceptance."""
import copy
import importlib.util
from pathlib import Path
import shutil
import sys

import pytest

from test_git_bsl_analyzer import git


def worker():
    path = Path(__file__).resolve().parents[2] / 'scripts/verification/scm_acceptance_worker.py'
    spec = importlib.util.spec_from_file_location('stock_source_worker_contract', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = {
    '.': {'directory': True},
    'CommonModules': {'directory': True},
    'CommonModules\\ServiceProbe': {'directory': True},
    'CommonModules\\ServiceProbe\\Ext': {'directory': True},
    'CommonModules\\ServiceProbe\\Ext\\Module.bsl': {'directory': False, 'bytes': 10, 'sha256': 'a' * 64},
}
GIT = BASE | {'.git': {'directory': True},
    '.git\\HEAD': {'directory': False, 'bytes': 3, 'sha256': 'b' * 64},
    '.git\\config': {'directory': False, 'bytes': 3, 'sha256': 'c' * 64},
    '.git\\index': {'directory': False, 'bytes': 3, 'sha256': 'd' * 64}}


def validate(observed, expected=None, digest='a' * 64):
    return worker().validate_source_inventory(observed, digest, 'a' * 64, expected=expected)


def test_original_five_entry_fixture_keeps_default_contract():
    validate(copy.deepcopy(BASE))


def test_default_refuses_git_extension_without_explicit_manifest():
    with pytest.raises(RuntimeError):
        validate(copy.deepcopy(GIT))


def test_exact_git_manifest_is_inert_and_preserves_input():
    original = copy.deepcopy(GIT)
    validate(copy.deepcopy(GIT), expected=GIT)
    assert GIT == original


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'bytes', 'sha', 'directory'])
def test_changed_inventory_cannot_pass_exact_manifest(mutation):
    observed = copy.deepcopy(GIT)
    if mutation == 'missing':
        del observed['.git\\index']
    elif mutation == 'extra':
        observed['.git\\extra'] = {'directory': True}
    elif mutation == 'bytes':
        observed['.git\\index']['bytes'] = 4
    elif mutation == 'sha':
        observed['.git\\index']['sha256'] = 'e' * 64
    else:
        observed['.git\\index'] = {'directory': True}
    with pytest.raises(RuntimeError):
        validate(observed, expected=GIT)


@pytest.mark.parametrize('field,value', [('directory', 0), ('bytes', True), ('bytes', -1),
    ('bytes', 1.0), ('sha256', 'A' * 64), ('sha256', 'short'), ('unknown', 'extra')])
def test_bad_manifest_row_refused_even_when_observed_matches(field, value):
    expected = copy.deepcopy(GIT)
    expected['.git\\index'][field] = value
    with pytest.raises(RuntimeError):
        validate(copy.deepcopy(expected), expected=expected)


@pytest.mark.parametrize('name', ['..\\escape', 'C:\\foreign', '.git\\..\\evil',
    '.git\\HEAD:stream', '.git/HEAD', 'CommonModules\\AnotherModule'])
def test_manifest_cannot_expand_outside_git_metadata_or_use_alias_spelling(name):
    expected = copy.deepcopy(GIT)
    expected[name] = {'directory': True}
    with pytest.raises(RuntimeError):
        validate(copy.deepcopy(expected), expected=expected)


@pytest.mark.parametrize('name', ['.git', '.git\\HEAD', '.git\\config', '.git\\index'])
def test_stock_manifest_requires_git_root_head_config_and_index(name):
    expected = copy.deepcopy(GIT)
    del expected[name]
    with pytest.raises(RuntimeError):
        validate(copy.deepcopy(expected), expected=expected)


def test_module_digest_remains_bound_to_original_fixture():
    with pytest.raises(RuntimeError):
        validate(copy.deepcopy(GIT), expected=GIT, digest='f' * 64)


@pytest.mark.skipif(sys.platform != 'win32' or shutil.which('git') is None,
    reason='Windows file attributes and Git required')
def test_real_initialized_registered_root_manifest_and_metadata_hash_refusal(tmp_path, monkeypatch):
    module = worker()
    source = tmp_path / 'source'
    path = source / 'CommonModules/ServiceProbe/Ext/Module.bsl'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'// existing fixture\r\n')
    git(source, 'init', '-q', '--template=', '--initial-branch=main')
    git(source, 'config', 'core.autocrlf', 'false')
    git(source, 'add', '.')
    git(source, 'commit', '-q', '-m', 'owned stock source fixture')
    monkeypatch.setattr(module, 'ROOT', source)
    observed = module.inventory(source)
    original = copy.deepcopy(observed)
    digest = module.sha(path)
    module.validate_source_inventory(observed, digest, digest, expected=original)
    assert module.inventory(source) == original
    (source / '.git/HEAD').write_bytes(b'ref: refs/heads/other\n')
    with pytest.raises(RuntimeError):
        module.validate_source_inventory(module.inventory(source), digest, digest, expected=original)
