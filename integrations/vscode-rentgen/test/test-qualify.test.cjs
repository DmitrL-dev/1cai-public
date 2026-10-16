'use strict';
// Constructed dossiers only: a consistent dossier is local_unattested, never native acceptance.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {createClient}=require('../lib/core.cjs');
const {createTestService}=require('../lib/testing.cjs');
const {createTestsUI}=require('../lib/tests-ui.cjs');
const {validateQualification}=require('../lib/tests-result.cjs');
const {Handles}=require('../lib/state.cjs');
const project='00000000-0000-4000-8000-000000000001',id='00000000-0000-4000-8000-000000000003';
const receipt={project_id:project,draft_id:'00000000-0000-4000-8000-000000000002',revision:3,proposal_content_id:'b'.repeat(64),source_ref:{snapshot:{project_id:project,snapshot_id:'a'.repeat(64),manifest_hash:'a'.repeat(64)},layer_id:'base',relative_path:'Module.bsl',raw_sha256:'c'.repeat(64)}};
const proposal={content_id:receipt.proposal_content_id,replacement:{raw_sha256:'d'.repeat(64)}};
const profile={profile_id:'e'.repeat(64),name:'Own tests',enabled:true,modules:[{name:'Tests',sha256:'f'.repeat(64),tests:['One']}]};
const names=['report_identity','profile_definition','input_inventories','native_roundtrip','step_sequence','runner_settings','junit_exit','engine_source','scratch_cleanup'];
function dossier(overrides={}){
 return {schema:1,kind:'yaxunit-retained-run-qualification',run_id:id,project_id:project,run_status:'completed',failure_code:null,
  binding:{source_ref:receipt.source_ref,proposal_content_id:receipt.proposal_content_id,profile_id:profile.profile_id,platform_executable_sha256:'9'.repeat(64)},
  profile:{profile_id:profile.profile_id,enabled:false},candidate_sha256:proposal.replacement.raw_sha256,report_sha256:'1'.repeat(64),
  test_result:{status:'passed',baseline:'failed',candidate:'passed'},evidence:'local_unattested',execution:'not_performed',apply:{status:'unavailable'},
  limitations:['Retained bytes are local_unattested and do not prove native execution'],
  checks:names.map(name=>({id:name,status:'verified',detail:null})),qualification:'consistent',dossier_sha256:'2'.repeat(64),...overrides};
}
function failing(name,status,detail){const d=dossier();d.checks=d.checks.map(row=>row.id===name?{id:name,status,detail}:row);d.qualification=status==='mismatch'?'inconsistent':'incomplete';return d;}

test('dossier contract derives the qualification and refuses self-asserted consistency',()=>{
 validateQualification(dossier(),id,project);validateQualification(failing('junit_exit','mismatch','CANDIDATE_JUNIT_STATUS'),id,project);
 validateQualification(failing('runner_settings','missing','PROFILE_REQUIRED'),id,project);
 const unfinished=dossier({run_status:'failed',failure_code:'PLATFORM_TIMEOUT',test_result:null,candidate_sha256:null,report_sha256:null,qualification:'incomplete',checks:names.map(name=>({id:name,status:'not_applicable',detail:'RUN_NOT_COMPLETED'}))});
 validateQualification(unfinished,id,project);
 for(const change of [
  d=>{d.checks[6]={id:'junit_exit',status:'mismatch',detail:'X'};},
  d=>{d.checks[0].detail='CLAIMED';},d=>{d.checks.reverse();},d=>{d.checks.pop();},
  d=>{d.evidence='verified';},d=>{d.execution='performed';},d=>{d.apply={status:'available'};},
  d=>{d.run_id='00000000-0000-4000-8000-000000000009';},d=>{d.project_id='other';},
  d=>{d.test_result.status='failed';},d=>{d.failure_code='PLATFORM_TIMEOUT';},d=>{d.kind='other';},
  d=>{d.checks[2]={id:'input_inventories',status:'mismatch',detail:'../path'};}
 ]){const d=structuredClone(dossier());change(d);assert.throws(()=>validateQualification(d,id,project),/TEST_RESULT_MISMATCH/);}
});

function client(capabilities,reply=dossier()){
 const calls=[];const config={schema:1,core_version:'0.1.0.dev4',python:'C:\\python.exe',registry:'C:\\state.sqlite3',project_id:project};
 const value=createClient(config,{execute:async(command,args)=>{calls.push(args);const result=args[3]==='capabilities'?capabilities:reply;return {code:0,stdout:Buffer.from(JSON.stringify({result}))};}});
 return {client:value,calls};
}
const caps=(operations,supported=true)=>({contract_version:1,platform:'win32',scope:'os-adapter-support',capabilities:{'native.evidence.read':{supported,reason:null,operations}}});

