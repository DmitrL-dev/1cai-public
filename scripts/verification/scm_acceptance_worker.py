"""Bounded, owner-invoked acceptance of one prepared non-production SCM service.

Default inspect is read-only. Run refuses before mutations without elevated
SCM create access and SeRestorePrivilege. No UAC/elevation workaround exists.
"""
if not __debug__:
    raise RuntimeError('Acceptance requires assertions; do not use Python -O')

from pathlib import Path
from datetime import datetime, timezone
from dataclasses import asdict
from uuid import uuid4
import argparse
import platform
import ctypes
from ctypes import wintypes as W
import hashlib
import importlib.util
import json
import os
import re
import shutil
from zipfile import ZipFile
import subprocess
import sys
import tempfile
import time

import rentgen_core as core
from rentgen_core.context import Principal
from rentgen_core.local import LocalRuntime
from rentgen_core.observer import Observer
from rentgen_core.service_installer import ServiceInstallSpec, WindowsServiceInstaller
from rentgen_core.local_identity import _WindowsTokenAPI
from rentgen_graph.snapshot_adapter import RentgenCapturedGoBuilder, RentgenGraphReaderFactory

# Configured only from one validated workspace, never an arbitrary service name.
B = ROOT = RUNTIME = PYTHON = NAME = None
BUDGET = None
SID = 'S-1-5-19'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(name):
    return json.loads((B / name).read_text('utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def inventory(root, *, hash_files=True):
    """Reject links/aliases before granting rights or hashing owned test trees."""
    require(root.resolve() == root and root in (ROOT, RUNTIME, ROOT/'localservice/source'), 'Unowned inventory root')
    items = [root, *root.rglob('*')]
    require(len(items) <= 20000, 'Owned inventory exceeds bound')
    for path in items:
        value = path.lstat()
        require(path.resolve().is_relative_to(root), 'Path escapes owned root')
        require(not value.st_file_attributes & 0x400, 'Reparse point in owned tree')
        require(path.is_dir() or value.st_nlink == 1, 'Hardlink in owned tree')
    return {str(p.relative_to(root)): {'directory': p.is_dir(),
             **({} if p.is_dir() else {'bytes': p.stat().st_size,
                **({'sha256': sha(p)} if hash_files else {})})} for p in items}


def configure(workdir):
    global B, ROOT, RUNTIME, PYTHON, NAME
    workdir = Path(workdir).absolute()
    require(workdir.resolve(strict=True) == workdir and re.fullmatch(r'rg-scm-[a-f0-9]{12}', workdir.name),
            'Invalid owned workspace')
    require(workdir.parent == Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())).resolve(strict=True),
            'Workspace must be a direct child of the temporary parent')
    B, ROOT, RUNTIME = workdir/'evidence', workdir/'fixture', workdir/'runtime'
    PYTHON, NAME = RUNTIME/'python.exe', 'Rentgen.CI.'+workdir.name[7:]
    require(all(p.is_dir() and not p.lstat().st_file_attributes & 0x400 for p in (B,ROOT,RUNTIME)),
            'Workspace directory is missing or is a reparse point')
    require(Path(sys.executable).resolve() == PYTHON, 'Use the prepared direct interpreter')
    require(Path(core.__file__).is_relative_to(RUNTIME/'Lib/site-packages'), 'Core imported outside prepared runtime')
    prep = read('preparation.json')
    require(prep['schema'] == 1 and prep['workdir'] == str(workdir) and prep['service_name'] == NAME,
            'Preparation workspace binding differs')
    for name, digest in prep['scripts'].items():
        require(name in {'verify_service_scm_delivery.py','scm_acceptance_worker.py','scm_native_evidence.py'}
                and sha(Path(__file__).with_name(name)) == digest, 'Verification script changed')
    return prep


