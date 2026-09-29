'use strict';
// Actual host functions in a VM; all editor/API/process/fixture IO is intercepted.
// Constructed reports and bytes never qualify native execution or model quality.
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const path=require('node:path'),{readFileSync}=require('node:fs'),{createHash}=require('node:crypto');
const {createDailySemantic}=require('./daily_semantic.cjs');
const {sourceRef}=require('../../../integrations/vscode-rentgen/lib/core.cjs');
const source=readFileSync(path.join(__dirname,'daily.cjs'),'utf8');
const sha=value=>createHash('sha256').update(value).digest('hex');
const plain=value=>value===undefined?undefined:JSON.parse(JSON.stringify(value));
const project='11111111-1111-1111-1111-111111111111',repairId='22222222-2222-2222-2222-222222222222',testId='33333333-3333-3333-3333-333333333333';

function fixture(options={}){
 const root=path.resolve('constructed-daily-profile'),files=new Map(),faults=new Map(),calls=[],terminals=[];
 const module='CommonModules/Probe/Ext/Module.bsl',original=Buffer.from('constructed original, never executable'),candidate=Buffer.from('constructed candidate, never executable');
 const snapshot={project_id:project,snapshot_id:'a'.repeat(64),manifest_hash:'a'.repeat(64)};
 const ref={snapshot,layer_id:'base',relative_path:module,raw_sha256:sha(original)};
 const receipt={project_id:project,draft_id:'44444444-4444-4444-4444-444444444444',operation_id:'55555555-5555-5555-5555-555555555555',revision:options.noRevision?1:2,proposal_content_id:'b'.repeat(64),source_ref:ref};
 const replacement=options.noRevision?original:candidate;
 const proposal={content_id:receipt.proposal_content_id,replacement:{base64:replacement.toString('base64'),raw_sha256:sha(replacement)}};
 const request={id:repairId,project_id:project,source_ref:ref,model:'constructed-model'};
 const testRequest={id:testId,receipt,profile:{profile_id:'c'.repeat(64)}};
 const repair={id:repairId,status:options.noRevision?'saved_unverified':'analysis_clean',truncated:false,receipt};
 const report={status:repair.status,receipt,before:{diagnostic:null},after:{receipt,diagnostic:null},candidate_sha256:sha(candidate),model:{}};
 const phase=(status,failures)=>({status,counts:{tests:1,failures,errors:0,skipped:0,passed:1-failures}});
 const result=options.unfinished?{status:'running',run_id:testId}:{status:'completed',run_id:testId,report:{proposal_content_id:proposal.content_id,candidate_sha256:sha(candidate),profile_id:testRequest.profile.profile_id,tests:{baseline:phase('failed',1),candidate:phase('passed',0),steps:['baseline','candidate'].map(p=>({name:p+'-compile',exit_code:0,log_sha256:'d'.repeat(64),stdout_sha256:'e'.repeat(64),stderr_sha256:'f'.repeat(64)}))}}};
 const head={project_id:project,revision:1,snapshot,source_revision:1};
 const inventory={[module]:{size:original.length,sha256:sha(original)}};
 const put=(name,value)=>files.set(path.join(root,name),Buffer.isBuffer(value)?value:Buffer.from(typeof value==='string'?value:JSON.stringify(value)));
 put('source/'+module,original);
 for(const [name,value] of Object.entries({'request.json':request,'source-ref.json':ref,'instruction.txt':'constructed instruction','result/result.json':report,'result/events.jsonl':'\n'}))put('repair-runs/'+repairId+'/'+name,value);
 put('test-runs/'+testId+'/request.json',testRequest);put('test-runs/'+testId+'/proposal.json',proposal);
 for(const name of ['request.json','report.json','baseline.junit.xml','candidate.junit.xml','baseline.exit','candidate.exit','baseline-settings.json','candidate-settings.json'])put('state/test-runs/'+testId+'/'+name,Buffer.from('constructed raw '+name));
 for(const phase of ['baseline','candidate'])for(const suffix of ['.log','.stdout','.stderr'])put('state/test-runs/'+testId+'/'+phase+'-compile'+suffix,Buffer.from('constructed declared step '+phase+suffix));
 const missing=file=>Object.assign(new Error('constructed unavailable '+file),{code:'ENOENT'});
 const memory={
  async lstat(file){if(faults.has(file))throw faults.get(file);const bytes=files.get(file),folder=[...files.keys()].some(key=>key.startsWith(file+path.sep));if(!bytes&&!folder)throw missing(file);return {size:bytes?.length??0,isFile:()=>Boolean(bytes),isDirectory:()=>folder,isSymbolicLink:()=>false};},
  async realpath(file){return path.resolve(file);},
  async open(file){if(!files.has(file))throw missing(file);return {async read(target,offset,length){const bytes=files.get(file),n=Math.min(bytes.length,length);bytes.copy(target,offset,0,n);return {bytesRead:n};},async close(){}};},
  async readdir(folder){const entries=new Map();for(const file of files.keys()){if(!file.startsWith(folder+path.sep))continue;const relative=file.slice(folder.length+1),name=relative.split(path.sep)[0],directory=relative.includes(path.sep);entries.set(name,{name,isDirectory:()=>directory,isFile:()=>!directory,isSymbolicLink:()=>false});}return [...entries.values()];},
  async writeFile(){throw new Error('Actual environment writes are forbidden in pure VM tests');}
 };
 const editor={window:{activeTextEditor:null,visibleTextEditors:[]},commands:{async executeCommand(name,...args){calls.push({name,args});if(name==='rentgen.repairSource'){state.repairStarted=true;return repair;}if(name==='rentgen.repairResult'){editor.window.activeTextEditor={document:{languageId:'plaintext',uri:{scheme:'rentgen-view',authority:'constructed-opaque-view',path:'/[v'+receipt.revision+'] '+path.posix.basename(ref.relative_path),query:'',fragment:''},getText:()=>new TextDecoder('utf-8',{fatal:true}).decode(replacement)}};editor.window.visibleTextEditors=[editor.window.activeTextEditor];return repair;}if(name==='rentgen.testDraft'){state.testStarted=true;return options.noTestRequest?null:result;}if(name==='rentgen.testResult'){editor.window.activeTextEditor={document:{languageId:'json',getText:()=>JSON.stringify(result)}};return result;}throw new Error('Unexpected constructed command '+name);}}};
 const safeAssert={...assert,deepEqual:(a,b,message)=>assert.deepEqual(plain(a),plain(b),message)};
 const context=vm.createContext({Buffer,TextDecoder,JSON,process:{env:{}},exports:{},require(name){if(name==='vscode')return editor;if(name==='node:fs/promises')return memory;if(name==='node:assert/strict')return safeAssert;if(name==='node:child_process')return {execFile(){throw new Error('Process launch forbidden');}};if(name==='./daily_semantic.cjs')return {createDailySemantic};return require(name);}});
 vm.runInContext(source+'\n;globalThis.host={diagnosticVerdict,evidence,attempt,recover};globalThis.bindEnvironment=env=>{environment=async()=>env;};',context);
 const state={repairStarted:false,testStarted:false,recovery:false};
 const api={async repairRuns(){return state.recovery||state.repairStarted?[request]:[];},async testRuns(){return (state.recovery||state.testStarted)&&!options.noTestRequest?[testRequest]:[];},async sources(){return [{ref:options.wrongSnapshot?{...ref,snapshot:{...snapshot,snapshot_id:'9'.repeat(64)}}:ref,token:'source'}];},async drafts(){return [{kind:'draft',token:'root',receipt}];},async history(){return [{kind:'version',token:'selected',receipt}];},selectedDraft(){return receipt;}};
 const semantic=createDailySemantic({validateTests:r=>r,sourceRef});
 const record={schema:'rentgen-daily-semantic/1',profile_root:root,inputs:{manifest:{sha256:'0'.repeat(64)},validator:{sha256:'1'.repeat(64)},source_validator:{sha256:'2'.repeat(64)}},repair:null,test:null,pipeline_verified:false,task_accepted:false,raw_qualification:'pending',full_product_ready:false};
 const env={root,scenario:{module,source_inventory:inventory,head,model:request.model,instruction:'constructed instruction',profile:testRequest.profile},config:{project_id:project},inputs:record.inputs,semantic,api,record,cli:async command=>command==='project-head'?head:{receipt,proposal},progress:async()=>{},terminal:async()=>{terminals.push(plain(record));}};
 context.bindEnvironment(env);
 return {host:context.host,context,env,record,files,faults,calls,terminals,repair,request,result,testRequest,receipt,head,state,root,put,editor};
}

