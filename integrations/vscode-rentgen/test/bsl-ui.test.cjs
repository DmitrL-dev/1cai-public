'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createBslUI}=require('../lib/bsl-ui.cjs');
const {Handles}=require('../lib/state.cjs');

function deferred(){let resolve;const promise=new Promise(done=>{resolve=done;});return {promise,resolve};}
function pendingCheck(){
 const commands=new Map(),messages=[],errors=[],opened=[],shown=[],handles=new Handles();
 const receipt={draft_id:'draft',revision:3,proposal_content_id:'a'.repeat(64)};
 const token=handles.add(receipt),started=deferred(),completed=deferred();
 const result={run_id:'run-v3',status:'completed',receipt,report:{diagnostic:{diagnostics_status:'clean'}}};
 let starts=0,reads=0;
 const vscode={workspace:{isTrusted:true,openTextDocument:async value=>{opened.push(value);return value;}},
  ProgressLocation:{Notification:15},commands:{registerCommand:(name,fn)=>{commands.set(name,fn);return {dispose(){}};},executeCommand:async()=>{}},
  window:{showTextDocument:async value=>shown.push(value),showInformationMessage:value=>messages.push(value),
   showErrorMessage:value=>errors.push(value),withProgress:async(_,fn)=>fn({}, {isCancellationRequested:false,onCancellationRequested:()=>({dispose(){}})})}};
 const service={running:false,dispose(){},cancel(){},start:async selected=>{assert.deepEqual(selected,receipt);starts++;started.resolve();await completed.promise;return result;},
  inspect:async id=>{assert.equal(id,result.run_id);reads++;return result;}};
 createBslUI(vscode,service,{selectedDraft:selected=>handles.get(selected)},{subscriptions:[]},true);
 return {commands,vscode,handles,token,receipt,result,started,completed,messages,errors,opened,shown,
  counts:()=>({starts,reads})};
}
test('BSL UI uses minted revision, states limitations, and recovery does not start analysis',async()=>{
 const commands=new Map(),messages=[];let starts=0,reads=0;
 const vscode={workspace:{isTrusted:true,openTextDocument:async value=>value},ProgressLocation:{Notification:15},
  commands:{registerCommand:(name,fn)=>{commands.set(name,fn);return {dispose(){}};},executeCommand:async()=>{}},
  window:{showTextDocument:async()=>{},showInformationMessage:m=>messages.push(m),showErrorMessage:m=>messages.push(m),
   withProgress:async(_,fn)=>fn({}, {isCancellationRequested:false,onCancellationRequested:()=>({dispose(){}})})}};
 const service={running:false,dispose(){},cancel(){},start:async receipt=>{assert.equal(receipt.revision,3);starts++;return {status:'completed',report:{diagnostic:{diagnostics_status:'diagnostics_present'}}};},
  inspect:async()=>{reads++;return {status:'incomplete'};}};
 createBslUI(vscode,service,{selectedDraft:token=>{if(token!=='minted')throw new Error('UNKNOWN_VIEW_HANDLE');return {revision:3};}},{subscriptions:[]},true);
 await assert.rejects(commands.get('rentgen.bslCheck')('forged'),/UNKNOWN_VIEW_HANDLE/);assert.equal(starts,0);
 await commands.get('rentgen.bslCheck')('minted');await commands.get('rentgen.bslResult')('saved');
 assert.equal(starts,1);assert.equal(reads,1);assert.ok(messages.some(m=>m.includes('есть замечания')));
 assert.ok(messages.some(m=>m.includes('не подтверждено')));assert.ok(messages.some(m=>m.includes('Функциональные тесты не запускались')));
 vscode.workspace.isTrusted=false;await assert.rejects(commands.get('rentgen.bslCheck')('minted'),/TRUST_REQUIRED/);assert.equal(starts,1);
});

test('an invalidated draft check stays in history without taking focus from the newer revision',async()=>{
 const f=pendingCheck(),pending=f.commands.get('rentgen.bslCheck')(f.token);
 await f.started.promise;
 // The real refreshDrafts boundary clears these minted selection handles.
 f.handles.clear();f.handles.add({...f.receipt,revision:4});
 f.completed.resolve();assert.equal(await pending,f.result);
 assert.deepEqual(f.opened,[]);assert.deepEqual(f.shown,[]);assert.deepEqual(f.messages,[]);assert.deepEqual(f.errors,[]);
 assert.equal(await f.commands.get('rentgen.bslResult')(f.result.run_id),f.result);
 assert.equal(f.shown.length,1);assert.equal(f.messages.length,1);
 assert.deepEqual(f.counts(),{starts:1,reads:1});
});

test('draft invalidation while the report document loads prevents automatic presentation',async()=>{
 const f=pendingCheck(),loading=deferred(),document=deferred();
 f.vscode.workspace.openTextDocument=async value=>{f.opened.push(value);loading.resolve();return document.promise;};
 const pending=f.commands.get('rentgen.bslCheck')({token:f.token});
 await f.started.promise;f.completed.resolve();await loading.promise;
 f.handles.clear();document.resolve({language:'json'});
 assert.equal(await pending,f.result);assert.equal(f.opened.length,1);
 assert.deepEqual(f.shown,[]);assert.deepEqual(f.messages,[]);assert.deepEqual(f.errors,[]);
});

test('a selection must still identify the complete originally checked receipt',async()=>{
 const f=pendingCheck(),pending=f.commands.get('rentgen.bslCheck')(f.token);
 await f.started.promise;
 f.handles.records.set(f.token,{...f.receipt,proposal_content_id:'b'.repeat(64)});
 f.completed.resolve();await pending;
 assert.deepEqual(f.opened,[]);assert.deepEqual(f.shown,[]);assert.deepEqual(f.messages,[]);
});

test('a valid historical selection is still presented even when a newer revision exists',async()=>{
 const f=pendingCheck();f.handles.add({...f.receipt,revision:4});
 const pending=f.commands.get('rentgen.bslCheck')(f.token);
 await f.started.promise;f.completed.resolve();assert.equal(await pending,f.result);
 assert.equal(f.shown.length,1);assert.equal(f.messages.length,1);
 assert.deepEqual(f.counts(),{starts:1,reads:0});
});

test('invalidation after display submission suppresses the later selected-version announcement',async()=>{
 const f=pendingCheck(),displaying=deferred(),displayed=deferred();
 f.vscode.window.showTextDocument=async value=>{f.shown.push(value);displaying.resolve();await displayed.promise;};
 const pending=f.commands.get('rentgen.bslCheck')(f.token);
 await f.started.promise;f.completed.resolve();await displaying.promise;
 f.handles.clear();displayed.resolve();await pending;
 // The display request was issued while the selection was valid; it cannot
 // be recalled through this API. Its asynchronous completion may not toast.
 assert.equal(f.shown.length,1);assert.deepEqual(f.messages,[]);assert.deepEqual(f.errors,[]);
});
