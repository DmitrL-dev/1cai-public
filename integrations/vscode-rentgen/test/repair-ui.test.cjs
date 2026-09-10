'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {createRepairUI}=require('../lib/repair-ui.cjs');

function fixture(inputs=[]) {
  const commands=new Map(), calls=[], context={subscriptions:[]}; let cancel;
  const result={id:'run',status:'saved_unverified',receipt:{revision:2}};
  const service={running:false,start:async(ref,options)=>{calls.push(['start',ref,options]);return result;},
    reconcile:async(id)=>{calls.push(['reconcile',id]);return result;},list:async()=>[],cancel(){calls.push(['cancel']);},dispose(){}};
  const vscode={workspace:{isTrusted:true},ProgressLocation:{Notification:15},commands:{
    registerCommand:(name,fn)=>{commands.set(name,fn);return {dispose(){}};},executeCommand:async(...args)=>calls.push(args)},
    window:{showInputBox:async()=>{calls.push(['input']);return inputs.shift();},showQuickPick:async()=>undefined,
      showInformationMessage:m=>calls.push(['info',m]),showErrorMessage:m=>calls.push(['error',m]),
      withProgress:async(_,fn)=>fn({}, {isCancellationRequested:false,onCancellationRequested:fn=>{cancel=fn;return {dispose(){}};}})}};
  const views={selectedSource:token=>{if(token!=='minted')throw new Error('UNKNOWN_VIEW_HANDLE');return {relative_path:'Module.bsl'};},
    refreshDrafts:()=>calls.push(['refresh']),openDraft:async r=>calls.push(['diff',r])};
  createRepairUI(vscode,service,views,context,true);
  return {commands,calls,service,vscode,cancel:()=>cancel()};
}
test('forged selection and cancelled native input never invoke the model',async()=>{
  const f=fixture([undefined]);
  await assert.rejects(f.commands.get('rentgen.repairSource')('forged'),/UNKNOWN_VIEW_HANDLE/);
  assert.equal(f.calls.filter(c=>c[0]==='input').length,0);
  assert.equal(await f.commands.get('rentgen.repairSource')('minted'),null);
  assert.equal(f.calls.filter(c=>c[0]==='start').length,0);
});
test('native inputs pass the chosen task once and inspection only reads existing results',async()=>{
  const f=fixture(['qwen3.5:9b','Исправь запись']);
  await f.commands.get('rentgen.repairSource')({token:'minted'});
  assert.deepEqual(f.calls.find(c=>c[0]==='start')[2],{model:'qwen3.5:9b',instruction:'Исправь запись'});
  await f.commands.get('rentgen.repairResult')('run');
  assert.equal(f.calls.filter(c=>c[0]==='start').length,1);
  assert.equal(f.calls.filter(c=>c[0]==='diff').length,2);
  assert.deepEqual(f.calls.find(c=>c[0]==='reconcile'),['reconcile','run']);
});
test('progress cancellation targets the running service and refuses a concurrent request',async()=>{
  const f=fixture();let complete,begin;
  const begun=new Promise(r=>{begin=r;});
  f.service.start=async()=>{begin();return new Promise(r=>{complete=r;});};
  const pending=f.commands.get('rentgen.repairSource')('minted',{model:'qwen3.5:9b',instruction:'Fix'});
  await begun;f.cancel();
  await assert.rejects(f.commands.get('rentgen.repairSource')('minted'),/REPAIR_RUNNING/);
  assert.equal(f.calls.filter(c=>c[0]==='cancel').length,1);
  complete({status:'unresolved'});await pending;
  assert.equal(f.calls.filter(c=>c[0]==='diff').length,0);
});
