'use strict';
const fs=require('node:fs/promises'),path=require('node:path'),{randomUUID}=require('node:crypto'),{isDeepStrictEqual}=require('node:util');
const {profileConfig,sourceRef}=require('./core.cjs');
const {validateProfiles,validateTests}=require('./tests-result.cjs');
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
async function directory(file){const s=await fs.lstat(file);if(!s.isDirectory()||s.isSymbolicLink())throw new Error('TEST_DIRECTORY_INVALID');}
async function read(file){
 const stat=await fs.lstat(file);if(!stat.isFile()||stat.isSymbolicLink()||stat.size>65536)throw new Error('TEST_REQUEST_INVALID');
 const handle=await fs.open(file,'r');try{const bytes=Buffer.alloc(65537),{bytesRead}=await handle.read(bytes,0,bytes.length,0);if(bytesRead>65536)throw new Error('TEST_REQUEST_INVALID');return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes.subarray(0,bytesRead)));}finally{await handle.close();}
}
async function write(file,value,max){const bytes=Buffer.from(JSON.stringify(value));if(bytes.length>max)throw new Error('TEST_INPUT_LIMIT');const handle=await fs.open(file+'.pending','wx');try{await handle.writeFile(bytes);await handle.sync();}finally{await handle.close();}await fs.rename(file+'.pending',file);}
function createTestService({root,config,client,trusted=()=>true,cancel=()=>{}}){
 config=profileConfig(config);const folder=path.join(root,'test-runs');let busy=false,disposed=false,cancelled=false;
 function check(){if(disposed||!trusted())throw new Error('TRUST_REQUIRED');if(config.core_version!=='0.1.0.dev8')throw new Error('TEST_REQUIRES_DEV8');}
 async function request(id){
  if(!uuid.test(id))throw new Error('INVALID_OPERATION_ID');await directory(folder);await directory(path.join(folder,id));const r=await read(path.join(folder,id,'request.json'));
  if(r.id!==id||r.receipt?.project_id!==config.project_id||!uuid.test(r.receipt.draft_id)||!Number.isSafeInteger(r.receipt.revision)||r.receipt.revision<1||typeof r.created_at!=='string'||!Number.isFinite(Date.parse(r.created_at)))throw new Error('TEST_REQUEST_INVALID');
  sourceRef(r.receipt.source_ref,config.project_id);validateProfiles([r.profile]);return r;
 }
 async function list(){
  check();await client.head();try{await directory(folder);}catch(e){if(e.code==='ENOENT')return [];throw e;}
  const rows=[];let count=0;for await(const entry of await fs.opendir(folder)){if(++count>1000)throw new Error('TEST_HISTORY_LIMIT');if(uuid.test(entry.name)){try{rows.push(await request(entry.name));}catch(e){if(e.code!=='ENOENT')throw e;}}}check();return rows.sort((a,b)=>b.created_at.localeCompare(a.created_at));
 }
 async function profiles(){check();const values=validateProfiles(await client.testProfiles());check();return values.filter(p=>p.enabled);}
 async function saved(receipt){sourceRef(receipt.source_ref,config.project_id);const value=await client.proposal(receipt.draft_id,receipt.revision);if(!isDeepStrictEqual(value.receipt,receipt))throw new Error('DRAFT_REVISION_MISMATCH');check();return value;}
 async function start(receipt,profileId){
  check();if(busy)throw new Error('TEST_RUNNING');busy=true;cancelled=false;let id;
  try{
   const value=await saved(receipt),profile=(await profiles()).find(p=>p.profile_id===profileId);if(!profile)throw new Error('TEST_PROFILE_UNAVAILABLE');
   await fs.mkdir(folder,{recursive:true});await directory(folder);if((await list()).length>=1000)throw new Error('TEST_HISTORY_LIMIT');
   check();if(cancelled)throw new Error('TEST_CANCELLED');id=randomUUID();const run=path.join(folder,id);await fs.mkdir(run);const file=path.join(run,'proposal.json');
   await write(file,value.proposal,1536*1024);await write(path.join(run,'request.json'),{id,receipt,profile,created_at:new Date().toISOString()},65536);
   check();if(cancelled)throw new Error('TEST_CANCELLED');const report=await client.testCheck({id,receipt,proposal:value.proposal,file,profile});
   check();if(cancelled)throw new Error('TEST_CANCELLED');validateTests(report,id,receipt,value.proposal,profile);return {run_id:id,status:'completed',report};
  }catch(error){if(id)throw new Error(`${error.message}; запуск ${id}. Получите сохранённый результат.`,{cause:error});throw error;}finally{busy=false;}
 }
 async function inspect(id){
  check();const intent=await request(id),value=await saved(intent.receipt);let result;
  try{result=await client.testResult(id);}catch(error){if(error.message!=='PLATFORM_RUN_NOT_FOUND')throw error;result={run_id:id,status:'incomplete',request:null};}
  check();if(result.run_id!==id||!['completed','failed','incomplete'].includes(result.status))throw new Error('TEST_RESULT_MISMATCH');
  if(result.request!==null){const r=result.request;if(r?.project_id!==config.project_id||r.run_id!==id||r.input?.profile_id!==intent.profile.profile_id||r.input.proposal_content_id!==intent.receipt.proposal_content_id||!isDeepStrictEqual(r.input.source_ref,intent.receipt.source_ref))throw new Error('TEST_RESULT_MISMATCH');}
  if(result.status==='completed'){if(!result.request)throw new Error('TEST_RESULT_MISMATCH');validateTests(result.report,id,intent.receipt,value.proposal,intent.profile);return {run_id:id,status:'completed',report:result.report};}
  if(result.status==='failed'&&(result.failure?.run_id!==id||result.failure.project_id!==config.project_id))throw new Error('TEST_RESULT_MISMATCH');
  return result;
 }
 return {start,list,profiles,inspect,get running(){return busy;},cancel(){cancelled=true;if(busy)cancel();},dispose(){disposed=true;if(busy)cancel();}};
}
module.exports={createTestService};
