"""Owned verifier control adapter for the installed public stock service entry."""
if not __debug__:
    raise RuntimeError('Stock acceptance requires assertions; do not use Python -O')

import os
from pathlib import Path
import re
import tempfile

from rentgen_core.service_installer import ServiceInstallSpec


def create_installer(control, probe, native, workdir, authority, output, expected_files):
    """Reuse acknowledged SCM controls, retaining the public Core image contract.

    The trusted coordinator binds both verifier modules to source hashes. No
    service JSON chooses an installer or executable. Native measurement remains
    the coordinator's responsibility; this adapter only records control output.
    """
    class StockInstaller(control.DiagnosticInstaller):
        def __init__(self):
            self.probe, self.native = probe, native
            self.workdir = probe._path(workdir, directory=True)
            if (self.workdir.parent != Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())).resolve(strict=True)
                    or not re.fullmatch(r'rg-scm-[a-f0-9]{12}', self.workdir.name)):
                raise ValueError('Unowned stock acceptance workspace')
            python = self.workdir / 'runtime/python.exe'
            config = self.workdir / 'fixture/localservice/stock-git-service.json'
            manifest = self.workdir / 'fixture/localservice/stock-source-manifest.json'
            entry = self.workdir / 'runtime/Lib/site-packages/rentgen_core/service_entry.py'
            if set(expected_files) != {python, config, manifest, entry}:
                raise ValueError('Stock input file binding differs')
            self.expected_files = dict(expected_files)
            self.output = probe._path(output, directory=True)
            if self.output != self.workdir / 'evidence/lifecycle':
                raise ValueError('Stock control evidence escapes owned lifecycle directory')
            self.sc = probe._path(Path(os.environ['SystemRoot']) / 'System32/sc.exe', single_link=False)
            self.spec = ServiceInstallSpec('Rentgen.CI.' + self.workdir.name[7:],
                'Rentgen Isolated Stock Git CI', str(python),
                ('-I', '-m', 'rentgen_core.service_entry', '--service', '--config', str(config)))
            self.authority = dict(authority)
            self.created = False
            self.sequence = 0
            self._check_files()
    return StockInstaller()
