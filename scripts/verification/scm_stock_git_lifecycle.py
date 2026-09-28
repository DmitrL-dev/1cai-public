"""Full owned stock Git/native BSL lifecycle; no production deployment."""
if not __debug__:
    raise RuntimeError('Stock acceptance requires assertions; do not use Python -O')

import ctypes
from ctypes import wintypes as W
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
from uuid import uuid4

SCOPE='stock schema3 Git/native BSL full owned lifecycle'



def validate_failure_events(rows,service_name,pids):
    """Read diagnostics only when their PID was actually observed by SCM."""
    from rentgen_core.service_entry import _FAILURE_STAGES,_FAILURE_KINDS,_FAILURE_REASONS
    def require(ok):
        if not ok: raise RuntimeError('Failure event binding or fixed fields differ')
    require(type(rows) is list and 0<len(rows)<=16 and type(pids) is set
        and pids and all(type(pid) is int and pid>0 for pid in pids))
    matches=[];records=set()
    for row in rows:
        require(type(row) is dict and set(row)=={'provider','event_id','level','record_id','utc','data'})
        require(row['provider']=='Rentgen.Core.Service' and type(row['event_id']) is int
            and row['event_id']==1 and type(row['level']) is int and row['level']==2
            and type(row['record_id']) is int and row['record_id']>0 and row['record_id'] not in records)
        records.add(row['record_id'])
        require(type(row['utc']) is str and datetime.fromisoformat(row['utc'].replace('Z','+00:00')).tzinfo is not None)
        require(type(row['data']) is str and len(row['data'])<=512)
        def pairs(items):
            result=dict(items);require(len(result)==len(items));return result
        doc=json.loads(row['data'],object_pairs_hook=pairs)
        require(type(doc) is dict and set(doc)=={'schema','event','service_name','pid','failure'}
            and type(doc['schema']) is int and doc['schema']==1 and doc['event']=='service_failed'
            and type(doc['service_name']) is str and type(doc['pid']) is int and doc['pid']>0)
        detail=doc['failure']
        require(type(detail) is dict and set(detail)=={'stage','kind','reason'})
        for key,values in (('stage',_FAILURE_STAGES),('kind',_FAILURE_KINDS),('reason',_FAILURE_REASONS)):
            require(type(detail[key]) is str and detail[key] in values)
        if doc['service_name']==service_name:
            require(doc['pid'] in pids);matches.append(doc)
    require(0<len(matches)<=4)
    return matches

def require_ready(worker,context):
    worker.require(context[5].get('exists') is False and all(context[6].get(key) is True
        for key in ('elevated','create_access','backup_privilege','restore_privilege')),
        'Fresh service and actual elevated SCM/backup/restore authority required')


def exercise(test):
    test.install()
    commits=[test.metadata['fixture_commit']]
    first=test.analyzed('first',commits)
    commits.append(test.next_commit())
    second=test.analyzed('next',commits)
    if first['commit']==second['commit'] or first['snapshot_id']==second['snapshot_id']:
        raise RuntimeError('Operator commit did not produce a new bound snapshot')
    test.unchanged('repeat',commits)
    test.interrupted_recovery(commits)
    test.history_refusal(commits)
    test.context_refusal(commits)
    test.final_inputs()
    return {'measurement_validated':True,'native_scope':SCOPE,'commits':commits,
        'first':first,'next':second,'interruption_scope':'quiet continuous wait after unchanged tick',
        'active_bsl_interruption_exercised':False,'raw_bsl_report_retained':False}


