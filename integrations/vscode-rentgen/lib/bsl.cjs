'use strict';
const fs=require('node:fs/promises'),path=require('node:path');
const {randomUUID}=require('node:crypto');
const {isDeepStrictEqual}=require('node:util');
const {profileConfig,sourceRef}=require('./core.cjs');
const {validateBsl}=require('./bsl-result.cjs');
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
async function directory(file){const stat=await fs.lstat(file);if(!stat.isDirectory()||stat.isSymbolicLink())throw new Error('BSL_DIRECTORY_INVALID');}
async function read(file,max){
 const stat=await fs.lstat(file);if(!stat.isFile()||stat.isSymbolicLink()||stat.size>max)throw new Error('BSL_FILE_INVALID');
 const handle=await fs.open(file,'r');
 try{const bytes=Buffer.alloc(max+1),{bytesRead}=await handle.read(bytes,0,bytes.length,0);
  if(bytesRead>max)throw new Error('BSL_FILE_LIMIT');
  return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes.subarray(0,bytesRead)));
 }finally{await handle.close();}
}
async function write(file,value,max){
 const bytes=Buffer.from(JSON.stringify(value));if(bytes.length>max)throw new Error('BSL_FILE_LIMIT');
 const pending=file+'.pending',handle=await fs.open(pending,'wx');
 try{await handle.writeFile(bytes);await handle.sync();}finally{await handle.close();}
 await fs.rename(pending,file);
}
function createBslService({root,config,client,trusted=()=>true,cancel=()=>{}}){
 config=profileConfig(config);const folder=path.join(root,'bsl-runs');
 let busy=false,disposed=false,cancelled=false;
 function check(){if(disposed||!trusted())throw new Error('TRUST_REQUIRED');if(config.core_version!=='0.1.0.dev8')throw new Error('BSL_REQUIRES_DEV8');}
 async function request(id){
  if(!uuid.test(id))throw new Error('INVALID_OPERATION_ID');
  await directory(folder);await directory(path.join(folder,id));
  const value=await read(path.join(folder,id,'request.json'),32768);
  if(value.id!==id||value.receipt?.project_id!==config.project_id||!uuid.test(value.receipt.draft_id)||
   !Number.isSafeInteger(value.receipt.revision)||value.receipt.revision<1||typeof value.created_at!=='string'||
   !Number.isFinite(Date.parse(value.created_at)))throw new Error('BSL_REQUEST_INVALID');
  sourceRef(value.receipt.source_ref,config.project_id);return value;
 }
 async function list(){
  check();await client.head();
  try{await directory(folder);}catch(error){if(error.code==='ENOENT')return [];throw error;}
  const rows=[],entries=await fs.opendir(folder);let count=0;
  for await(const entry of entries){
   if(++count>1000)throw new Error('BSL_HISTORY_LIMIT');
   if(uuid.test(entry.name)){
    try{rows.push(await request(entry.name));}
    catch(error){if(error.code!=='ENOENT')throw error;} // Preparation stopped before durable intent; no analysis submitted.
   }
  }
  check();return rows.sort((a,b)=>b.created_at.localeCompare(a.created_at));
 }
 async function saved(receipt){
  sourceRef(receipt.source_ref,config.project_id);
  const value=await client.proposal(receipt.draft_id,receipt.revision);
  if(!isDeepStrictEqual(value.receipt,receipt))throw new Error('DRAFT_REVISION_MISMATCH');
  check();return value;
 }
 async function start(receipt){
  check();if(busy)throw new Error('BSL_RUNNING');busy=true;cancelled=false;let id;
  try{
   const value=await saved(receipt);
   await fs.mkdir(folder,{recursive:true});await directory(folder);
   if((await list()).length>=1000)throw new Error('BSL_HISTORY_LIMIT');
   check();if(cancelled)throw new Error('BSL_CANCELLED');
   id=randomUUID();const run=path.join(folder,id);await fs.mkdir(run);
   const file=path.join(run,'proposal.json');await write(file,value.proposal,1536*1024);
   await write(path.join(run,'request.json'),{id,receipt,created_at:new Date().toISOString()},32768);
   check();if(cancelled)throw new Error('BSL_CANCELLED');
   const report=await client.bslCheck({receipt,proposal:value.proposal,file});
   check();if(cancelled)throw new Error('BSL_CANCELLED');
   validateBsl(report,receipt,value.proposal);
   const result={run_id:id,status:'completed',receipt,report,evidence:'local_unattested'};
   await write(path.join(run,'result.json'),result,2*1024*1024);check();return result;
  }catch(error){if(id)throw new Error(`${error.message}; запуск ${id}. Проверьте сохранённый результат.`,{cause:error});throw error;}
  finally{busy=false;}
 }
 async function inspect(id){
  check();const intent=await request(id),value=await saved(intent.receipt);let result;
  try{result=await read(path.join(folder,id,'result.json'),2*1024*1024);}
  catch(error){if(error.code==='ENOENT'){check();return {run_id:id,status:'incomplete',receipt:intent.receipt};}throw error;}
  if(result.run_id!==id||result.status!=='completed'||result.evidence!=='local_unattested'||!isDeepStrictEqual(result.receipt,intent.receipt))throw new Error('BSL_RESULT_MISMATCH');
  validateBsl(result.report,intent.receipt,value.proposal);check();return result;
 }
 return {start,list,inspect,get running(){return busy;},cancel(){cancelled=true;if(busy)cancel();},dispose(){disposed=true;if(busy)cancel();}};
}
module.exports={createBslService};