test('missing diagnostic receipt is unproven rather than a host exception',()=>{
 const f=fixture();assert.deepEqual(plain(f.host.diagnosticVerdict(undefined,undefined,'a'.repeat(64))),{status:'unproven'});
});
test('available AI2 still reaches functional collection when baseline diagnostic receipt is missing',async()=>{
 const f=fixture();await f.host.attempt();assert.equal(f.record.diagnostics.baseline.status,'unproven');assert.ok(f.record.functional);assert.equal(f.calls.filter(c=>c.name==='rentgen.testDraft').length,1);assert.equal(f.record.pipeline_verified,false);assert.equal(f.record.task_accepted,false);
});
test('early return without AI2 retains available repair raw evidence without preservation claim',async()=>{
 const f=fixture({noRevision:true});await f.host.attempt();assert.equal(f.record.status,'unproven');assert.ok(f.record.raw_evidence['repair-runs/'+repairId+'/result/result.json']);assert.notEqual(f.record.preservation_verified,true);assert.equal(f.calls.filter(c=>c.name==='rentgen.testDraft').length,0);
});
test('early return without a durable test request retains repair and available test raw evidence',async()=>{
 const f=fixture({noTestRequest:true});await f.host.attempt();assert.equal(f.record.status,'unproven');assert.ok(f.record.raw_evidence['repair-runs/'+repairId+'/request.json']);assert.notEqual(f.record.preservation_verified,true);assert.equal(f.calls.filter(c=>c.name==='rentgen.testDraft').length,1);
});
test('selected source snapshot binds to nested project head snapshot',async()=>{
 const f=fixture();await f.host.attempt();assert.deepEqual(plain(f.record.source_ref.snapshot),f.head.snapshot);
});
test('wrong selected source snapshot refuses before requesting repair',async()=>{
 const f=fixture({wrongSnapshot:true});await assert.rejects(f.host.attempt(),/DAILY_SOURCE_HEAD_MISMATCH/);assert.equal(f.calls.filter(c=>c.name==='rentgen.repairSource').length,0);assert.notEqual(f.record.preservation_verified,true);
});
test('actual native phase basenames are retained as bounded raw identities',async()=>{
 const f=fixture();const raw=await f.host.evidence(f.root,repairId,testId,f.result);for(const name of ['baseline.junit.xml','candidate.junit.xml','baseline.exit','candidate.exit','baseline-settings.json','candidate-settings.json'])assert.ok(raw['state/test-runs/'+testId+'/'+name]);
});
test('one unreadable raw file retains other available evidence and its error',async()=>{
 const f=fixture({noRevision:true});f.faults.set(path.join(f.root,'repair-runs',repairId,'instruction.txt'),Object.assign(new Error('constructed unreadable input'),{code:'EACCES'}));await assert.rejects(f.host.attempt());assert.ok(f.record.raw_evidence['repair-runs/'+repairId+'/request.json']);assert.ok(f.record.raw_evidence_errors.length);assert.notEqual(f.record.preservation_verified,true);
});
test('repair-only prior is recovered through cached result with zero new starts',async()=>{
 const f=fixture({noRevision:true,noTestRequest:true});await f.host.attempt();const prior=plain(f.record);f.put('prior.json',prior);f.context.process.env.RENTGEN_DAILY_PRIOR=path.join(f.root,'prior.json');f.state.recovery=true;f.calls.length=0;f.record.repair=null;f.record.test=null;await f.host.recover();assert.equal(f.record.recovered,true);assert.equal(f.record.model_requests_started,0);assert.equal(f.record.test_requests_started,0);assert.equal(f.calls.filter(c=>['rentgen.repairSource','rentgen.testDraft'].includes(c.name)).length,0);assert.ok(f.calls.some(c=>c.name==='rentgen.repairResult'));assert.ok(!f.calls.some(c=>c.name==='rentgen.testResult'));assert.equal(f.record.raw_qualification,'pending');
});
test('unfinished durable test is inspected without repeating either operation',async()=>{
 const f=fixture({unfinished:true});await f.host.attempt();const prior=plain(f.record);f.put('prior.json',prior);f.context.process.env.RENTGEN_DAILY_PRIOR=path.join(f.root,'prior.json');f.state.recovery=true;f.calls.length=0;f.record.test=null;await f.host.recover();assert.equal(f.record.recovered,true);assert.equal(f.record.functional.semantic_verdict,'unproven');assert.equal(f.calls.filter(c=>['rentgen.repairSource','rentgen.testDraft'].includes(c.name)).length,0);assert.equal(f.record.task_accepted,false);
});
test('malformed raw step retains static evidence and refuses preservation',async()=>{
 const f=fixture();f.result.report.tests.steps[0].name='../escape';await assert.rejects(f.host.attempt());assert.ok(f.record.raw_evidence['state/test-runs/'+testId+'/report.json']);assert.ok(f.record.raw_evidence_errors.length);assert.notEqual(f.record.preservation_verified,true);
});
test('recovery refuses an array-shaped prior run ID before any cached command',async()=>{
 const f=fixture({noRevision:true,noTestRequest:true});await f.host.attempt();const prior=plain(f.record);prior.test_run_id=[testId];f.put('prior.json',prior);f.context.process.env.RENTGEN_DAILY_PRIOR=path.join(f.root,'prior.json');f.state.recovery=true;f.calls.length=0;await assert.rejects(f.host.recover(),/DAILY_PRIOR_RUN_REQUIRED/);assert.equal(f.calls.length,0);
});
test('final recovery capture detects raw drift after the earlier comparison',async()=>{
 const f=fixture({unfinished:true});await f.host.attempt();const prior=plain(f.record);f.put('prior.json',prior);f.context.process.env.RENTGEN_DAILY_PRIOR=path.join(f.root,'prior.json');f.state.recovery=true;
 const command=f.editor.commands.executeCommand;f.editor.commands.executeCommand=async(name,...args)=>{const result=await command(name,...args);if(name==='rentgen.testResult')f.editor.window.activeTextEditor.document.getText=()=>{f.put('repair-runs/'+repairId+'/instruction.txt','constructed later raw drift');return JSON.stringify(result);};return result;};
 await f.host.recover();assert.equal(f.record.preservation_verified,false);assert.equal(f.record.recovered,false);assert.ok(f.record.raw_evidence_errors.some(e=>e.message==='DAILY_RAW_EVIDENCE_CHANGED'));assert.equal(f.record.status,'unproven');
});


