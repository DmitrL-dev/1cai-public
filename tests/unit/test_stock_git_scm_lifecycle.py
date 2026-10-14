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


def test_quiet_wait_uses_original_handle_and_never_reads_live_journal():
    module=api();calls=[]
    def require(ok,msg):
        if not ok: raise RuntimeError(msg)
    worker=SimpleNamespace(Acceptance=object,require=require,bounded=lambda seconds:seconds)
    cls=module.acceptance_type(worker,None,None,None,None,None,None);test=cls.__new__(cls)
    test.event=lambda *a,**kw:None
    test.current=lambda:{'status':{'state':4,'pid':17}}
    test.held=SimpleNamespace(pid=17,require_alive=lambda:calls.append('held_alive'))
    test.journal=SimpleNamespace(read=lambda:pytest.fail('Live journal must not be opened'))
    def wait(alive,*,seconds):
        assert seconds==45;alive();calls.append('directory_hint')
    test.quiet(SimpleNamespace(wait=wait))
    assert calls==['held_alive','held_alive','directory_hint','held_alive','held_alive']
    test.current=lambda:{'status':{'state':4,'pid':18}}
    with pytest.raises(RuntimeError,match='SCM PID'): test.quiet(SimpleNamespace(wait=wait))


@pytest.mark.parametrize('interrupted',[False,True])
@pytest.mark.parametrize('change',['valid','same_run','bad_run','cycle0','cycle_bool','failures',
    'failures_bool','phase','event','missing'])
def test_offline_quiet_journal_requires_fresh_completed_successful_run(interrupted,change):
    module=api()
    previous={'run_id':'00000000-0000-0000-0000-000000000001'}
    doc={'run_id':'00000000-0000-0000-0000-000000000002','cycle':1,'failures':0,
        'phase':'running' if interrupted else 'idle',
        'event':{'status':'unchanged' if interrupted else 'stopped'}}
    if change=='same_run': doc['run_id']=previous['run_id']
    if change=='bad_run': doc['run_id']='not-a-run'
    if change=='cycle0': doc['cycle']=0
    if change=='cycle_bool': doc['cycle']=True
    if change=='failures': doc['failures']=1
    if change=='failures_bool': doc['failures']=False
    if change=='phase': doc['phase']='idle' if interrupted else 'running'
    if change=='event': doc['event']=None
    if change=='missing': doc=None
    if change=='valid': assert module.validate_quiet_journal(previous,doc,interrupted=interrupted)==doc
    else:
        with pytest.raises(RuntimeError): module.validate_quiet_journal(previous,doc,interrupted=interrupted)


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


def test_old_worker_failure_cannot_turn_access_denied_start_into_expected_refusal(tmp_path):
    module=api();events=[]
    def require(ok,msg):
        if not ok: raise RuntimeError(msg)
    class Lease:
        def __enter__(self): pass
        def __exit__(self,*a): pass
    worker=SimpleNamespace(Acceptance=object,require=require,wait_until=lambda check,*a:check())
    from tests.unit.test_stock_git_scm_measurement import api as measurement_api
    measurement=measurement_api()
    fixture=SimpleNamespace(read_object=lambda path:__import__('json').loads(path.read_text('utf-8')))
    cls=module.acceptance_type(worker,fixture,None,None,None,None,measurement);test=cls.__new__(cls)
    test.output=tmp_path;test.spec=SimpleNamespace(service_name='Rentgen.CI.'+'a'*12)
    test.event=lambda name,**kw:events.append(name)
    test.current=lambda:{'status':{'state':1,'pid':0,'win32_exit':1066,'service_exit':2}}
    test.state=lambda *a:test.current();test.observer=SimpleNamespace(locked=Lease);test.children=lambda:[]
    test.installer=SimpleNamespace(sequence=12,sc=tmp_path/'sc.exe')
    def denied(_):
        test.installer.sequence+=1
        row={'argv':[str(test.installer.sc),'start',test.spec.service_name],
            'exit_code':5,'child_reaped':True,'timed_out':False,'output_limit_exceeded':False,'process_error':None}
        (tmp_path/'control-13-start.json').write_text(__import__('json').dumps(row),'utf-8')
        raise RuntimeError('SCM access denied')
    test.installer.start=denied
    with pytest.raises(RuntimeError): test.failed_start('analysis-permission-revoked')
    assert 'stock_start_refused' not in events


