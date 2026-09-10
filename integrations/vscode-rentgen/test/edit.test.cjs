'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {createHash}=require('node:crypto');
const {createEditService}=require('../lib/edit.cjs');
const project='00000000-0000-4000-8000-000000000001',draft='00000000-0000-4000-8000-000000000002';
const hash=b=>createHash('sha256').update(b).digest('hex');
const bytes=Buffer.from('\uFEFFReturn 42;\r\n');
const ref={snapshot:{project_id:project,snapshot_id:'a'.repeat(64),manifest_hash:'a'.repeat(64)},layer_id:'base',relative_path:'Module.bsl',raw_sha256:hash(bytes)};
const receipt={project_id:project,draft_id:draft,revision:2,title:'Fix',proposal_content_id:'b'.repeat(64),source_ref:ref};
const config={schema:1,core_version:'0.1.0.dev8',python:'C:\\python.exe',registry:'C:\\registry',project_id:project};
async function fixture(t){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'rentgen-edit-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const replies=new Map();let mutations=0, fail=null;
 const client={proposal:async()=>({receipt,proposal:{replacement:{base64:bytes.toString('base64')}}}),
  createProposal:async(_,__,file)=>{const b=await fs.readFile(file);return {source_ref:ref,content_id:hash(b),replacement:{raw_sha256:hash(b)}};},
  saveDraft:async(base,_,contentId,operation)=>{mutations++;if(fail==='conflict')throw new Error('DRAFT_CONFLICT');
    const r={...base,revision:base.revision+1,proposal_content_id:contentId,operation_id:operation};replies.set(operation,r);
    if(fail==='lost')throw new Error('CLI_TIMEOUT');return r;},receipt:async id=>replies.get(id)??null};
 const service=createEditService({root,config,client});
 return {root,client,service,replies,count:()=>mutations,fail:value=>{fail=value;}};
}
test('working copy preserves bytes; unchanged save creates no revision',async t=>{
 const f=await fixture(t),edit=await f.service.open(receipt);
 assert.deepEqual(await fs.readFile(edit.file),bytes);assert.equal((await f.service.save(edit.id)).status,'unchanged');assert.equal(f.count(),0);
 assert.equal((await f.service.forFile(edit.file)).id,edit.id);
 const foreign=path.join(f.root,'foreign.bsl');await fs.writeFile(foreign,'foreign');
 const originalOpen=fs.open;
 fs.open=async(file,...args)=>{if(file===foreign)throw new Error('FOREIGN_CONTENT_READ');return originalOpen(file,...args);};
 try{await assert.rejects(f.service.forFile(foreign),/UNKNOWN_EDIT_DOCUMENT/);}finally{fs.open=originalOpen;}
});
test('a rejected proposal can be corrected before any mutation was attempted',async t=>{
 const f=await fixture(t),edit=await f.service.open(receipt);await fs.writeFile(edit.file,'wrong encoding');
 const real=f.client.createProposal;f.client.createProposal=async()=>{throw new Error('PROPOSAL_POLICY');};
 await assert.rejects(f.service.save(edit.id),/PROPOSAL_POLICY/);assert.equal(f.count(),0);
 f.client.createProposal=real;await fs.writeFile(edit.file,'corrected');
 assert.equal((await f.service.save(edit.id)).receipt.revision,3);assert.equal(f.count(),1);
});
test('lost reply recovers one commit; next changed save uses the recovered revision',async t=>{
 const f=await fixture(t),edit=await f.service.open(receipt);f.fail('lost');
 await fs.writeFile(edit.file,Buffer.from('\uFEFFReturn 43;\r\n'));
 const saved=await f.service.save(edit.id);assert.equal(saved.status,'saved');assert.equal(saved.receipt.revision,3);assert.equal(f.count(),1);
 const reopened=createEditService({root:f.root,config,client:f.client});
 assert.equal((await reopened.inspect(edit.id)).receipt.revision,3);
 assert.equal((await reopened.save(edit.id)).status,'unchanged');assert.equal(f.count(),1);
 await fs.writeFile(edit.file,Buffer.from('\uFEFFReturn 44;\r\n'));f.fail(null);
 assert.equal((await reopened.save(edit.id)).receipt.revision,4);assert.equal(f.count(),2);
});
test('conflict preserves work and never automatically retries an unresolved operation',async t=>{
 const f=await fixture(t),edit=await f.service.open(receipt);f.fail('conflict');
 await fs.writeFile(edit.file,'changed');const result=await f.service.save(edit.id);
 assert.equal(result.status,'unresolved');assert.equal(result.error,'DRAFT_CONFLICT');
 assert.equal((await f.service.save(edit.id)).status,'unresolved');assert.equal(f.count(),1);
 assert.equal(await fs.readFile(edit.file,'utf8'),'changed');
});
test('revoked trust and concurrent save cannot publish another mutation',async t=>{
 const f=await fixture(t),edit=await f.service.open(receipt);await fs.writeFile(edit.file,'changed');
 let release,begin;const started=new Promise(r=>{begin=r;});const real=f.client.saveDraft;
 f.client.saveDraft=async(...args)=>{begin();await new Promise(r=>{release=r;});return real(...args);};
 const pending=f.service.save(edit.id);await started;
 await assert.rejects(f.service.save(edit.id),/EDIT_RUNNING/);release();await pending;assert.equal(f.count(),1);
 const denied=createEditService({root:f.root,config,client:f.client,trusted:()=>false});
 await assert.rejects(denied.open(receipt),/TRUST_REQUIRED/);await assert.rejects(denied.save(edit.id),/TRUST_REQUIRED/);
});
