"""Strict observation bindings for an owned stock LocalService qualification.

These validators grant no SCM authority. Native proofs are collected separately;
constructed dictionaries or a success boolean alone never prove execution.
"""
import ctypes
from ctypes import wintypes as W
from pathlib import Path
import re
from uuid import UUID


def require(condition,message):
    if not condition: raise RuntimeError(message)


def validate_stopped(status,*,failed=False):
    expected={'state':1,'pid':0,'win32_exit':1066 if failed else 0,'service_exit':2 if failed else 0}
    require(all(type(status.get(key)) is int and status[key]==value for key,value in expected.items()),
        'Terminal SCM state/exit/PID binding differs')


def validate_refused_start_control(result,*,sc,service_name):
    # StartService may acknowledge START_PENDING or return the actual service
    # specific error. Access denied/timeout/unknown capture cannot qualify an
    # expected worker refusal using a previous lifetime's unchanged exit status.
    # https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-startservicew
    require(result.get('argv')==[str(sc),'start',service_name]
        and type(result.get('exit_code')) is int and result['exit_code'] in (0,1066)
        and result.get('child_reaped') is True and result.get('timed_out') is False
        and result.get('output_limit_exceeded') is False and result.get('process_error') is None,
        'Expected refusal lacks acknowledged fresh bounded SCM start')


def command_line_argv(command):
    # https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-commandlinetoargvw
    require(type(command) is str and 0<len(command)<=32768 and '\0' not in command,'Invalid process command line')
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    parse=shell.CommandLineToArgvW
    parse.argtypes,parse.restype=[W.LPCWSTR,ctypes.POINTER(ctypes.c_int)],ctypes.POINTER(W.LPWSTR)
    kernel.LocalFree.argtypes,kernel.LocalFree.restype=[ctypes.c_void_p],ctypes.c_void_p
    count=ctypes.c_int();values=parse(command,ctypes.byref(count))
    require(bool(values),'Cannot parse native command line')
    try:
        require(1<=count.value<=64,'Native argv exceeds bound')
        return [values[index] for index in range(count.value)]
    finally:
        require(not kernel.LocalFree(ctypes.cast(values,ctypes.c_void_p)),'Cannot release native argv')


def expected_java_argv(runtime,attempt):
    config=attempt/'configuration.json'
    return [str(runtime/'jdk/bin/java.exe'),'-Xmx512m','-XX:ActiveProcessorCount=2','-Dfile.encoding=UTF-8',
        '-Duser.home='+str(attempt/'profile'),'-Djava.io.tmpdir='+str(attempt/'tmp'),
        '-Dsentry.dsn=','-Dsentry.enabled=false','-Dapp.globalConfiguration.path='+str(config),
        '-Dapp.configuration.path='+str(config),'-jar',str(runtime/'bsl-language-server.jar'),'analyze',
        '--srcDir',str(attempt/'src'),'--workspaceDir',str(attempt/'src'),'--outputDir',str(attempt/'report'),
        '--configuration',str(config),'--reporter','json','--silent']


def validate_java(row,process,*,service_pid,runtime,scratch):
    image=runtime/'jdk/bin/java.exe'
    require(type(service_pid) is int and service_pid>0 and type(row.get('ProcessId')) is int
        and row['ProcessId']>0 and row.get('ParentProcessId')==service_pid
        and process.get('pid')==row['ProcessId'] and process.get('token_user_sid')=='S-1-5-19'
        and Path(row.get('ExecutablePath',''))==Path(process.get('image',''))==image,
        'Actual Java parent/image/LocalService token differs')
    argv=command_line_argv(row.get('CommandLine'))
    require(len(argv)==24 and argv[13]=='--srcDir','Actual native BSL argv differs')
    attempt=Path(argv[14]).parent
    try: canonical=str(UUID(attempt.name))
    except (ValueError,AttributeError): canonical=None
    require(attempt.parent==scratch and attempt.name==canonical and argv==expected_java_argv(runtime,attempt),
        'Native BSL command escapes fixed pinned runtime/scratch')
    return {**process,'parent_pid':service_pid,'argv':argv,'attempt':str(attempt),
        'private_scratch_read':False,'raw_bsl_report_retained':False}


