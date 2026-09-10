'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {createTestService}=require('../lib/testing.cjs');
const {validateTests}=require('../lib/tests-result.cjs');
const project='00000000-0000-4000-8000-000000000001';
const receipt={project_id:project,draft_id:'00000000-0000-4000-8000-000000000002',revision:3,proposal_content_id:'b'.repeat(64),source_ref:{snapshot:{project_id:project,snapshot_id:'a'.repeat(64),manifest_hash:'a'.repeat(64)},layer_id:'base',relative_path:'Module.bsl',raw_sha256:'c'.repeat(64)}};
const proposal={content_id:receipt.proposal_content_id,replacement:{raw_sha256:'d'.repeat(64)}};
const profile={profile_id:'e'.repeat(64),name:'Own tests',enabled:true,modules:[{name:'Tests',sha256:'f'.repeat(64),tests:['One']}]};
function result(id){
 const phase={status:'passed',counts:{tests:1,passed:1,failures:0,errors:0,skipped:0},cases:[{classname:'Tests.One',name:'One',context:'Сервер',outcome:'passed'}],module_text_verified:true};
 return {schema:1,run_id:id,source_ref:receipt.source_ref,proposal_content_id:proposal.content_id,profile_id:profile.profile_id,candidate_sha256:proposal.replacement.raw_sha256,report_sha256:'1'.repeat(64),tests:{status:'passed',baseline:structuredClone(phase),candidate:structuredClone(phase),isolated_infobases:true},apply:{status:'unavailable'},evidence:'local_unattested',runtime_dependencies:'not_fully_pinned'};
}
async function fixture(t){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'rentgen-tests-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const config={schema:1,core_version:'0.1.0.dev8',python:'C:\\python.exe',registry:'C:\\state.sqlite3',project_id:project};let calls=0;const reports=new Map();
 const client={head:async()=>({}),proposal:async()=>({receipt,proposal}),testProfiles:async()=>[profile],testCheck:async({id})=>{calls++;const report=result(id);reports.set(id,report);return report;},testResult:async(id)=>reports.has(id)?{run_id:id,status:'completed',request:{run_id:id,project_id:project,input:{source_ref:receipt.source_ref,proposal_content_id:proposal.content_id,profile_id:profile.profile_id}},report:reports.get(id)}:{run_id:id,status:'incomplete',request:null}};
 return {root,config,client,reports,calls:()=>calls,service:createTestService({root,config,client})};
}
test('test result rejects foreign profile, bytes, unexpected inventory and false pass',()=>{
 const id='00000000-0000-4000-8000-000000000003';validateTests(result(id),id,receipt,proposal,profile);
 for(const change of [r=>r.profile_id='a'.repeat(64),r=>r.candidate_sha256='a'.repeat(64),r=>r.tests.candidate.cases[0].name='Other',r=>r.tests.candidate.counts.passed=0,r=>r.tests.candidate.status='failed']){
  const r=result(id);change(r);assert.throws(()=>validateTests(r,id,receipt,proposal,profile),/TEST_RESULT_MISMATCH/);
 }
});
test('saved result binds revision and survives reopening and profile disabling without execution',async t=>{
 const f=await fixture(t),completed=await f.service.start(receipt,profile.profile_id);
 f.client.testProfiles=async()=>[{...profile,enabled:false}];const reopened=createTestService(f);
 assert.deepEqual(await reopened.inspect(completed.run_id),completed);assert.equal(f.calls(),1);
 await assert.rejects(reopened.start(receipt,profile.profile_id),/TEST_PROFILE_UNAVAILABLE/);assert.equal(f.calls(),1);
 f.client.proposal=async()=>{throw new Error('ACCESS_DENIED');};await assert.rejects(reopened.inspect(completed.run_id),/ACCESS_DENIED/);
});
test('lost response keeps durable intent and recovery never resubmits',async t=>{
 const f=await fixture(t);f.client.testCheck=async({id,file})=>{const saved=JSON.parse(await fs.readFile(path.join(path.dirname(file),'request.json'),'utf8'));assert.equal(saved.id,id);assert.deepEqual(saved.receipt,receipt);throw new Error('CLI_TIMEOUT');};
 await assert.rejects(f.service.start(receipt,profile.profile_id),/CLI_TIMEOUT/);
 const [run]=await f.service.list();assert.equal((await f.service.inspect(run.id)).status,'incomplete');assert.equal(f.calls(),0);
});
test('wrong draft, concurrent start, cancellation and trust loss are refused',async t=>{
 const f=await fixture(t);f.client.proposal=async()=>({receipt:{...receipt,revision:4},proposal});await assert.rejects(f.service.start(receipt,profile.profile_id),/DRAFT_REVISION_MISMATCH/);
 f.client.proposal=async()=>({receipt,proposal});let finish,begin;const begun=new Promise(r=>begin=r);f.client.testCheck=async({id})=>{begin();return new Promise(r=>finish=()=>r(result(id)));};
 const pending=f.service.start(receipt,profile.profile_id);await begun;
 await assert.rejects(f.service.start(receipt,profile.profile_id),/TEST_RUNNING/);f.service.cancel();finish();await assert.rejects(pending,/TEST_CANCELLED/);
 await assert.rejects(createTestService({...f,trusted:()=>false}).list(),/TRUST_REQUIRED/);
});
test('recovery refuses a different stored run binding',async t=>{
 const f=await fixture(t),completed=await f.service.start(receipt,profile.profile_id);
 f.reports.get(completed.run_id).profile_id='a'.repeat(64);await assert.rejects(f.service.inspect(completed.run_id),/TEST_RESULT_MISMATCH/);
});
test('CLI uses a registered profile and literal proposal path, without executable options',async()=>{
 const {createClient}=require('../lib/core.cjs');let args;const id='00000000-0000-4000-8000-000000000003';
 const client=createClient({schema:1,core_version:'0.1.0.dev8',python:'C:\\python.exe',registry:'C:\\state.sqlite3',project_id:project},{execute:async(_,argv)=>{args=argv;return {code:0,stdout:Buffer.from(JSON.stringify({result:argv[3]==='test-profile-list'?[profile]:result(id)}))};}});
 assert.deepEqual(await client.testProfiles(),[profile]);const file='C:\\owned $()\\proposal.json';
 assert.deepEqual(await client.testCheck({id,receipt,proposal,file,profile}),result(id));
 assert.deepEqual(args.slice(3),['proposal-test','--registry','C:\\state.sqlite3','--project',project,'--snapshot',receipt.source_ref.snapshot.snapshot_id,'--proposal-json',file,'--test-profile',profile.profile_id,'--operation-id',id]);
 await assert.rejects(client.testCheck({id,receipt,proposal,file:'relative',profile}),/INVALID_TEST_PATH/);
});
