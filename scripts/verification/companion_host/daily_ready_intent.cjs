'use strict';
// Observation only. No process, IPC, model, Native, or permission operations.
const assert=require('node:assert/strict'),path=require('node:path');
const {isDeepStrictEqual:same}=require('node:util');
const hash=/^[0-9a-f]{64}$/,uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const controls=/[\p{Cc}\p{Cf}\p{Cs}]/u;
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const text=(value,limit)=>typeof value==='string'&&value.length>0&&value.length<=limit&&!controls.test(value);
const sha=value=>typeof value==='string'&&hash.test(value);
function binding(value){
 assert.ok(object(value),'DAILY_READY_BINDING_INVALID');
 const result={};
 for(const [name,limit] of [['profile',65536],['scenario',2097152],['manifest',4194304]]){
  const pin=value[name];
  assert.ok(object(pin)&&text(pin.path,4096)&&(path.win32.isAbsolute(pin.path)||path.posix.isAbsolute(pin.path))&&Number.isSafeInteger(pin.size)&&pin.size>=0&&pin.size<=limit&&sha(pin.sha256),'DAILY_READY_PIN_INVALID');
  result[name]={path:pin.path,size:pin.size,sha256:pin.sha256};
 }
 assert.ok(Number.isInteger(value.context_tokens)&&[8192,16384,32768].includes(value.context_tokens),'DAILY_READY_CONTEXT_INVALID');
 assert.ok(text(value.core_version,128)&&text(value.companion_version,128),'DAILY_READY_VERSION_INVALID');
 Object.assign(result,{context_tokens:value.context_tokens,core_version:value.core_version,companion_version:value.companion_version});
 assert.ok(same(result,value),'DAILY_READY_BINDING_INVALID');
 return result;
}
function makeReadyIntent(observation,sourceRefValidator){
 // Bound the serialized observation, then validate a detached JSON value.
 let encoded;
 try{encoded=JSON.stringify(observation);}catch{throw new Error('DAILY_READY_JSON_INVALID');}
 assert.ok(typeof encoded==='string'&&Buffer.byteLength(encoded,'utf8')<=65536,'DAILY_READY_OBSERVATION_LIMIT');
 const value=JSON.parse(encoded);
 assert.ok(object(value)&&value.schema==='rentgen-daily-ready-observation/1'&&value.mode==='ready-intent-only','DAILY_READY_SCHEMA_INVALID');
 assert.equal(value.ready,true,'DAILY_READY_NOT_OBSERVED');
 assert.ok(typeof value.project_id==='string'&&uuid.test(value.project_id),'DAILY_READY_PROJECT_INVALID');
 for(const name of ['repair_history','test_history'])assert.ok(Array.isArray(value[name])&&value[name].length===0,'DAILY_READY_HISTORY_NOT_EMPTY');
 const selected=value.selected_source_ref;
 assert.ok(object(selected)&&object(selected.snapshot)&&sha(selected.raw_sha256)&&sha(selected.snapshot.snapshot_id)&&sha(selected.snapshot.manifest_hash),'DAILY_READY_SOURCE_REF_INVALID');
 assert.equal(typeof sourceRefValidator,'function','DAILY_READY_SOURCE_VALIDATOR_REQUIRED');
 let ref;
 try{ref=sourceRefValidator(selected,value.project_id);}catch{throw new Error('DAILY_READY_SOURCE_REF_INVALID');}
 assert.ok(same(ref,selected),'DAILY_READY_SOURCE_REF_INVALID');
 assert.equal(ref.relative_path,value.expected_module,'DAILY_READY_SOURCE_MODULE_MISMATCH');
 assert.equal(ref.raw_sha256,value.expected_raw_sha256,'DAILY_READY_SOURCE_BYTES_MISMATCH');
 assert.ok(object(value.head)&&value.head.project_id===value.project_id&&same(value.head,value.expected_head)&&same(ref.snapshot,value.head.snapshot),'DAILY_READY_SOURCE_HEAD_MISMATCH');
 const checked=binding(value.binding),expected=binding(value.expected_binding);
 assert.ok(same(checked,expected),'DAILY_READY_BINDING_MISMATCH');
 let correlation=null;
 if(value.correlation!=null){
  assert.ok(object(value.correlation),'DAILY_READY_CORRELATION_INVALID');correlation={};
  for(const name of ['pid','nonce','marker'])if(Object.hasOwn(value.correlation,name)){
   const item=value.correlation[name];
   assert.ok(name==='pid'?Number.isSafeInteger(item)&&item>0&&item<=4294967295:text(item,256),'DAILY_READY_CORRELATION_INVALID');
   correlation[name]=item;
  }
 }
 const intent={schema:'rentgen-daily-ready-intent/1',mode:'ready-intent-only',ready_observed:true,
  project_id:value.project_id,source_ref:ref,binding:checked,head:value.head,correlation,
  kernel_authority:false,peer_identity:null,held_editor_owner:null,loading_grant:null,native_grant:null,
  loading_allowed:false,native_allowed:false,runtime_verified:false,pipeline_verified:false,
  task_accepted:false,full_product_ready:false,production_deployment:false};
 assert.ok(Buffer.byteLength(JSON.stringify(intent),'utf8')<=32768,'DAILY_READY_INTENT_LIMIT');
 return intent;
}
exports.makeReadyIntent=makeReadyIntent;