const mandatoryRaw=[
 ...['request.json','source-ref.json','instruction.txt','result/events.jsonl','result/result.json'].map(name=>'repair-runs/'+repairId+'/'+name),
 ...['request.json','proposal.json'].map(name=>'test-runs/'+testId+'/'+name),
 ...['request.json','report.json','candidate.junit.xml','candidate.exit','candidate-settings.json','candidate-compile.log','candidate-compile.stdout','candidate-compile.stderr'].map(name=>'state/test-runs/'+testId+'/'+name)
];
for(const name of mandatoryRaw)test('completed attempt refuses missing retained proof '+name,async()=>{
 const f=fixture();f.files.delete(path.join(f.root,name));
 // A missing input read before collection can also reject; its terminal receipt must still demote preservation.
 try{await f.host.attempt();}catch{}
 assert.equal(f.record.preservation_verified,false);assert.equal(f.record.eligible_for_raw_qualification,false);assert.notEqual(f.record.status,'collected');
 assert.ok(f.record.raw_evidence_errors?.some(error=>error.path===name&&error.code==='ENOENT'));
 assert.ok(f.record.raw_evidence['repair-runs/'+repairId+'/source-ref.json']||f.record.raw_evidence['repair-runs/'+repairId+'/request.json']);
 assert.equal(f.record.pipeline_verified,false);assert.equal(f.record.task_accepted,false);
});
function bindRecovery(f,prior=plain(f.record)){
 f.put('prior.json',prior);f.context.process.env.RENTGEN_DAILY_PRIOR=path.join(f.root,'prior.json');f.state.recovery=true;f.calls.length=0;f.record.repair=null;f.record.test=null;return prior;
}
for(const change of [{revision:3},{operation_id:'66666666-6666-6666-6666-666666666666'}])test('repair-only recovery refuses a different full receipt '+JSON.stringify(change),async()=>{
 const f=fixture({noTestRequest:true});await f.host.attempt();const prior=plain(f.record),replacement={...prior.selected_receipt,...change};prior.selected_receipt=replacement;
 let historyReads=0;f.env.api.drafts=async()=>[{kind:'draft',token:'manual-root',receipt:replacement}];f.env.api.history=async()=>{historyReads++;return [{kind:'version',token:'manual-selected',receipt:replacement}];};
 bindRecovery(f,prior);await assert.rejects(f.host.recover(),/DAILY_PRIOR_REPAIR_BINDING_MISMATCH/);
 assert.equal(historyReads,0);assert.notEqual(f.record.recovered,true);assert.equal(f.record.model_requests_started,0);assert.equal(f.record.test_requests_started,0);assert.equal(f.calls.filter(c=>['rentgen.repairSource','rentgen.testDraft'].includes(c.name)).length,0);
});
test('exact AI2 repair-only recovery remains cached and starts zero requests',async()=>{
 const f=fixture({noTestRequest:true});await f.host.attempt();bindRecovery(f);await f.host.recover();assert.equal(f.record.recovered,true);assert.deepEqual(plain(f.record.selected_receipt),f.receipt);assert.equal(f.record.recovery_scope,'repair_only');assert.equal(f.calls.filter(c=>['rentgen.repairSource','rentgen.testDraft'].includes(c.name)).length,0);
});
test('incomplete companion request before Core start does not require unexecuted native files',async()=>{
 const f=fixture({unfinished:true});f.result.status='incomplete';f.result.request=null;for(const name of [...f.files.keys()])if(name.startsWith(path.join(f.root,'state','test-runs',testId)+path.sep))f.files.delete(name);
 await f.host.attempt();assert.equal(f.record.preservation_verified,true);assert.equal(f.record.raw_evidence_errors,undefined);assert.ok(f.record.raw_evidence['test-runs/'+testId+'/request.json']);bindRecovery(f);await f.host.recover();assert.equal(f.record.recovered,true);assert.equal(f.record.functional.semantic_verdict,'unproven');assert.equal(f.calls.filter(c=>['rentgen.repairSource','rentgen.testDraft'].includes(c.name)).length,0);
});
test('compiler diagnostics not_run phases do not require native JUnit exits or settings',async()=>{
 const f=fixture();for(const phase of ['baseline','candidate']){
  f.result.report.tests[phase]={status:'not_run',reason:'compiler_diagnostics'};f.result.report.tests.steps.find(step=>step.name===phase+'-compile').exit_code=101;
  for(const name of [phase+'.junit.xml',phase+'.exit',phase+'-settings.json'])f.files.delete(path.join(f.root,'state','test-runs',testId,name));
 }
 await f.host.attempt();assert.equal(f.record.preservation_verified,true);assert.equal(f.record.raw_evidence_errors,undefined);assert.equal(f.record.eligible_for_raw_qualification,false);bindRecovery(f);await f.host.recover();assert.equal(f.record.recovered,true);assert.equal(f.record.functional.semantic_verdict,'unproven');
});
test('saved_unverified repair can retain its journal without an absent report',async()=>{
 const f=fixture({noTestRequest:true});f.repair.status='saved_unverified';f.files.delete(path.join(f.root,'repair-runs',repairId,'result/result.json'));
 await f.host.attempt();assert.equal(f.record.raw_evidence_errors,undefined);assert.ok(f.record.raw_evidence['repair-runs/'+repairId+'/result/events.jsonl']);bindRecovery(f);await f.host.recover();assert.equal(f.record.recovered,true);assert.equal(f.record.functional.semantic_verdict,'unproven');
});
for(const present of [false,true])test('failed native run requires its durable failure receipt present='+present,async()=>{
 const f=fixture({unfinished:true});Object.assign(f.result,{status:'failed',request:{},failure:{run_id:testId}});if(present)f.put('state/test-runs/'+testId+'/failure.json',{run_id:testId});
 await f.host.attempt();assert.equal(f.record.preservation_verified,present);if(present)assert.equal(f.record.raw_evidence_errors,undefined);else assert.ok(f.record.raw_evidence_errors?.some(error=>error.path==='state/test-runs/'+testId+'/failure.json'&&error.code==='ENOENT'));
 assert.equal(f.record.eligible_for_raw_qualification,false);assert.equal(f.record.task_accepted,false);
});

