'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {createPlatformUI}=require('../lib/platform-ui.cjs');
const {Handles}=require('../lib/state.cjs');
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

function deferred(){let resolve;const promise=new Promise(done=>{resolve=done;});return {promise,resolve};}
function pendingCheck(status='completed'){
  const commands=new Map(),messages=[],errors=[],opened=[],shown=[],handles=new Handles();
  const receipt={draft_id:'draft',revision:3,proposal_content_id:'a'.repeat(64)};
  const token=handles.add(receipt),started=deferred(),completed=deferred();
  const result={run_id:'run-v3',status,report:{analysis:{baseline:{status:'passed'},candidate:{status:'passed'}}}};
  let starts=0,reads=0;
  const vscode={workspace:{isTrusted:true,openTextDocument:async value=>{opened.push(value);return value;}},
    ProgressLocation:{Notification:15},commands:{registerCommand:(name,fn)=>{commands.set(name,fn);return {dispose(){}};},executeCommand:async()=>{}},
    window:{showTextDocument:async value=>shown.push(value),showInformationMessage:value=>messages.push(value),
      showErrorMessage:value=>errors.push(value),withProgress:async(_,fn)=>fn({}, {isCancellationRequested:false,onCancellationRequested:()=>({dispose(){}})})}};
  const service={running:false,dispose(){},cancel(){},start:async(selected,platform)=>{
    assert.deepEqual(selected,receipt);assert.equal(platform,'C:\\1cv8.exe');starts++;started.resolve();await completed.promise;return result;
  },inspect:async id=>{assert.equal(id,result.run_id);reads++;return result;}};
  createPlatformUI(vscode,service,{selectedDraft:selected=>handles.get(selected)},{subscriptions:[]},true);
  return {commands,vscode,handles,token,receipt,result,started,completed,messages,errors,opened,shown,counts:()=>({starts,reads})};
}

for(const status of ['completed','incomplete','failed'])test(`an invalidated ${status} platform check stays recoverable without automatic presentation`,async()=>{
  const f=pendingCheck(status),pending=f.commands.get('rentgen.platformCheck')(f.token,'C:\\1cv8.exe');
  await f.started.promise;f.handles.clear();f.handles.add({...f.receipt,revision:4});
  f.completed.resolve();assert.equal(await pending,f.result);
  assert.deepEqual(f.opened,[]);assert.deepEqual(f.shown,[]);assert.deepEqual(f.messages,[]);assert.deepEqual(f.errors,[]);
  assert.equal(await f.commands.get('rentgen.platformResult')(f.result.run_id),f.result);
  assert.equal(f.shown.length,1);assert.equal(f.messages.length,1);assert.deepEqual(f.counts(),{starts:1,reads:1});
});

test('draft invalidation while the platform report loads suppresses automatic display',async()=>{
  const f=pendingCheck(),loading=deferred(),loaded=deferred();
  f.vscode.workspace.openTextDocument=async value=>{f.opened.push(value);loading.resolve();return loaded.promise;};
  const pending=f.commands.get('rentgen.platformCheck')({token:f.token},'C:\\1cv8.exe');
  await f.started.promise;f.completed.resolve();await loading.promise;f.handles.clear();loaded.resolve({language:'json'});
  assert.equal(await pending,f.result);assert.equal(f.opened.length,1);
  assert.deepEqual(f.shown,[]);assert.deepEqual(f.messages,[]);assert.deepEqual(f.errors,[]);
});

test('platform check compares the complete receipt rather than just its revision',async()=>{
  const f=pendingCheck(),pending=f.commands.get('rentgen.platformCheck')(f.token,'C:\\1cv8.exe');
  await f.started.promise;f.handles.records.set(f.token,{...f.receipt,proposal_content_id:'b'.repeat(64)});
  f.completed.resolve();assert.equal(await pending,f.result);
  assert.deepEqual(f.opened,[]);assert.deepEqual(f.shown,[]);assert.deepEqual(f.messages,[]);
});

test('a still-valid historical platform check is displayed even with a newer revision present',async()=>{
  const f=pendingCheck();f.handles.add({...f.receipt,revision:4});
  const pending=f.commands.get('rentgen.platformCheck')(f.token,'C:\\1cv8.exe');
  await f.started.promise;
  // Equivalent receipt objects remain valid; object identity alone is not the contract.
  f.handles.records.set(f.token,{...f.receipt});
  f.completed.resolve();assert.equal(await pending,f.result);
  assert.equal(f.shown.length,1);assert.equal(f.messages.length,1);assert.deepEqual(f.counts(),{starts:1,reads:0});
});

test('platform check remains busy through display and suppresses a stale late announcement',async()=>{
  const f=pendingCheck(),displaying=deferred(),displayed=deferred();
  f.vscode.window.showTextDocument=async value=>{f.shown.push(value);displaying.resolve();await displayed.promise;};
  const pending=f.commands.get('rentgen.platformCheck')(f.token,'C:\\1cv8.exe');
  await f.started.promise;f.completed.resolve();await displaying.promise;
  await assert.rejects(f.commands.get('rentgen.platformCheck')(f.token,'C:\\1cv8.exe'),/PLATFORM_RUNNING/);
  f.handles.clear();displayed.resolve();assert.equal(await pending,f.result);
  // An already submitted display cannot be recalled; only its late toast is suppressed.
  assert.equal(f.shown.length,1);assert.deepEqual(f.messages,[]);assert.deepEqual(f.counts(),{starts:1,reads:0});
  assert.equal(await f.commands.get('rentgen.platformResult')(f.result.run_id),f.result);
  assert.deepEqual(f.counts(),{starts:1,reads:1});
});
