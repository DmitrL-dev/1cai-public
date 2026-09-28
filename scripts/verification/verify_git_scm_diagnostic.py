"""One owned disposable LocalService diagnostic; no stock Git/BSL acceptance."""
if not __debug__:
    raise RuntimeError('Diagnostic requires assertions; do not use Python -O')

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


def load_script(name, *, path=None):
    spec = importlib.util.spec_from_file_location('rentgen_git_diagnostic_' + name,
        Path(__file__).with_name(name + '.py') if path is None else path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_diagnostic(worker, prep):
    probe = load_script('scm_git_probe_service')
    f = worker.read('fixture.json')
    folder = worker.ROOT / 'git-probe'
    worker.require(not folder.exists(), 'Git diagnostic fixture must be new')
    installed = worker.RUNTIME / 'Lib/site-packages/scm_git_probe_service.py'
    worker.require(not installed.exists(), 'Diagnostic module must be new')
    folder.mkdir()
    (Path(f['service_data']) / 'git-probe').mkdir()
    source = Path(__file__).with_name('scm_git_probe_service.py')
    shutil.copyfile(source, installed)
    worker.require(worker.sha(source) == worker.sha(installed), 'Module copy differs')
    empty = folder / 'empty-global.cfg'
    empty.write_bytes(b'')
    env = probe.probe_environment(os.environ, isolated_global=empty)
    found = shutil.which('git', path=env.get('PATH', ''))
    worker.require(found is not None, 'Git unavailable for fixture preparation')
    git = probe._path(Path(found).absolute(), single_link=False)
    native = worker.load_native()
    repositories = {}
    for name in ('selected', 'other'):
        root = folder / 'source' / name
        bsl = root / 'CommonModules/ServiceProbe/Ext/Module.bsl'
        bsl.parent.mkdir(parents=True)
        bsl.write_bytes((Path(f['service_source']) / 'CommonModules/ServiceProbe/Ext/Module.bsl').read_bytes())
        steps = (('init', 'init', '-q', '--template=', '--initial-branch=main'),
                 ('add', 'add', 'CommonModules/ServiceProbe/Ext/Module.bsl'),
                 ('commit', '-c', 'user.name=Rentgen Isolated Diagnostic', '-c', 'user.email=probe@example.invalid',
                  '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', 'Owned ' + name + ' Git diagnostic fixture'),
                 ('head', 'rev-parse', '--verify', 'HEAD^{commit}'))
        for label, *args in steps:
            result = probe.capture((str(git), '-C', str(root), *args), env, worker.B, 'prepare-' + name + '-' + label)
            worker.save(worker.B / ('prepare-' + name + '-' + label + '.json'), result)
            worker.require(result['exit_code'] == 0 and not result['timed_out'] and not result['output_limit_exceeded']
                           and result['process_error'] is None, 'Owned Git preparation failed')
        commit = probe._raw(result, 'stdout').decode('utf-8').strip()
        owner = native.owner(root)
        worker.require(owner != worker.SID, 'Repository owner must differ from LocalService')
        repositories[name] = {'root': str(root), 'commit': commit, 'owner_sid': owner,
                              'files': probe.inventory_repository(root)}
    worker.save(folder / 'inputs.json', {'schema': 1, 'workdir': str(worker.B.parent), 'service_name': worker.NAME,
        'project': f['project_id'], 'config_sha256': f['config_sha256'], 'module_sha256': worker.sha(installed),
        'repositories': repositories, 'empty_global_sha256': worker.sha(empty)})
    scripts = {name: worker.sha(Path(__file__).with_name(name)) for name in
               ('verify_git_scm_diagnostic.py', 'scm_git_diagnostic_control.py', 'scm_git_probe_service.py')}
    worker.save(worker.B / 'git-preparation.json', {'schema': 1, 'workdir': str(worker.B.parent),
        'source_commit': prep['source_commit'], 'kit_sha256': prep['kit_sha256'], 'scripts': scripts,
        'installed_module_sha256': worker.sha(installed), 'inputs_sha256': worker.sha(folder / 'inputs.json'),
        'setup_git': {'path': str(git), 'sha256': probe._digest(git, single_link=False)},
        'actual_localservice_exercised': False, 'recorded_utc': datetime.now(timezone.utc).isoformat()})


def auxiliary_context(worker, prep, context):
    from rentgen_core.service_entry import load_config
    f, _, _, native, _, _, _ = context
    extra = worker.read('git-preparation.json')
    names = {'verify_git_scm_diagnostic.py', 'scm_git_diagnostic_control.py', 'scm_git_probe_service.py'}
    worker.require(extra['schema'] == 1 and extra['workdir'] == str(worker.B.parent)
        and extra['source_commit'] == prep['source_commit'] and extra['kit_sha256'] == prep['kit_sha256'],
        'Auxiliary preparation binding differs')
    worker.require(set(extra['scripts']) == names and all(worker.sha(Path(__file__).with_name(name)) == digest
                   for name, digest in extra['scripts'].items()), 'Auxiliary verification script changed')
    installed = worker.RUNTIME / 'Lib/site-packages/scm_git_probe_service.py'
    path = worker.ROOT / 'git-probe/inputs.json'
    worker.require(worker.sha(installed) == extra['installed_module_sha256'] == extra['scripts']['scm_git_probe_service.py']
        and worker.sha(path) == extra['inputs_sha256'], 'Installed diagnostic input changed')
    probe = load_script('scm_git_probe_service', path=installed)
    inputs = probe.load_inputs(load_config(Path(f['config'])), Path(f['config']))
    worker.require(all(native.owner(inputs[name]) == inputs['document']['repositories'][name]['owner_sid'] != worker.SID
                       for name in ('selected', 'other')), 'Repository owner changed')
    files = {worker.PYTHON: f['interpreter_sha256'], Path(f['config']): f['config_sha256'],
             installed: extra['installed_module_sha256'], path: extra['inputs_sha256']}
    return extra, probe, load_script('scm_git_diagnostic_control'), inputs, files


def run_lifecycle(test, worker, metadata):
    failure, measurement = None, None
    try:
        measurement = test.exercise()
        if type(measurement) is not dict or measurement.get('measurement_validated') is not True:
            raise RuntimeError('Actual diagnostic measurement proof missing')
    except BaseException as error:
        failure = {'type': type(error).__name__, 'message': str(error)[:400]}
        test.event('diagnostic_failure', **failure)
    finally:
        worker.BUDGET.begin_cleanup()
        try:
            cleanup = test.cleanup()
        except BaseException as error:
            cleanup = [{'stage': 'cleanup', 'type': type(error).__name__}]
    try:
        remaining = test.native.query(test.spec.service_name)['exists']
    except Exception as error:
        remaining = True
        cleanup.append({'stage': 'final_service_query', 'type': type(error).__name__})
    events = test.output / 'events.jsonl'
    retained = events.is_file() and events.stat().st_size > 0
    result = {**metadata, 'scope': 'owned Git ownership/availability diagnostic only',
        'diagnostic_accepted': failure is None and not cleanup and not remaining and retained,
        'failure': failure, 'measurement': measurement, 'cleanup_errors': cleanup,
        'service_name': test.spec.service_name, 'service_exists_after': remaining,
        'events_sha256': worker.sha(events) if retained else None, 'events_retained': retained,
        **{name: False for name in ('native_git_scm_accepted', 'continuous_git_accepted',
            'production_trust_policy_selected', 'full_product_ready', 'production_deployment', 'independent_review')},
        'recorded_utc': datetime.now(timezone.utc).isoformat()}
    worker.save(test.output / 'acceptance.json', result)
    return result


def validate_measurement(probe, inputs, report, process):
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    document = inputs['document']
    expected_image = inputs['workdir'] / 'runtime/python.exe'
    observed = report['process']
    require(type(process['pid']) is int and process['pid'] > 0
        and observed['pid'] == process['pid']
        and process['token_user_sid'] == observed['token_user_sid'] == 'S-1-5-19'
        and Path(process['image']) == Path(observed['interpreter']) == expected_image,
        'Actual service process binding differs')
    require(report['failure'] is None and report['ownership_pattern_verified'] is True,
        'Diagnostic worker reported failure')
    require(report['service_name'] == document['service_name'] and report['project'] == document['project']
        and report['input_document_sha256'] == probe._digest(inputs['workdir'] / 'fixture/git-probe/inputs.json'),
        'Measurement input binding differs')
    require(all(report.get(name) is False for name in ('diagnostic_accepted', 'native_git_scm_accepted',
        'continuous_git_accepted', 'production_trust_policy_selected', 'full_product_ready',
        'production_deployment', 'independent_review')), 'Worker cannot declare acceptance')
    git = probe._path(report['git']['path'], single_link=False)
    require(probe._digest(git, single_link=False) == report['git']['sha256'], 'Observed Git bytes changed')

    def capture_binding(result, label, argv):
        require(result['argv'] == list(argv) and result['child_reaped'] is True
            and result['timed_out'] is False and result['output_limit_exceeded'] is False
            and result['process_error'] is None, 'Child command/capture binding differs')
        for stream in ('stdout', 'stderr'):
            require(Path(result[stream]['path']) == inputs['output'] / (label + '-' + stream + '.raw'),
                'Raw capture path escapes fixed output')
            probe._raw(result, stream)

    version = report['git']['version_result']
    capture_binding(version, 'git-version', (str(git), '--version'))
    text = probe._raw(version, 'stdout').decode('utf-8', errors='strict').strip()
    require(version['exit_code'] == 0 and re.fullmatch(r'git version [^\r\n]{1,100}', text)
        and text == report['git']['version'], 'Git version capture differs')
    labels = {'default-env', 'isolated-default', 'trusted-selected', 'isolated-other', 'isolated-after'}
    require(set(report['cases']) == labels, 'Diagnostic cases differ')
    outcomes = {}
    for label, result in report['cases'].items():
        name = 'other' if label == 'isolated-other' else 'selected'
        trusted = inputs['selected'] if label in ('trusted-selected', 'isolated-other') else None
        capture_binding(result, label, probe.probe_command(git, inputs[name], trusted_root=trusted))
        scope = 'product-style' if label == 'default-env' else 'empty-global-nosystem'
        require(result['environment_scope'] == scope, 'Probe environment scope differs')
        outcome = probe.classify_probe(result, inputs[name], document['repositories'][name]['commit'])
        require(outcome == result['classification'], 'Reported classification differs from raw bytes')
        outcomes[label] = outcome
    require(all(outcomes[label] == expected for label, expected in {
        'isolated-default': 'foreign_owner_refused', 'trusted-selected': 'accepted',
        'isolated-other': 'foreign_owner_refused', 'isolated-after': 'foreign_owner_refused'}.items()),
        'Isolated ownership pattern differs')
    return outcomes


def acceptance_type(worker, probe, control):
    class DiagnosticAcceptance(worker.Acceptance):
        def __init__(self, context, output, inputs, files):
            authority, service = context[6], context[5]
            worker.require(service.get('exists') is False and all(authority.get(key) is True for key in
                ('elevated', 'create_access', 'backup_privilege', 'restore_privilege')),
                'Fresh service and actual elevated SCM/backup/restore authority required')
            super().__init__(context, output)
            self.inputs, self.input_files = inputs, files
            self.installer = control.DiagnosticInstaller(probe, self.native, inputs['workdir'],
                authority, output, files)
            self.spec = self.installer.spec

        def exercise(self):
            self.prepare_acl()
            self.installer.install(self.spec, start=False)
            self.created = self.installer.created
            self.event('diagnostic_created', **self.current())
            row = self.start()
            process = self.native.process(row['status']['pid'])
            result_path = self.inputs['output'] / 'result.json'
            report = wait_document(worker, probe, result_path, 90)
            worker.require(self.current()['status']['state'] == 4, 'Diagnostic did not hold RUNNING until STOP')
            outcomes = validate_measurement(probe, self.inputs, report, process)
            self.event('raw_measurement_verified', pid=process['pid'], result_sha256=worker.sha(result_path),
                outcomes=outcomes)
            self.stop()
            closed_path = self.inputs['output'] / 'closed.json'
            closed = wait_document(worker, probe, closed_path, 15)
            worker.require(closed.get('closed') is True and closed.get('pid') == process['pid'],
                'Diagnostic close process differs')
            document = self.inputs['document']
            for name in ('selected', 'other'):
                root, item = self.inputs[name], document['repositories'][name]
                worker.require(self.native.owner(root) == item['owner_sid'] != 'S-1-5-19'
                    and probe.inventory_repository(root) == item['files'], 'Source bytes or owner changed')
            worker.require(probe._digest(self.inputs['empty_global']) == document['empty_global_sha256']
                and all(probe._digest(path) == digest for path, digest in self.input_files.items()),
                'Diagnostic inputs changed during measurement')
            proof = {'measurement_validated': True, 'native_process': process, 'outcomes': outcomes,
                'result_sha256': worker.sha(result_path), 'closed_sha256': worker.sha(closed_path),
                'repository_bytes_and_owners_unchanged': True, 'input_files_unchanged': True}
            self.event('diagnostic_stop_and_inputs_verified', **proof)
            return proof

        def cleanup(self):
            errors = []
            try:
                errors = super().cleanup()
            except Exception as error:
                errors.append({'stage': 'baseline_cleanup', 'type': type(error).__name__})
            try:
                retained = retain_measurement(worker, probe, self.inputs)
                self.event('git_measurement_retained', **retained)
            except Exception as error:
                errors.append({'stage': 'measurement_retention', 'type': type(error).__name__})
            return errors
    return DiagnosticAcceptance


def wait_document(worker, probe, path, seconds):
    def complete():
        if not path.is_file():
            return None
        try:
            return probe._document(path)
        except json.JSONDecodeError:
            return None
    return worker.wait_until(complete, seconds, 'complete diagnostic document ' + path.name)


def retain_measurement(worker, probe, inputs):
    labels = ('git-version', 'default-env', 'isolated-default', 'trusted-selected', 'isolated-other', 'isolated-after')
    allowed = {label + '-' + stream + '.raw' for label in labels for stream in ('stdout', 'stderr')}
    allowed.update(('result.json', 'closed.json'))
    folder = probe._path(inputs['output'], directory=True)
    paths = list(folder.iterdir())
    if len(paths) > len(allowed) or any(path.name not in allowed for path in paths):
        raise ValueError('Unexpected diagnostic output')
    paths.append(inputs['workdir'] / 'fixture/git-probe/inputs.json')
    for path in paths:
        probe._path(path)
        if path.stat().st_size > (32768 if path.suffix == '.raw' else 262144):
            raise ValueError('Diagnostic retention exceeds byte bound')
    target = worker.B / 'git-measurement'
    target.mkdir(exist_ok=False)
    files = {}
    for path in paths:
        digest = probe._digest(path)
        destination = target / path.name
        with destination.open('xb') as stream:
            stream.write(path.read_bytes())
        if probe._digest(destination) != digest:
            raise ValueError('Diagnostic retention bytes changed')
        files[path.name] = {'source': str(path), 'sha256': digest, 'size_bytes': destination.stat().st_size}
    result = {'files': files, 'complete_result_and_close': {'result.json', 'closed.json'} <= set(files),
        'scope': 'retained raw measurement; acceptance remains the coordinator decision'}
    probe._write_result(target / 'retention.json', result)
    return result


def runtime_stage(workdir, mode):
    worker = load_script('scm_acceptance_worker')
    prep = worker.configure(workdir)
    if mode == 'prepare':
        prepare_diagnostic(worker, prep)
        return 0
    context = worker.preflight()
    extra, probe, control, inputs, files = auxiliary_context(worker, prep, context)
    authority, service = context[6], context[5]
    ready = service.get('exists') is False and all(authority.get(key) is True for key in
        ('elevated', 'create_access', 'backup_privilege', 'restore_privilege'))
    metadata = {'schema': 1, 'source_commit': prep['source_commit'], 'kit_sha256': prep['kit_sha256'],
        'wheel_sha256': prep['wheel_sha256'], 'scanner_sha256': prep['scanner_sha256'],
        'installed_core_files': prep['installed_core_files'], 'auxiliary_preparation': extra,
        'runner_sha256': worker.sha(Path(__file__)), 'service_name': worker.NAME}
    inspection = {**metadata, 'authority': authority, 'service_exists': service['exists'],
        'ready_for_privileged_run': ready, 'input_hashes_verified': True, 'mutations_performed': False,
        'recorded_utc': datetime.now(timezone.utc).isoformat()}
    worker.save(worker.B / 'git-inspection.json', inspection)
    if mode == 'inspect':
        print(json.dumps(inspection))
        return 0
    worker.require(mode == 'run' and ready, 'SCM create and elevated backup/restore authority required')
    output = worker.B / 'lifecycle'
    output.mkdir(exist_ok=False)
    worker.BUDGET = worker.Budget()
    test = acceptance_type(worker, probe, control)(context, output, inputs, files)
    result = run_lifecycle(test, worker, metadata)
    print(json.dumps({'output': str(output), **result}))
    return 0 if result['diagnostic_accepted'] else 2


def main(argv=None):
    values = list(sys.argv[1:] if argv is None else argv)
    if values[:1] == ['--workdir']:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--workdir', type=Path, required=True)
        parser.add_argument('mode', choices=('prepare', 'inspect', 'run'))
        args = parser.parse_args(values)
        return runtime_stage(args.workdir, args.mode)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--build-receipt', type=Path, required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args(values)
    delivery = load_script('verify_service_scm_delivery')
    parent = Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir()))
    output = delivery.validate_output(args.output, parent)
    python, _ = delivery.prepare(args.kit.resolve(strict=True), args.build_receipt.resolve(strict=True),
        args.expected_commit, output)
    evidence, coordinator = output / 'evidence', Path(__file__).resolve()
    for mode in ('prepare', 'inspect'):
        delivery.run(python, [coordinator, '--workdir', output, mode], evidence, 'git-' + mode)
    if args.run:
        delivery.run(python, [coordinator, '--workdir', output, 'run'], evidence, 'git-lifecycle', timeout=1260)
    print(json.dumps({'output': str(output), 'prepared': True, 'scm_requested': args.run,
        'native_git_scm_accepted': False, 'production_trust_policy_selected': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
