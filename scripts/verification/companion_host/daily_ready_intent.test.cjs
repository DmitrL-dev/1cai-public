'use strict';
// Constructed JSON only; these tests provide no editor, model or Native authority.
const test=require('node:test'),assert=require('node:assert/strict');
const {existsSync}=require('node:fs'),path=require('node:path');
const {sourceRef}=require('../../../integrations/vscode-rentgen/lib/core.cjs');
const target=path.join(__dirname,'daily_ready_intent.cjs');
const implementation=existsSync(target)?require(target):{};
const make=value=>{assert.equal(typeof implementation.makeReadyIntent,'function','READY_INTENT_IMPLEMENTATION_REQUIRED');return implementation.makeReadyIntent(value,sourceRef);};
const copy=value=>JSON.parse(JSON.stringify(value));
const project='11111111-1111-1111-1111-111111111111',hash='a'.repeat(64);
function observation(){
 const pin=(name,size)=>({path:path.resolve('constructed/'+name),size,sha256:hash});
 const binding={profile:pin('profile.json',23),scenario:pin('daily-scenario.json',47),manifest:pin('frozen.json',61),context_tokens:8192,core_version:'0.1.0.dev16',companion_version:'0.1.17'};
 const snapshot={project_id:project,snapshot_id:hash,manifest_hash:hash};
 const head={project_id:project,revision:1,source_revision:1,snapshot};
 return {schema:'rentgen-daily-ready-observation/1',mode:'ready-intent-only',ready:true,project_id:project,
  selected_source_ref:{snapshot,layer_id:'base',relative_path:'CommonModules/Probe/Ext/Module.bsl',raw_sha256:hash},
  expected_module:'CommonModules/Probe/Ext/Module.bsl',expected_raw_sha256:hash,head,expected_head:copy(head),
  repair_history:[],test_history:[],binding,expected_binding:copy(binding)};
}
test('R01 bounded intent binds SourceRef and inputs while every authority remains absent',()=>{
 const value=observation(),intent=make(value);
 assert.equal(intent.schema,'rentgen-daily-ready-intent/1');assert.equal(intent.mode,'ready-intent-only');
 assert.deepEqual(intent.source_ref,value.selected_source_ref);assert.deepEqual(intent.binding,value.binding);
 for(const key of ['kernel_authority','loading_allowed','native_allowed','runtime_verified','pipeline_verified','task_accepted','full_product_ready','production_deployment'])assert.equal(intent[key],false,key);
 for(const key of ['peer_identity','held_editor_owner','loading_grant','native_grant'])assert.equal(intent[key],null,key);
 assert.ok(Buffer.byteLength(JSON.stringify(intent),'utf8')<=32768);
 value.selected_source_ref.raw_sha256='b'.repeat(64);value.binding.profile.path='changed';
 assert.equal(intent.source_ref.raw_sha256,hash);assert.notEqual(intent.binding.profile.path,'changed');
});
for(const [name,change] of [
 ['schema',v=>v.schema='other'],['mode',v=>v.mode='attempt'],['ready false',v=>v.ready=false],
 ['ready string',v=>v.ready='true'],['project',v=>v.project_id='foreign'],
 ['module drift',v=>v.expected_module='Other.bsl'],['raw drift',v=>v.expected_raw_sha256='b'.repeat(64)],
 ['head drift',v=>v.head.snapshot.snapshot_id='b'.repeat(64)],
 ['head project',v=>{v.head.project_id='foreign';v.expected_head=copy(v.head);}],
 ['repair history',v=>v.repair_history=[{id:'old'}]],['test history',v=>v.test_history=[{id:'old'}]],
 ['nonarray history',v=>v.repair_history={}],['context drift',v=>v.binding.context_tokens=16384],
 ['equal invalid context',v=>{v.binding.context_tokens=true;v.expected_binding=copy(v.binding);}],
 ['same size byte drift',v=>v.binding.profile.sha256='b'.repeat(64)],
 ['relative input path',v=>{v.binding.profile.path='relative';v.expected_binding=copy(v.binding);}],
 ['invalid pin size',v=>{v.binding.profile.size=-1;v.expected_binding=copy(v.binding);}],
 ['profile size limit',v=>{v.binding.profile.size=65537;v.expected_binding=copy(v.binding);}],
 ['hash array',v=>v.selected_source_ref.raw_sha256=[hash]],
 ['snapshot hash array',v=>{v.selected_source_ref.snapshot.manifest_hash=[hash];v.head.snapshot.manifest_hash=[hash];v.expected_head=copy(v.head);}],
 ['input overflow',v=>v.ignored='я'.repeat(40000)],['invalid PID',v=>v.correlation={pid:0}],
 ['invalid nonce',v=>v.correlation={nonce:'x'.repeat(257)}],['marker controls',v=>v.correlation={marker:'warm\nready'}]
])test('R01/R02 refuses '+name,()=>{const value=observation();change(value);assert.throws(()=>make(value),/DAILY_READY_/);});
test('R03 an historical offline draft does not impose an empty-drafts requirement',()=>{
 const value=observation();value.draft_history=[{revision:1,origin:'offline'}];
 assert.equal(make(value).loading_allowed,false);
});
test('R04 a warm marker, PID, nonce and caller allow never grant authority',()=>{
 const value=observation();value.correlation={pid:42,nonce:'warm',marker:'READY'};
 value.allow=true;value.kernel_authority=true;value.held_editor_owner={handle:123};
 const intent=make(value);assert.deepEqual(intent.correlation,value.correlation);
 assert.equal(intent.kernel_authority,false);assert.equal(intent.loading_allowed,false);assert.equal(intent.native_allowed,false);assert.equal(intent.held_editor_owner,null);
});