test('client admits the read by the advertised operation, not the version allowlist',async()=>{
 const f=client(caps(['test-run-qualify']));
 assert.deepEqual(await f.client.testQualifyCapability(),{supported:true});
 assert.equal((await f.client.testQualify(id)).qualification,'consistent');
 assert.deepEqual(f.calls[1],['-I','-m','rentgen_core','test-run-qualify','--registry','C:\\state.sqlite3','--project',project,'--operation-id',id]);
 for(const reply of [caps([]),caps(['test-run-qualify'],false),{contract_version:1,platform:'linux',scope:'os-adapter-support',capabilities:{}}])
  assert.deepEqual(await client(reply).client.testQualifyCapability(),{supported:false});
 await assert.rejects(f.client.testQualify('not-a-uuid'),/INVALID_OPERATION_ID/);
 await assert.rejects(client(caps(['test-run-qualify']),dossier({evidence:'native'})).client.testQualify(id),/TEST_RESULT_MISMATCH/);
});

async function service(t,reply=dossier()){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'rentgen-qualify-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 await fs.mkdir(path.join(root,'test-runs',id),{recursive:true});
 await fs.writeFile(path.join(root,'test-runs',id,'request.json'),JSON.stringify({id,receipt,profile,created_at:new Date().toISOString()}));
 const config={schema:1,core_version:'0.1.0.dev4',python:'C:\\python.exe',registry:'C:\\state.sqlite3',project_id:project};
 let trusted=true,reads=0;const state={reply,proposal:{receipt,proposal}};
 const value=createTestService({root,config,trusted:()=>trusted,client:{proposal:async()=>state.proposal,testQualify:async()=>{reads++;return state.reply;},
  testCheck:async()=>{throw new Error('NO_EXECUTION');},testResult:async()=>{throw new Error('NO_RESULT_READ');}}});
 return {service:value,state,revoke(){trusted=false;},reads:()=>reads};
}

test('service binds the dossier to the saved intent, revision and candidate bytes without execution',async t=>{
 const f=await service(t);const {dossier:value}=await f.service.qualify(id);assert.equal(value.qualification,'consistent');
 await assert.rejects(f.service.qualify(id,{receipt:{...receipt,revision:4}}),/TEST_RESULT_MISMATCH/);
 f.state.reply=dossier({candidate_sha256:'7'.repeat(64)});await assert.rejects(f.service.qualify(id),/TEST_RESULT_MISMATCH/);
 f.state.reply=dossier({binding:{...dossier().binding,profile_id:'8'.repeat(64)}});await assert.rejects(f.service.qualify(id),/TEST_RESULT_MISMATCH/);
 f.state.reply=dossier();f.state.proposal={receipt:{...receipt,revision:5},proposal};await assert.rejects(f.service.qualify(id),/DRAFT_REVISION_MISMATCH/);
 f.state.proposal={receipt,proposal};await assert.rejects(f.service.qualify('00000000-0000-4000-8000-000000000004'),/ENOENT/);
 f.revoke();await assert.rejects(f.service.qualify(id),/TRUST_REQUIRED/);assert.equal(f.reads(),3); // selection/revision mismatches refuse before any Core read
});

function ui({available=true}={}){
 const commands=new Map(),messages=[],shown=[],handles=new Handles(),selected={...receipt};
 const token=handles.add(selected);let contextVersion=0,calls=[];
 const vscode={workspace:{isTrusted:true,openTextDocument:async value=>value},commands:{registerCommand:(name,fn)=>{commands.set(name,fn);return {dispose(){}};},executeCommand:async()=>{}},
  window:{showTextDocument:async value=>shown.push(value),showInformationMessage:value=>messages.push(value),showErrorMessage:value=>messages.push(value),showQuickPick:async rows=>rows[0]}};
 const state={reply:failing('junit_exit','mismatch','CANDIDATE_JUNIT_STATUS'),onRead:()=>{}};
 const service={running:false,dispose(){},cancel(){},list:async()=>[{id,receipt:selected,profile}],
  qualify:async(value,options)=>{calls.push({value,options});state.onRead();return {dossier:state.reply};}};
 createTestsUI(vscode,service,{selectedDraft:value=>handles.get(value),contextVersion:()=>contextVersion},{subscriptions:[]},false,{qualifyAvailable:available});
 return {commands,messages,shown,handles,token,selected,state,calls,vscode,change:()=>{contextVersion++;}};
}

test('UI shows the first unproven check for the selected revision and hides stale selections',async()=>{
 const f=ui();const value=await f.commands.get('rentgen.testQualify')({token:f.token});
 assert.equal(value.qualification,'inconsistent');assert.deepEqual(f.calls[0].options.receipt,f.selected);
 assert.ok(f.messages.some(m=>m.includes('не совпадают с отчётом')&&m.includes('junit_exit: CANDIDATE_JUNIT_STATUS')&&m.includes('local_unattested')));
 assert.equal(f.shown.length,1);
 f.state.onRead=()=>f.change();await f.commands.get('rentgen.testQualify')({token:f.token});assert.equal(f.shown.length,1);
 f.state.onRead=()=>{};f.handles.clear();await assert.rejects(f.commands.get('rentgen.testQualify')({token:f.token}),/UNKNOWN_VIEW_HANDLE/);
 f.vscode.workspace.isTrusted=false;await assert.rejects(f.commands.get('rentgen.testQualify')(id),/TRUST_REQUIRED/);
 await assert.rejects(ui({available:false}).commands.get('rentgen.testQualify')(id),/TEST_QUALIFY_UNAVAILABLE/);
});