// Regression: repairResult opens an immutable read-only draft diff, not a JSON result document.
test('repair-only recovery reads the visible saved revision when the original side has focus',async()=>{
 const f=fixture({noRevision:true,noTestRequest:true});await f.host.attempt();bindRecovery(f);
 const command=f.editor.commands.executeCommand;f.editor.commands.executeCommand=async(name,...args)=>{const result=await command(name,...args);if(name==='rentgen.repairResult')f.editor.window.activeTextEditor={document:{languageId:'plaintext',uri:{scheme:'rentgen-view',path:'/[snapshot] Module.bsl'},getText:()=> 'constructed focused original'}};return result;};
 await f.host.recover();assert.equal(f.record.recovered,true);assert.equal(f.record.recovery_scope,'repair_only');assert.equal(f.record.model_requests_started,0);assert.equal(f.record.test_requests_started,0);assert.equal(f.calls.filter(c=>['rentgen.repairSource','rentgen.testDraft'].includes(c.name)).length,0);assert.equal(f.record.task_accepted,false);
});
for(const mutation of ['text','revision','scheme','missing'])test('repair-only recovery refuses a mismatched readonly draft view '+mutation,async()=>{
 const f=fixture({noTestRequest:true});await f.host.attempt();bindRecovery(f);
 const command=f.editor.commands.executeCommand;f.editor.commands.executeCommand=async(name,...args)=>{const result=await command(name,...args);if(name==='rentgen.repairResult'){
  const doc=f.editor.window.visibleTextEditors[0].document;
  if(mutation==='text')doc.getText=()=> 'constructed unrelated shown draft';
  if(mutation==='revision')doc.uri.path='/[v3] Module.bsl';
  if(mutation==='scheme')doc.uri.scheme='file';
  if(mutation==='missing')f.editor.window.visibleTextEditors=[];
 }return result;};
 await assert.rejects(f.host.recover(),/DAILY_REPAIR_VIEW/);assert.notEqual(f.record.recovered,true);assert.notEqual(f.record.preservation_verified,true);assert.equal(f.record.model_requests_started,0);assert.equal(f.record.test_requests_started,0);assert.equal(f.calls.filter(c=>['rentgen.repairSource','rentgen.testDraft'].includes(c.name)).length,0);assert.equal(f.record.task_accepted,false);
});

