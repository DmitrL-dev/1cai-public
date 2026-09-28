"""Prepare one owned stock Git fixture from locally pinned runtime inputs.

No download, Java warm-up, SCM creation, permission grant or acceptance here.
"""
if not __debug__:
    raise RuntimeError('Stock preparation requires assertions; do not use Python -O')

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil


def load_script(path):
    spec=importlib.util.spec_from_file_location('rentgen_stock_'+path.stem,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_installer():
    return load_script(Path(__file__).resolve().parents[2]/'integrations/open-editor/install_bsl_runtime.py')


def scripts(worker):
    root=Path(__file__).resolve().parents[2]
    names=('scripts/verification/scm_stock_git_fixture.py','scripts/verification/scm_stock_git_control.py',
        'scripts/verification/scm_stock_git_acl.py','scripts/verification/scm_git_diagnostic_control.py',
        'scripts/verification/scm_git_probe_service.py','integrations/open-editor/install_bsl_runtime.py')
    return {name:worker.sha(root/name) for name in names}


def verify_runtime(base):
    descriptor,expected,pins_type=load_installer().contract()
    target=base/'Rentgen/runtimes'/descriptor['profile_id']
    pins=pins_type()
    try:
        pins.tree(target/'jdk',expected)
        pins.file(target/'bsl-language-server.jar',expected_size=descriptor['bsl']['jar_size_bytes'],
            expected_sha256=descriptor['bsl']['jar_sha256'])
        pins.verify()
    finally:
        pins.close()
    return {'profile_id':descriptor['profile_id'],'jdk_files':len(expected),'verified':True}


def read_object(path):
    path=load_script(Path(__file__).with_name('scm_git_probe_service.py'))._path(path)
    def unique(pairs):
        result=dict(pairs)
        if len(result)!=len(pairs):
            raise ValueError('Duplicate stock metadata key')
        return result
    with path.open('rb') as stream:
        raw=stream.read(256*1024+1)
    if len(raw)>256*1024:
        raise ValueError('Stock metadata exceeds bound')
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=unique,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Invalid stock constant')))
    if type(value) is not dict:
        raise ValueError('Stock metadata must be object')
    return value


def stock_config(worker,f):
    data=worker.ROOT/'localservice/data'
    return {'schema':3,'service_name':worker.NAME,'registry':str(data/'registry.sqlite3'),
        'profile':str(data/'observer-profile'),'project':f['project_id'],'scanner':str(worker.ROOT/'bsl-scan.exe'),
        'diagnostics_root':str(worker.ROOT/'localservice/diagnostics'),'interval_seconds':5,
        'max_cycles':None,'mode':'read-only','trust_registered_source':True}


def prepare_stock(worker,prep,*,java_home,jar):
    context=worker.preflight()
    f,_,_,native,_,status,_=context
    worker.require(status['exists'] is False,'Existing service cannot become stock fixture')
    source=worker.ROOT/'localservice/source'
    base=worker.ROOT/'localservice/diagnostics'
    config=worker.ROOT/'localservice/stock-git-service.json'
    manifest=worker.ROOT/'localservice/stock-source-manifest.json'
    worker.require(Path(f['service_source'])==source and not (source/'.git').exists(), 'Registered source is not fresh')
    worker.require(all(not path.exists() for path in (base,config,manifest,worker.B/'stock-preparation.json')),
        'Stock preparation must be new; retain interrupted attempt')
    base.mkdir()
    installed=load_installer().install(java_home=java_home,jar=jar,local_app_data=base)
    runtime=verify_runtime(base)
    worker.require(installed['status']=='installed' and installed['profile_id']==runtime['profile_id']
        and runtime['verified'] is True and runtime['jdk_files']==490,'Pinned fresh installation required')
    scratch=base/'Rentgen/diagnostic-runs'
    scratch.mkdir()
    probe=load_script(Path(__file__).with_name('scm_git_probe_service.py'))
    empty=worker.B/'stock-setup-global.cfg'
    worker.require(not empty.exists(),'Stock setup config must be new')
    empty.write_bytes(b'')
    env=probe.probe_environment(os.environ,isolated_global=empty)
    found=shutil.which('git',path=env.get('PATH',''))
    worker.require(found is not None,'Git required for registered fixture')
    git=probe._path(Path(found).absolute(),single_link=False)
    commands=(('init','init','-q','--template=','--initial-branch=main'),
        ('autocrlf','config','core.autocrlf','false'),
        ('add','add','CommonModules/ServiceProbe/Ext/Module.bsl'),
        ('commit','-c','user.name=Rentgen Isolated Stock Fixture','-c','user.email=stock@example.invalid',
            '-c','commit.gpgsign=false','commit','-q','-m','Owned registered stock Git fixture'),
        ('head','rev-parse','--verify','HEAD^{commit}'))
    for label,*args in commands:
        result=probe.capture((str(git),'-c','core.fsmonitor=false','-C',str(source),*args),env,worker.B,'stock-prepare-'+label)
        worker.save(worker.B/('stock-prepare-'+label+'.json'),result)
        worker.require(result['exit_code']==0 and result['child_reaped'] is True and not result['timed_out']
            and not result['output_limit_exceeded'] and result['process_error'] is None,'Owned stock Git setup failed')
    commit=probe._raw(result,'stdout').decode('utf-8').strip()
    worker.require(re.fullmatch(r'[a-f0-9]{40}',commit),'Invalid fixture commit')
    owner=native.owner(source)
    worker.require(owner!=worker.SID,'Registered Git owner must differ from LocalService')
    inventory=worker.inventory(source)
    module=source/'CommonModules/ServiceProbe/Ext/Module.bsl'
    worker.validate_source_inventory(inventory,worker.sha(module),f['source_file_sha256'],expected=inventory)
    worker.save(config,stock_config(worker,f))
    worker.save(manifest,{'schema':1,'files':inventory})
    entry=worker.RUNTIME/'Lib/site-packages/rentgen_core/service_entry.py'
    metadata={'schema':1,'workdir':str(worker.B.parent),'source_commit':prep['source_commit'],
        'kit_sha256':prep['kit_sha256'],'config_sha256':worker.sha(config),'manifest_sha256':worker.sha(manifest),
        'stock_entry_sha256':worker.sha(entry),'source_owner_sid':owner,'fixture_commit':commit,
        'profile_id':runtime['profile_id'],'scripts':scripts(worker),'actual_localservice_exercised':False}
    worker.save(worker.B/'stock-preparation.json',metadata)
    return metadata


def inspect_stock(worker,prep):
    from rentgen_core._git_policy import GitRepositoryTrust
    from rentgen_core.git_observer import observe_git
    from rentgen_core.service_entry import load_config
    from rentgen_core.service_installer import ServiceInstallSpec
    metadata=read_object(worker.B/'stock-preparation.json')
    expected_fields={'schema','workdir','source_commit','kit_sha256','config_sha256','manifest_sha256',
        'stock_entry_sha256','source_owner_sid','fixture_commit','profile_id','scripts','actual_localservice_exercised'}
    worker.require(set(metadata)==expected_fields and type(metadata['schema']) is int and metadata['schema']==1
        and metadata['workdir']==str(worker.B.parent) and metadata['source_commit']==prep['source_commit']
        and metadata['kit_sha256']==prep['kit_sha256'] and metadata['scripts']==scripts(worker)
        and metadata['actual_localservice_exercised'] is False,'Stock preparation identity/scripts differ')
    config=worker.ROOT/'localservice/stock-git-service.json'
    manifest=worker.ROOT/'localservice/stock-source-manifest.json'
    entry=worker.RUNTIME/'Lib/site-packages/rentgen_core/service_entry.py'
    worker.require(worker.sha(config)==metadata['config_sha256'] and worker.sha(manifest)==metadata['manifest_sha256']
        and worker.sha(entry)==metadata['stock_entry_sha256'],'Stock input hash changed')
    rows=read_object(manifest)
    worker.require(set(rows)=={'schema','files'} and type(rows['schema']) is int and rows['schema']==1,'Stock manifest schema differs')
    context=worker.preflight(source_manifest=rows['files'])
    f,_,_,native,observer,status,authority=context
    cfg=read_object(config)
    worker.require(cfg==stock_config(worker,f),'Stock config differs from fixed registered profile')
    load_config(config)
    runtime=verify_runtime(worker.ROOT/'localservice/diagnostics')
    source=worker.ROOT/'localservice/source'
    worker.require(runtime['verified'] is True and runtime['profile_id']==metadata['profile_id']
        and runtime['jdk_files']==490 and native.owner(source)==metadata['source_owner_sid']!=worker.SID,
        'Installed runtime or original repository owner changed')
    worker.require(type(metadata['fixture_commit']) is str and re.fullmatch(r'[a-f0-9]{40}',metadata['fixture_commit']),
        'Invalid stock fixture commit')
    observation=observe_git(source,trust=GitRepositoryTrust(source))
    worker.require(observation.commit==metadata['fixture_commit'] and worker.inventory(source)==rows['files'],
        'Stock fixture commit or bytes changed during read-only inspection')
    spec=ServiceInstallSpec(worker.NAME,'Rentgen Isolated Stock Git CI',str(worker.PYTHON),
        ('-I','-m','rentgen_core.service_entry','--service','--config',str(config)))
    stock_f={**f,'config':str(config),'config_sha256':metadata['config_sha256']}
    files={worker.PYTHON:f['interpreter_sha256'],config:metadata['config_sha256'],manifest:metadata['manifest_sha256'],
        entry:metadata['stock_entry_sha256']}
    return (stock_f,cfg,spec,native,observer,status,authority),metadata,files
