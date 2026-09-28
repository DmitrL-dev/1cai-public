"""Owned diagnostic SCM controls; injected observations are not native acceptance."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.unit.test_scm_git_probe import prepared_inputs, fake_capture


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/verification/scm_git_diagnostic_control.py'


def control_api():
    assert SCRIPT.is_file(), 'Fixed diagnostic SCM adapter is missing'
    spec = importlib.util.spec_from_file_location('scm_git_diagnostic_control_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(spec, state=1):
    return {'name': spec.service_name, 'exists': True,
        'config': {'binary_path': spec.binary_path, 'account': r'NT AUTHORITY\LocalService',
                   'service_type': 16, 'start_type': 3, 'display_name': spec.display_name},
        'status': {'state': state}}


def prepared_control(tmp_path, monkeypatch, **authority_changes):
    module = control_api()
    probe, _, config, sidecar, inputs, _ = prepared_inputs(tmp_path, monkeypatch)
    work = Path(inputs['workdir'])
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    system = tmp_path / 'system/System32'
    system.mkdir(parents=True)
    (system / 'sc.exe').write_bytes(b'owned unit SCM executable metadata; never executed')
    monkeypatch.setenv('SystemRoot', str(system.parent))
    output = work / 'evidence/lifecycle'
    output.mkdir(parents=True)
    authority = {'elevated': True, 'create_access': True, 'backup_privilege': True,
                 'restore_privilege': True, **authority_changes}
    native = Mock()
    native.query.return_value = {'exists': False}
    paths = (work / 'runtime/python.exe', config,
             work / 'runtime/Lib/site-packages/scm_git_probe_service.py', sidecar)
    expected = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    installer = module.DiagnosticInstaller(probe, native, work, authority, output, expected)
    commands = []
    def capture(command, environment, folder, label, **bounds):
        commands.append(tuple(command))
        verb = command[1]
        if verb == 'create':
            native.query.return_value = row(installer.spec)
        elif verb == 'start':
            native.query.return_value = row(installer.spec, 4)
        elif verb == 'stop':
            native.query.return_value = row(installer.spec, 1)
        elif verb == 'delete':
            native.query.return_value = {'exists': False}
        result = {'argv': list(command), 'exit_code': 0, 'timed_out': False,
                  'output_limit_exceeded': False, 'process_error': None, 'child_reaped': True}
        for stream in ('stdout', 'stderr'):
            path = folder / (label + '-' + stream + '.raw')
            path.write_bytes(b'')
            result[stream] = {'path': str(path), 'size_bytes': 0, 'sha256': hashlib.sha256(b'').hexdigest()}
        return result
    monkeypatch.setattr(probe, 'capture', capture)
    return module, installer, native, probe, commands, expected


def test_adapter_creates_only_fixed_owned_localservice_image_then_controls_it(tmp_path, monkeypatch):
    _, installer, native, _, commands, _ = prepared_control(tmp_path, monkeypatch)
    installer.install(installer.spec)
    assert installer.created
    expected = (str(tmp_path / 'system/System32/sc.exe'), 'create', 'Rentgen.CI.' + 'a' * 12,
        'binPath=', installer.spec.binary_path, 'DisplayName=', installer.spec.display_name,
        'start=', 'demand', 'type=', 'own', 'obj=', r'NT AUTHORITY\LocalService')
    assert commands == [expected]
    assert '-I -m scm_git_probe_service --service --config' in installer.spec.binary_path
    installer.start(installer.spec)
    installer.stop(installer.spec)
    installer.uninstall(installer.spec)
    assert [command[1] for command in commands] == ['create', 'start', 'stop', 'delete']
    assert native.query.return_value == {'exists': False}


@pytest.mark.parametrize('missing', ['elevated', 'create_access', 'backup_privilege', 'restore_privilege'])
def test_adapter_refuses_without_authority_before_any_scm_query_or_child(tmp_path, monkeypatch, missing):
    _, installer, native, _, commands, _ = prepared_control(tmp_path, monkeypatch, **{missing: False})
    with pytest.raises(RuntimeError):
        installer.install(installer.spec)
    assert not commands and not installer.created
    native.query.assert_not_called()


def test_unknown_existing_service_is_never_created_or_controlled(tmp_path, monkeypatch):
    _, installer, native, _, commands, _ = prepared_control(tmp_path, monkeypatch)
    native.query.return_value = {'exists': True, 'name': installer.spec.service_name}
    with pytest.raises(RuntimeError):
        installer.install(installer.spec)
    with pytest.raises(RuntimeError):
        installer.uninstall(installer.spec)
    assert not commands and not installer.created


@pytest.mark.parametrize('changed', ['binary_path', 'account', 'service_type', 'start_type', 'display_name'])
def test_changed_service_binding_is_not_controlled_even_after_known_create(tmp_path, monkeypatch, changed):
    _, installer, native, _, commands, _ = prepared_control(tmp_path, monkeypatch)
    installer.install(installer.spec)
    value = row(installer.spec)
    value['config'][changed] = 'foreign value'
    native.query.return_value = value
    with pytest.raises(RuntimeError):
        installer.start(installer.spec)
    with pytest.raises(RuntimeError):
        installer.uninstall(installer.spec)
    assert len(commands) == 1


@pytest.mark.parametrize('index', [0, 1, 2, 3])
def test_changed_python_config_module_or_manifest_refuses_before_create(tmp_path, monkeypatch, index):
    _, installer, _, _, commands, expected = prepared_control(tmp_path, monkeypatch)
    list(expected)[index].write_bytes(b'changed input')
    with pytest.raises(ValueError):
        installer.install(installer.spec)
    assert not commands and not installer.created


def test_timeout_never_acknowledges_creation_or_authorizes_delete(tmp_path, monkeypatch):
    _, installer, native, probe, commands, _ = prepared_control(tmp_path, monkeypatch)
    original = probe.capture
    def timeout(*args, **kwargs):
        return original(*args, **kwargs) | {'timed_out': True}
    monkeypatch.setattr(probe, 'capture', timeout)
    with pytest.raises(RuntimeError):
        installer.install(installer.spec)
    assert native.query.return_value['exists'] and not installer.created
    with pytest.raises(RuntimeError):
        installer.uninstall(installer.spec)
    assert len(commands) == 1


def test_adapter_rejects_external_spec_and_start_during_install(tmp_path, monkeypatch):
    _, installer, _, _, commands, _ = prepared_control(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        installer.install(Mock())
    with pytest.raises(ValueError):
        installer.install(installer.spec, start=True)
    assert not commands


def test_public_core_installer_still_rejects_diagnostic_module(tmp_path, monkeypatch):
    from rentgen_core.errors import CoreError
    from rentgen_core.service_installer import ServiceInstallSpec
    _, installer, _, _, _, _ = prepared_control(tmp_path, monkeypatch)
    with pytest.raises(CoreError):
        ServiceInstallSpec(service_name=installer.spec.service_name, display_name=installer.spec.display_name,
            executable=str(Path(installer.workdir) / 'runtime/python.exe'),
            arguments=('-I', '-m', 'scm_git_probe_service', '--service', '--config',
                       str(Path(installer.workdir) / 'fixture/localservice/service.json')))


def coordinator_api():
    path = SCRIPT.with_name('verify_git_scm_diagnostic.py')
    assert path.is_file(), 'Owned diagnostic coordinator is missing'
    spec = importlib.util.spec_from_file_location('git_scm_coordinator_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def preparation_fixture(tmp_path, monkeypatch):
    from rentgen_core.service_entry import load_config
    from uuid import uuid4
    coordinator = coordinator_api()
    work = tmp_path / ('rg-scm-' + 'b' * 12)
    root, runtime, evidence = work / 'fixture', work / 'runtime', work / 'evidence'
    data = root / 'localservice/data'
    (data / 'observer-profile').mkdir(parents=True)
    source = root / 'localservice/source'
    bsl = source / 'CommonModules/ServiceProbe/Ext/Module.bsl'
    bsl.parent.mkdir(parents=True)
    bsl.write_bytes(b'// owned source fixture input\r\n')
    (runtime / 'Lib/site-packages').mkdir(parents=True)
    python = runtime / 'python.exe'
    python.write_bytes(b'unit interpreter metadata; never executed')
    scanner = root / 'bsl-scan.exe'
    scanner.write_bytes(b'unit unused scanner metadata')
    registry = data / 'registry.sqlite3'
    registry.write_bytes(b'unit unused database metadata')
    evidence.mkdir()
    config = root / 'localservice/service.json'
    config.write_text(json.dumps({'schema': 1, 'service_name': 'Rentgen.CI.' + 'b' * 12,
        'registry': str(registry), 'profile': str(data / 'observer-profile'), 'project': str(uuid4()),
        'scanner': str(scanner), 'interval_seconds': 5, 'max_cycles': None}), 'utf-8')
    cfg = load_config(config)
    f = {'service_name': cfg.service_name, 'root': str(root), 'interpreter': str(python),
         'interpreter_sha256': hashlib.sha256(python.read_bytes()).hexdigest(), 'config': str(config),
         'config_sha256': hashlib.sha256(config.read_bytes()).hexdigest(), 'project_id': cfg.project,
         'service_data': str(data), 'service_source': str(source)}
    (evidence / 'fixture.json').write_text(json.dumps(f), 'utf-8')
    native = Mock()
    native.owner.return_value = 'S-1-5-32-544'
    native.query.return_value = {'exists': False}
    def require(condition, message):
        if not condition:
            raise RuntimeError(message)
    def save(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    worker = SimpleNamespace(B=evidence, ROOT=root, RUNTIME=runtime, PYTHON=python, NAME=cfg.service_name,
        SID='S-1-5-19', require=require, sha=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        read=lambda name: json.loads((evidence / name).read_text('utf-8')), save=save,
        load_native=lambda: native)
    monkeypatch.setattr(__import__('sys'), 'executable', str(python))
    prep = {'source_commit': 'a' * 40, 'kit_sha256': 'b' * 64}
    authority = {key: True for key in ('elevated', 'create_access', 'backup_privilege', 'restore_privilege')}
    context = (f, cfg, Mock(), native, Mock(), {'exists': False}, authority)
    return coordinator, worker, prep, context


def test_prepare_creates_real_current_user_git_fixtures_with_bound_hashes_only(tmp_path, monkeypatch):
    coordinator, worker, prep, context = preparation_fixture(tmp_path, monkeypatch)
    coordinator.prepare_diagnostic(worker, prep)
    extra, probe, _, inputs, expected = coordinator.auxiliary_context(worker, prep, context)
    assert extra['actual_localservice_exercised'] is False
    assert extra['source_commit'] == prep['source_commit']
    assert len(expected) == 4 and inputs['document']['module_sha256'] == worker.sha(
        worker.RUNTIME / 'Lib/site-packages/scm_git_probe_service.py')
    for name in ('selected', 'other'):
        item = inputs['document']['repositories'][name]
        assert len(item['commit']) == 40 and item['owner_sid'] != worker.SID
        assert item['files'] == probe.inventory_repository(inputs[name])
        config = (inputs[name] / '.git/config').read_text('utf-8')
        assert '[remote ' not in config and 'safe.directory' not in config
    context[3].query.assert_not_called()


@pytest.mark.parametrize('changed', ['installed_module', 'inputs', 'repository', 'owner', 'script_hash'])
def test_auxiliary_preflight_rejects_changed_diagnostic_inputs_before_controls(tmp_path, monkeypatch, changed):
    coordinator, worker, prep, context = preparation_fixture(tmp_path, monkeypatch)
    coordinator.prepare_diagnostic(worker, prep)
    if changed == 'installed_module':
        (worker.RUNTIME / 'Lib/site-packages/scm_git_probe_service.py').write_bytes(b'changed')
    elif changed == 'inputs':
        (worker.ROOT / 'git-probe/inputs.json').write_bytes(b'changed')
    elif changed == 'repository':
        (worker.ROOT / 'git-probe/source/selected/.git/HEAD').write_bytes(b'changed')
    elif changed == 'owner':
        context[3].owner.return_value = worker.SID
    else:
        extra = worker.read('git-preparation.json')
        extra['scripts']['scm_git_diagnostic_control.py'] = '0' * 64
        worker.save(worker.B / 'git-preparation.json', extra)
    with pytest.raises((ValueError, RuntimeError)):
        coordinator.auxiliary_context(worker, prep, context)
    context[3].query.assert_not_called()


def test_lifecycle_always_enters_cleanup_and_failure_cannot_be_accepted(tmp_path):
    coordinator = coordinator_api()
    test = Mock()
    test.exercise.side_effect = RuntimeError('owned probe failure')
    test.cleanup.return_value = []
    test.native.query.return_value = {'exists': False}
    test.output = tmp_path
    test.spec.service_name = 'Rentgen.CI.' + 'a' * 12
    worker = SimpleNamespace(BUDGET=Mock(), sha=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        save=lambda path, value: path.write_text(json.dumps(value), 'utf-8'))
    result = coordinator.run_lifecycle(test, worker, {'source_commit': 'a' * 40, 'kit_sha256': 'b' * 64})
    test.cleanup.assert_called_once()
    worker.BUDGET.begin_cleanup.assert_called_once()
    assert result['failure'] and not result['diagnostic_accepted']
    assert all(result[key] is False for key in ('native_git_scm_accepted', 'continuous_git_accepted',
        'production_trust_policy_selected', 'full_product_ready', 'production_deployment'))


def test_lifecycle_refuses_remaining_service_or_cleanup_errors(tmp_path):
    coordinator = coordinator_api()
    for remaining, cleanup in ((True, []), (False, [{'stage': 'acl'}])):
        output = tmp_path / ('remaining' if remaining else 'acl')
        output.mkdir()
        test = Mock()
        test.output = output
        test.spec.service_name = 'Rentgen.CI.' + 'a' * 12
        test.exercise.return_value = {'measurement_validated': True}
        test.cleanup.return_value = cleanup
        test.native.query.return_value = {'exists': remaining}
        worker = SimpleNamespace(BUDGET=Mock(), sha=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            save=lambda path, value: path.write_text(json.dumps(value), 'utf-8'))
        result = coordinator.run_lifecycle(test, worker, {'source_commit': 'a' * 40, 'kit_sha256': 'b' * 64})
        assert not result['diagnostic_accepted']


def test_lifecycle_missing_measurement_proof_still_cleans_and_refuses_acceptance(tmp_path):
    coordinator = coordinator_api()
    test = Mock()
    test.output = tmp_path
    test.spec.service_name = 'Rentgen.CI.' + 'a' * 12
    test.exercise.return_value = None
    test.cleanup.return_value = []
    test.native.query.return_value = {'exists': False}
    worker = SimpleNamespace(BUDGET=Mock(), sha=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        save=lambda path, value: path.write_text(json.dumps(value), 'utf-8'))
    result = coordinator.run_lifecycle(test, worker, {'source_commit': 'a' * 40, 'kit_sha256': 'b' * 64})
    assert not result['diagnostic_accepted'] and result['failure']
    test.cleanup.assert_called_once()


def measurement_fixture(tmp_path, monkeypatch):
    import os
    coordinator = coordinator_api()
    probe, cfg, path, _, _, output = prepared_inputs(tmp_path, monkeypatch)
    fake_capture(probe, monkeypatch)
    worker = probe.ProbeWorker(cfg, path)
    worker.tick()
    report = json.loads((output / 'result.json').read_text('utf-8'))
    process = {'pid': os.getpid(), 'image': str(Path(__import__('sys').executable)),
               'token_user_sid': 'S-1-5-19'}
    return coordinator, probe, worker.inputs, report, process


def test_coordinator_recomputes_all_raw_outcomes_and_binds_actual_process(tmp_path, monkeypatch):
    coordinator, probe, inputs, report, process = measurement_fixture(tmp_path, monkeypatch)
    outcomes = coordinator.validate_measurement(probe, inputs, report, process)
    assert outcomes == {name: case['classification'] for name, case in report['cases'].items()}
    assert report['diagnostic_accepted'] is False


@pytest.mark.parametrize('changed', ['pid', 'sid', 'image', 'raw_path', 'argv', 'classification', 'raw_bytes', 'git_hash', 'failure'])
def test_coordinator_refuses_unbound_process_or_raw_measurement(tmp_path, monkeypatch, changed):
    coordinator, probe, inputs, report, process = measurement_fixture(tmp_path, monkeypatch)
    if changed == 'pid':
        process['pid'] += 1
    elif changed == 'sid':
        process['token_user_sid'] = 'S-1-5-21-123'
    elif changed == 'image':
        process['image'] = str(tmp_path / 'foreign.exe')
    elif changed == 'raw_path':
        report['cases']['trusted-selected']['stdout']['path'] = str(tmp_path / 'foreign.raw')
    elif changed == 'argv':
        report['cases']['trusted-selected']['argv'] = ['git', '-c', 'safe.directory=*']
    elif changed == 'classification':
        report['cases']['isolated-other']['classification'] = 'accepted'
    elif changed == 'raw_bytes':
        Path(report['cases']['trusted-selected']['stdout']['path']).write_bytes(b'changed')
    elif changed == 'git_hash':
        report['git']['sha256'] = '0' * 64
    else:
        report['failure'] = {'type': 'UnsuccessfulMeasurement'}
    with pytest.raises((ValueError, RuntimeError)):
        coordinator.validate_measurement(probe, inputs, report, process)


def test_auxiliary_accepts_actual_preflight_json_config(tmp_path, monkeypatch):
    coordinator, worker, prep, context = preparation_fixture(tmp_path, monkeypatch)
    coordinator.prepare_diagnostic(worker, prep)
    actual = (context[0], json.loads(Path(context[0]['config']).read_text('utf-8')), *context[2:])
    assert coordinator.auxiliary_context(worker, prep, actual)[3]['document']['service_name'] == worker.NAME


def exercise_fixture(tmp_path, monkeypatch, *, ready=True, existing=False, changed=None):
    coordinator, probe, inputs, report, process = measurement_fixture(tmp_path, monkeypatch)
    config = inputs['workdir'] / 'fixture/localservice/service.json'
    events = []
    class Base:
        def __init__(self, context, output):
            self.f, self.cfg, self.spec, self.native, self.observer, _, self.authority = context
            self.output, self.created = output, False
        def event(self, kind, **details):
            events.append((kind, details))
        def prepare_acl(self):
            events.append(('acl', {}))
        def current(self):
            return {'status': {'state': 4, 'pid': process['pid']}}
        def start(self):
            events.append(('start', {}))
            return self.current()
        def stop(self):
            events.append(('stop', {}))
            probe._write_result(inputs['output'] / 'closed.json', {'closed': True,
                'pid': process['pid'] + (1 if changed == 'close_pid' else 0)})
            if changed == 'owner':
                self.native.owner.return_value = 'S-1-5-19'
            if changed == 'repository':
                (inputs['selected'] / '.git/HEAD').write_bytes(b'changed')
    def require(condition, message):
        if not condition:
            raise RuntimeError(message)
    def wait(check, seconds, description):
        value = check()
        require(value is not None, description)
        return value
    worker = SimpleNamespace(Acceptance=Base, require=require, wait_until=wait,
        sha=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest())
    worker.B = inputs['workdir'] / 'evidence'
    worker.B.mkdir()
    installer = Mock()
    installer.created = True
    installer.spec.service_name = report['service_name']
    control = SimpleNamespace(DiagnosticInstaller=Mock(return_value=installer))
    native = Mock()
    native.process.return_value = process
    native.owner.return_value = inputs['document']['repositories']['selected']['owner_sid']
    authority = {key: ready for key in ('elevated', 'create_access', 'backup_privilege', 'restore_privilege')}
    context = ({'config': str(config)}, {}, Mock(), native, Mock(), {'exists': existing}, authority)
    cls = coordinator.acceptance_type(worker, probe, control)
    return cls, context, inputs, control, events


@pytest.mark.parametrize('condition', ['authority', 'existing'])
def test_exercise_refuses_before_acl_or_controls_without_fresh_authority(tmp_path, monkeypatch, condition):
    cls, context, inputs, control, events = exercise_fixture(tmp_path, monkeypatch,
        ready=condition != 'authority', existing=condition == 'existing')
    with pytest.raises(RuntimeError):
        cls(context, tmp_path, inputs, {})
    assert not events
    control.DiagnosticInstaller.assert_not_called()


def test_exercise_proves_raw_measurement_stop_close_and_unchanged_sources(tmp_path, monkeypatch):
    cls, context, inputs, _, events = exercise_fixture(tmp_path, monkeypatch)
    test = cls(context, tmp_path, inputs, {})
    result = test.exercise()
    assert result['measurement_validated'] is True
    assert result['repository_bytes_and_owners_unchanged'] is True
    assert test.created is True
    assert [name for name, _ in events if name in ('acl', 'start', 'stop')] == ['acl', 'start', 'stop']
    assert result['outcomes']['isolated-other'] == 'foreign_owner_refused'


@pytest.mark.parametrize('changed', ['close_pid', 'owner', 'repository'])
def test_exercise_rejects_wrong_close_pid_or_modified_source_after_stop(tmp_path, monkeypatch, changed):
    cls, context, inputs, _, _ = exercise_fixture(tmp_path, monkeypatch, changed=changed)
    with pytest.raises((ValueError, RuntimeError)):
        cls(context, tmp_path, inputs, {}).exercise()


def test_host_cli_prepares_and_inspects_but_runs_scm_only_when_requested(tmp_path, monkeypatch):
    coordinator = coordinator_api()
    kit, receipt = tmp_path / 'kit.zip', tmp_path / 'receipt.json'
    kit.write_bytes(b'metadata only')
    receipt.write_bytes(b'{}')
    output = tmp_path / ('rg-scm-' + 'a' * 12)
    delivery = Mock()
    delivery.validate_output.return_value = output
    python = output / 'runtime/python.exe'
    delivery.prepare.return_value = (python, Mock())
    monkeypatch.setattr(coordinator, 'load_script', Mock(return_value=delivery))
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    common = ['--kit', str(kit), '--build-receipt', str(receipt), '--expected-commit', 'a' * 40,
              '--output', str(output)]
    assert coordinator.main(common) == 0
    assert [call.args[1][-1] for call in delivery.run.call_args_list] == ['prepare', 'inspect']
    delivery.reset_mock()
    assert coordinator.main(common + ['--run']) == 0
    assert [call.args[1][-1] for call in delivery.run.call_args_list] == ['prepare', 'inspect', 'run']
    assert delivery.run.call_args_list[-1].kwargs['timeout'] == 1260
    delivery.prepare.assert_called_once_with(kit, receipt, 'a' * 40, output)


def test_runtime_inspection_and_missing_authority_never_start_lifecycle(tmp_path, monkeypatch):
    coordinator = coordinator_api()
    worker = Mock()
    worker.B, worker.NAME = tmp_path, 'Rentgen.CI.' + 'a' * 12
    worker.sha.side_effect = lambda path: 'e' * 64
    prep = {'source_commit': 'a' * 40, 'kit_sha256': 'b' * 64,
            'wheel_sha256': 'c' * 64, 'scanner_sha256': 'd' * 64, 'installed_core_files': 103}
    worker.configure.return_value = prep
    context = (Mock(), {}, Mock(), Mock(), Mock(), {'exists': False}, {'elevated': False})
    worker.preflight.return_value = context
    def require(condition, message):
        if not condition:
            raise RuntimeError(message)
    worker.require.side_effect = require
    monkeypatch.setattr(coordinator, 'load_script', Mock(return_value=worker))
    monkeypatch.setattr(coordinator, 'auxiliary_context', Mock(return_value=({'schema': 1}, Mock(), Mock(), {}, {})))
    lifecycle = Mock()
    monkeypatch.setattr(coordinator, 'run_lifecycle', lifecycle)
    assert coordinator.runtime_stage(tmp_path, 'inspect') == 0
    with pytest.raises(RuntimeError):
        coordinator.runtime_stage(tmp_path, 'run')
    lifecycle.assert_not_called()
    assert not (tmp_path / 'lifecycle').exists()


def test_failed_native_result_exits_nonzero_and_keeps_false_product_scope(tmp_path, monkeypatch):
    coordinator = coordinator_api()
    worker = Mock()
    worker.B, worker.NAME = tmp_path, 'Rentgen.CI.' + 'a' * 12
    worker.sha.side_effect = lambda path: 'e' * 64
    worker.configure.return_value = {'source_commit': 'a' * 40, 'kit_sha256': 'b' * 64,
        'wheel_sha256': 'c' * 64, 'scanner_sha256': 'd' * 64, 'installed_core_files': 103}
    authority = {key: True for key in ('elevated', 'create_access', 'backup_privilege', 'restore_privilege')}
    worker.preflight.return_value = (Mock(), {}, Mock(), Mock(), Mock(), {'exists': False}, authority)
    monkeypatch.setattr(coordinator, 'load_script', Mock(return_value=worker))
    monkeypatch.setattr(coordinator, 'auxiliary_context', Mock(return_value=({'schema': 1}, Mock(), Mock(), {}, {})))
    monkeypatch.setattr(coordinator, 'acceptance_type', Mock(return_value=Mock()))
    lifecycle = Mock(return_value={'diagnostic_accepted': False})
    monkeypatch.setattr(coordinator, 'run_lifecycle', lifecycle)
    assert coordinator.runtime_stage(tmp_path, 'run') == 2
    assert (tmp_path / 'lifecycle').is_dir()
    metadata = lifecycle.call_args.args[2]
    assert metadata['source_commit'] == 'a' * 40 and metadata['wheel_sha256'] == 'c' * 64


def test_lifecycle_cannot_accept_without_retained_events(tmp_path):
    coordinator = coordinator_api()
    test = Mock()
    test.output = tmp_path
    test.spec.service_name = 'Rentgen.CI.' + 'a' * 12
    test.exercise.return_value = {'measurement_validated': True}
    test.cleanup.return_value = []
    test.native.query.return_value = {'exists': False}
    worker = SimpleNamespace(BUDGET=Mock(), sha=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        save=lambda path, value: path.write_text(json.dumps(value), 'utf-8'))
    assert coordinator.run_lifecycle(test, worker, {})['diagnostic_accepted'] is False


def test_workflow_keeps_git_diagnostic_separate_and_uploads_failed_evidence():
    import yaml
    document = yaml.safe_load((SCRIPT.parents[2] / '.github/workflows/core-ci.yml').read_text('utf-8'))
    jobs = document['jobs']
    git = jobs['native-git-diagnostic']
    assert git['needs'] == 'windows' and git['runs-on'] == 'windows-latest'
    steps = git['steps']
    download = next(step for step in steps if 'actions/download-artifact@' in step.get('uses', ''))
    assert download['with']['name'] == 'verified-core-development'
    invoke = next(step['run'] for step in steps if 'verify_git_scm_diagnostic.py' in step.get('run', ''))
    assert 'git rev-parse HEAD' in invoke and '--expected-commit $commit' in invoke and '--run' in invoke
    assert 'always()' in steps[-1]['if'] and steps[-1]['with']['name'] == 'native-git-diagnostic-evidence'
    assert 'verify_service_scm_delivery.py' in next(step['run'] for step in jobs['native-scm']['steps']
        if 'verify_service_scm_delivery.py' in step.get('run', ''))


@pytest.mark.parametrize('name', ['verify_git_scm_diagnostic', 'scm_git_diagnostic_control', 'scm_git_probe_service'])
@pytest.mark.parametrize('flag', ['-O', '-OO'])
def test_diagnostic_optimized_python_refuses_before_product_loading(tmp_path, name, flag):
    import subprocess
    import sys
    result = subprocess.run([sys.executable, flag, '-I', str(SCRIPT.with_name(name + '.py')),
        '--workdir', str(tmp_path)], capture_output=True, timeout=10)
    assert result.returncode != 0 and b'do not use Python -O' in result.stderr
    assert not list(tmp_path.iterdir())


def test_retention_keeps_actual_raw_measurement_and_manifest_inside_uploaded_evidence(tmp_path, monkeypatch):
    coordinator, probe, inputs, _, _ = measurement_fixture(tmp_path, monkeypatch)
    evidence = inputs['workdir'] / 'evidence'
    evidence.mkdir()
    worker = SimpleNamespace(B=evidence)
    retained = coordinator.retain_measurement(worker, probe, inputs)
    source_names = {path.name for path in inputs['output'].iterdir()} | {'inputs.json'}
    assert set(retained['files']) == source_names
    assert len(source_names) == 14  # Twelve pipes, report, input manifest; STOP has not run.
    for name, item in retained['files'].items():
        target = evidence / 'git-measurement' / name
        assert target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == item['sha256']
    assert retained['complete_result_and_close'] is False


@pytest.mark.parametrize('changed', ['unexpected', 'oversized'])
def test_retention_refuses_unexpected_or_oversized_evidence(tmp_path, monkeypatch, changed):
    coordinator, probe, inputs, _, _ = measurement_fixture(tmp_path, monkeypatch)
    evidence = inputs['workdir'] / 'evidence'
    evidence.mkdir()
    name = 'unexpected.raw' if changed == 'unexpected' else 'git-version-stdout.raw'
    (inputs['output'] / name).write_bytes(b'foreign' if changed == 'unexpected' else b'x' * 32769)
    with pytest.raises(ValueError):
        coordinator.retain_measurement(SimpleNamespace(B=evidence), probe, inputs)
    assert not (evidence / 'git-measurement').exists()


@pytest.mark.parametrize('failed', [False, True])
def test_measurement_retained_even_when_baseline_cleanup_raises(tmp_path, monkeypatch, failed):
    cls, context, inputs, _, events = exercise_fixture(tmp_path, monkeypatch)
    baseline = Mock(side_effect=RuntimeError('cleanup failed') if failed else None, return_value=[])
    monkeypatch.setattr(cls.__mro__[1], 'cleanup', baseline, raising=False)
    errors = cls(context, tmp_path, inputs, {}).cleanup()
    baseline.assert_called_once()
    assert bool(errors) == failed
    assert (inputs['workdir'] / 'evidence/git-measurement/result.json').is_file()
    assert any(kind == 'git_measurement_retained' for kind, _ in events)


def test_coordinator_waits_for_complete_json_when_writer_has_created_file(tmp_path, monkeypatch):
    coordinator = coordinator_api()
    path = tmp_path / 'result.json'
    path.write_bytes(b'{')
    probe = Mock()
    probe._document.side_effect = [json.JSONDecodeError('writer pending', '{', 1), {'complete': True}]
    def wait(check, seconds, description):
        assert check() is None
        return check()
    assert coordinator.wait_document(SimpleNamespace(wait_until=wait), probe, path, 15) == {'complete': True}