def test_owned_children_does_not_wait_for_its_own_live_coordinator(tmp_path):
    module=api();runtime=tmp_path/'runtime';root=tmp_path/'fixture';python=runtime/'python.exe'
    worker=SimpleNamespace(Acceptance=object,PYTHON=python,ROOT=root)
    from tests.unit.test_stock_git_scm_measurement import api as measurement_api
    measurement=measurement_api()
    cls=module.acceptance_type(worker,None,None,None,None,None,measurement);test=cls.__new__(cls)
    test.runtime=root/'localservice/diagnostics/Rentgen/runtimes/p';test.source=root/'localservice/source'
    coordinator_pid=module.os.getpid()
    test.processes=lambda:[
        {'ProcessId':coordinator_pid,'ExecutablePath':str(python)},
        {'ProcessId':coordinator_pid+1,'ExecutablePath':str(python)},
        {'ProcessId':coordinator_pid+2,'ExecutablePath':str(test.runtime/'jdk/bin/java.exe')},
        {'ProcessId':coordinator_pid+3,'ExecutablePath':str(root/'bsl-scan.exe')},
        {'ProcessId':coordinator_pid+4,'ExecutablePath':str(tmp_path/'foreign/python.exe')}]
    assert [row['ProcessId'] for row in test.children()]==[coordinator_pid+1,coordinator_pid+2,coordinator_pid+3]
    # After the real owned service/children exit, the coordinator remains live
    # and the cooperative STOP/cleanup wait must be able to complete.
    test.processes=lambda:[{'ProcessId':coordinator_pid,'ExecutablePath':str(python)}]
    assert test.children()==[]


@pytest.mark.parametrize('change',['valid','missing','pid','service','private','code','stage','kind','record','provider','level','event_id'])
def test_failure_event_reader_requires_fixed_fields_and_observed_scm_pid(change):
    from copy import deepcopy
    module=api();name='Rentgen.CI.'+'a'*12
    doc={'schema':1,'event':'service_failed','service_name':name,'pid':321,
        'failure':{'stage':'factory','kind':'CoreError','reason':'OBSERVER_PROFILE_MISMATCH'}}
    row={'provider':'Rentgen.Core.Service','event_id':1,'level':2,'record_id':42,
        'utc':'2026-09-28T08:00:00.0000000Z','data':__import__('json').dumps(doc)}
    rows=[row]
    if change=='missing': rows=[]
    elif change=='pid': doc['pid']=654
    elif change=='service': doc['service_name']='Other.Service'
    elif change=='private': doc['private']='private-value'
    elif change=='code': doc['failure']['reason']='PRIVATE_VALUE'
    elif change=='stage': doc['failure']['stage']='private-value'
    elif change=='kind': doc['failure']['kind']='private-value'
    elif change=='record': row['record_id']=True
    elif change=='provider': row['provider']='Other.Provider'
    elif change=='level': row['level']=4
    elif change=='event_id': row['event_id']=2
    row['data']=__import__('json').dumps(doc)
    if change=='valid': assert module.validate_failure_events(rows,name,{321})==[doc]
    else:
        with pytest.raises(RuntimeError): module.validate_failure_events(rows,name,{321})


def test_publication_includes_outbox_tail_beyond_default_peek_limit():
    module=api()
    cls=module.acceptance_type(SimpleNamespace(Acceptance=object),None,None,None,None,None,None)
    test=cls.__new__(cls)
    events=[{'id':i,'event':{'status':'error','code':'EXAMPLE'}} for i in range(101)]
    limits=[]
    def peek(limit=100):
        limits.append(limit);return events[:limit]
    test.outbox=SimpleNamespace(MAX_EVENTS=1000,peek=peek)
    test.observer=SimpleNamespace(status=lambda:{},findings_status=lambda:{'state':None})
    assert test.publication()['outbox']==events
    assert limits==[1000]


