"""Fixed verification-only SCM adapter; it cannot install another Core module."""
if not __debug__:
    raise RuntimeError('Diagnostic requires assertions; do not use Python -O')

from collections import namedtuple
import os
from pathlib import Path
import re
import subprocess
import tempfile


DiagnosticSpec = namedtuple('DiagnosticSpec', 'service_name display_name binary_path')


class DiagnosticInstaller:
    def __init__(self, probe, native, workdir, authority, output, expected_files):
        self.probe, self.native = probe, native
        self.workdir = probe._path(workdir, directory=True)
        if (self.workdir.parent != Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())).resolve(strict=True)
                or not re.fullmatch(r'rg-scm-[a-f0-9]{12}', self.workdir.name)):
            raise ValueError('Unowned diagnostic workspace')
        python = self.workdir / 'runtime/python.exe'
        config = self.workdir / 'fixture/localservice/service.json'
        module = self.workdir / 'runtime/Lib/site-packages/scm_git_probe_service.py'
        inputs = self.workdir / 'fixture/git-probe/inputs.json'
        if set(expected_files) != {python, config, module, inputs}:
            raise ValueError('Diagnostic file binding differs')
        self.expected_files = dict(expected_files)
        self.output = probe._path(output, directory=True)
        if self.output != self.workdir / 'evidence/lifecycle':
            raise ValueError('Control evidence must be in owned lifecycle directory')
        self.sc = probe._path(Path(os.environ['SystemRoot']) / 'System32/sc.exe', single_link=False)
        self.spec = DiagnosticSpec('Rentgen.CI.' + self.workdir.name[7:], 'Rentgen Isolated Git Diagnostic CI',
            subprocess.list2cmdline((str(python), '-I', '-m', 'scm_git_probe_service', '--service', '--config', str(config))))
        self.authority = dict(authority)
        self.created = False
        self.sequence = 0
        self._check_files()

    def _check_files(self):
        for path, expected in self.expected_files.items():
            if self.probe._digest(path) != expected:
                raise ValueError('Diagnostic input file changed')

    def _ready(self, spec):
        if spec is not self.spec:
            raise ValueError('Foreign diagnostic spec')
        if not all(self.authority.get(key) is True for key in
                   ('elevated', 'create_access', 'backup_privilege', 'restore_privilege')):
            raise RuntimeError('Elevated SCM create/backup/restore authority required')

    def _current(self):
        if not self.created:
            raise RuntimeError('No acknowledged owned service creation')
        row = self.native.query(self.spec.service_name)
        expected = {'binary_path': self.spec.binary_path, 'service_type': 16, 'start_type': 3,
                    'display_name': self.spec.display_name}
        if (row.get('exists') is not True or row.get('name') != self.spec.service_name or
                any(row.get('config', {}).get(key) != value for key, value in expected.items()) or
                row.get('config', {}).get('account', '').casefold() != r'nt authority\localservice'):
            raise RuntimeError('Diagnostic service binding changed; refuse control')
        return row

    def _invoke(self, verb, *arguments):
        self.sequence += 1
        label = 'control-' + str(self.sequence) + '-' + verb
        command = (str(self.sc), verb, self.spec.service_name, *arguments)
        result = self.probe.capture(command, dict(os.environ), self.output, label, timeout=10)
        self.probe._write_result(self.output / (label + '.json'), result)
        if (result['exit_code'] != 0 or result['timed_out'] or result['output_limit_exceeded'] or
                result['process_error'] is not None):
            raise RuntimeError('SCM command unsuccessful or outcome unknown: ' + verb)

    def install(self, spec, *, start=False):
        self._ready(spec)
        if type(start) is not bool or start:
            raise ValueError('Diagnostic installation never starts implicitly')
        self._check_files()
        if self.native.query(self.spec.service_name)['exists']:
            raise RuntimeError('Existing service is never adopted')
        self._invoke('create', 'binPath=', self.spec.binary_path, 'DisplayName=', self.spec.display_name,
                     'start=', 'demand', 'type=', 'own', 'obj=', r'NT AUTHORITY\LocalService')
        self.created = True

    def start(self, spec):
        self._ready(spec)
        self._check_files()
        if self._current()['status']['state'] != 1:
            raise RuntimeError('Start requires STOPPED')
        self._invoke('start')

    def stop(self, spec):
        self._ready(spec)
        if self._current()['status']['state'] != 4:
            raise RuntimeError('Stop requires RUNNING')
        self._invoke('stop')

    def uninstall(self, spec):
        self._ready(spec)
        if self._current()['status']['state'] != 1:
            raise RuntimeError('Delete requires STOPPED')
        self._invoke('delete')
