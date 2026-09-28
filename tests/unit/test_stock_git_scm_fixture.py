"""Real Git fixture preparation with injected runtime/native observations only."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

from tests.unit.test_git_scm_diagnostic import preparation_fixture
from tests.unit.test_scm_stock_source_manifest import worker as real_worker

pytestmark=pytest.mark.skipif(sys.platform!='win32' or shutil.which('git') is None,
    reason='Windows inventory and actual Git required')


def api():
    path = Path(__file__).resolve().parents[2]/'scripts/verification/scm_stock_git_fixture.py'
    assert path.is_file(), 'Stock fixture preparation missing'
    spec=importlib.util.spec_from_file_location('stock_fixture_contract',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepared(tmp_path,monkeypatch):
    module=api()
    _,sdk,prep,old_context=preparation_fixture(tmp_path,monkeypatch)
    f,*tail=old_context
    source=Path(f['service_source'])
    f['source_file_sha256']=sdk.sha(source/'CommonModules/ServiceProbe/Ext/Module.bsl')
    sdk.save(sdk.B/'fixture.json',f)
    actual=real_worker()
    actual.ROOT,actual.RUNTIME= sdk.ROOT,sdk.RUNTIME
    sdk.inventory=actual.inventory
    sdk.validate_source_inventory=actual.validate_source_inventory
    calls=[]
    def preflight(*,source_manifest=None):
        calls.append(copy.deepcopy(source_manifest))
        sdk.validate_source_inventory(sdk.inventory(source),sdk.sha(source/'CommonModules/ServiceProbe/Ext/Module.bsl'),f['source_file_sha256'],expected=source_manifest)
        return (f,*tail)
    sdk.preflight=preflight
    profile='bsl-ls-1.0.5-temurin21.0.12.1-win64-bmp-default-v1'
    def install(**kwargs):
        assert kwargs['local_app_data']==sdk.ROOT/'localservice/diagnostics'
        assert not (source/'.git').exists()
        target=kwargs['local_app_data']/'Rentgen/runtimes'/profile
        (target/'jdk/bin').mkdir(parents=True)
        (target/'jdk/bin/java.exe').write_bytes(b'injected runtime input; never executed')
        (target/'bsl-language-server.jar').write_bytes(b'injected JAR; never executed')
        return {'status':'installed','profile_id':profile,'runtime':str(target),'jdk_files':490}
    monkeypatch.setattr(module,'load_installer',lambda:SimpleNamespace(install=install))
    monkeypatch.setattr(module,'verify_runtime',lambda base:{'profile_id':profile,'jdk_files':490,'verified':True})
    entry=sdk.RUNTIME/'Lib/site-packages/rentgen_core/service_entry.py'
    entry.parent.mkdir()
    entry.write_bytes(b'# stock input metadata; never executed\n')
    return module,sdk,prep,calls


def test_prepares_git_on_existing_registered_root_exact_schema3_and_inert_inspection(tmp_path,monkeypatch):
    module,sdk,prep,calls=prepared(tmp_path,monkeypatch)
    meta=module.prepare_stock(sdk,prep,java_home=tmp_path/'external-jdk',jar=tmp_path/'external.jar')
    assert calls==[None]
    assert meta['actual_localservice_exercised'] is False
    assert meta['fixture_commit'] and meta['source_owner_sid']!='S-1-5-19'
    original=sdk.inventory(sdk.ROOT/'localservice/source')
    context,back,files=module.inspect_stock(sdk,prep)
    f,cfg,spec,_,_,_,_=context
    assert back==meta and cfg['schema']==3 and cfg['max_cycles'] is None
    assert cfg['trust_registered_source'] is True and cfg['mode']=='read-only'
    assert spec.arguments[2]=='rentgen_core.service_entry'
    assert Path(f['config'])==sdk.ROOT/'localservice/stock-git-service.json'
    assert len(files)==4 and calls[1]==original
    assert sdk.inventory(sdk.ROOT/'localservice/source')==original
    assert json.loads((sdk.ROOT/'localservice/service.json').read_text('utf-8'))['schema']==1


@pytest.mark.parametrize('name',['config','manifest','entry','source','metadata'])
def test_changed_owned_inputs_refused_by_inspection(tmp_path,monkeypatch,name):
    module,sdk,prep,_=prepared(tmp_path,monkeypatch)
    module.prepare_stock(sdk,prep,java_home=tmp_path/'jdk',jar=tmp_path/'jar')
    paths={'config':sdk.ROOT/'localservice/stock-git-service.json',
        'manifest':sdk.ROOT/'localservice/stock-source-manifest.json',
        'entry':sdk.RUNTIME/'Lib/site-packages/rentgen_core/service_entry.py',
        'source':sdk.ROOT/'localservice/source/.git/HEAD','metadata':sdk.B/'stock-preparation.json'}
    path=paths[name]
    if name=='metadata':
        data=json.loads(path.read_text('utf-8'));data['source_commit']='c'*40
        path.write_text(json.dumps(data),'utf-8')
    else:
        path.write_bytes(b'changed owned input')
    with pytest.raises((RuntimeError,ValueError)):
        module.inspect_stock(sdk,prep)


def test_changed_foreign_owner_refused_before_stock_control(tmp_path,monkeypatch):
    module,sdk,prep,_=prepared(tmp_path,monkeypatch)
    module.prepare_stock(sdk,prep,java_home=tmp_path/'jdk',jar=tmp_path/'jar')
    sdk.load_native().owner.return_value='S-1-5-19'
    with pytest.raises(RuntimeError):
        module.inspect_stock(sdk,prep)


def test_existing_git_root_never_reinitialized(tmp_path,monkeypatch):
    module,sdk,prep,_=prepared(tmp_path,monkeypatch)
    path=sdk.ROOT/'localservice/source/.git'
    path.mkdir()
    (path/'HEAD').write_bytes(b'foreign existing metadata')
    with pytest.raises(RuntimeError):
        module.prepare_stock(sdk,prep,java_home=tmp_path/'jdk',jar=tmp_path/'jar')
    assert (path/'HEAD').read_bytes()==b'foreign existing metadata'


def test_runtime_installation_failure_preserved_without_git_bootstrap(tmp_path,monkeypatch):
    module,sdk,prep,_=prepared(tmp_path,monkeypatch)
    def failure(**kwargs):
        raise ValueError('pinned input mismatch')
    monkeypatch.setattr(module,'load_installer',lambda:SimpleNamespace(install=failure))
    with pytest.raises(ValueError):
        module.prepare_stock(sdk,prep,java_home=tmp_path/'jdk',jar=tmp_path/'jar')
    assert not (sdk.ROOT/'localservice/source/.git').exists()
    assert not (sdk.B/'stock-preparation.json').exists()


def test_false_fixture_commit_cannot_pass_unchanged_valid_manifest(tmp_path,monkeypatch):
    module,sdk,prep,_=prepared(tmp_path,monkeypatch)
    module.prepare_stock(sdk,prep,java_home=tmp_path/'jdk',jar=tmp_path/'jar')
    path=sdk.B/'stock-preparation.json'
    data=json.loads(path.read_text('utf-8'));data['fixture_commit']='c'*40
    path.write_text(json.dumps(data),'utf-8')
    with pytest.raises(RuntimeError):
        module.inspect_stock(sdk,prep)


def test_hardlinked_metadata_is_refused_even_with_exact_bytes(tmp_path,monkeypatch):
    module,sdk,prep,_=prepared(tmp_path,monkeypatch)
    module.prepare_stock(sdk,prep,java_home=tmp_path/'jdk',jar=tmp_path/'jar')
    path=sdk.B/'stock-preparation.json'
    baseline=sdk.B/'stock-baseline.json'
    path.rename(baseline)
    os.link(baseline,path)
    with pytest.raises(ValueError):
        module.inspect_stock(sdk,prep)
