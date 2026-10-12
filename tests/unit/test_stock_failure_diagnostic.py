"""Offline diagnostic contracts: no SCM, accounts or provider requests."""
import json
from types import SimpleNamespace

import pytest

from tests.unit.test_stock_git_scm_lifecycle import api


def test_nested_operation_keeps_original_exception_and_no_secrets():
    module=api()
    secret='TOKEN-super-private'
    error=PermissionError(13,secret,'C:/Users/'+secret+'/observer.sqlite3')
    error.filename2='C:/'+secret+'/destination'
    with pytest.raises(PermissionError) as caught:
        with module.failure_operation('analyzed.published'):
            with module.failure_operation('publication.database','ignored'):
                raise error
    assert caught.value is error
    result=module.failure_diagnostic(error);detail=result['diagnostic']
    assert detail['operation']=='publication.database'
    assert detail['errno']==13 and detail['path_source']=='exception_filename'
    assert detail['path']['leaf']=='observer.sqlite3'
    assert detail['destination']['leaf']=='<redacted>'
    encoded=json.dumps(result)
    assert secret not in encoded and 'C:/' not in encoded and 'ignored' not in encoded
    assert detail['traceback'] and detail['traceback'][0]['file']=='<external>'
    assert module.failure_diagnostic(error)['diagnostic']['path']['id']!=detail['path']['id']


def test_unrelated_handled_error_does_not_contaminate_next_failure():
    module=api()
    try:
        with module.failure_operation('publication.native_process'):
            raise PermissionError('handled-secret')
    except PermissionError:
        pass
    with pytest.raises(PermissionError) as caught:
        with module.failure_operation('publication.save','/private/publication-next.json'):
            raise PermissionError('new-secret')
    detail=module.failure_diagnostic(caught.value)['diagnostic']
    assert detail['operation']=='publication.save'
    assert detail['path']['leaf']=='publication-next.json'
    assert detail['path_source']=='operation_target'
    assert 'secret' not in json.dumps(detail)


def test_traceback_is_bounded_and_does_not_include_cause_or_locals():
    module=api()
    def recurse(n):
        hidden='SENSITIVE-local'
        if n: return recurse(n-1)
        raise PermissionError(hidden) from RuntimeError('SECRET-cause')
    with pytest.raises(PermissionError) as caught: recurse(25)
    detail=module.failure_diagnostic(caught.value)['diagnostic']
    assert len(detail['traceback'])==16 and detail['traceback_truncated'] is True
    assert 'SENSITIVE' not in json.dumps(detail) and 'SECRET' not in json.dumps(detail)
    assert detail['operation']=='unclassified' and detail['path'] is None


@pytest.mark.parametrize('operation',['status','findings','outbox'])
def test_actual_publication_tags_failure_without_retry(operation):
    module=api();calls=[]
    cls=module.acceptance_type(SimpleNamespace(Acceptance=object),None,None,None,None,None,None)
    test=cls.__new__(cls)
    def call(name):
        calls.append(name)
        if name==operation: raise PermissionError('SECRET-message')
        return {}
    test.observer=SimpleNamespace(status=lambda:call('status'),findings_status=lambda:call('findings'))
    test.outbox=SimpleNamespace(peek=lambda:call('outbox'))
    with pytest.raises(PermissionError) as caught: test.publication()
    detail=module.failure_diagnostic(caught.value)['diagnostic']
    assert detail['operation']=='publication.'+operation
    assert any(f['file']=='scm_stock_git_lifecycle.py' and f['function']=='publication' for f in detail['traceback'])
    assert calls.count(operation)==1


@pytest.mark.parametrize('collector_fails',[False,True])
def test_run_lifecycle_retains_safe_diagnostic_and_still_cleans_up(tmp_path,collector_fails):
    module=api();calls=[];events=[]
    def fail():
        calls.append('exercise')
        with module.failure_operation('publication.save',tmp_path/'publication-next.json'):
            raise PermissionError(13,'TOKEN-secret')
    def event(name,**detail):
        events.append((name,detail));(tmp_path/'events.jsonl').write_text(json.dumps(events))
    def cleanup(): calls.append('cleanup');return []
    test=SimpleNamespace(exercise=fail,event=event,cleanup=cleanup,retain=lambda:{'complete':True},
        output=tmp_path,spec=SimpleNamespace(service_name='test'),native=SimpleNamespace(query=lambda _:{'exists':False}))
    def require(ok,msg):
        if not ok: raise RuntimeError(msg)
    worker=SimpleNamespace(require=require,BUDGET=SimpleNamespace(begin_cleanup=lambda:None),sha=lambda _: 'digest',
        save=lambda p,v:p.write_text(json.dumps(v)))
    if collector_fails:
        def broken(_): raise RuntimeError('SECRET-diagnostic-failure')
        module.failure_diagnostic=broken
    result=module.run_lifecycle(test,worker,{})
    assert calls==['exercise','cleanup'] and result['native_stock_git_accepted'] is False
    assert result['cleanup_errors']==[]
    if collector_fails:
        assert result['failure']['diagnostic']['unavailable'] is True
    else:
        assert result['failure']['diagnostic']['operation']=='publication.save'
    assert events[0][1]==result['failure']
    assert 'TOKEN-secret' not in (tmp_path/'acceptance.json').read_text()
    assert str(tmp_path) not in json.dumps(result['failure'])


def test_database_failure_carries_target_and_original_exception(tmp_path,monkeypatch):
    module=api();calls=[]
    cls=module.acceptance_type(SimpleNamespace(Acceptance=object),None,None,None,None,None,None)
    test=cls.__new__(cls)
    test.observer=SimpleNamespace(status=lambda:{},findings_status=lambda:{'state':{}},database=tmp_path/'observer.sqlite3')
    test.outbox=SimpleNamespace(peek=lambda:[])
    error=PermissionError(13,'private-database-uri')
    def connect(*args,**kwargs): calls.append(1);raise error
    monkeypatch.setattr(module.sqlite3,'connect',connect)
    with pytest.raises(PermissionError) as caught: test.publication()
    assert caught.value is error and calls==[1]
    detail=module.failure_diagnostic(error)['diagnostic']
    assert detail['operation']=='publication.database' and detail['path']['leaf']=='observer.sqlite3'
    assert 'private-database-uri' not in json.dumps(detail)