def validate_publication(document,*,project,source,commits):
    from rentgen_diagnostics.git_bsl_analyzer import PROFILE_ID,SCOPE_ID
    source=Path(source).resolve()
    require(type(commits) is list and 1<=len(commits)<=2 and len(set(commits))==len(commits)
        and all(type(c) is str and re.fullmatch('[a-f0-9]{40}',c) for c in commits),'Invalid expected fixture commits')
    status,findings,outbox,owners=(document[key] for key in ('status','findings','outbox','owners'))
    count=len(commits);snapshot=status.get('last_snapshot')
    require(type(snapshot) is str and re.fullmatch('[a-f0-9]{64}',snapshot) and status.get('error') is None,
        'Complete current snapshot required')
    require(len(status['jobs'])==len(status['reports'])==count
        and all(job.get('phase')=='done' for job in status['jobs'])
        and len({job['operation_id'] for job in status['jobs']})==count
        and {report['operation_id'] for report in status['reports']}=={job['operation_id'] for job in status['jobs']}
        and all(report.get('project_id')==project for report in status['reports']),
        'Capture publications are incomplete or duplicated')
    snapshots={report['after'] for report in status['reports']}
    require(len(snapshots)==count and snapshot in snapshots,'Snapshot history differs')
    require(set(document['bindings'])==set(commits) and set(document['bindings'].values())==snapshots,
        'Durable Git evidence/snapshot binding differs')
    report=findings['state']['report'] if findings['state'] else None
    require(type(report) is dict and report.get('complete') is True
        and report.get('profile_id')==PROFILE_ID and report.get('scope_id')==SCOPE_ID
        and report['observation']['repository']==str(source) and report['observation']['commit']==commits[-1],
        'Complete findings profile/source/commit differs')
    receipts=findings['reports']
    require(findings.get('reports_truncated') is False and len(receipts)==count
        and {item['report']['observation']['commit'] for item in receipts}==set(commits),
        'Durable findings history differs')
    require(len(outbox)==len(owners)==count and [item['id'] for item in outbox]==list(range(1,count+1)),
        'Notifications were duplicated, acknowledged or omitted')
    owner_ids=[];owner_snapshots=[]
    for item,commit in zip(outbox,commits):
        event=item['event'];receipt=event.get('receipt')
        require(event.get('status')=='analyzed' and event.get('commit')==commit
            and event.get('snapshot_binding')=='git_source_verified'
            and event.get('observation',{}).get('repository')==str(source)
            and event.get('observation',{}).get('commit')==commit
            and receipt in receipts and receipt.get('project_id')==project
            and receipt['report']['observation']==event['observation']
            and receipt['report'].get('complete') is True and receipt['report'].get('profile_id')==PROFILE_ID
            and receipt['report'].get('scope_id')==SCOPE_ID,'Notification/findings receipt binding differs')
        owner_id=event.get('owner_report_id');owner_ids.append(owner_id)
        require(owner_id in owners,'Owner receipt missing')
        owner=owners[owner_id];stored=owner['report'];quality=stored['quality']
        require(owner.get('report_id')==owner_id and stored.get('project_id')==project
            and stored.get('snapshot_id')==document['bindings'][commit] and quality.get('status')=='available'
            and quality.get('provenance')=='git_source_verified' and quality.get('commit')==commit
            and quality.get('profile_id')==PROFILE_ID and quality.get('scope_id')==SCOPE_ID
            and stored['business_metrics'].get('status')=='not_available','Verified owner-report context differs')
        owner_snapshots.append(stored['snapshot_id'])
    require(len(set(owner_ids))==len(set(owner_snapshots))==count and owner_snapshots[-1]==snapshot,
        'New commit must have a distinct owner receipt/snapshot')
    return {'commit':commits[-1],'snapshot_id':snapshot,'owner_report_ids':owner_ids,
        'findings_reports':count,'notifications':count}