@pytest.mark.parametrize('status',['unchanged','analyzed','error'])
def test_stop_overwrite_needs_complete_outbox_to_infer_unchanged(tmp_path,status):
    from rentgen_core.git_watcher import NotificationOutbox,SchedulerJournal
    from rentgen_core.service_composition import GitAuditWorker
    from threading import Event
    module=api();journal=SchedulerJournal(tmp_path/'journal.json');outbox=NotificationOutbox(tmp_path/'outbox.json')
    previous_id=journal.begin();journal.stop(previous_id,1,0);previous=journal.read()
    # Place a distinguishing new event beyond the default peek prefix. None
    # may be acknowledged/cleared by qualification to make a repeat look quiet.
    for _ in range(100): outbox.enqueue({'status':'analyzed'})
    before=outbox.peek(limit=outbox.MAX_EVENTS)
    stock=GitAuditWorker.__new__(GitAuditWorker)
    stock._started=False;stock._lease=object()
    stock.config=SimpleNamespace(interval_seconds=5,max_cycles=1,scanner=tmp_path/'bsl-scan.exe')
    stock.watcher=SimpleNamespace(tick=lambda:{'status':status,**({'code':'GIT_HEAD_CHANGED'} if status=='error' else {})})
    stock.journal=journal;stock.outbox=outbox
    if status=='error':
        from rentgen_core.errors import CoreError
        with pytest.raises(CoreError): stock.run(Event())
    else: assert stock.run(Event())==1
    proof=module.validate_quiet_journal(previous,journal.read())
    assert proof['event']=={'status':'stopped'}  # last tick event was overwritten
    assert outbox.peek()==before  # default prefix would hide a new notification
    assert (outbox.peek(limit=outbox.MAX_EVENTS)==before)==(status=='unchanged')


@pytest.mark.parametrize('change',['valid','cycle0','publication','source','error'])
def test_repeat_arms_before_start_and_proves_only_after_stop_and_reap(tmp_path,change):
    from copy import deepcopy
    module=api();calls=[];live=False
    previous={'run_id':'00000000-0000-0000-0000-000000000001'}
    journal={'run_id':'00000000-0000-0000-0000-000000000002','cycle':0 if change=='cycle0' else 1,
        'failures':0,'phase':'idle','event':{'status':'stopped'}}
    doc={'outbox':[{'id':1}], 'source':'bound','status':{'error':None}}
    def require(ok,msg):
        if not ok: raise RuntimeError(msg)
    worker=SimpleNamespace(Acceptance=object,require=require,save=lambda *a:calls.append('save'))
    def validate(doc,**kw):
        calls.append('validate_publication');require(doc['status'].get('error') is None,'Observer error')
    measurement=SimpleNamespace(validate_publication=validate)
    cls=module.acceptance_type(worker,None,None,None,None,None,measurement);test=cls.__new__(cls)
    test.f={'project_id':'p'};test.source=tmp_path;test.output=tmp_path;test.held=None
    test.current=lambda:{'status':{'state':4 if live else 1}}
    def read():
        assert not live,'Live journal opened';calls.append('journal_read')
        return journal if 'stop_reap' in calls else previous
    test.journal=SimpleNamespace(read=read)
    test.source_before=lambda label:calls.append('source_before') or {'files':'fixed'}
    def source_after(*args):
        assert not live;calls.append('source_after')
        require(change!='source','Source changed')
    test.unchanged_source=source_after
    test.stable=lambda value:{**value,'status':{}}
    def publication():
        assert not live;calls.append('publication')
        result=deepcopy(doc)
        if change=='publication' and 'stop_reap' in calls: result['outbox'].append({'id':2})
        if change=='error' and 'stop_reap' in calls: result['status']['error']='OBSERVER_FAILED'
        return result
    test.publication=publication
    class Hint:
        def __enter__(self):
            assert not live;calls.append('arm');return self
        def __exit__(self,*args): calls.append('hint_close')
    test.quiet_hint=Hint
    def start():
        nonlocal live
        assert calls[-1]=='arm';live=True;calls.append('start')
    test.start=start
    test.quiet=lambda hint:calls.append('hint')
    def stop():
        nonlocal live
        live=False;calls.append('stop_reap')
    test.stop=stop;test.event=lambda *a,**kw:calls.append('accepted')
    if change=='valid': test.unchanged('repeat',['commit']);assert calls[-1]=='accepted'
    else:
        with pytest.raises(RuntimeError): test.unchanged('repeat',['commit'])
        assert 'accepted' not in calls
    assert calls.index('arm')<calls.index('start')<calls.index('stop_reap')
    assert calls[calls.index('stop_reap')+1:calls.index('stop_reap')+3]==['hint_close','journal_read']


