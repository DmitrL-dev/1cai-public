'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {createBslService}=require('../lib/bsl.cjs');
const {validateBsl,PROFILE}=require('../lib/bsl-result.cjs');
const project='00000000-0000-4000-8000-000000000001';
const receipt={project_id:project,draft_id:'00000000-0000-4000-8000-000000000002',revision:3,proposal_content_id:'b'.repeat(64),source_ref:{snapshot:{project_id:project,snapshot_id:'a'.repeat(64),manifest_hash:'a'.repeat(64)},layer_id:'base',relative_path:'Module.bsl',raw_sha256:'c'.repeat(64)}};
const proposal={content_id:receipt.proposal_content_id,replacement:{raw_sha256:'d'.repeat(64),size_bytes:12}};
function report(){return {diagnostic:{source_ref:receipt.source_ref,proposal_content_id:receipt.proposal_content_id,diagnostics_status:'clean',tests_status:'not_run',apply_status:'unavailable',evidence:'ephemeral_unattested',analysis:{candidate_sha256:proposal.replacement.raw_sha256,candidate_size_bytes:12,profile_id:PROFILE,status:'completed',scope:'single_module_isolated',runtime_verified:true,coverage:'exact_one',diagnostics:[],diagnostics_complete:true,total_diagnostics:0}},tests:{status:'not_run'},apply:{status:'unavailable'}};}
async function fixture(t){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'rentgen-bsl-'));
 t.after(()=>fs.rm(root,{recursive:true,force:true}));
 let calls=0;
 const client={head:async()=>({}),proposal:async()=>({receipt,proposal}),bslCheck:async()=>{calls++;return report();}};
 const config={schema:1,core_version:'0.1.0.dev8',python:'C:\\python.exe',registry:'C:\\state.sqlite3',project_id:project};
 return {root,config,client,calls:()=>calls,service:createBslService({root,config,client})};
}
test('BSL response binds bytes and rejects incomplete or false clean',()=>{
 assert.equal(validateBsl(report(),receipt,proposal),undefined);
 for(const patch of [{candidate_sha256:'e'.repeat(64)},{candidate_size_bytes:13},{runtime_verified:false},{coverage:'incomplete'},{diagnostics_complete:false},{total_diagnostics:1}]){
  const value=report();Object.assign(value.diagnostic.analysis,patch);assert.throws(()=>validateBsl(value,receipt,proposal),/BSL_RESULT_MISMATCH/);
 }
 const foreign=report();foreign.diagnostic={...foreign.diagnostic,proposal_content_id:'e'.repeat(64)};assert.throws(()=>validateBsl(foreign,receipt,proposal));
});
test('completed result reopens without another analysis and rechecks access',async t=>{
 const f=await fixture(t),result=await f.service.start(receipt);
 const reopened=createBslService(f);
 assert.deepEqual(await reopened.inspect(result.run_id),result);assert.equal(f.calls(),1);
 f.client.proposal=async()=>{throw new Error('ACCESS_DENIED');};
 await assert.rejects(reopened.inspect(result.run_id),/ACCESS_DENIED/);assert.equal(f.calls(),1);
});
test('lost response leaves intent, never repeats analysis when inspected',async t=>{
 const f=await fixture(t);
 f.client.bslCheck=async({file})=>{assert.deepEqual(JSON.parse(await fs.readFile(path.join(path.dirname(file),'request.json'),'utf8')).receipt,receipt);throw new Error('CLI_TIMEOUT');};
 await assert.rejects(f.service.start(receipt),/CLI_TIMEOUT/);
 const [run]=await f.service.list();assert.ok(run.id);
 assert.equal((await f.service.inspect(run.id)).status,'incomplete');
});
test('wrong revision and lost trust refuse execution',async t=>{
 const f=await fixture(t);f.client.proposal=async()=>({receipt:{...receipt,revision:4},proposal});
 await assert.rejects(f.service.start(receipt),/DRAFT_REVISION_MISMATCH/);assert.equal(f.calls(),0);
 const denied=createBslService({...f,trusted:()=>false});await assert.rejects(denied.list(),/TRUST_REQUIRED/);
});
test('busy and cancellation cannot create a successful saved report',async t=>{
 const f=await fixture(t);let finish,started;
 const began=new Promise(resolve=>{started=resolve;});
 f.client.bslCheck=async()=>{started();return new Promise(resolve=>{finish=resolve;});};
 const pending=f.service.start(receipt);await began;
 await assert.rejects(f.service.start(receipt),/BSL_RUNNING/);
 f.service.cancel();finish(report());await assert.rejects(pending,/BSL_CANCELLED/);
 assert.equal((await f.service.inspect((await f.service.list())[0].id)).status,'incomplete');
});
test('interrupted preparation does not block history; tampered result is refused',async t=>{
 const f=await fixture(t);
 const orphan=path.join(f.root,'bsl-runs','00000000-0000-4000-8000-000000000099');await fs.mkdir(orphan,{recursive:true});
 assert.deepEqual(await f.service.list(),[]);
 const result=await f.service.start(receipt),file=path.join(f.root,'bsl-runs',result.run_id,'result.json');
 const altered=structuredClone(result);altered.report.diagnostic.analysis.candidate_sha256='f'.repeat(64);
 await fs.writeFile(file,JSON.stringify(altered));await assert.rejects(f.service.inspect(result.run_id),/BSL_RESULT_MISMATCH/);
 assert.equal(f.calls(),1);
});
test('BSL CLI uses literal selected proposal and fixed profile',async()=>{
 const {createClient}=require('../lib/core.cjs');let args;
 const client=createClient({schema:1,core_version:'0.1.0.dev8',python:'C:\\python.exe',registry:'C:\\state.sqlite3',project_id:project},{execute:async(_,argv)=>{args=argv;return {code:0,stdout:Buffer.from(JSON.stringify({result:report()}))};}});
 const file='C:\\owned $()\\proposal.json';
 assert.deepEqual(await client.bslCheck({receipt,proposal,file}),report());
 assert.deepEqual(args.slice(3),['proposal-check','--registry','C:\\state.sqlite3','--project',project,'--snapshot',receipt.source_ref.snapshot.snapshot_id,'--proposal-json',file,'--diagnostics-profile',PROFILE]);
 await assert.rejects(client.bslCheck({receipt,proposal,file:'relative.json'}),/INVALID_BSL_PATH/);
});
