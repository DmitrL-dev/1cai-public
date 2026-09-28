"""Service opt-in and real Git plumbing; injected BSL, no native SCM acceptance."""
import json
from dataclasses import replace
from pathlib import Path
import subprocess

import pytest

from rentgen_core import service_entry
from rentgen_core.errors import CoreError
from rentgen_core.git_watcher import NotificationOutbox
from test_git_repository_trust import inventory
from test_git_watcher import git
import test_service_composition as fixtures

configured, scanner = fixtures.configured, fixtures.scanner
project, workspace = fixtures.project, fixtures.workspace
pytestmark = fixtures.pytestmark


def config_updates(schema, scanner):
    return {'schema': schema, **({'scanner': str(scanner)} if schema == 3 else {})}


@pytest.mark.parametrize('schema', [2, 3])
def test_service_permission_defaults_to_false(configured, scanner, schema):
    configured.write(**config_updates(schema, scanner))
    assert service_entry.load_config(configured.path).trust_registered_source is False


@pytest.mark.parametrize('schema', [2, 3])
@pytest.mark.parametrize('selected', [False, True])
def test_service_accepts_only_explicit_boolean_permission(configured, scanner, schema, selected):
    configured.write(**config_updates(schema, scanner), trust_registered_source=selected)
    config = service_entry.load_config(configured.path)
    assert config.trust_registered_source is selected and config.mode == 'dry-run'
    result = service_entry.run_console(configured.path,
        worker_factory=lambda _: pytest.fail('dry-run permission created a worker'))
    assert result.exit_code == result.cycles == 0


@pytest.mark.parametrize('schema', [2, 3])
@pytest.mark.parametrize('value', [0, 1, None, 'true', [], {}, 1.0])
def test_service_permission_rejects_non_boolean(configured, scanner, schema, value):
    configured.write(**config_updates(schema, scanner), trust_registered_source=value)
    with pytest.raises(CoreError) as error:
        service_entry.load_config(configured.path)
    assert error.value.code == 'SERVICE_CONFIG_INVALID'


@pytest.mark.parametrize('selected', [False, True])
def test_schema_one_rejects_git_permission(configured, scanner, selected):
    document = {key: value for key, value in configured.document.items() if key != 'diagnostics_root'}
    document.update(schema=1, scanner=str(scanner))
    configured.path.write_text(json.dumps(document), 'utf-8')
    assert isinstance(service_entry.load_config(configured.path), service_entry.ServiceConfig)
    document['trust_registered_source'] = selected
    configured.path.write_text(json.dumps(document), 'utf-8')
    with pytest.raises(CoreError) as error:
        service_entry.load_config(configured.path)
    assert error.value.code == 'SERVICE_CONFIG_INVALID'


@pytest.mark.parametrize('schema', [2, 3])
def test_service_cannot_supply_trust_root_or_wildcard(configured, scanner, schema):
    configured.write(**config_updates(schema, scanner), trust_registered_source=True, trusted_root='*')
    with pytest.raises(CoreError) as error:
        service_entry.load_config(configured.path)
    assert error.value.code == 'SERVICE_CONFIG_INVALID'


def wire(configured, workspace, monkeypatch, scanner, schema, selected=True):
    configured.document['trust_registered_source'] = selected
    if schema == 3:
        return fixtures.autonomous(configured, workspace, monkeypatch, scanner)
    return fixtures.wire(configured, workspace, monkeypatch)


@pytest.mark.parametrize('schema', [2, 3])
def test_one_authorized_permission_reaches_every_real_child_and_durable_report(
    configured, workspace, monkeypatch, scanner, schema
):
    observer, source, module, _, adapter = wire(configured, workspace, monkeypatch, scanner, schema)
    config = replace(service_entry.load_config(configured.path), max_cycles=2)
    worker = service_entry.create_worker(config)
    seen, active, run = [], [True], subprocess.run
    def capture(command, **kwargs):
        if active[0] and Path(command[0]).name.casefold() in ('git', 'git.exe'):
            seen.append((command, kwargs['env']))
        return run(command, **kwargs)
    monkeypatch.setattr(subprocess, 'run', capture)
    try:
        reporting = worker.watcher
        watcher = reporting.watcher
        options = [component._git_options for component in
            (reporting, watcher, watcher.analyzer, watcher.observer)]
        trust = options[0]['trust']
        assert all(option['trust'] is trust for option in options)
        assert trust.repository == source.resolve()
        original = [inventory(source)]
        class NextCommit:
            def is_set(self):
                return False

            def wait(self, interval):
                assert inventory(source) == original[0]
                active[0] = False
                module.write_bytes(module.read_bytes().replace(b'1', b'2'))
                git(source, 'add', '.')
                git(source, 'commit', '-m', 'authorized next commit')
                if schema == 2:
                    # The real worker already owns this profile's lifetime lease.
                    observer._tick()
                original[0] = inventory(source)
                active[0] = True

        assert worker.run(NextCommit()) == 2
        assert inventory(source) == original[0]
        notices = NotificationOutbox(observer.profile / 'git-outbox.json').peek()
        assert len(notices) == 2
        first, second = [notice['event'] for notice in notices]
        assert first['commit'] != second['commit'] and first['owner_report_id'] != second['owner_report_id']
        assert observer.findings_status()['state']['report']['observation']['commit'] == second['commit']
        assert len(adapter.calls) == 2
        assert seen and any('merge-base' in command for command, _ in seen)
        assert any('ls-tree' in command for command, _ in seen) and any('cat-file' in command for command, _ in seen)
        assert all(command[4:8] == ['-c', 'safe.directory=', '-c', 'safe.directory=' + str(source.resolve())]
            and command[9] == str(source.resolve()) and env['GIT_NO_REPLACE_OBJECTS'] == '1'
            for command, env in seen)
    finally:
        worker.close()


@pytest.mark.parametrize('schema', [2, 3])
@pytest.mark.parametrize('selected', [False, True])
def test_revocation_precedes_every_service_git_read(configured, workspace, monkeypatch, scanner, schema, selected):
    from project_access_test_support import grant_membership
    observer, _, _, _, adapter = wire(configured, workspace, monkeypatch, scanner, schema, selected)
    ctx = observer._context(write=True)
    worker = service_entry.create_worker(service_entry.load_config(configured.path))
    try:
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            grant_membership(tx, ctx.principal, {'project:read', 'project:admin'})
        monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: pytest.fail('revoked service launched a child'))
        with pytest.raises(CoreError) as error:
            worker.watcher.tick()
        assert error.value.code == 'PROJECT_FORBIDDEN' and adapter.calls == []
        # Restore query authorization after proving refusal, without invoking Git.
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            grant_membership(tx, ctx.principal, {'project:read', 'project:admin', 'analysis:run'})
        assert observer.findings_status()['state'] is None
    finally:
        worker.close()
