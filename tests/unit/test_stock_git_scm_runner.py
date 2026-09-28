"""Stock native entry orchestration; injected delivery is not SCM proof."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


def api():
    path=Path(__file__).resolve().parents[2]/'scripts/verification/verify_stock_git_scm.py'
    assert path.is_file(),'Installed stock SCM coordinator missing'
    spec=importlib.util.spec_from_file_location('stock_runner_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_runtime_inspection_binds_coordinator_hashes_and_never_constructs_native_runner(tmp_path,monkeypatch):
    module=api();events=[];evidence=tmp_path/'evidence';evidence.mkdir()
    prep={'source_commit':'a'*40,'kit_sha256':'b'*64,'wheel_sha256':'c'*64,'scanner_sha256':'d'*64,'installed_core_files':105}
    def require(ok,msg):
        if not ok: raise RuntimeError(msg)
    worker=SimpleNamespace(B=evidence,NAME='Rentgen.CI.'+'a'*12,configure=lambda _:prep,
        require=require,sha=lambda _: 'e'*64,save=lambda p,v:p.write_text(json.dumps(v),'utf-8'))
    context=(None,None,None,None,None,{'exists':False},{k:True for k in ('elevated','create_access','backup_privilege','restore_privilege')})
    metadata={'fixture_commit':'f'*40,'source_commit':prep['source_commit']}
    fixture=SimpleNamespace(prepare_stock=lambda *a,**kw:events.append(('prepare',kw)),
        inspect_stock=lambda *a:(context,metadata,{}),read_object=lambda p:json.loads(p.read_text('utf-8')))
    lifecycle=SimpleNamespace(require_ready=lambda *a:events.append(('ready',)),
        acceptance_type=lambda *a:pytest.fail('Read-only inspection constructed native controls'))
    def load(name): return {'scm_acceptance_worker':worker,'scm_stock_git_fixture':fixture,'scm_stock_git_lifecycle':lifecycle}[name]
    monkeypatch.setattr(module,'load_script',load)
    assert module.runtime_stage(tmp_path,'prepare',java_home=tmp_path/'jdk',jar=tmp_path/'jar')==0
    binding=json.loads((evidence/'stock-coordinator.json').read_text('utf-8'))
    assert set(binding['scripts'])=={'verify_stock_git_scm.py','scm_stock_git_lifecycle.py','scm_stock_git_measurement.py'}
    assert module.runtime_stage(tmp_path,'inspect')==0
    assert [e[0] for e in events]==['prepare']
    binding['source_commit']='f'*40;(evidence/'stock-coordinator.json').write_text(json.dumps(binding),'utf-8')
    with pytest.raises(RuntimeError): module.runtime_stage(tmp_path,'inspect')


@pytest.mark.parametrize('run',[False,True])
def test_outer_entry_uses_copied_interpreter_and_same_owned_fixture(tmp_path,monkeypatch,run):
    module=api();calls=[];output=tmp_path/'rg-scm-aaaaaaaaaaaa';python=output/'runtime/python.exe'
    kit=tmp_path/'kit.zip';kit.write_bytes(b'input metadata')
    receipt=tmp_path/'receipt.json';receipt.write_bytes(b'input metadata')
    java=tmp_path/'jdk';java.mkdir();jar=tmp_path/'bsl.jar';jar.write_bytes(b'input metadata')
    delivery=SimpleNamespace(validate_output=lambda p,parent:p,
        prepare=lambda *a:(python,None),run=lambda *a,**kw:calls.append((a,kw)))
    monkeypatch.setattr(module,'load_script',lambda name:delivery)
    args=['--kit',str(kit),'--build-receipt',str(receipt),'--expected-commit','a'*40,'--output',str(output),
        '--java-home',str(java),'--jar',str(jar)]
    if run:args.append('--run')
    assert module.main(args)==0
    assert len(calls)==(3 if run else 2)
    assert all(call[0][0]==python for call in calls)
    assert '--java-home' in calls[0][0][1] and java in calls[0][0][1]
    assert calls[1][0][1][-1]=='inspect'
    if run: assert calls[-1][1]['timeout']==1260


def test_stock_job_uses_verified_kit_pins_no_warmup_and_retains_failures():
    path=Path(__file__).resolve().parents[2]/'.github/workflows/core-ci.yml'
    jobs=yaml.safe_load(path.read_text('utf-8'))['jobs']
    assert 'native-stock-git' in jobs,'Native stock Git/BSL job missing'
    job=jobs['native-stock-git'];assert job['needs']=='windows' and job['runs-on']=='windows-latest'
    steps=job['steps']
    prepare=next(s for s in steps if s.get('id')=='stock_scm_paths')
    assert 'rg-scm-' in prepare['run'] and 'rg-bsl-' in prepare['run']
    runtime=next(s['run'] for s in steps if s.get('name')=='Acquire and verify pinned BSL runtime inputs')
    assert '205073461' in runtime and '131962428' in runtime
    assert 'f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e' in runtime
    assert 'de97f571e6474c5c151cf859294f589ee01152de3b4826b43e1a80b69ee2602a' in runtime
    assert runtime.index('Get-FileHash')<runtime.index('Expand-Archive')
    assert 'java.exe -version' not in runtime and 'java -version' not in runtime
    command=next(s['run'] for s in steps if 'verify_stock_git_scm.py' in s.get('run',''))
    assert '--java-home' in command and '--jar' in command and '--run' in command
    assert steps[-1]['with']['name']=='native-stock-git-evidence' and 'always()' in steps[-1]['if']
    assert '/evidence/' in steps[-1]['with']['path']