def run_lifecycle(test,worker,metadata):
    failure,measurement=None,None
    try:
        measurement=test.exercise()
        worker.require(type(measurement) is dict and measurement.get('measurement_validated') is True
            and measurement.get('native_scope')==SCOPE and len(measurement.get('commits',[]))==2,
            'Full native stock measurement proof missing')
    except BaseException as error:
        failure={'type':type(error).__name__,'message':str(error)[:400]}
        test.event('stock_failure',**failure)
        try:
            observe=getattr(test,'failure_telemetry',None)
            if callable(observe): observe()
        except BaseException as error:
            test.event('stock_failure_telemetry_unavailable',type=type(error).__name__)
    finally:
        worker.BUDGET.begin_cleanup()
        try: cleanup=test.cleanup()
        except BaseException as error: cleanup=[{'stage':'cleanup','type':type(error).__name__}]
        try:
            retention=test.retain()
            worker.require(retention.get('complete') is True,'Raw stock evidence incomplete')
        except BaseException as error:
            retention=None;cleanup.append({'stage':'retention','type':type(error).__name__})
    try:
        remaining=test.native.query(test.spec.service_name)['exists']
        if remaining: cleanup.append({'stage':'remaining_service'})
    except BaseException as error:
        remaining=True;cleanup.append({'stage':'final_service_query','type':type(error).__name__})
    events=test.output/'events.jsonl';retained=events.is_file() and events.stat().st_size>0
    result={**metadata,'scope':SCOPE,'native_stock_git_accepted':failure is None and not cleanup and not remaining and retained,
        'failure':failure,'measurement':measurement,'cleanup_errors':cleanup,'retention':retention,
        'service_name':test.spec.service_name,'service_exists_after':remaining,
        'events_sha256':worker.sha(events) if retained else None,'events_retained':retained,
        'full_product_ready':False,'production_deployment':False,'independent_review':False,
        'recorded_utc':datetime.now(timezone.utc).isoformat()}
    worker.save(test.output/'acceptance.json',result)
    return result


class HeldProcess:
    """Wait on the same verified native object, never a later process with its PID."""
    def __init__(self,test,worker,pid):
        self.test,self.worker,self.pid=test,worker,pid;self.handle=None
        kernel=test.native.kernel
        self.handle=test.native.require(kernel.OpenProcess(0x1000|0x100000,False,pid),'OpenHeldStockService')
        try:
            size=W.DWORD(32768);image=ctypes.create_unicode_buffer(size.value)
            test.native.require(kernel.QueryFullProcessImageNameW(self.handle,0,image,ctypes.byref(size)),'ReadHeldStockImage')
            worker.require(Path(image.value).resolve()==worker.PYTHON,'Held stock image changed')
            api=worker._WindowsTokenAPI();token=W.HANDLE()
            test.native.require(api.security.OpenProcessToken(self.handle,8,ctypes.byref(token)),'ReadHeldStockToken')
            try:
                storage,sid=api.token_user(token);value=api.sid_string(sid)
                try: worker.require(value.value==worker.SID,'Held stock LocalService SID changed')
                finally: api.free_string(value)
            finally: api.close_token(token)
            row=test.current()
            worker.require(row['status']['state']==4 and row['status']['pid']==pid,'SCM/held process binding changed')
            test.event('stock_process_held',pid=pid,image=str(worker.PYTHON),token_user_sid=worker.SID)
        except BaseException:
            self.close();raise

    def wait(self):
        # https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject
        kernel=self.test.native.kernel
        wait=kernel.WaitForSingleObject;wait.argtypes,wait.restype=[W.HANDLE,W.DWORD],W.DWORD
        self.worker.require(wait(self.handle,int(self.worker.bounded(30)*1000))==0,'Original stock process did not exit')
        self.test.event('stock_process_reaped',pid=self.pid,same_held_handle=True)
        self.close()

    def close(self):
        if self.handle is not None:
            self.test.native.require(self.test.native.kernel.CloseHandle(self.handle),'CloseHeldStockProcess')
            self.handle=None



