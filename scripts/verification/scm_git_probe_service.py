"""Verification-only bounded Git measurements; no production trust policy."""
if not __debug__:
    raise RuntimeError('Diagnostic requires assertions; do not use Python -O')

import hashlib
import math
import os
from pathlib import Path
import re
import subprocess
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
