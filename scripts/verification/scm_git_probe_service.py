"""Verification-only bounded Git measurements; no production trust policy."""
if not __debug__:
    raise RuntimeError('Diagnostic requires assertions; do not use Python -O')

import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import shutil
import sys
from threading import Event, Thread
import time


def _path(value, *, directory=False, single_link=True):
    spelling = str(value)
    if any(ord(char) < 32 for char in spelling) or '*' in spelling or '?' in spelling:
        raise ValueError('Invalid diagnostic path')
    path = Path(value)
    try:
        if not path.is_absolute() or path.resolve(strict=True) != path or '..' in path.parts:
            raise ValueError('Diagnostic path must be absolute and canonical')
        info = path.lstat()
        if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Diagnostic path must not be an alias')
        if (not path.is_dir() if directory else not path.is_file() or (single_link and info.st_nlink != 1)):
            raise ValueError('Invalid diagnostic path type')
    except OSError as error:
        raise ValueError('Diagnostic path is unavailable') from error
    return path


def probe_environment(inherited, *, isolated_global=None):
    env = {key: value for key, value in inherited.items() if not key.upper().startswith('GIT_')}
    env.update(GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1')
    if isolated_global is not None:
        config = _path(isolated_global)
        if config.stat().st_size != 0:
            raise ValueError('Isolated global config must be empty')
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=str(config))
    return env


def probe_command(git, repository, *, trusted_root=None):
    # Installed Git for Windows can legitimately hardlink cmd/git.exe. The
    # coordinator records its observed path/hash; owned inputs still reject links.
    executable = _path(git, single_link=False)
    root = _path(repository, directory=True)
    if root.name not in ('selected', 'other'):
        raise ValueError('Unknown diagnostic repository')
    argv = (str(executable), '--no-pager', '-c', 'core.fsmonitor=false')
    if trusted_root is not None:
        selected = _path(trusted_root, directory=True)
        if selected != root.parent / 'selected':
            raise ValueError('Trust must name the selected sibling repository')
        argv += ('-c', 'safe.directory=', '-c', 'safe.directory=' + str(selected))
    return argv + ('-C', str(root), 'rev-parse', '--show-toplevel', 'HEAD^{commit}')