def fixture_owner_profile(service_observer,owner):
    """Authorize the owned verifier and preserve the LocalService binding.

    The owner must retain project admin and analysis permissions. This view
    reads durable publications and tests the file lease after SCM exits. The
    installed service retains the unchanged production Observer policy.
    The view changes neither the database binding nor service membership.
    """
    from dataclasses import asdict
    from rentgen_core.context import Principal
    from rentgen_core.errors import CoreError
    from rentgen_core.observer import Observer
    service=Principal('windows-sid:S-1-5-19','local_os')
    if service_observer.principal!=service or owner==service:
        raise CoreError('OBSERVER_PROFILE_MISMATCH','Owned LocalService fixture required')
    class OwnerView(Observer):
        def _context(self,*,write=False):
            return self.runtime.state_context(owner,self.project_id,
                permissions={'project:read','project:admin','analysis:run'})
        def _binding(self,ctx):
            if ctx.principal!=owner:
                raise CoreError('OBSERVER_PROFILE_MISMATCH','Fixture owner context changed')
            return {**super()._binding(ctx),'principal':asdict(service)}
    return OwnerView(service_observer.runtime,owner,service_observer.project_id,
        service_observer.profile,**({'git_trust':service_observer._git_options['trust']}
            if service_observer._git_options else {}))

