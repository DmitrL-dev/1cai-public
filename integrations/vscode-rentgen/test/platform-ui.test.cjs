'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {createPlatformUI}=require('../lib/platform-ui.cjs');
function fixture() {
  const commands=new Map(), calls=[],context={subscriptions:[]};
  const service={running:false,dispose(){},cancel(){calls.push('cancel');},list:async()=>[],
    start:async()=>{calls.push('start');return {status:'completed',report:{analysis:{baseline:{status:'passed'},candidate:{status:'diagnostics_present'}}}};},
    inspect:async()=>{calls.push('inspect');return {status:'incomplete'};}};
  const vscode={workspace:{isTrusted:true,openTextDocument:async value=>{calls.push(value);return value;}},ProgressLocation:{Notification:15},
    commands:{registerCommand:(id,fn)=>{commands.set(id,fn);return {dispose(){}};},executeCommand:async()=>{}},
    window:{showOpenDialog:async()=>undefined,showInputBox:async()=>undefined,showQuickPick:async()=>undefined,
      showTextDocument:async()=>{},showInformationMessage:m=>calls.push(m),showErrorMessage:m=>calls.push(m),
      withProgress:async(_,fn)=>fn({}, {isCancellationRequested:false,onCancellationRequested:()=>({dispose(){}})})}};
  createPlatformUI(vscode,service,{selectedDraft:token=>{if(token!=='minted')throw new Error('UNKNOWN_VIEW_HANDLE');return {revision:2};}},context,true);
  return {commands,calls,service,vscode};
}
test('forged draft handle and cancelled executable picker launch nothing',async()=>{
  const f=fixture();await assert.rejects(f.commands.get('rentgen.platformCheck')('forged'),/UNKNOWN_VIEW_HANDLE/);
  assert.equal(await f.commands.get('rentgen.platformCheck')('minted'),null);
  assert.equal(f.calls.includes('start'),false);
});
test('diagnostics and incomplete recovery are not presented as successful tests',async()=>{
  const f=fixture();f.vscode.window.showOpenDialog=async()=>[{fsPath:'C:\\1cv8.exe'}];
  await f.commands.get('rentgen.platformCheck')('minted');
  assert.ok(f.calls.some(c=>typeof c==='string'&&c.includes('замечания')));
  await f.commands.get('rentgen.platformResult')('known-id');
  assert.equal(f.calls.filter(c=>c==='start').length,1);
  assert.equal(f.calls.filter(c=>c==='inspect').length,1);
  assert.ok(f.calls.some(c=>typeof c==='string'&&c.includes('не подтверждено')));
});

test('explicit automation path uses the same minted selection and service',async()=>{
  const f=fixture();let selected;
  f.vscode.window.showOpenDialog=async()=>{throw new Error('Unexpected picker');};
  f.service.start=async(receipt,platform)=>{selected={receipt,platform};return {status:'incomplete'};};
  await assert.rejects(f.commands.get('rentgen.platformCheck')('forged','C:\\1cv8.exe'),/UNKNOWN_VIEW_HANDLE/);
  await f.commands.get('rentgen.platformCheck')('minted','C:\\1cv8.exe');
  assert.deepEqual(selected,{receipt:{revision:2},platform:'C:\\1cv8.exe'});
});