@pytest.mark.parametrize('event',[{'status':'unchanged'},None,{'status':'analyzed'}])
def test_interruption_reads_after_reaping_and_refuses_nonquiet_recovery(tmp_path,event):
    from contextlib import nullcontext
    module=api();calls=[];live=False;children_live=False
    previous={'run_id':'00000000-0000-0000-0000-000000000001'}
    journal={'run_id':'00000000-0000-0000-0000-000000000002','phase':'running',
        'cycle':1,'failures':0,'event':event}
    (tmp_path/'git-journal.json').write_text('retained offline journal')
    def require(ok,msg):
        if not ok: raise RuntimeError(msg)
    def wait(check,*args):
        assert check()
    worker=SimpleNamespace(Acceptance=object,require=require,wait_until=wait,sha=lambda p:'digest')
    measurement=SimpleNamespace(validate_publication=lambda *a,**kw:None)
    cls=module.acceptance_type(worker,None,None,None,None,None,measurement);test=cls.__new__(cls)
    test.f={'project_id':'p'};test.source=tmp_path;test.output=tmp_path;test.held=None
    test.current=lambda:{'status':{'state':4 if live else 1}}
    test.state=lambda *a:{'status':{'state':1,'pid':0}}
    test.observer=SimpleNamespace(profile=tmp_path,locked=nullcontext)
    def read():
        assert not live and not children_live,'Journal read before original process/children reaped'
        calls.append('journal_read');return journal if 'terminate' in calls else previous
    def recover(*a):
        calls.append('recover');journal['phase']='recovered'
    test.journal=SimpleNamespace(read=read,recover=recover)
    test.source_before=lambda *a:{'fixed':'source'}
    test.unchanged_source=lambda *a:calls.append('source_checked')
    test.stable=lambda doc:doc;test.publication=lambda:{'fixed':'publication'}
    class Hint:
        def __enter__(self):
            assert not live;calls.append('arm');return self
        def __exit__(self,*a):calls.append('hint_close')
    test.quiet_hint=Hint
    def reap():
        nonlocal live
        calls.append('reap');live=False
    def start(*,interrupt):
        assert interrupt is True
        nonlocal live,children_live
        assert calls[-1]=='arm';live=True;children_live=True;calls.append('start')
        test.held=SimpleNamespace(pid=17,require_alive=lambda:calls.append('held_alive'),wait=reap,
            terminate=lambda:calls.append('terminate'))
    test.start=start;test.quiet=lambda hint:calls.append('hint')
    test.terminate_owned_running_process=lambda pid:calls.append('terminate')
    def children():
        nonlocal children_live
        assert not live;children_live=False;calls.append('children_reaped');return []
    test.children=children;test.failed_start=lambda *a:calls.append('refused_start')
    test.unchanged=lambda *a:calls.append('recovered_repeat')
    test.event=lambda *a,**kw:calls.append('event')
    if event=={'status':'unchanged'}:
        test.interrupted_recovery(['commit'])
        assert calls.index('children_reaped')<calls.index('recover')<calls.index('recovered_repeat')
    else:
        with pytest.raises(RuntimeError): test.interrupted_recovery(['commit'])
        assert 'recover' not in calls and 'refused_start' not in calls
    assert calls.index('arm')<calls.index('start')<calls.index('terminate')<calls.index('reap')<calls.index('children_reaped')


@pytest.mark.parametrize('allowed',[True,False])
def test_termination_uses_original_held_handle_only_for_authorized_lifetime(allowed):
    module=api();calls=[]
    def require(ok,msg):
        if not ok: raise RuntimeError(msg)
    def terminate(handle,code):
        calls.append((handle,code));return True
    kernel=SimpleNamespace(TerminateProcess=terminate,
        OpenProcess=lambda *a:pytest.fail('Do not reopen service by PID'))
    native=SimpleNamespace(kernel=kernel,require=lambda ok,msg:require(ok,msg))
    test=SimpleNamespace(native=native,current=lambda:{'status':{'state':4,'pid':17}},event=lambda *a,**kw:None)
    held=module.HeldProcess.__new__(module.HeldProcess)
    held.test=test;held.worker=SimpleNamespace(require=require);held.pid=17
    held.handle=12345;held.interrupt=allowed;held.require_alive=lambda:calls.append('alive')
    if allowed:
        held.terminate();assert calls==['alive','alive',(12345,87)]
    else:
        with pytest.raises(RuntimeError,match='observation-only'): held.terminate()
        assert calls==[]


def test_journal_hint_loads_hash_bound_sibling_under_isolated_python():
    import subprocess,sys
    path=Path(__file__).resolve().parents[2]/'scripts/verification/scm_stock_git_lifecycle.py'
    code="""import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
path=Path(sys.argv[1])
spec=importlib.util.spec_from_file_location('lifecycle',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
cls=module.acceptance_type(SimpleNamespace(Acceptance=object),None,None,None,None,None,None)
test=cls.__new__(cls);test.native=None;test.observer=SimpleNamespace(profile=path.parent)
assert type(test.quiet_hint()).__name__=='JournalRenameHint'
"""
    result=subprocess.run([sys.executable,'-I','-c',code,str(path)],capture_output=True,timeout=10)
    assert result.returncode==0,result.stderr.decode()
