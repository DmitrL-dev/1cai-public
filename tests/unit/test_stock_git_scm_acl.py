"""Stock verifier ACL boundaries; no real ACL mutation or service in these tests."""
import importlib.util
from pathlib import Path

import pytest

from tests.unit.test_scm_stock_source_manifest import worker


def api():
    script = Path(__file__).resolve().parents[2] / 'scripts/verification/scm_stock_git_acl.py'
    assert script.is_file(), 'Stock ACL adapter missing'
    spec = importlib.util.spec_from_file_location('stock_scm_acl_test',script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepared(tmp_path):
    module, sdk = api(), worker()
    root, runtime = tmp_path/'fixture', tmp_path/'runtime'
    data = root/'localservice/data'
    scratch = root/'localservice/diagnostics/Rentgen/diagnostic-runs'
    source = root/'localservice/source/CommonModules/ServiceProbe/Ext/Module.bsl'
    jar = scratch.parent/'runtimes/fixed/bsl-language-server.jar'
    for path in (data/'registry.sqlite3',scratch/'retained-input.bsl',source,jar,runtime/'python.exe'):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b'owned ACL contract input')
    sdk.ROOT,sdk.RUNTIME = root,runtime
    baseline = {path:'D:' for path in (root,*root.rglob('*'))}
    return module,sdk,root,runtime,data,scratch,source,jar,baseline


def test_only_fixed_data_and_diagnostic_scratch_receive_modify(tmp_path):
    module,sdk,root,runtime,data,scratch,source,jar,baseline = prepared(tmp_path)
    original = dict(baseline)
    policy = module.temporary_policy(sdk,root,baseline)
    assert baseline==original and set(policy)==set(baseline)
    for path,sddl in policy.items():
        writable = path.is_relative_to(data) or path.is_relative_to(scratch)
        assert (';0x1301bf;;;LS)' in sddl) is writable
        assert (';0x1200a9;;;LS)' in sddl) is (not writable)
    proof = module.verify_policy(sdk,root,policy)
    assert proof['entries']==len(baseline) and proof['service_modify_only_data_and_scratch'] is True
    assert ';0x1200a9;;;LS)' in policy[source] and ';0x1200a9;;;LS)' in policy[jar]
    runtime_policy = module.temporary_policy(sdk,runtime,{runtime:'D:',runtime/'python.exe':'D:'})
    assert all(';0x1200a9;;;LS)' in sddl for sddl in runtime_policy.values())
    assert module.verify_policy(sdk,runtime,runtime_policy)['entries']==2


@pytest.mark.parametrize('missing',['data','scratch','root'])
def test_fixed_writable_roots_and_fixture_root_must_be_in_baseline(tmp_path,missing):
    module,sdk,root,_,data,scratch,_,_,baseline = prepared(tmp_path)
    baseline.pop({'data':data,'scratch':scratch,'root':root}[missing])
    with pytest.raises(RuntimeError):
        module.temporary_policy(sdk,root,baseline)


@pytest.mark.parametrize('wrong',['foreign','source','diagnostics_parent'])
def test_no_caller_selected_alternative_root(tmp_path,wrong):
    module,sdk,root,_,_,scratch,source,_,baseline = prepared(tmp_path)
    chosen = {'foreign':root.parent,'source':source.parent,'diagnostics_parent':scratch.parent}[wrong]
    with pytest.raises(RuntimeError):
        module.temporary_policy(sdk,chosen,baseline)
    with pytest.raises(RuntimeError):
        module.verify_policy(sdk,chosen,baseline)


@pytest.mark.parametrize('which',['source','jar','parent','scratch'])
def test_broader_or_weaker_service_rights_do_not_pass_exact_policy(tmp_path,which):
    module,sdk,root,_,_,scratch,source,jar,baseline = prepared(tmp_path)
    policy = module.temporary_policy(sdk,root,baseline)
    target = {'source':source,'jar':jar,'parent':scratch.parent,'scratch':scratch/'retained-input.bsl'}[which]
    policy[target] = policy[target].replace('0x1200a9','0x1301bf') if which!='scratch' else policy[target].replace('0x1301bf','0x1200a9')
    with pytest.raises(RuntimeError):
        module.verify_policy(sdk,root,policy)


@pytest.mark.parametrize('which',['inherited','duplicate','extra_principal'])
def test_scratch_cannot_hide_unprotected_or_additional_grants(tmp_path,which):
    module,sdk,root,_,_,scratch,_,_,baseline = prepared(tmp_path)
    policy = module.temporary_policy(sdk,root,baseline)
    target = scratch/'retained-input.bsl'
    if which=='inherited':
        policy[target]=policy[target].replace('D:P','D:')
    else:
        policy[target]+='(A;;FA;;;LS)' if which=='duplicate' else '(A;;FA;;;BU)'
    with pytest.raises(RuntimeError):
        module.verify_policy(sdk,root,policy)
