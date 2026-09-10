'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const {createPlatformService} = require('../lib/platform.cjs');
const project = '00000000-0000-4000-8000-000000000001';
const receipt = {project_id:project,draft_id:'00000000-0000-4000-8000-000000000002',revision:2,
  proposal_content_id:'b'.repeat(64),source_ref:{snapshot:{project_id:project,snapshot_id:'a'.repeat(64),manifest_hash:'a'.repeat(64)},layer_id:'base',relative_path:'CommonModules/Probe/Ext/Module.bsl',raw_sha256:'c'.repeat(64)}};
const config = {schema:1,core_version:'0.1.0.dev8',python:'C:\\python.exe',registry:'C:\\registry.sqlite3',project_id:project};
async function fixture(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(),'rentgen-platform-'));
  t.after(()=>fs.rm(root,{recursive:true,force:true}));
  const platform = path.join(root,'1cv8.exe'); await fs.writeFile(platform,'fixture executable');
  const calls=[];
  const client={proposal:async()=>({receipt,proposal:{content_id:receipt.proposal_content_id}}),
    platformCheck:async(options)=>{calls.push(options);return {run_id:options.id};},
    platformResult:async id=>({run_id:id,status:'incomplete',request:null})};
  const service=createPlatformService({root,config,client});
  return {root,platform,client,service,calls};
}
test('intent and exact proposal survive a lost response; recovery starts no process',async t=>{
  const f=await fixture(t);
  f.client.platformCheck=async options=>{
    const request=JSON.parse(await fs.readFile(path.join(f.root,'platform-runs',options.id,'request.json'),'utf8'));
    assert.deepEqual(request.receipt,receipt);
    assert.deepEqual(JSON.parse(await fs.readFile(options.proposal,'utf8')),{content_id:receipt.proposal_content_id});
    throw new Error('CLI_TIMEOUT');
  };
  await assert.rejects(f.service.start(receipt,f.platform),/CLI_TIMEOUT.*[0-9a-f-]{36}/);
  const reopened=createPlatformService({root:f.root,config,client:f.client});
  const runs=await reopened.list();assert.equal(runs.length,1);
  assert.equal((await reopened.inspect(runs[0].id)).status,'incomplete');
  assert.equal(f.calls.length,0);
});
test('different revision receipt is refused before native execution',async t=>{
  const f=await fixture(t);
  f.client.proposal=async()=>({receipt:{...receipt,revision:3},proposal:{}});
  await assert.rejects(f.service.start(receipt,f.platform),/DRAFT_REVISION_MISMATCH/);
  assert.equal(f.calls.length,0);assert.deepEqual(await f.service.list(),[]);
});
test('busy service rejects another start; trust loss prevents recovery',async t=>{
  const f=await fixture(t);let finish,begin;
  const begun=new Promise(r=>{begin=r;});
  f.client.platformCheck=async()=>{begin();return new Promise(r=>{finish=r;});};
  const pending=f.service.start(receipt,f.platform);await begun;
  await assert.rejects(f.service.start(receipt,f.platform),/PLATFORM_RUNNING/);
  finish({});await pending;
  const denied=createPlatformService({root:f.root,config,client:f.client,trusted:()=>false});
  await assert.rejects(denied.list(),/TRUST_REQUIRED/);
  await assert.rejects(denied.inspect((await f.service.list())[0].id),/TRUST_REQUIRED/);
});