def acceptance_type(worker,fixture,probe,control,stock_control,acl,measurement):
    class StockAcceptance(worker.Acceptance):
        def __init__(self,context,output,metadata,files):
            require_ready(worker,context)
            super().__init__(context,output)
            self.metadata,self.input_files=metadata,files
            self.source=worker.ROOT/'localservice/source'
            self.module=self.source/'CommonModules/ServiceProbe/Ext/Module.bsl'
            self.initial_module=self.module.read_bytes()
            self.runtime=worker.ROOT/'localservice/diagnostics/Rentgen/runtimes'/metadata['profile_id']
            self.scratch=worker.ROOT/'localservice/diagnostics/Rentgen/diagnostic-runs'
            self.installer=stock_control.create_installer(control,probe,self.native,worker.B.parent,
                self.authority,output,files)
            self.spec=self.installer.spec
            from rentgen_core._git_policy import GitRepositoryTrust
            from rentgen_core.local_identity import current_windows_principal
            # Parent observations use the actual fixture owner so revoking LS
            # cannot revoke the coordinator's evidence access.
            self.owner=current_windows_principal()
            service_observer=worker.Observer(self.observer.runtime,self.observer.principal,
                self.f['project_id'],self.observer.profile,git_trust=GitRepositoryTrust(self.source))
            self.observer=fixture_owner_profile(service_observer,self.owner)
            self.context=self.observer._context(write=True)
            from rentgen_core.git_watcher import SchedulerJournal,NotificationOutbox
            self.journal=SchedulerJournal(self.observer.profile/'git-journal.json')
            self.outbox=NotificationOutbox(self.observer.profile/'git-outbox.json')
            self.query_sequence=0;self.held=None;self.service_pids=set()
            self.java_proofs={};self.next_module=None;self.final_commit=None

        def prepare_acl(self):
            original=self.backup_acl(worker.ROOT,'fixture')
            self.restore_acl(worker.ROOT,original,'fixture-preflight-restore')
            self.backup_acl(worker.RUNTIME,'runtime')
            for root in (worker.RUNTIME,worker.ROOT):
                saved=next(p for candidate,p,_ in self.acl_backups if candidate==root)
                before=worker.acl_entries(saved,root)
                worker.require({root/name for name in worker.inventory(root)}==set(before),'Stock ACL inventory changed')
                requested=self.output/(root.name+'-requested.acl')
                worker.write_acl_policy(requested,root,acl.temporary_policy(worker,root,before))
                digest=worker.sha(requested)
                self.icacls([root.parent,'/restore',requested,'/Q'],root.name+'-apply-policy')
                worker.require(worker.sha(requested)==digest,'Requested stock ACL changed')
                observed=self.output/(root.name+'-temporary.acl')
                self.icacls([root,'/save',observed,'/T','/Q'],root.name+'-policy')
                rows=worker.acl_entries(observed,root)
                worker.require(set(rows)==set(before),'Stock ACL scope changed')
                self.event('temporary_acl_verified',root=str(root),observed_sha256=worker.sha(observed),
                    requested_sha256=digest,**acl.verify_policy(worker,root,rows))

        def install(self):
            self.prepare_acl()
            worker.require(not self.native.query(worker.NAME)['exists'],'Service appeared before stock creation')
            self.installer.install(self.spec,start=False)
            self.created=self.installer.created
            self.current();self.event('stock_service_created',binary_path=self.spec.binary_path)

        def processes(self):
            self.query_sequence+=1
            worker.require(self.query_sequence<=200,'Stock native process observations exceed bound')
            pwsh=shutil.which('pwsh.exe');worker.require(pwsh is not None,'PowerShell 7 required')
            script="$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); " \
                "ConvertTo-Json -Compress -InputObject @(Get-CimInstance -ClassName Win32_Process " \
                "-Filter \"Name='java.exe' OR Name='git.exe' OR Name='bsl-scan.exe' OR Name='python.exe'\" " \
                "-Property ProcessId,ParentProcessId,ExecutablePath,CommandLine | " \
                "Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine)"
            label='stock-processes-'+str(self.query_sequence)
            result=probe.capture((pwsh,'-NoProfile','-NonInteractive','-Command',script),dict(os.environ),self.output,label)
            worker.save(self.output/(label+'.json'),result)
            worker.require(result['exit_code']==0 and result['child_reaped'] is True and not result['timed_out']
                and not result['output_limit_exceeded'] and result['process_error'] is None,'Native process inventory failed')
            rows=json.loads(probe._raw(result,'stdout').decode('utf-8-sig'))
            worker.require(type(rows) is list and len(rows)<=100 and all(type(row) is dict
                and type(row.get('ProcessId')) is int and row['ProcessId']>0 and row.get('ExecutablePath') for row in rows),
                'Native process inventory is incomplete')
            return rows

        def children(self):
            owned=[]
            for row in self.processes():
                # The verifier itself uses the same copied interpreter as SCM.
                # Its live PID is not a service child and must not prevent STOP
                # or cleanup from completing after the real owned processes exit.
                if row['ProcessId']==os.getpid(): continue
                image=Path(row['ExecutablePath'])
                selected=image in (worker.PYTHON,worker.ROOT/'bsl-scan.exe',self.runtime/'jdk/bin/java.exe')
                if image.name.casefold()=='git.exe':
                    argv=measurement.command_line_argv(row.get('CommandLine'))
                    selected=selected or any(argv[i]=='-C' and Path(argv[i+1])==self.source for i in range(len(argv)-1))
                if selected: owned.append(row)
            return owned

        def failure_telemetry(self):
            pwsh=shutil.which('pwsh.exe');worker.require(pwsh is not None,'PowerShell 7 required')
            script="$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); " \
                "$filter=\"*[System[Provider[@Name='Rentgen.Core.Service'] and EventID=1 " \
                "and TimeCreated[timediff(@SystemTime)<=1200000]]]\"; " \
                "$rows=@(Get-WinEvent -LogName Application -FilterXPath $filter -MaxEvents 16 | ForEach-Object { " \
                "@{provider=$_.ProviderName;event_id=$_.Id;level=$_.Level;record_id=$_.RecordId;" \
                "utc=$_.TimeCreated.ToUniversalTime().ToString('o');data=$_.Properties[0].Value}}); " \
                "ConvertTo-Json -Compress -InputObject $rows"
            label='stock-failure-events'
            result=probe.capture((pwsh,'-NoProfile','-NonInteractive','-Command',script),dict(os.environ),self.output,label)
            worker.save(self.output/(label+'.json'),result)
            worker.require(result['exit_code']==0 and result['child_reaped'] is True and not result['timed_out']
                and not result['output_limit_exceeded'] and result['process_error'] is None,'Failure event read incomplete')
            raw=(self.output/'events.jsonl').read_bytes();worker.require(len(raw)<=4*1024**2,'Event inventory exceeds bound')
            observations=[json.loads(line) for line in raw.splitlines()]
            pids={row['status']['pid'] for row in observations if row['kind']=='service_status' and row['status']['pid']>0}
            rows=json.loads(probe._raw(result,'stdout').decode('utf-8-sig'))
            matches=validate_failure_events(rows,self.spec.service_name,pids)
            for doc in matches:
                self.event('stock_service_failure_detail',pid=doc['pid'],failure=doc['failure'],
                    capture_sha256=worker.sha(self.output/(label+'.json')),observed_scm_pid=True)

        def source_guard(self):
            files=worker.inventory(self.source)
            return {'files':files,'owners':{name:self.native.owner(self.source/name) for name in files}}

        def source_before(self,label):
            before=self.source_guard();path=self.output/('source-'+label+'-before.json')
            worker.save(path,before)
            self.event('stock_source_before',label=label,manifest_sha256=worker.sha(path),entries=len(before['files']))
            return before

        def unchanged_source(self,label,before):
            after=self.source_guard()
            worker.require(after==before,'Stock lifetime changed source bytes or owners')
            path=self.output/('source-'+label+'-after.json');worker.save(path,after)
            self.event('stock_source_unchanged',label=label,manifest_sha256=worker.sha(path),entries=len(after['files']))

        def start(self):
            worker.require(self.held is None,'Previous held process not closed')
            row=super().start();pid=row['status']['pid']
            self.held=HeldProcess(self,worker,pid);self.service_pids.add(pid)
            return row

        def stop(self):
            row=super().stop();measurement.validate_stopped(row['status'])
            worker.require(self.held is not None,'Stock stop lost original process handle')
            self.held.wait();self.held=None
            worker.wait_until(lambda:not self.children(),45,'stock children exit after STOP')
            journal=self.journal.read()
            worker.require(journal and journal['phase']=='idle' and journal['event']=={'status':'stopped'},'STOP journal is not idle')
            self.event('stock_clean_stop',pid=0,win32_exit=0,service_exit=0,lease_released=True,
                original_process_reaped=True,no_owned_children=True,journal=journal)
            return row

        def publication(self):
            from rentgen_core.owner_report_store import OwnerReportStore
            status=self.observer.status();findings=self.observer.findings_status();events=self.outbox.peek()
            bindings={};owners={}
            if findings['state'] is not None:
                with sqlite3.connect(self.observer.database.as_uri()+'?mode=ro',uri=True) as db:
                    rows=db.execute('SELECT commit_id,snapshot_id FROM finding_binding LIMIT 3').fetchall()
                worker.require(len(rows)<=2,'Unexpected fixture findings bindings')
                bindings=dict(rows)
                store=OwnerReportStore(self.context.state.path.parent/'owner-reports')
                for item in events:
                    event=item['event']
                    if event.get('status')!='analyzed': continue
                    commit=event['commit'];owner_id=event['owner_report_id']
                    owners[owner_id]=store.get(owner_id,expected_project_id=self.f['project_id'],
                        expected_snapshot_id=bindings[commit],authorize=lambda:self.observer._context(write=True))
            return {'status':status,'findings':findings,'outbox':events,'owners':owners,'bindings':bindings}

        def stable(self,document):
            return {**document,'status':self.identity(document['status'])}

        def published(self,label,commits,*,native_bsl=False):
            def inspect():
                row=self.current();worker.require(row['status']['state']==4,'Stock service stopped before findings')
                if native_bsl and label not in self.java_proofs:
                    for child in self.processes():
                        if Path(child['ExecutablePath'])!=self.runtime/'jdk/bin/java.exe': continue
                        try: process=self.native.process(child['ProcessId'])
                        except Exception as error:
                            if getattr(error,'code',None)==87: continue  # exited during read-only sampling
                            raise
                        proof=measurement.validate_java(child,process,service_pid=self.held.pid,runtime=self.runtime,scratch=self.scratch)
                        self.java_proofs[label]=proof;self.event('stock_native_bsl_process',label=label,**proof)
                doc=self.publication();events=doc['outbox']
                worker.require(all(item['event'].get('status')=='analyzed' for item in events),'Stock analyzer reported failure')
                worker.require(len(events)<=len(commits),'Duplicate stock notification')
                if len(events)!=len(commits): return None
                proof=measurement.validate_publication(doc,project=self.f['project_id'],source=self.source,commits=commits)
                worker.require(not native_bsl or label in self.java_proofs,'Native BSL process window was not proved')
                worker.save(self.output/('publication-'+label+'.json'),doc)
                return proof
            return worker.wait_until(inspect,180,'stock complete publication '+label)

        def analyzed(self,label,commits):
            before=self.source_before(label);self.start()
            proof=self.published(label,commits,native_bsl=True)
            self.stop();self.unchanged_source(label,before)
            self.event('stock_analyzed',label=label,**proof)
            return proof

        def operator_git(self,label,*args):
            worker.require(self.current()['status']['state']==1,'Operator Git mutation requires STOPPED')
            empty=worker.B/'stock-setup-global.cfg';env=probe.probe_environment(os.environ,isolated_global=empty)
            found=shutil.which('git',path=env.get('PATH',''));worker.require(found is not None,'Operator Git missing')
            git=probe._path(Path(found).absolute(),single_link=False)
            result=probe.capture((str(git),'-c','core.fsmonitor=false','-C',str(self.source),*args),env,self.output,'operator-'+label)
            worker.save(self.output/('operator-'+label+'.json'),result)
            worker.require(result['exit_code']==0 and result['child_reaped'] is True and not result['timed_out']
                and not result['output_limit_exceeded'] and result['process_error'] is None,'Owned operator Git failed')
            return probe._raw(result,'stdout').decode('utf-8').strip()

        def next_commit(self):
            worker.require(self.current()['status']['state']==1,'Input edit requires STOPPED')
            self.next_module=self.initial_module+b'// owned stock SCM second commit\r\n'
            self.module.write_bytes(self.next_module)
            self.operator_git('next-add','add','CommonModules/ServiceProbe/Ext/Module.bsl')
            self.operator_git('next-commit','-c','user.name=Rentgen Isolated Stock Fixture','-c','user.email=stock@example.invalid',
                '-c','commit.gpgsign=false','commit','-q','-m','Owned stock second commit')
            commit=self.operator_git('next-head','rev-parse','--verify','HEAD^{commit}')
            from rentgen_core.git_observer import require_ancestor
            from rentgen_core._git_policy import GitRepositoryTrust
            require_ancestor(self.source,self.metadata['fixture_commit'],commit,trust=GitRepositoryTrust(self.source))
            self.final_commit=commit
            self.event('stock_operator_commit',before=self.metadata['fixture_commit'],after=commit,scm_state=1)
            return commit

        def quiet(self):
            def check():
                worker.require(self.current()['status']['state']==4,'Stock quiet lifetime stopped')
                journal=self.journal.read()
                event=None if journal is None else journal.get('event')
                return journal if journal and journal['phase']=='running' and journal['cycle']>=1 \
                    and type(event) is dict and event.get('status')=='unchanged' else None
            return worker.wait_until(check,45,'stock quiet unchanged tick')

        def unchanged(self,label,commits):
            before=self.source_before(label);stable=self.stable(self.publication())
            self.start();journal=self.quiet();self.published(label,commits);self.stop()
            worker.require(self.stable(self.publication())==stable,'Restart duplicated findings/owner/outbox')
            self.unchanged_source(label,before)
            self.event('stock_repeat_without_publication',label=label,journal=journal)

        def failed_start(self,label):
            worker.require(self.current()['status']['state']==1,'Refusal start requires STOPPED')
            previous=self.installer.sequence
            try: self.installer.start(self.spec)
            except RuntimeError as error: self.event('stock_expected_start_control_error',label=label,type=type(error).__name__)
            worker.require(self.installer.sequence==previous+1,'Refusal start did not invoke a fresh SCM control')
            path=self.output/('control-'+str(self.installer.sequence)+'-start.json')
            result=fixture.read_object(path)
            measurement.validate_refused_start_control(result,sc=self.installer.sc,service_name=self.spec.service_name)
            for stream in ('stdout','stderr'): probe._raw(result,stream)
            self.event('stock_refused_start_control_verified',label=label,control_sha256=worker.sha(path),
                exit_code=result['exit_code'],fresh_control=True,child_reaped=True)
            row=self.state(1,45);measurement.validate_stopped(row['status'],failed=True)
            with self.observer.locked(): pass
            worker.wait_until(lambda:not self.children(),45,'failed stock process exits')
            self.event('stock_start_refused',label=label,status=row['status'],lease_released=True,no_owned_children=True)

        def interrupted_recovery(self,commits):
            before=self.source_before('interrupted-recovery');stable=self.stable(self.publication())
            self.start();journal=self.quiet();pid=self.held.pid
            self.terminate_owned_running_process(pid);row=self.state(1)
            worker.require(row['status']['pid']==0,'Interrupted service retained PID')
            self.held.wait();self.held=None
            worker.wait_until(lambda:not self.children(),45,'interrupted stock children exit')
            with self.observer.locked(): pass
            path=self.observer.profile/'git-journal.json';raw=path.read_bytes()
            worker.require(self.journal.read()==journal and journal['phase']=='running','Interrupted running journal was not retained')
            (self.output/'interrupted-journal.raw').write_bytes(raw)
            self.failed_start('recovery-required')
            worker.require(path.read_bytes()==raw and self.stable(self.publication())==stable,'Refused recovery changed durable publications')
            with self.observer.locked(): self.journal.recover('Owned native SCM interruption explicitly inspected')
            worker.require(self.journal.read()['phase']=='recovered','Explicit scheduler recovery not durable')
            self.event('stock_explicit_recovery',interrupted_run_id=journal['run_id'],pid=pid,
                journal_sha256=worker.sha(self.output/'interrupted-journal.raw'))
            self.unchanged('recovered',commits)
            worker.require(self.stable(self.publication())==stable,'Recovery acknowledged or duplicated publication')
            self.unchanged_source('interrupted-recovery',before)

        def history_refusal(self,commits):
            stable=self.stable(self.publication())
            self.operator_git('rewrite','update-ref','refs/heads/main',commits[0],commits[1])
            self.module.write_bytes(self.initial_module)
            before=self.source_before('history-refused')
            try:
                self.failed_start('history-rewrite')
                doc=self.publication()
                worker.require(doc['outbox'][:-1]==stable['outbox'] and len(doc['outbox'])==len(commits)+1
                    and doc['outbox'][-1]['event']=={'status':'fatal','code':'GIT_HISTORY_REWRITE'},'History rewrite fatal notification differs')
                worker.require(self.stable({**doc,'outbox':doc['outbox'][:-1]})==stable,'History refusal captured or published findings')
                journal=self.journal.read()
                worker.require(journal['phase']=='idle' and journal['event']=={'status':'fatal','code':'GIT_HISTORY_REWRITE'},'History refusal journal differs')
                self.unchanged_source('history-refused',before)
                worker.save(self.output/'publication-history-refused.json',doc)
                self.event('stock_history_refused_before_capture',journal=journal,new_captures=0,new_findings=0)
            finally:
                if self.current()['status']['state']==1:
                    self.operator_git('restore-ref','update-ref','refs/heads/main',commits[1],commits[0])
                    self.module.write_bytes(self.next_module)

        def membership(self,permissions):
            from rentgen_core.access import change_membership
            from rentgen_core.context import Principal
            with self.context.state.transaction(self.owner) as tx: revision=tx.membership_revision()
            receipt=change_membership(self.context.state,self.owner,target=Principal('windows-sid:'+worker.SID,'local_os'),
                permissions=permissions,action='membership.set',operation_id=str(uuid4()),expected_revision=revision)
            self.event('stock_operator_membership',permissions=permissions,scm_state=1,receipt=receipt)

        def context_refusal(self,commits):
            worker.require(self.current()['status']['state']==1,'Membership edit requires STOPPED')
            before=self.source_before('context-refused');stable=self.stable(self.publication())
            self.membership(['project:read'])
            try:
                self.failed_start('analysis-permission-revoked')
                worker.require(self.stable(self.publication())==stable,'Context refusal changed durable publications')
                self.unchanged_source('context-refused',before)
                self.event('stock_context_refused_before_capture',new_captures=0,new_findings=0,new_notifications=0)
            finally:
                worker.require(self.current()['status']['state']==1,'Refusing membership restore while service lives')
                self.membership(['project:read','analysis:run'])

        def final_inputs(self):
            worker.require(self.operator_git('final-head','rev-parse','--verify','HEAD^{commit}')==self.final_commit
                and self.module.read_bytes()==self.next_module,'Operator source restoration differs')
            worker.require(all(worker.sha(path)==digest for path,digest in self.input_files.items()),'Stock fixed inputs changed')
            worker.require(fixture.verify_runtime(worker.ROOT/'localservice/diagnostics')['verified'] is True,'Pinned runtime changed')
            worker.require(self.native.owner(self.source)==self.metadata['source_owner_sid']!=worker.SID,'Source root owner changed')
            worker.require(not list(self.scratch.iterdir()),'Native BSL left owned scratch after successful lifetime')
            self.event('stock_fixed_inputs_verified',runtime_verified=True,native_bsl_lifetimes=sorted(self.java_proofs),
                source_owner_unchanged=True,scratch_empty=True)

        def exercise(self): return exercise(self)

        def cleanup(self):
            # Stop the acknowledged service and wait for every owned process
            # before the SDK may restore ACLs. Unknown lifetimes preserve grants.
            try:
                if self.created:
                    row=self.current()
                    if row['status']['state']==4: self.installer.stop(self.spec)
                    if row['status']['state']!=1: self.state(1,180)
                    if self.held is not None:
                        self.held.wait();self.held=None
                worker.wait_until(lambda:not self.children(),150,'stock owned processes before ACL restoration')
                self.event('stock_no_owned_process_before_acl_restore')
            except BaseException as error:
                return [{'stage':'stock_process_lifetime','type':type(error).__name__}]
            return super().cleanup()

        def retain(self):
            worker.require(not self.native.query(worker.NAME)['exists'],'Do not read mutable state while service remains')
            target=worker.B/'stock-measurement';target.mkdir(exist_ok=False)
            paths=[Path(self.f['config']),worker.ROOT/'localservice/stock-source-manifest.json',
                worker.B/'stock-preparation.json',worker.B/'stock-coordinator.json',
                self.observer.profile/'git-journal.json',self.observer.profile/'git-outbox.json']
            owners=self.context.state.path.parent/'owner-reports/reports'
            if owners.exists(): paths.extend(owners.glob('*.json'))
            worker.require(len(paths)<=10,'Stock raw record inventory exceeds bound')
            retained={}
            for path in paths:
                if not path.exists(): continue  # Failure receipts retain only existing evidence.
                path=probe._path(path);size=path.stat().st_size
                worker.require(size<=4*1024*1024,'Stock raw record exceeds bound')
                raw=path.read_bytes();destination=target/path.name
                with destination.open('xb') as stream: stream.write(raw)
                worker.require(worker.sha(destination)==worker.sha(path),'Retained stock record changed')
                retained[path.name]={'source':str(path),'size_bytes':size,'sha256':worker.sha(destination)}
            # An SQLite backup retains a coherent database, including WAL data;
            # copying the main file alone could omit committed native findings.
            for label,path in (('observer',self.observer.database),('project',self.context.state.path)):
                path=probe._path(path);worker.require(path.stat().st_size<=32*1024*1024,'Stock database exceeds bound')
                destination=target/(label+'.sqlite3')
                with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(destination) as output:
                    source.backup(output)
                    worker.require(output.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'Retained database is invalid')
                worker.require(destination.stat().st_size<=32*1024*1024,'Stock database backup exceeds bound')
                retained[destination.name]={'source':str(path),'size_bytes':destination.stat().st_size,'sha256':worker.sha(destination),
                    'coherent_sqlite_backup':True}
            result={'complete':True,'files':retained,'raw_bsl_report_retained':False,
                'native_bsl_provenance':'actual pinned Java image/token/parent/argv plus stock wheel and complete durable findings'}
            worker.save(target/'retention.json',result)
            self.event('stock_measurement_retained',retention_sha256=worker.sha(target/'retention.json'))
            return result
    return StockAcceptance
