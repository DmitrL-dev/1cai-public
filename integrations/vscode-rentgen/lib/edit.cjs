'use strict';
const fs=require('node:fs/promises'),path=require('node:path');
const {randomUUID,createHash}=require('node:crypto');
const {isDeepStrictEqual:same}=require('node:util');
const {profileConfig,sourceRef}=require('./core.cjs');
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const sha=/^[0-9a-f]{64}$/;
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const requireValue=(ok,code)=>{if(!ok)throw new Error(code);};
async function directory(file){const s=await fs.lstat(file);requireValue(s.isDirectory()&&!s.isSymbolicLink(),'EDIT_DIRECTORY_INVALID');}
async function read(file,limit){
 const s=await fs.lstat(file);requireValue(s.isFile()&&!s.isSymbolicLink()&&s.size<=limit,'EDIT_FILE_INVALID');
 const h=await fs.open(file,'r');
 try{const b=Buffer.alloc(limit+1),{bytesRead}=await h.read(b,0,b.length,0);requireValue(bytesRead<=limit,'EDIT_FILE_LIMIT');return b.subarray(0,bytesRead);}
 finally{await h.close();}
}
async function json(file){return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(await read(file,32768)));}
async function write(file,bytes){const h=await fs.open(file,'wx');try{await h.writeFile(bytes);await h.sync();}finally{await h.close();}}
async function writeJson(file,value,limit=32768){const b=Buffer.from(JSON.stringify(value));requireValue(b.length<=limit,'EDIT_FILE_LIMIT');await write(file,b);}
async function entries(folder,limit){
 await directory(folder);const result=[],dir=await fs.opendir(folder);
 for await(const e of dir){requireValue(result.length<limit,'EDIT_HISTORY_LIMIT');result.push(e.name);}
 return result;
}
function createEditService({root,config,client,trusted=()=>true}){
 config=profileConfig(config);const home=path.join(root,'edit-sessions');let busy=false,disposed=false;
 function check(){requireValue(!disposed&&trusted(),'TRUST_REQUIRED');requireValue(['0.1.0.dev7','0.1.0.dev8'].includes(config.core_version),'EDIT_REQUIRES_DEV7_OR_DEV8');}
 function validateReceipt(r){
  requireValue(r?.project_id===config.project_id&&uuid.test(r.draft_id)&&Number.isSafeInteger(r.revision)&&r.revision>0&&sha.test(r.proposal_content_id),'EDIT_RECEIPT_INVALID');
  sourceRef(r.source_ref,config.project_id);
 }
 async function session(id){
  check();requireValue(uuid.test(id),'INVALID_EDIT_ID');await directory(home);
  const folder=path.join(home,id);await directory(folder);const value=await json(path.join(folder,'session.json'));
  requireValue(value.id===id&&sha.test(value.initial_sha256)&&typeof value.created_at==='string','EDIT_SESSION_INVALID');validateReceipt(value.receipt);
  return {...value,folder,file:path.join(folder,'module.bsl')};
 }
 async function list(){
  check();let names;try{names=await entries(home,200);}catch(e){if(e.code==='ENOENT')return [];throw e;}
  const result=[];for(const id of names){requireValue(uuid.test(id),'EDIT_SESSION_INVALID');
   try{result.push(await session(id));}catch(e){if(e.code!=='ENOENT')throw e;}}
  check();return result;
 }
 async function open(receipt){
  check();validateReceipt(receipt);const saved=await client.proposal(receipt.draft_id,receipt.revision);check();
  requireValue(same(saved.receipt,receipt),'DRAFT_REVISION_MISMATCH');
  const bytes=Buffer.from(saved.proposal.replacement.base64,'base64');requireValue(bytes.length<=1048576,'EDIT_FILE_LIMIT');
  await fs.mkdir(home,{recursive:true});await directory(home);requireValue((await list()).length<200,'EDIT_HISTORY_LIMIT');
  const id=randomUUID(),folder=path.join(home,id);await fs.mkdir(folder);await fs.mkdir(path.join(folder,'attempts'));
  await write(path.join(folder,'module.bsl'),bytes);
  await writeJson(path.join(folder,'session.json'),{id,created_at:new Date().toISOString(),receipt,initial_sha256:digest(bytes)});
  check();return session(id);
 }
 function savedReceipt(saved,intent){
  validateReceipt(saved);const base=intent.base;
  requireValue(saved.operation_id===intent.operation_id&&saved.draft_id===base.draft_id&&saved.revision===base.revision+1&&
    saved.proposal_content_id===intent.content_id&&same(saved.source_ref,base.source_ref),'EDIT_RESULT_MISMATCH');return saved;
 }
 async function current(s){
  const attempts=path.join(s.folder,'attempts'),names=(await entries(attempts,64)).sort();
  names.forEach((n,i)=>requireValue(n===String(i).padStart(4,'0'),'EDIT_JOURNAL_INVALID'));
  if(!names.length)return {status:'editing',receipt:s.receipt,sha256:s.initial_sha256,count:0};
  const folder=path.join(attempts,names.at(-1));await directory(folder);let intent;
  try{intent=await json(path.join(folder,'intent.json'));}catch(e){
   if(e.code!=='ENOENT')throw e;
   let aborted;try{aborted=await json(path.join(folder,'preparation-failed.json'));}catch(missing){if(missing.code==='ENOENT')return {status:'unresolved',count:names.length};throw missing;}
   validateReceipt(aborted.base);requireValue(sha.test(aborted.sha256)&&aborted.base.draft_id===s.receipt.draft_id&&same(aborted.base.source_ref,s.receipt.source_ref),'EDIT_JOURNAL_INVALID');
   return {status:'editing',receipt:aborted.base,sha256:aborted.sha256,count:names.length};
  }
  validateReceipt(intent.base);requireValue(uuid.test(intent.operation_id)&&sha.test(intent.content_id)&&sha.test(intent.sha256),'EDIT_JOURNAL_INVALID');
  requireValue(intent.base.draft_id===s.receipt.draft_id&&same(intent.base.source_ref,s.receipt.source_ref),'EDIT_JOURNAL_INVALID');
  const found=await client.receipt(intent.operation_id);check();
  return found ? {status:'saved',receipt:savedReceipt(found,intent),sha256:intent.sha256,count:names.length,operation_id:intent.operation_id} :
    {status:'unresolved',count:names.length,operation_id:intent.operation_id};
 }
 async function inspect(id){const s=await session(id),value=await current(s);check();return {id,file:s.file,...value};}
 async function save(id){
  check();requireValue(!busy,'EDIT_RUNNING');busy=true;
  try{
   const s=await session(id),base=await current(s);if(base.status==='unresolved')return {id,file:s.file,...base};
   const bytes=await read(s.file,1048576),sha256=digest(bytes);check();
   if(sha256===base.sha256)return {id,file:s.file,status:'unchanged',receipt:base.receipt};
   requireValue(base.count<64,'EDIT_HISTORY_LIMIT');
   const folder=path.join(s.folder,'attempts',String(base.count).padStart(4,'0'));
   try{await fs.mkdir(folder);}catch(e){if(e.code==='EEXIST')throw new Error('EDIT_RUNNING');throw e;}
   let proposal;const proposalFile=path.join(folder,'proposal.json');
   try{
    await write(path.join(folder,'replacement.bsl'),bytes);await writeJson(path.join(folder,'source-ref.json'),base.receipt.source_ref);
    proposal=await client.createProposal(base.receipt.source_ref,path.join(folder,'source-ref.json'),path.join(folder,'replacement.bsl'));check();
    requireValue(proposal.replacement.raw_sha256===sha256,'CONTENT_HASH_MISMATCH');
    await writeJson(proposalFile,proposal,1572864);
   }catch(error){check();await writeJson(path.join(folder,'preparation-failed.json'),{base:base.receipt,sha256:base.sha256});throw error;}
   const intent={operation_id:randomUUID(),base:base.receipt,content_id:proposal.content_id,sha256};
   await writeJson(path.join(folder,'intent.json'),intent);check();
   let error;
   try{savedReceipt(await client.saveDraft(base.receipt,proposalFile,proposal.content_id,intent.operation_id),intent);}
   catch(e){error=/^[A-Z][A-Z0-9_]{1,80}$/.test(e.message)?e.message:'EDIT_SAVE_FAILED';}
   check();const result=await inspect(id);
   return result.status==='saved'?result:{...result,error};
  }finally{busy=false;}
 }
 return {open,list,save,inspect,get running(){return busy;},
  async forFile(file){check();requireValue(typeof file==='string'&&path.isAbsolute(file),'UNKNOWN_EDIT_DOCUMENT');
   const stat=await fs.lstat(file);requireValue(stat.isFile()&&!stat.isSymbolicLink(),'UNKNOWN_EDIT_DOCUMENT');
   const canonical=await fs.realpath(file);let selected;
   for(const s of await list())if(await fs.realpath(s.file)===canonical){selected=s;break;}
   requireValue(selected,'UNKNOWN_EDIT_DOCUMENT');await read(selected.file,1048576);return selected;},
  dispose(){disposed=true;},
 };
}
module.exports={createEditService};
