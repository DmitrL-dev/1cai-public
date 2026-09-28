"""Verifier contracts only; constructed observations do not prove native BSL."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
from uuid import UUID

import pytest


def api():
    path=Path(__file__).resolve().parents[2]/'scripts/verification/scm_stock_git_measurement.py'
    assert path.is_file(), 'Stock SCM measurement boundary missing'
    spec=importlib.util.spec_from_file_location('stock_measurement_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def publication(tmp_path):
    source=tmp_path/'source';project=str(UUID(int=1));commit='a'*40;snapshot='b'*64
    report={'observation':{'repository':str(source),'commit':commit},
        'profile_id':'bsl-ls-1.0.5-temurin21.0.12.1-win64-bmp-default-v1:git-v1',
        'scope_id':'whole-repository-bsl','complete':True,'findings':[]}
    receipt={'operation_id':str(UUID(int=2)),'project_id':project,'report':report}
    owner_id=str(UUID(int=3))
    owner={'report_id':owner_id,'report':{'project_id':project,'snapshot_id':snapshot,
        'quality':{'status':'available','provenance':'git_source_verified','commit':commit,
            'profile_id':report['profile_id'],'scope_id':report['scope_id']},
        'business_metrics':{'status':'not_available'}}}
    event={'status':'analyzed','commit':commit,'snapshot_binding':'git_source_verified',
        'observation':report['observation'],'receipt':receipt,'owner_report_id':owner_id}
    doc={'status':{'last_snapshot':snapshot,'error':None,'jobs':[{'phase':'done','operation_id':str(UUID(int=4))}],
                  'reports':[{'after':snapshot,'project_id':project,'operation_id':str(UUID(int=4))}]},
        'findings':{'state':{'report':report},'reports':[receipt],'reports_truncated':False},
        'outbox':[{'id':1,'event':event,'created_at':'2026-09-28T00:00:00+00:00'}],
        'owners':{owner_id:owner},'bindings':{commit:snapshot}}
    return doc,project,source,[commit]


def test_complete_durable_commit_snapshot_owner_and_outbox_binding(tmp_path):
    doc,project,source,commits=publication(tmp_path)
    proof=api().validate_publication(doc,project=project,source=source,commits=commits)
    assert proof['commit']==commits[0] and proof['snapshot_id']==doc['status']['last_snapshot']
    assert proof['findings_reports']==proof['notifications']==1


@pytest.mark.parametrize('changed',[
    'incomplete','wrong_profile','wrong_scope','wrong_repository','wrong_commit','unfinished_capture',
    'capture_error','missing_snapshot','duplicate_job','duplicate_findings','truncated_findings',
    'missing_outbox','wrong_event_commit','unbound_event','receipt_changed','wrong_owner_id',
    'wrong_owner_snapshot','wrong_owner_project','unverified_owner','owner_commit','business_invented'])
def test_cross_context_incomplete_or_duplicate_publication_cannot_qualify(tmp_path,changed):
    doc,project,source,commits=publication(tmp_path);doc=copy.deepcopy(doc)
    report=doc['findings']['state']['report'];event=doc['outbox'][0]['event']
    owner=next(iter(doc['owners'].values()))['report']
    if changed=='incomplete': report['complete']=False
    elif changed=='wrong_profile': report['profile_id']='other'
    elif changed=='wrong_scope': report['scope_id']='other'
    elif changed=='wrong_repository': report['observation']['repository']=str(source.parent/'other')
    elif changed=='wrong_commit': report['observation']['commit']='c'*40
    elif changed=='unfinished_capture': doc['status']['jobs'][0]['phase']='capture'
    elif changed=='capture_error': doc['status']['error']={'code':'failed'}
    elif changed=='missing_snapshot': doc['status']['last_snapshot']=None
    elif changed=='duplicate_job': doc['status']['jobs']*=2
    elif changed=='duplicate_findings': doc['findings']['reports']*=2
    elif changed=='truncated_findings': doc['findings']['reports_truncated']=True
    elif changed=='missing_outbox': doc['outbox']=[]
    elif changed=='wrong_event_commit': event['commit']='c'*40
    elif changed=='unbound_event': event['snapshot_binding']='caller_asserted'
    elif changed=='receipt_changed': event['receipt']={**event['receipt'],'operation_id':str(UUID(int=7))}
    elif changed=='wrong_owner_id': event['owner_report_id']=str(UUID(int=7))
    elif changed=='wrong_owner_snapshot': owner['snapshot_id']='c'*64
    elif changed=='wrong_owner_project': owner['project_id']=str(UUID(int=7))
    elif changed=='unverified_owner': owner['quality']['provenance']='caller_asserted'
    elif changed=='owner_commit': owner['quality']['commit']='c'*40
    elif changed=='business_invented': owner['business_metrics']['status']='available'
    with pytest.raises((RuntimeError,ValueError)):
        api().validate_publication(doc,project=project,source=source,commits=commits)


@pytest.mark.parametrize('change',['pid','win32','service','state','bool_pid'])
def test_stop_requires_terminal_success_and_zero_pid(change):
    row={'state':1,'win32_exit':0,'service_exit':0,'pid':0}
    row[{'pid':'pid','win32':'win32_exit','service':'service_exit','state':'state','bool_pid':'pid'}[change]]=False if change=='bool_pid' else 4
    with pytest.raises(RuntimeError): api().validate_stopped(row)


def test_clean_stop_is_distinct_from_expected_worker_failure():
    module=api();module.validate_stopped({'state':1,'win32_exit':0,'service_exit':0,'pid':0})
    module.validate_stopped({'state':1,'win32_exit':1066,'service_exit':2,'pid':0},failed=True)
    with pytest.raises(RuntimeError):
        module.validate_stopped({'state':1,'win32_exit':1066,'service_exit':2,'pid':0})


def test_windows_command_line_preserves_quoted_profile_paths(tmp_path):
    if sys.platform!='win32': pytest.skip('Native Windows command-line parser required')
    values=[str(tmp_path/'two words/java.exe'),'-Duser.home='+str(tmp_path/'two words/profile'),'-jar',str(tmp_path/'two words/server.jar')]
    assert api().command_line_argv(subprocess.list2cmdline(values))==values


def test_native_java_proof_requires_fixed_argv_parent_and_localservice(tmp_path):
    module=api();runtime=tmp_path/'runtimes/profile';scratch=tmp_path/'diagnostic-runs'
    attempt=scratch/str(UUID(int=12));argv=module.expected_java_argv(runtime,attempt)
    row={'ProcessId':17,'ParentProcessId':11,'ExecutablePath':str(runtime/'jdk/bin/java.exe'),
        'CommandLine':subprocess.list2cmdline(argv)}
    process={'pid':17,'image':row['ExecutablePath'],'token_user_sid':'S-1-5-19'}
    assert module.validate_java(row,process,service_pid=11,runtime=runtime,scratch=scratch)['argv']==argv
    for key,value in [('ParentProcessId',12),('ExecutablePath',str(tmp_path/'foreign/java.exe'))]:
        changed={**row,key:value}
        with pytest.raises(RuntimeError): module.validate_java(changed,process,service_pid=11,runtime=runtime,scratch=scratch)
    with pytest.raises(RuntimeError):
        module.validate_java(row,{**process,'token_user_sid':'S-1-5-18'},service_pid=11,runtime=runtime,scratch=scratch)
    row['CommandLine']=subprocess.list2cmdline([*argv,'--override'])
    with pytest.raises(RuntimeError): module.validate_java(row,process,service_pid=11,runtime=runtime,scratch=scratch)
