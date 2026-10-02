'use strict';
// Actual host in a VM; editor/API/process and output IO are intercepted.
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const path=require('node:path'),{readFileSync,existsSync}=require('node:fs'),{createHash}=require('node:crypto');
const {sourceRef}=require('../../../integrations/vscode-rentgen/lib/core.cjs');
const source=readFileSync(path.join(__dirname,'daily.cjs'),'utf8');
const plain=value=>JSON.parse(JSON.stringify(value)),sha=value=>createHash('sha256').update(value).digest('hex');
function fixture(options={}){
 const calls=[],writes=[],terminals=[],root=path.resolve('constructed-ready-profile');
 const out=path.resolve('constructed-ready-output/acceptance.json'),module='Probe/Module.bsl',bytes=Buffer.from('constructed only');
 const project='11111111-1111-1111-1111-111111111111',hash='a'.repeat(64);
 const snapshot={project_id:project,snapshot_id:hash,manifest_hash:hash};
 const head={project_id:project,revision:1,source_revision:1,snapshot};
 const ref={snapshot,layer_id:'base',relative_path:module,raw_sha256:sha(bytes)};
 const file=path.join(root,'source',module);
 const memory={
  async lstat(target){calls.push('lstat');return {size:target===file?bytes.length:0,isFile:()=>target===file,isDirectory:()=>target!==file,isSymbolicLink:()=>false};},
  async realpath(target){calls.push('realpath');return path.resolve(target);},
  async open(target){calls.push('open');assert.equal(target,file);return {async read(target,offset){bytes.copy(target,offset);return {bytesRead:bytes.length};},async close(){}};},
  async readdir(folder){calls.push('readdir');const name=folder===path.join(root,'source')?'Probe':'Module.bsl',directory=name==='Probe';return [{name,isDirectory:()=>directory,isFile:()=>!directory,isSymbolicLink:()=>false}];},
  async writeFile(target,value,flags){calls.push('write');if(options.writeFailure)throw new Error('constructed write failure');writes.push({target,value,flags});}
 };
 const editor={extensions:{getExtension(){calls.push('extension');throw new Error('Actual activation forbidden');}},commands:{async executeCommand(){calls.push('command');throw new Error('Command forbidden');}}};
 const safeAssert={...assert,deepEqual:(a,b,message)=>assert.deepEqual(plain(a),plain(b),message)};
 const context=vm.createContext({Buffer,TextDecoder,JSON,process:{env:{RENTGEN_EDITOR_OWNER:'{"accepted":true,"pid":42}'}},exports:{},require(name){
  if(name==='vscode')return editor;if(name==='node:fs/promises')return memory;if(name==='node:assert/strict')return safeAssert;
  if(name==='node:child_process')return {execFile(){calls.push('process');throw new Error('Process forbidden');}};
  if(name==='./daily_ready_intent.cjs')return require('./daily_ready_intent.cjs');return require(name);
 }});
 vm.runInContext(source+'\n;globalThis.host={environment,readyIntentOnly:typeof readyIntentOnly===\'function\'?readyIntentOnly:null};globalThis.bind=env=>{environment=async mode=>{if(mode!==\'ready-intent-only\')throw new Error(\'Attempt fallback forbidden\');return env;};};',context);
 const pin=(name,size)=>({path:path.join(root,name),size,sha256:hash});
 const inputs={manifest:pin('frozen.json',61),daily_profile_files:{profile:pin('profile.json',23),scenario:pin('daily-scenario.json',47)},context_tokens:8192,core_version:'0.1.0.dev16',companion_version:'0.1.17'};
 const record={pipeline_verified:false,task_accepted:false,full_product_ready:false,production_deployment:false,repair:null,test:null};
 const env={root,out,config:{project_id:project,context_tokens:8192,core_version:inputs.core_version},scenario:{module,source_inventory:{[module]:{size:bytes.length,sha256:sha(bytes)}},head,context_tokens:8192,frozen_inputs:inputs.manifest,companion_version:inputs.companion_version},context_tokens:8192,inputs,sourceRef,api:{ready:true,
  async repairRuns(){calls.push('repairs');return options.repairs??[];},async testRuns(){calls.push('tests');return options.tests??[];},
  async sources(){calls.push('sources');return [{ref:options.wrongSource?{...ref,raw_sha256:'b'.repeat(64)}:ref,token:'constructed'}];},
  async drafts(){calls.push('drafts');return [{revision:1,origin:'offline'}];}},
  async cli(command){calls.push('cli:'+command);assert.equal(command,'project-head');return head;},record,
  async progress(){calls.push('progress');if(options.cancel)throw new Error('constructed cancellation');},
  async terminal(){calls.push('terminal');if(options.terminalFailure)throw new Error('constructed terminal failure');terminals.push(plain(record));}};
 return {context,host:context.host,env,calls,writes,terminals,record};
}
test('R05 real READY environment refuses caller marker before any IO or extension activation',async()=>{
 const f=fixture();await assert.rejects(f.host.environment('ready-intent-only'),/DAILY_ROOT_EDITOR_OWNER_REQUIRED/);assert.deepEqual(f.calls,[]);
});
test('R05 dedicated wrapper selects READY intent only',()=>{
 const file=path.join(__dirname,'daily_ready_only.cjs');assert.ok(existsSync(file),'READY_WRAPPER_REQUIRED');
 const ready=()=>{},context=vm.createContext({exports:{},require(name){assert.equal(name,'./daily.cjs');return {readyIntentOnly:ready,run(){throw new Error('Attempt forbidden');}};}});
 vm.runInContext(readFileSync(file,'utf8'),context);assert.equal(context.exports.run,ready);
});
async function runFixture(f){assert.equal(typeof f.host.readyIntentOnly,'function','READY_HOST_ROUTE_REQUIRED');f.context.bind(f.env);return f.host.readyIntentOnly();}
test('R03/R05 ready route retains separate intent and never asks for repair, test or drafts',async()=>{
 const f=fixture();await runFixture(f);assert.equal(f.record.status,'ready_intent_collected');assert.equal(f.writes.length,1);
 assert.equal(f.writes[0].target,path.join(path.dirname(f.env.out),'ready-intent.json'));assert.equal(f.writes[0].flags.flag,'wx');
 const intent=JSON.parse(f.writes[0].value);assert.equal(intent.loading_allowed,false);assert.equal(intent.native_allowed,false);assert.deepEqual(intent.source_ref,f.record.source_ref);
 assert.equal(f.terminals.length,1);assert.equal(f.record.pipeline_verified,false);assert.equal(f.record.task_accepted,false);
 assert.equal(f.calls.filter(c=>['command','process','drafts'].includes(c)).length,0);assert.equal(f.record.repair_call_requested,undefined);assert.equal(f.record.test_call_requested,undefined);
});
for(const [name,options] of [['repair history',{repairs:[{id:'old'}]}],['test history',{tests:[{id:'old'}]}],['source drift',{wrongSource:true}],['intent write',{writeFailure:true}],['cancellation',{cancel:true}],['terminal write',{terminalFailure:true}]])test('R02/R06 refuses '+name+' without fallthrough or PASS',async()=>{
 const f=fixture(options);await assert.rejects(runFixture(f));assert.equal(f.record.status,'refused');assert.equal(f.record.pipeline_verified,false);assert.equal(f.record.task_accepted,false);assert.equal(f.terminals.length,0);assert.equal(f.calls.filter(c=>['command','process'].includes(c)).length,0);
});
for(const [role,key] of [['config','core_version'],['scenario','companion_version'],['scenario','frozen_inputs']])test('R01 refuses a missing expected '+key+' without a self-comparison fallback',async()=>{
 const f=fixture();delete f.env[role][key];await assert.rejects(runFixture(f));assert.equal(f.record.status,'refused');assert.equal(f.writes.length,0);assert.equal(f.terminals.length,0);
});
