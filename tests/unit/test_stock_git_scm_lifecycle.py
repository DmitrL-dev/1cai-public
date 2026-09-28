"""Injected lifecycle ordering/failure contracts; no native acceptance claimed."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def api():
    path=Path(__file__).resolve().parents[2]/'scripts/verification/scm_stock_git_lifecycle.py'
    assert path.is_file(),'Full stock native lifecycle missing'
    spec=importlib.util.spec_from_file_location('stock_lifecycle_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class Exercise:
    def __init__(self,*,fail=None):
        self.calls=[];self.fail=fail;self.commits=['a'*40];self.metadata={'fixture_commit':self.commits[0]}
    def step(self,name,*args):
        self.calls.append((name,*args))
        if self.fail==name: raise RuntimeError('injected '+name)
    def install(self): self.step('install')
    def analyzed(self,label,commits):
        self.step(label,tuple(commits));return {'commit':commits[-1],'snapshot_id':('b' if len(commits)==1 else 'c')*64}
    def next_commit(self): self.step('operator_commit');return 'd'*40
    def unchanged(self,label,commits): self.step(label,tuple(commits))
    def interrupted_recovery(self,commits): self.step('interrupted_recovery',tuple(commits))
    def history_refusal(self,commits): self.step('history_refusal',tuple(commits))
    def context_refusal(self,commits): self.step('context_refusal',tuple(commits))
    def final_inputs(self): self.step('final_inputs')


def test_full_scope_cannot_stop_after_first_success_or_drop_recovery_refusals():
    test=Exercise();result=api().exercise(test)
    assert [row[0] for row in test.calls]==['install','first','operator_commit','next','repeat',
        'interrupted_recovery','history_refusal','context_refusal','final_inputs']
    assert result['measurement_validated'] is True and result['commits']==['a'*40,'d'*40]
    assert result['native_scope']=='stock schema3 Git/native BSL full owned lifecycle'


@pytest.mark.parametrize('failure',['install','first','operator_commit','next','repeat',
    'interrupted_recovery','history_refusal','context_refusal','final_inputs'])
def test_each_gate_failure_stops_the_exercise_without_warm_retry(failure):
    test=Exercise(fail=failure)
    with pytest.raises(RuntimeError): api().exercise(test)
    assert test.calls[-1][0]==failure
    assert sum(row[0]=='first' for row in test.calls)<=1


@pytest.mark.parametrize('failure',['exercise','cleanup','retention','remaining','query','missing_gate'])
def test_failure_and_cleanup_or_retention_uncertainty_cannot_accept(tmp_path,failure):
    module=api();events=[]
    def require(condition,message):
        if not condition: raise RuntimeError(message)
    class Test:
        output=tmp_path
        spec=SimpleNamespace(service_name='Rentgen.CI.'+'a'*12)
        def event(self,name,**details):
            events.append(name);(tmp_path/'events.jsonl').write_text('\n'.join(events),'utf-8')
        def exercise(self):
            self.event('exercise')
            if failure=='exercise': raise RuntimeError('first cold run failed')
            return {'measurement_validated':failure!='missing_gate','native_scope':module.SCOPE,
                'commits':['a'*40,'b'*40]}
        def cleanup(self):
            self.event('cleanup')
            if failure=='cleanup': raise RuntimeError('uncertain cleanup')
            return []
        def retain(self):
            self.event('retention')
            if failure=='retention': raise RuntimeError('retention failure')
            return {'complete':True}
    def query(_):
        if failure=='query': raise RuntimeError('unknown service')
        return {'exists':failure=='remaining'}
    test=Test();test.native=SimpleNamespace(query=query)
    worker=SimpleNamespace(require=require,BUDGET=SimpleNamespace(begin_cleanup=lambda:events.append('budget_cleanup')),
        save=lambda path,data:path.write_text(__import__('json').dumps(data),'utf-8'),
        sha=lambda path:__import__('hashlib').sha256(path.read_bytes()).hexdigest())
    result=module.run_lifecycle(test,worker,{'source_commit':'c'*40})
    assert result['native_stock_git_accepted'] is False
    assert 'cleanup' in events and 'retention' in events
    assert result['failure'] or result['cleanup_errors']
    assert (tmp_path/'acceptance.json').is_file()


def test_run_refuses_missing_actual_authority_before_constructor_or_permissions(tmp_path):
    module=api()
    context=(None,None,None,None,None,{'exists':False},
        {'elevated':False,'create_access':True,'backup_privilege':True,'restore_privilege':True})
    worker=SimpleNamespace(require=lambda ok,msg:None if ok else (_ for _ in ()).throw(RuntimeError(msg)))
    with pytest.raises(RuntimeError): module.require_ready(worker,context)


def test_quiet_wait_tolerates_valid_running_journal_before_first_event():
    module=api();rows=iter([None,{'phase':'running','cycle':1,'event':None},
        {'phase':'running','cycle':1,'event':{'status':'unchanged'}}])
    def require(ok,msg):
        if not ok: raise RuntimeError(msg)
    def wait(check,*args):
        for _ in range(3):
            result=check()
            if result: return result
        pytest.fail('Quiet state never reached')
    worker=SimpleNamespace(Acceptance=object,require=require,wait_until=wait)
    cls=module.acceptance_type(worker,None,None,None,None,None,None);test=cls.__new__(cls)
    test.current=lambda:{'status':{'state':4}}
    test.journal=SimpleNamespace(read=lambda:next(rows))
    assert test.quiet()['event']['status']=='unchanged'


def test_unknown_or_live_stock_children_prevent_sdk_acl_restoration():
    module=api();calls=[]
    class Base:
        def cleanup(self): calls.append('restore_acls');return []
    worker=SimpleNamespace(Acceptance=Base,wait_until=lambda *a:(_ for _ in ()).throw(RuntimeError('unverified child lifetime')))
    cls=module.acceptance_type(worker,None,None,None,None,None,None);test=cls.__new__(cls)
    test.created=False;test.children=lambda:[{'ProcessId':17}]
    assert test.cleanup()==[{'stage':'stock_process_lifetime','type':'RuntimeError'}]
    assert not calls


def test_source_owner_or_bytes_change_cannot_be_reported_unchanged(tmp_path):
    module=api();events=[]
    def require(ok,msg):
        if not ok: raise RuntimeError(msg)
    worker=SimpleNamespace(Acceptance=object,require=require,
        save=lambda p,v:p.write_text(__import__('json').dumps(v),'utf-8'),
        sha=lambda p:__import__('hashlib').sha256(p.read_bytes()).hexdigest())
    cls=module.acceptance_type(worker,None,None,None,None,None,None);test=cls.__new__(cls)
    test.output=tmp_path;test.event=lambda name,**kw:events.append(name)
    source={'files':{'Module.bsl':{'sha256':'a'*64}},'owners':{'Module.bsl':'S-1-5-21-1'}}
    test.source_guard=lambda:source
    before=test.source_before('first')
    test.unchanged_source('first',before)
    assert (tmp_path/'source-first-before.json').read_bytes()==(tmp_path/'source-first-after.json').read_bytes()
    for key,value in [('files',{'Module.bsl':{'sha256':'b'*64}}),('owners',{'Module.bsl':'S-1-5-19'})]:
        test.source_guard=lambda:{**source,key:value}
        with pytest.raises(RuntimeError): test.unchanged_source('changed',before)
    assert not (tmp_path/'source-changed-after.json').exists()


def test_final_source_refusal_precedes_runtime_or_success_claim():
    module=api()
    def require(ok,msg):
        if not ok: raise RuntimeError(msg)
    worker=SimpleNamespace(Acceptance=object,require=require)
    cls=module.acceptance_type(worker,None,None,None,None,None,None);test=cls.__new__(cls)
    test.operator_git=lambda *args:'b'*40;test.final_commit='a'*40
    with pytest.raises(RuntimeError): test.final_inputs()