// ibcmd extension-properties emits stdout/stderr, unlike platform /Out steps.
function addTwoStreamSteps(f){
 for(const phase of ['baseline','candidate']){
  const name=phase+'-extension-properties',step={name,exit_code:0};
  for(const stream of ['stdout','stderr']){const bytes=Buffer.from('constructed ibcmd '+name+' '+stream);step[stream+'_sha256']=sha(bytes);f.put('state/test-runs/'+testId+'/'+name+'.'+stream,bytes);}
  f.result.report.tests.steps.push(step);
 }
 return f;
}
test('both ibcmd extension-properties retain two mandatory streams without invented log files',async()=>{
 const f=addTwoStreamSteps(fixture());await f.host.attempt();assert.equal(f.record.preservation_verified,true);assert.equal(f.record.raw_evidence_errors,undefined);
 for(const phase of ['baseline','candidate']){const base='state/test-runs/'+testId+'/'+phase+'-extension-properties';assert.ok(f.record.raw_evidence[base+'.stdout']);assert.ok(f.record.raw_evidence[base+'.stderr']);assert.equal(f.record.raw_evidence[base+'.log'],undefined);}
 assert.equal(f.record.task_accepted,false);assert.equal(f.record.pipeline_verified,false);
});
test('two-stream native proof recovers cached results without starting either operation',async()=>{
 const f=addTwoStreamSteps(fixture());await f.host.attempt();bindRecovery(f);await f.host.recover();assert.equal(f.record.recovered,true);assert.equal(f.record.preservation_verified,true);assert.equal(f.record.model_requests_started,0);assert.equal(f.record.test_requests_started,0);assert.equal(f.calls.filter(c=>['rentgen.repairSource','rentgen.testDraft'].includes(c.name)).length,0);assert.equal(f.record.task_accepted,false);
});
for(const phase of ['baseline','candidate'])for(const stream of ['stdout','stderr'])test('ibcmd still refuses a missing '+phase+' '+stream,async()=>{
 const f=addTwoStreamSteps(fixture()),name='state/test-runs/'+testId+'/'+phase+'-extension-properties.'+stream;f.files.delete(path.join(f.root,name));await f.host.attempt();assert.equal(f.record.preservation_verified,false);assert.ok(f.record.raw_evidence_errors.some(error=>error.path===name&&error.code==='ENOENT'));assert.equal(f.record.eligible_for_raw_qualification,false);
});
for(const phase of ['baseline','candidate'])test('extension-properties with a declared log still requires '+phase+' log file',async()=>{
 const f=addTwoStreamSteps(fixture()),name=phase+'-extension-properties';f.result.report.tests.steps.find(step=>step.name===name).log_sha256=sha('constructed declared log');await f.host.attempt();assert.equal(f.record.preservation_verified,false);assert.ok(f.record.raw_evidence_errors.some(error=>error.path==='state/test-runs/'+testId+'/'+name+'.log'&&error.code==='ENOENT'));
});
test('two-stream exception is limited to exact ibcmd phase names',async()=>{
 const f=addTwoStreamSteps(fixture());f.result.report.tests.steps.at(-1).name='candidate-extension-property';await f.host.attempt();assert.equal(f.record.preservation_verified,false);assert.ok(f.record.raw_evidence_errors.some(error=>error.message==='DAILY_STEP_INVALID'));assert.equal(f.record.eligible_for_raw_qualification,false);
});
for(const [field,value]of [['stdout_sha256','bad'],['stderr_sha256',null],['log_sha256',null],['exit_code','0'],['log_sha256',undefined],['stdout_sha256',['a'.repeat(64)]],['exit_code',1]])test('ibcmd rejects malformed producer declaration '+field+' type='+typeof value,async()=>{
 const f=addTwoStreamSteps(fixture());f.result.report.tests.steps.at(-1)[field]=value;await f.host.attempt();assert.equal(f.record.preservation_verified,false);assert.ok(f.record.raw_evidence_errors.some(error=>error.message==='DAILY_STEP_INVALID'));assert.equal(f.record.eligible_for_raw_qualification,false);assert.ok(f.record.raw_evidence['state/test-runs/'+testId+'/report.json']);
});
test('ordinary platform steps cannot omit their declared log hash',async()=>{
 const f=fixture();delete f.result.report.tests.steps[1].log_sha256;try{await f.host.attempt();}catch{}assert.equal(f.record.preservation_verified,false);assert.ok(f.record.raw_evidence_errors.some(error=>error.message==='DAILY_STEP_INVALID'));assert.equal(f.record.eligible_for_raw_qualification,false);
});