def load_native():
    path = Path(__file__).with_name('scm_native_evidence.py')
    require(sha(path) == read('preparation.json')['scripts'][path.name], 'Native helper changed')
    spec = importlib.util.spec_from_file_location('rentgen_scm_readonly_evidence', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.NativeEvidence()


class Budget:
    def __init__(self, exercise_seconds=840, cleanup_seconds=360):
        self.deadline = time.monotonic() + exercise_seconds
        self.hard_deadline = self.deadline + cleanup_seconds
        self.cleanup_seconds = cleanup_seconds

    def remaining(self):
        value = self.deadline - time.monotonic()
        require(value > 0, 'Acceptance time budget exhausted')
        return value

    def begin_cleanup(self):
        self.deadline = min(time.monotonic()+self.cleanup_seconds, self.hard_deadline)


def bounded(seconds):
    return min(seconds, BUDGET.remaining()) if BUDGET is not None else seconds


def owned_scanner_pids():
    # Windows does not terminate children when their parent exits. Wait for this
    # fixture's scanner before recovery or restoring the fixture ACLs.
    powershell = shutil.which('pwsh.exe')
    require(powershell is not None, 'Prepared PowerShell 7 is unavailable')
    script = "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); " \
        "ConvertTo-Json -Compress -InputObject @(Get-CimInstance -ClassName Win32_Process " \
        "-Filter \"Name='bsl-scan.exe'\" -Property ProcessId,ExecutablePath | " \
        "Select-Object ProcessId,ExecutablePath)"
    result = subprocess.run([powershell,'-NoProfile','-NonInteractive','-Command',script],
        stdin=subprocess.DEVNULL,capture_output=True,timeout=bounded(20))
    require(result.returncode == 0 and not result.stderr, 'Cannot inspect scanner process lifetime')
    require(len(result.stdout) <= 1024*1024, 'Scanner process inventory exceeds bound')
    rows = json.loads(result.stdout.decode('utf-8-sig'))
    require(type(rows) is list and len(rows) <= 100, 'Invalid scanner process inventory')
    require(all(row.get('ExecutablePath') for row in rows), 'Scanner image could not be verified')
    return [row['ProcessId'] for row in rows if Path(row['ExecutablePath']).resolve() == ROOT/'bsl-scan.exe']


def prepare_fixture():
    from rentgen_core.access import change_membership
    from rentgen_core.local_identity import current_windows_principal
    from rentgen_core.service_entry import load_config
    prep = read('preparation.json')
    folder = ROOT/'localservice'
    require(not folder.exists(), 'Fixture must be new')
    folder.mkdir()
    source = folder/'source'
    module = source/'CommonModules/ServiceProbe/Ext/Module.bsl'
    module.parent.mkdir(parents=True)
    module.write_bytes('Функция Значение() Экспорт\r\n\tВозврат 1;\r\nКонецФункции\r\n'.encode('utf-8'))
    data = folder/'data'
    data.mkdir()
    owner = current_windows_principal()
    principal = Principal('windows-sid:'+SID,'local_os')
    registry = core.ProjectRegistry.create(data/'registry.sqlite3')
    project = registry.register(owner,source_root=source,state_root=data/'state',display_name='Owned SCM CI fixture')
    runtime = LocalRuntime(registry.path,RentgenGraphReaderFactory(),RentgenCapturedGoBuilder(ROOT/'bsl-scan.exe'))
    ctx = runtime.state_context(owner,project.project_id)
    with ctx.state.transaction(owner) as tx:
        revision = tx.membership_revision()
    change_membership(ctx.state,owner,target=principal,permissions=['project:read','analysis:run'],
                      action='membership.set',operation_id=str(uuid4()),expected_revision=revision)
    observer = Observer(runtime,principal,project.project_id,data/'observer-profile')
    observer.initialize()
    cfg = {'schema':1,'service_name':NAME,'registry':str(registry.path),'profile':str(observer.profile),
           'project':project.project_id,'scanner':str(ROOT/'bsl-scan.exe'),'interval_seconds':5,'max_cycles':None}
    path = folder/'service.json'
    save(path,cfg)
    require(load_config(path).service_name == NAME,'Config binding differs')
    save(B/'fixture.json',{'service_name':NAME,'root':str(ROOT),'interpreter':str(PYTHON),
         'interpreter_sha256':sha(PYTHON),'config':str(path),'config_sha256':sha(path),
         'project_id':project.project_id,'scanner_sha256':prep['scanner_sha256'],
         'service_data':str(data),'service_source':str(source),'source_file_sha256':sha(module)})


def preflight():
    f, prep = read('fixture.json'), read('preparation.json')
    require(Path(sys.executable).resolve() == PYTHON, 'Use the prepared direct interpreter')
    require(Path(core.__file__).is_relative_to(RUNTIME/'Lib/site-packages'), 'Core imported outside prepared runtime')
    require(f['service_name'] == NAME and Path(f['root']) == ROOT, 'Fixture identity differs')
    require(Path(f['interpreter']) == PYTHON and Path(f['service_source']) == ROOT/'localservice/source',
            'Unexpected interpreter or source path')
    for key in ('interpreter','config'):
        require(sha(f[key]) == f[key+'_sha256'], 'Prepared input hash changed')
    require(Path(f['config']) == ROOT/'localservice/service.json' and
            Path(f['service_data']) == ROOT/'localservice/data', 'Unexpected config or data path')
    cfg = json.loads(Path(f['config']).read_text('utf-8'))
    require(cfg['service_name'] == NAME and cfg['project'] == f['project_id'], 'Config binding differs')
    require(cfg['schema'] == 1 and cfg['max_cycles'] is None and cfg['interval_seconds'] == 5, 'Config lifetime differs')
    require(Path(cfg['registry']) == ROOT/'localservice/data/registry.sqlite3'
            and Path(cfg['profile']) == ROOT/'localservice/data/observer-profile'
            and Path(cfg['scanner']) == ROOT/'bsl-scan.exe', 'Config path escapes fixture')
    require(sha(ROOT/'bsl-scan.exe') == f['scanner_sha256'] == prep['scanner_sha256'], 'Scanner changed')
    require(all(sha(RUNTIME/name) == digest for name,digest in prep['runtime_files'].items()), 'Original CPython file changed')
    wheel = Path(prep['wheel'])
    require(wheel.resolve().is_relative_to(B.parent/'unpacked') and sha(wheel) == prep['wheel_sha256'], 'Wheel changed')
    with ZipFile(wheel) as archive:
        files = [n for n in archive.namelist() if n.startswith(
            ('rentgen_core/','rentgen_graph/','rentgen_diagnostics/')) and not n.endswith('/')]
        require(len(files) == prep['installed_core_files'] and files and all(archive.read(n) ==
            (RUNTIME/'Lib/site-packages'/n).read_bytes() for n in files), 'Installed runtime differs from wheel')
    require(shutil.disk_usage(ROOT).free >= 2*1024**3, 'At least 2 GiB free space required')
    inventory(ROOT)
    inventory(RUNTIME)
    require(not owned_scanner_pids(), 'Owned scanner is already running')
    source = inventory(ROOT/'localservice/source')
    module = ROOT/'localservice/source/CommonModules/ServiceProbe/Ext/Module.bsl'
    require(sha(module) == f['source_file_sha256'] and len(source) == 5, 'Prepared source changed')
    spec = ServiceInstallSpec(service_name=NAME,display_name='Rentgen Isolated SCM CI',executable=str(PYTHON),
        arguments=('-I','-m','rentgen_core.service_entry','--service','--config',f['config']))
    native = load_native()
    status = native.query(NAME)
    privileges = native.privileges()
    manager = native.security.OpenSCManagerW(None,None,1|2)
    error = 0 if manager else ctypes.get_last_error()
    if manager:
        native.require(native.security.CloseServiceHandle(manager),'CloseSCManagerHandle')
    authority = {'elevated':bool(ctypes.windll.shell32.IsUserAnAdmin()),'create_access':bool(manager),
                 'create_error':error,'restore_privilege':any(p['name']=='SeRestorePrivilege' for p in privileges)}
    runtime = LocalRuntime(Path(cfg['registry']),RentgenGraphReaderFactory(),RentgenCapturedGoBuilder(ROOT/'bsl-scan.exe'))
    observer = Observer(runtime,Principal('windows-sid:'+SID,'local_os'),f['project_id'],Path(cfg['profile']))
    current = observer.status()
    require(not current['jobs'] and not current['reports'], 'Fixture already used; inspect retained evidence')
    return f,cfg,spec,native,observer,status,authority


def binding(row, spec):
    return (row.get('exists') is True and row.get('name') == NAME
        and row['config']['binary_path'] == spec.binary_path
        and row['config']['account'].casefold() == 'nt authority\\localservice'
        and row['config']['service_type'] == 16 and row['config']['start_type'] == 3
        and row['config']['display_name'] == spec.display_name)


def acl_entries(path, root):
    raw = path.read_bytes()
    require(len(raw) < 32*1024*1024, 'ACL backup exceeds bound')
    lines = raw.decode('utf-16').splitlines()
    require(len(lines) % 2 == 0 and 0 < len(lines) <= 40000, 'Invalid ACL backup')
    result = {}
    for name, dacl in zip(lines[::2], lines[1::2]):
        target = (root.parent/name).resolve()
        require(target.is_relative_to(root) and target not in result, 'ACL entry escapes or duplicates owned root')
        require(dacl.startswith('D:'), 'Expected DACL-only backup')
        result[target] = dacl
    require(root in result, 'Root DACL missing')
    return result


def dacl_parts(sddl):
    """Keep exact ACE text; AI is descriptor control, not an ACE permission.

    https://learn.microsoft.com/en-us/windows/win32/secauthz/security-descriptor-string-format
    Only the ordinary DACL format produced for this fixture is supported.
    """
    match = re.fullmatch(r'D:((?:P|AR|AI)*)((?:\([^()]*\))*)', sddl)
    require(match is not None, 'Invalid DACL descriptor')
    flags = re.findall(r'P|AR|AI', match[1])
    require(len(flags) == len(set(flags)), 'Invalid DACL control flags')
    require(all(len(ace.split(';')) == 6 for ace in re.findall(r'\(([^()]*)\)', match[2])),
            'Invalid DACL ACE format')
    return frozenset(flags), match[2]


def has_localservice_ace(dacl):
    return bool(re.search(r';(?:LS|S-1-5-19)\)', dacl))


def verify_acl_restoration(before, after):
    original = {path: dacl_parts(dacl) for path, dacl in before.items()}
    restored = {path: dacl_parts(dacl) for path, dacl in after.items()}
    require(set(before) <= set(after), 'Original DACL was not restored exactly')
    require(all((flags - {'AI'}, aces) == (restored[path][0] - {'AI'}, restored[path][1])
                for path, (flags, aces) in original.items()), 'Original DACL was not restored exactly')
    added = set(after) - set(before)
    require(not any(has_localservice_ace(after[path]) for path in added),
            'LocalService ACE remains on a new test entry')
    return {'original_entries': len(before), 'new_entries': len(added), 'original_dacls_equal': True,
            'original_descriptor_strings_equal': all(after[path] == dacl for path, dacl in before.items()),
            'auto_inherited_control_changes': sum(('AI' in flags) != ('AI' in restored[path][0])
                                                 for path, (flags, _) in original.items()),
            'new_entries_have_no_localservice_ace': True}


def new_acl_cleanup_frontiers(root, before, after):
    """Select new subtrees only; never change ownership of a baseline entry."""
    require(root in before and set(before) <= set(after), 'Missing original entry in ACL inventory')
    require(all(path.is_absolute() and path.is_relative_to(root) for path in after),
            'ACL cleanup path escapes owned root')
    added = set(after) - set(before)
    roots = set()
    for path in added:
        if not has_localservice_ace(after[path]):
            continue
        while path.parent in added:
            path = path.parent
        require(path.parent in before, 'Incomplete original entry boundary')
        require(not any(old.is_relative_to(path) for old in before),
                'New subtree contains an original entry')
        roots.add(path)
    return sorted(roots)


def temporary_acl_policy(root, baseline, data):
    """An explicit protected descriptor for every file and directory.

    icacls inheritance flags apply to directories. /grant with OI/CI followed
    by /inheritancelevel:r can leave file DACLs empty. Restore complete
    per-entry descriptors instead of layering grants on inherited permissions.
    https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls
    """
    require(root.is_absolute() and root in baseline
            and all(path.is_absolute() and path.is_relative_to(root) for path in baseline),
            'Temporary policy escapes owned root')
    require(data is None or (data in baseline and data.is_relative_to(root) and data.is_dir()),
            'Temporary policy data directory is outside its inventory')
    result = {}
    for path in baseline:
        require(path.exists(), 'Temporary policy entry is missing')
        inheritance = 'OICI' if path.is_dir() else ''
        rights = '0x1301bf' if data is not None and path.is_relative_to(data) else '0x1200a9'
        result[path] = ('D:P' + ''.join(f'(A;{inheritance};{mask};;;{sid})'
                       for sid, mask in (('BA', 'FA'), ('SY', 'FA'), ('LS', rights))))
    return result


def write_acl_policy(path, root, entries):
    lines = []
    for target, sddl in entries.items():
        require(target.is_relative_to(root), 'ACL policy escapes owned root')
        name = str(target.relative_to(root.parent))
        require(not any(c in name for c in '\r\n\0'), 'Invalid ACL policy path')
        dacl_parts(sddl)
        lines.extend((name, sddl))
    with path.open('xb') as stream:
        stream.write(('\r\n'.join(lines) + '\r\n').encode('utf-16-le'))
    require(acl_entries(path, root) == entries, 'Written ACL policy differs')


def verify_temporary_acls(root, entries, data):
    """No inherited BU/CREATOR OWNER grants may broaden service RX or M."""
    require(root in entries and all(path.is_relative_to(root) for path in entries),
            'Temporary ACL inventory escapes root')
    aliases = {'S-1-5-32-544': 'BA', 'S-1-5-18': 'SY', SID: 'LS'}
    for path, sddl in entries.items():
        flags, aces = dacl_parts(sddl)
        require('P' in flags, 'Temporary ACL must block inherited grants')
        expected = {'BA': 'FA', 'SY': 'FA',
                    'LS': '0x1301bf' if data is not None and path.is_relative_to(data) else '0x1200a9'}
        observed = {}
        for ace in re.findall(r'\(([^()]*)\)', aces):
            kind, inheritance, rights, object_id, inherited_object, sid = ace.split(';')
            sid = aliases.get(sid, sid)
            require(kind == 'A' and inheritance == ('OICI' if path.is_dir() else '')
                    and not object_id and not inherited_object and sid not in observed,
                    'Temporary ACL has unexpected ACE flags or duplicate principal')
            observed[sid] = rights
        require(observed == expected, 'Temporary ACL grants differ from isolated service policy')
    return {'entries': len(entries), 'protected': True, 'only_administrators_system_localservice': True,
            'service_read_execute_except_modify_data': True}


def wait_until(check, seconds, description):
    deadline = time.monotonic() + bounded(seconds)
    while True:
        bounded(1)
        result = check()
        if result:
            return result
        require(time.monotonic() < deadline, 'Timed out: '+description)
        time.sleep(0.05)


class Acceptance:
    def __init__(self, context, output):
        self.f, self.cfg, self.spec, self.native, self.observer, _, self.authority = context
        self.output = output
        self.installer = WindowsServiceInstaller(timeout=15)
        self.created = False
        self.acl_backups = []
        self.owner_backups = {}
        self.events = []
        self.original_config = Path(self.f['config']).read_bytes()

    def event(self, kind, **details):
        row = {'utc': datetime.now(timezone.utc).isoformat(), 'kind': kind, **details}
        self.events.append(row)
        with (self.output/'events.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')

    def current(self):
        bounded(1)
        row = self.native.query(NAME)
        require(binding(row, self.spec), 'Service identity changed; refuse control')
        return row

    def state(self, wanted, seconds=45):
        previous = None
        def inspect():
            nonlocal previous
            row = self.current()
            if row['status'] != previous:
                self.event('service_status', **row)
                previous = row['status']
            if row['status']['state'] == wanted:
                return row
            if wanted == 4:
                require(row['status']['state'] != 1, 'Service stopped before RUNNING')
            return None
        return wait_until(inspect, seconds, 'SCM state '+str(wanted))

    def start(self):
        require(self.current()['status']['state'] == 1, 'Start requires STOPPED')
        self.installer.start(self.spec)
        row = self.state(4)
        require(row['pid_valid'], 'No valid RUNNING PID')
        process = self.native.process(row['status']['pid'])
        require(Path(process['image']).resolve() == PYTHON and process['token_user_sid'] == SID, 'Wrong service process or token')
        self.event('running_process', **process)
        return row

    def stop(self):
        require(self.current()['status']['state'] == 4, 'Stop requires RUNNING')
        self.installer.stop(self.spec)
        row = self.state(1)
        require(row['status']['win32_exit'] == row['status']['service_exit'] == 0, 'Service did not stop cleanly')
        with self.observer.locked():
            pass
        return row

    def icacls(self, args, label):
        path = self.output/(label+'.log')
        with path.open('xb') as log:
            result = subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/icacls.exe'), *map(str,args)],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=bounded(60))
        self.event('icacls', label=label, exit_code=result.returncode, log_sha256=sha(path))
        require(result.returncode == 0, 'ACL operation failed: '+label)

    def backup_acl(self, root, label):
        inventory(root)
        saved = self.output/(label+'.acl')
        self.icacls([root, '/save', saved, '/T', '/Q'], label+'-save')
        rows = acl_entries(saved, root)
        owners = {str(path.relative_to(root)): self.native.owner(path) for path in rows}
        owner_path = self.output/(label+'-owners.json')
        save(owner_path, owners)
        self.owner_backups[root] = (owner_path, sha(owner_path))
        self.acl_backups.append((root, saved, sha(saved)))
        return saved

    def prepare_acl(self):
        # A no-change restore of the fixture baseline proves that this token can
        # restore ACLs before either tree receives a LocalService grant.
        fixture = self.backup_acl(ROOT, 'fixture')
        self.icacls([ROOT.parent, '/restore', fixture, '/Q'], 'fixture-preflight-restore')
        self.backup_acl(RUNTIME, 'runtime')
        for root in (RUNTIME, ROOT):
            baseline = next(saved for candidate, saved, _ in self.acl_backups if candidate == root)
            before = acl_entries(baseline, root)
            current_paths = {root/name for name in inventory(root)}
            require(current_paths == set(before), 'Temporary ACL inventory changed before application')
            data = Path(self.f['service_data']) if root == ROOT else None
            requested = self.output/(root.name+'-requested.acl')
            write_acl_policy(requested, root, temporary_acl_policy(root, before, data))
            requested_digest = sha(requested)
            # /restore applies the complete DACL to each named entry. Files get
            # explicit grants without inheritance flags; directories get OI/CI.
            self.icacls([root.parent, '/restore', requested, '/Q'], root.name+'-apply-policy')
            require(sha(requested) == requested_digest, 'Requested ACL policy changed')
            policy = self.output/(root.name+'-temporary.acl')
            self.icacls([root, '/save', policy, '/T', '/Q'], root.name+'-policy')
            rows = acl_entries(policy, root)
            require(set(rows) == set(before), 'Temporary ACL inventory changed')
            proof = verify_temporary_acls(root, rows, data)
            self.event('temporary_acl_verified', root=str(root), observed_sha256=sha(policy),
                       requested_sha256=requested_digest, **proof)

    def status(self):
        return self.observer.status()

    @staticmethod
    def identity(status):
        return {key: status[key] for key in ('last_snapshot','jobs','reports')}

    def reported(self, count):
        def inspect():
            status = self.status()
            row = self.current()
            require(row['status']['state'] == 4, 'Service stopped while waiting for report')
            require(status['error'] is None, 'Observer failed while waiting for report')
            require(len(status['reports']) <= count and len(status['jobs']) <= count, 'Unexpected duplicate publication')
            if len(status['reports']) == count and len(status['jobs']) == count:
                require(all(job['phase'] == 'done' for job in status['jobs']), 'Report has unfinished journal')
                return status
            return None
        return wait_until(inspect, 180, 'durable report '+str(count))

    def capture_job(self, previous_ids):
        def inspect():
            status = self.status()
            row = self.current()
            require(row['status']['state'] == 4, 'Service stopped before capture')
            new = [j for j in status['jobs'] if j['operation_id'] not in previous_ids]
            require(not any(j['phase'] in {'failed','superseded'} for j in new), 'Capture failed before observation')
            return next((j for j in new if j['phase'] == 'capture'), None)
        return wait_until(inspect, 90, 'active capture journal')

    def seed_corpus(self):
        require(self.current()['status']['state'] == 1, 'Seed only while STOPPED')
        source = Path(self.f['service_source'])
        for index in range(256):
            path = source/f'CommonModules/ScmProbe{index:04d}/Ext/Module.bsl'
            require(not path.exists(), 'Corpus path already exists')
            path.parent.mkdir(parents=True)
            path.write_bytes((b'// owned SCM timing fixture\r\n'*10000)
                + 'Функция Значение() Экспорт\r\nВозврат 1;\r\nКонецФункции\r\n'.encode('utf-8'))
        return inventory(source)

    def terminate_owned_running_process(self, pid):
        row = self.current()
        require(row['status']['state'] == 4 and row['status']['pid'] == pid and row['pid_valid'], 'SCM PID changed')
        kernel = self.native.kernel
        terminate = kernel.TerminateProcess
        terminate.argtypes, terminate.restype = [W.HANDLE,W.UINT], W.BOOL
        wait = kernel.WaitForSingleObject
        wait.argtypes, wait.restype = [W.HANDLE,W.DWORD], W.DWORD
        handle = self.native.require(kernel.OpenProcess(0x1000|0x100000|1,False,pid),'OpenOwnedServiceProcess')
        try:
            size=W.DWORD(32768);image=ctypes.create_unicode_buffer(size.value)
            self.native.require(kernel.QueryFullProcessImageNameW(handle,0,image,ctypes.byref(size)),'ReadOwnedServiceImage')
            require(Path(image.value).resolve()==PYTHON,'Held process image changed')
            api=_WindowsTokenAPI();token=W.HANDLE()
            self.native.require(api.security.OpenProcessToken(handle,0x0008,ctypes.byref(token)),'ReadOwnedServiceToken')
            try:
                storage,sid=api.token_user(token);value=api.sid_string(sid)
                try:require(value.value==SID,'Held process SID changed')
                finally:api.free_string(value)
            finally:api.close_token(token)
            row=self.current()
            require(row['status']['state']==4 and row['status']['pid']==pid,'Service changed before interruption')
            self.native.require(terminate(handle,87),'TerminateOwnedServiceProcess')
            require(wait(handle,int(bounded(30)*1000))==0,'Owned process did not exit')
            self.event('owned_process_interrupted',pid=pid,exit_code=87)
        finally:
            self.native.require(kernel.CloseHandle(handle),'CloseOwnedProcessHandle')

    def exercise(self):
        self.prepare_acl()
        require(not self.native.query(NAME)['exists'], 'Service appeared before installation')
        # No automatic deletion when create times out or has an unknown result.
        self.installer.install(self.spec, start=False)
        self.created=True
        require(binding(self.native.query(NAME),self.spec),'Created service binding differs')
        self.event('service_created',name=NAME)
        source_before=inventory(Path(self.f['service_source']))
        self.start();first=self.reported(1);self.stop()
        require(inventory(Path(self.f['service_source']))==source_before,'Initial service changed source')
        self.event('first_report',identity=self.identity(first))

        before=self.status();self.start()
        repeated=wait_until(lambda: (s if s['checked_at']!=before['checked_at'] else None)
            if (s:=self.status()) else None,45,'repeat tick')
        self.stop()
        require(self.identity(repeated)==self.identity(first),'Repeat duplicated publication')
        require(inventory(Path(self.f['service_source']))==source_before,'Repeated service changed source')
        self.event('repeat_without_publication',snapshot=repeated['last_snapshot'])

        corpus=self.seed_corpus();old_ids={j['operation_id'] for j in repeated['jobs']}
        self.start();job=self.capture_job(old_ids)
        self.current()  # Bind the service again immediately before control.
        self.installer.stop(self.spec)
        during=self.status();same=next(j for j in during['jobs'] if j['operation_id']==job['operation_id'])
        require(same['phase']=='capture','Stop-in-tick window was not proved; do not claim acceptance')
        self.event('stop_accepted_during_capture',operation_id=job['operation_id'])
        stopped=self.state(1,180)
        require(stopped['status']['win32_exit']==stopped['status']['service_exit']==0,'Active stop failed')
        after=self.status();require(len(after['reports'])==2 and len(after['jobs'])==2
            and all(j['phase']=='done' for j in after['jobs']),'Active stop did not finish one tick')
        require(inventory(Path(self.f['service_source']))==corpus,'Active stop changed source')
        with self.observer.locked():pass

        # Deterministically change only one owned input before the crash case.
        changed=Path(self.f['service_source'])/'CommonModules/ScmProbe0000/Ext/Module.bsl'
        changed.write_bytes(changed.read_bytes()+b'// second owned capture\r\n')
        crash_source=inventory(Path(self.f['service_source']));old_ids={j['operation_id'] for j in after['jobs']}
        running=self.start();interrupted=self.capture_job(old_ids)
        self.terminate_owned_running_process(running['status']['pid']);self.state(1)
        wait_until(lambda: not owned_scanner_pids(),150,'owned scanner exits after service interruption')
        self.event('no_owned_scanner_before_recovery')
        durable=self.status();retained=next(j for j in durable['jobs'] if j['operation_id']==interrupted['operation_id'])
        require(retained['phase'] in {'capture','report'},'Interruption window not retained')
        with self.observer.locked():pass
        self.start();recovered=self.reported(3);self.stop()
        require({j['operation_id'] for j in recovered['jobs']}==old_ids|{interrupted['operation_id']},'Recovery replaced operation identity')
        require(inventory(Path(self.f['service_source']))==crash_source,'Recovery changed source')
        self.event('interrupted_capture_recovered',operation_id=interrupted['operation_id'],snapshot=recovered['last_snapshot'])

        config_path=Path(self.f['config']);wrong={**self.cfg,'project':str(uuid4())}
        config_path.write_text(json.dumps(wrong)+'\n',encoding='utf-8')
        try:
            try:self.installer.start(self.spec)
            except core.CoreError as error:self.event('expected_bad_profile_start_error',code=error.code)
            def expected_failure():
                row = self.current()
                if row['status']['state'] == 1 and row['status']['win32_exit'] == 1066 and row['status']['service_exit'] == 2:
                    return row
                return None
            row=wait_until(expected_failure,45,'wrong-profile terminal failure 1066/2')
            require(self.identity(self.status())==self.identity(recovered),'Bad profile changed publication')
            self.event('wrong_project_refused',win32_exit=1066,service_exit=2)
        finally:
            config_path.write_bytes(self.original_config)
        require(sha(config_path)==self.f['config_sha256'],'Config restoration failed')
        require(inventory(Path(self.f['service_source']))==crash_source,'Wrong-project refusal changed source')

    def cleanup(self):
        errors=[]
        if self.created:
            try:
                row=self.current()
                if row['status']['state']!=1:
                    if row['status']['state']==4:self.installer.stop(self.spec)
                    self.state(1,180)
                self.installer.uninstall(self.spec)
                wait_until(lambda:not self.native.query(NAME)['exists'],45,'service deletion')
                self.event('service_absent_after_cleanup')
            except Exception as error:
                errors.append({'stage':'service','type':type(error).__name__})
        # Restore only validated saved entries within the two owned roots.
        # An unconfirmed create outcome or still-running service cannot be called clean.
        try:
            remaining = self.native.query(NAME)
            if remaining['exists']:
                errors.append({'stage':'remaining_service','name':NAME})
        except Exception as error:
            errors.append({'stage':'remaining_service_query','type':type(error).__name__})
        try:
            wait_until(lambda: not owned_scanner_pids(),150,'owned scanner exits before ACL restoration')
        except Exception as error:
            errors.append({'stage':'scanner_lifetime','type':type(error).__name__})
        if errors:
            # Preserve grants and baseline when a live/unknown process may still
            # need the fixture; the receipt reports incomplete cleanup.
            return errors
        for root,saved,digest in reversed(self.acl_backups):
            try:
                require(sha(saved)==digest,'ACL backup changed')
                inventory(root, hash_files=False)
                self.icacls([root.parent,'/restore',saved,'/Q'],root.name+'-restore')
                intermediate=self.output/(root.name+'-after-restore.acl')
                self.icacls([root,'/save',intermediate,'/T','/Q'],root.name+'-after-restore')
                before=acl_entries(saved,root)
                after=acl_entries(intermediate,root)
                frontiers=new_acl_cleanup_frontiers(root,before,after)
                # A restored CREATOR OWNER ACE can give LS full access to files
                # it created. Change only validated new subtrees, then inherit
                # the restored parent ACL again with an administrator owner.
                inventory(root)
                affected={path for path in after if any(path.is_relative_to(p) for p in frontiers)}
                for index, path in enumerate(frontiers):
                    label=root.name+'-new-'+str(index)
                    self.icacls([path,'/setowner','*S-1-5-32-544','/T','/Q'],label+'-owner')
                    self.icacls([path,'/reset','/T','/Q'],label+'-reset')
                observed=self.output/(root.name+'-restored.acl')
                self.icacls([root,'/save',observed,'/T','/Q'],root.name+'-verify')
                restored=acl_entries(observed,root)
                require(set(restored)==set(after), 'ACL cleanup changed entry inventory')
                inventory(root)
                verification=verify_acl_restoration(before,restored)
                owner_path,owner_digest=self.owner_backups[root]
                require(sha(owner_path)==owner_digest, 'Original owner backup changed')
                original_owners=json.loads(owner_path.read_text('utf-8'))
                final_owners={str(path.relative_to(root)):self.native.owner(path) for path in restored}
                require(all(final_owners.get(name)==sid for name,sid in original_owners.items()),
                        'Original file owner changed')
                require(all(final_owners[str(path.relative_to(root))]=='S-1-5-32-544' for path in affected),
                        'New file owner was not reassigned')
                owners_observed=self.output/(root.name+'-restored-owners.json')
                save(owners_observed,final_owners)
                self.event('acl_restoration_verified',root=str(root),observed_sha256=sha(observed),
                           owners_sha256=sha(owners_observed),original_owners_equal=True,
                           reassigned_new_entries=len(affected),new_owner_sid='S-1-5-32-544',
                           cleanup_frontiers=[str(path.relative_to(root)) for path in frontiers],**verification)
            except Exception as error:
                errors.append({'stage':'acl','root':str(root),'type':type(error).__name__,'message':str(error)[:400]})
        # Config may be inaccessible after a partial ACL failure. Its rewrite
        # must follow process shutdown and both ACL restoration attempts; a file
        # write failure must never prevent safe restoration of the owned trees.
        try:
            Path(self.f['config']).write_bytes(self.original_config)
            require(sha(Path(self.f['config']))==self.f['config_sha256'],'Config cleanup failed')
        except Exception as error:
            errors.append({'stage':'config','type':type(error).__name__})
        return errors


def main():
    global BUDGET
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir',required=True,type=Path)
    parser.add_argument('mode',choices=('prepare','inspect','run'))
    args=parser.parse_args()
    prep=configure(args.workdir)
    if args.mode=='prepare':
        prepare_fixture()
        return
    context=preflight()
    f,cfg,spec,native,observer,service,authority=context
    ready=all(authority[k] for k in ('elevated','create_access','restore_privilege')) and not service['exists']
    inspection={'service_name':NAME,'service_exists':service['exists'],'authority':authority,
                'ready_for_privileged_run':ready,'mutations_performed':False,'input_hashes_verified':True,
                'installed_runtime_files_verified':prep['installed_core_files'],'runner_sha256':sha(Path(__file__)),
                'source_commit':prep['source_commit'],'kit_sha256':prep['kit_sha256'],
                'host':platform.platform(),'python':sys.version,
                'plans':{name:asdict(WindowsServiceInstaller().plan(name,spec,start=False))
                         for name in ('install','start','stop','uninstall')},
                'recorded_utc':datetime.now(timezone.utc).isoformat()}
    save(B/'inspection.json',inspection)
    if args.mode=='inspect':
        print(json.dumps(inspection))
        return
    require(ready,'SCM create access and elevated restore privilege are required before mutations')
    output=B/'lifecycle'
    output.mkdir(exist_ok=False)
    BUDGET=Budget()
    test=Acceptance(context,output)
    failure=None
    try:
        test.exercise()
    except BaseException as error:
        failure={'type':type(error).__name__,'message':str(error)[:400]}
        test.event('acceptance_failure',**failure)
    finally:
        BUDGET.begin_cleanup()
        cleanup=test.cleanup()
    final_service=native.query(NAME)
    result={'accepted':failure is None and not cleanup and not final_service['exists'],
            'failure':failure,'cleanup_errors':cleanup,'events_sha256':sha(output/'events.jsonl'),
            'service_name':NAME,'runner_sha256':sha(Path(__file__)),
            'source_commit':prep['source_commit'],'kit_sha256':prep['kit_sha256'],
            'wheel_sha256':prep['wheel_sha256'],'scanner_sha256':prep['scanner_sha256'],
            'service_exists_after':final_service['exists'],'full_product_ready':False,
            'production_deployment':False,'new_independent_review':False,
            'recorded_utc':datetime.now(timezone.utc).isoformat()}
    save(output/'acceptance.json',result)
    print(json.dumps({'output':str(output),**result}))
    if not result['accepted']:
        raise SystemExit(2)


if __name__=='__main__':
    main()