def capture(command, environment, output, label, *, timeout=10, output_limit=32768):
    if (type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 10
            or type(output_limit) is not int or not 128 <= output_limit <= 32768
            or not isinstance(label, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', label)):
        raise ValueError('Invalid capture bounds or label')
    output = _path(output, directory=True)
    if not command or not all(isinstance(part, str) and '\0' not in part for part in command):
        raise ValueError('Invalid child command')
    _path(command[0], single_link=False)
    paths = {name: output / (label + '-' + name + '.raw') for name in ('stdout', 'stderr')}
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Capture evidence already exists')
    handles = {name: path.open('xb') for name, path in paths.items()}
    data = {name: bytearray() for name in paths}
    overflow = Event()
    errors, readers = [], []
    process, timed_out, process_error = None, False, None
    started = time.monotonic()

    def read_pipe(name, pipe):
        try:
            while chunk := pipe.read(4096):
                remaining = output_limit - len(data[name])
                data[name].extend(chunk[:remaining])
                if len(chunk) > remaining:
                    overflow.set()
                    try:
                        process.kill()
                    except OSError:
                        pass
                    break
        except OSError as error:
            errors.append(type(error).__name__)
        finally:
            pipe.close()

    try:
        try:
            process = subprocess.Popen(list(command), shell=False, env=environment,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for name in paths:
                thread = Thread(target=read_pipe, args=(name, getattr(process, name)), daemon=True)
                readers.append(thread)
                thread.start()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                process.wait(timeout=2)
        except OSError as error:
            process_error = type(error).__name__
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=2)
            for reader in readers:
                reader.join(timeout=2)
            if any(reader.is_alive() for reader in readers) or errors:
                process_error = 'IncompletePipeCapture'
        for name, handle in handles.items():
            handle.write(data[name])
    finally:
        for handle in handles.values():
            handle.close()
    return {'argv': list(command), 'exit_code': None if process is None else process.returncode,
            'child_pid': None if process is None else process.pid,
            'child_reaped': process is not None and process.poll() is not None,
            'timed_out': timed_out, 'output_limit_exceeded': overflow.is_set(),
            'process_error': process_error, 'duration_seconds': time.monotonic() - started,
            **{name: {'path': str(path), 'size_bytes': len(data[name]),
                      'sha256': hashlib.sha256(data[name]).hexdigest()} for name, path in paths.items()}}


def _raw(result, stream):
    item = result[stream]
    path = _path(item['path'])
    if type(item['size_bytes']) is not int or not 0 <= item['size_bytes'] <= 32768:
        raise ValueError('Raw evidence exceeds bound')
    with path.open('rb') as handle:
        raw = handle.read(32769)
    if len(raw) != item['size_bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise ValueError('Raw evidence changed')
    return raw


def classify_probe(result, repository, commit):
    stdout, stderr = _raw(result, 'stdout'), _raw(result, 'stderr')
    if result['timed_out']:
        return 'timeout'
    if result['output_limit_exceeded']:
        return 'output_limit'
    if result['process_error'] is not None:
        return 'process_unavailable'
    root = _path(repository, directory=True)
    if not re.fullmatch(r'(?:[a-f0-9]{40}|[a-f0-9]{64})', commit):
        raise ValueError('Invalid expected commit')
    if result['exit_code'] == 0:
        try:
            lines = stdout.decode('utf-8', errors='strict').splitlines()
            same = len(lines) == 2 and Path(lines[0]).resolve() == root and lines[1] == commit
            return 'accepted' if same else 'identity_mismatch'
        except (UnicodeError, OSError, ValueError):
            return 'invalid_output'
    if result['exit_code'] == 128:
        message = stderr.decode('utf-8', errors='replace')
        match = re.search(r"^fatal: detected dubious ownership in repository at '([^\r\n']+)'\r?$", message, re.M)
        if match and Path(match[1]).resolve() == root:
            return 'foreign_owner_refused'
    return 'command_failed'


def _digest(path, *, single_link=True):
    path = _path(path, single_link=single_link)
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory_repository(root):
    root = _path(root, directory=True)
    files, entries, total = {}, 0, 0
    for directory, dirs, names in os.walk(root, followlinks=False):
        for name in [*dirs, *names]:
            path = Path(directory) / name
            entries += 1
            if entries > 2000:
                raise ValueError('Repository inventory exceeds bound')
            _path(path, directory=path.is_dir())
        for name in names:
            path = Path(directory) / name
            size = path.stat().st_size
            total += size
            if size > 4 * 1024**2 or total > 16 * 1024**2:
                raise ValueError('Repository byte inventory exceeds bound')
            files[path.relative_to(root).as_posix()] = {'size_bytes': size, 'sha256': _digest(path)}
    return files


def _document(path):
    def unique(pairs):
        value = dict(pairs)
        if len(value) != len(pairs):
            raise ValueError('Duplicate diagnostic input key')
        return value
    with _path(path).open('rb') as stream:
        raw = stream.read(262145)
    if len(raw) > 262144:
        raise ValueError('Diagnostic input document exceeds bound')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique)
    if type(value) is not dict:
        raise ValueError('Invalid diagnostic document')
    return value


def load_inputs(config, config_path):
    from rentgen_core.service_entry import ServiceConfig, load_config
    executable = _path(sys.executable)
    work = executable.parent.parent
    if (executable != work / 'runtime/python.exe' or
            not re.fullmatch(r'rg-scm-[a-f0-9]{12}', work.name) or
            _path(__file__) != work / 'runtime/Lib/site-packages/scm_git_probe_service.py' or
            _path(config_path) != work / 'fixture/localservice/service.json' or
            type(config) is not ServiceConfig or load_config(config_path) != config or
            config.service_name != 'Rentgen.CI.' + work.name[7:] or config.max_cycles is not None or
            config.interval_seconds != 5 or config.registry != work / 'fixture/localservice/data/registry.sqlite3' or
            config.profile != work / 'fixture/localservice/data/observer-profile' or
            config.scanner != work / 'fixture/bsl-scan.exe'):
        raise ValueError('Diagnostic runtime/config binding differs')
    probe = _path(work / 'fixture/git-probe', directory=True)
    document = _document(probe / 'inputs.json')
    if (type(document.get('schema')) is not int or document['schema'] != 1 or
            document.get('workdir') != str(work) or document.get('service_name') != config.service_name or
            document.get('project') != config.project or document.get('config_sha256') != _digest(config_path) or
            document.get('module_sha256') != _digest(__file__) or
            set(document.get('repositories', {})) != {'selected', 'other'}):
        raise ValueError('Diagnostic manifest binding differs')
    paths = {}
    for name in ('selected', 'other'):
        item = document['repositories'][name]
        root = _path(probe / 'source' / name, directory=True)
        if (item.get('root') != str(root) or not re.fullmatch(r'[a-f0-9]{40}', item.get('commit', '')) or
                not re.fullmatch(r'S-1-[0-9-]{1,120}', item.get('owner_sid', '')) or
                item['owner_sid'] == 'S-1-5-19' or item.get('files') != inventory_repository(root) or
                not (root / '.git/HEAD').is_file() or not (root / '.git/config').is_file()):
            raise ValueError('Prepared diagnostic repository changed')
        paths[name] = root
    empty = _path(probe / 'empty-global.cfg')
    if empty.stat().st_size != 0 or document.get('empty_global_sha256') != _digest(empty):
        raise ValueError('Prepared empty Git config changed')
    output = _path(work / 'fixture/localservice/data/git-probe', directory=True)
    if any(output.iterdir()):
        raise ValueError('Diagnostic evidence output already used')
    return {'document': document, 'output': output, 'empty_global': empty, 'workdir': work, **paths}


def current_identity():
    from rentgen_core.local_identity import current_windows_principal
    return current_windows_principal().id.removeprefix('windows-sid:')


def _write_result(path, value):
    with path.open('xb') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


class ProbeWorker:
    def __init__(self, config, config_path):
        self.inputs = load_inputs(config, config_path)
        self.config = config
        self.done = self.closed = False

    def tick(self):
        if self.done:
            return
        self.done = True
        from datetime import datetime, timezone
        inputs, document = self.inputs, self.inputs['document']
        report = {'scope': 'Git diagnostic measurement; actual SCM/coordinator qualification pending',
            'service_name': self.config.service_name, 'project': self.config.project,
            'process': {'pid': os.getpid(), 'interpreter': str(sys.executable), 'token_user_sid': None},
            'input_document_sha256': _digest(inputs['workdir'] / 'fixture/git-probe/inputs.json'),
            'cases': {}, 'failure': None, 'ownership_pattern_verified': False,
            **{name: False for name in ('diagnostic_accepted', 'native_git_scm_accepted',
                'continuous_git_accepted', 'production_trust_policy_selected', 'full_product_ready',
                'production_deployment', 'independent_review')}}
        try:
            report['process']['token_user_sid'] = current_identity()
            if report['process']['token_user_sid'] != 'S-1-5-19':
                raise ValueError('Diagnostic requires actual LocalService token')
            observed_path = os.environ.get('PATH', '').encode('utf-8', errors='surrogatepass')
            if len(observed_path) > 32768:
                raise ValueError('Observed PATH exceeds bound')
            report['path'] = {'size_bytes': len(observed_path), 'sha256': hashlib.sha256(observed_path).hexdigest()}
            found = shutil.which('git', path=os.environ.get('PATH', ''))
            if found is None:
                raise ValueError('Git unavailable in actual LocalService PATH')
            git = _path(Path(found).absolute(), single_link=False)
            report['git'] = {'path': str(git), 'sha256': _digest(git, single_link=False),
                             'hardlinks': git.stat().st_nlink}
            default = probe_environment(os.environ)
            isolated = probe_environment(os.environ, isolated_global=inputs['empty_global'])
            version = capture((str(git), '--version'), default, inputs['output'], 'git-version')
            report['git']['version_result'] = version
            version_text = _raw(version, 'stdout').decode('utf-8', errors='strict').strip()
            if (version['exit_code'] != 0 or version['timed_out'] or version['output_limit_exceeded'] or
                    version['process_error'] is not None or not re.fullmatch(r'git version [^\r\n]{1,100}', version_text)):
                raise ValueError('Git version probe failed')
            report['git']['version'] = version_text
            selected, other = inputs['selected'], inputs['other']
            cases = (('default-env', selected, default, None),
                     ('isolated-default', selected, isolated, None),
                     ('trusted-selected', selected, isolated, selected),
                     ('isolated-other', other, isolated, selected),
                     ('isolated-after', selected, isolated, None))
            for label, root, env, trusted in cases:
                result = capture(probe_command(git, root, trusted_root=trusted), env, inputs['output'], label)
                name = 'selected' if root == selected else 'other'
                report['cases'][label] = result | {
                    'environment_scope': 'product-style' if env is default else 'empty-global-nosystem',
                    'classification': classify_probe(result, root, document['repositories'][name]['commit'])}
            expected = {'isolated-default': 'foreign_owner_refused', 'trusted-selected': 'accepted',
                        'isolated-other': 'foreign_owner_refused', 'isolated-after': 'foreign_owner_refused'}
            report['ownership_pattern_verified'] = all(report['cases'][name]['classification'] == outcome
                                                       for name, outcome in expected.items())
            if not report['ownership_pattern_verified']:
                raise ValueError('Isolated ownership/trust pattern was not proved')
            for name in ('selected', 'other'):
                if inventory_repository(inputs[name]) != document['repositories'][name]['files']:
                    raise ValueError('Git measurement changed repository bytes')
            if _digest(inputs['empty_global']) != document['empty_global_sha256']:
                raise ValueError('Git measurement changed isolated config')
        except Exception as error:
            report['failure'] = {'type': type(error).__name__, 'message': str(error)[:400]}
        report['recorded_utc'] = datetime.now(timezone.utc).isoformat()
        _write_result(inputs['output'] / 'result.json', report)
        if report['failure']:
            raise RuntimeError('Git diagnostic measurement unsuccessful') from None

    def close(self):
        if not self.closed:
            _write_result(self.inputs['output'] / 'closed.json', {'closed': True, 'pid': os.getpid()})
            self.closed = True


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3 or args[:2] != ['--service', '--config']:
        return 2
    try:
        executable = _path(sys.executable)
        work = executable.parent.parent
        config_path = _path(args[2])
        if (not re.fullmatch(r'rg-scm-[a-f0-9]{12}', work.name) or
                executable != work / 'runtime/python.exe' or
                _path(__file__) != work / 'runtime/Lib/site-packages/scm_git_probe_service.py' or
                config_path != work / 'fixture/localservice/service.json'):
            return 2
    except (OSError, ValueError, TypeError):
        return 2
    from rentgen_core.service_entry import NativeService
    return NativeService(config_path, worker_factory=lambda config: ProbeWorker(config, config_path)).run().exit_code


if __name__ == '__main__':
    raise SystemExit(main())
