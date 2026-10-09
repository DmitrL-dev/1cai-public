'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createTestsUI}=require('../lib/tests-ui.cjs');
const {Handles}=require('../lib/state.cjs');
test('test UI selects registered profile and minted revision, recovery never starts tests',async()=>{
 const commands=new Map(),messages=[];let starts=0,reads=0,choices=[];
 const vscode={workspace:{isTrusted:true,openTextDocument:async value=>value},ProgressLocation:{Notification:15},commands:{registerCommand:(name,fn)=>{commands.set(name,fn);return {dispose(){}};},executeCommand:async()=>{}},window:{showTextDocument:async()=>{},showInformationMessage:m=>messages.push(m),showErrorMessage:m=>messages.push(m),showQuickPick:async rows=>{choices=rows;return rows[0];},withProgress:async(_,fn)=>fn({}, {isCancellationRequested:false,onCancellationRequested:()=>({dispose(){}})})}};
 const service={running:false,dispose(){},cancel(){},profiles:async()=>[{profile_id:'registered',name:'Own tests',modules:[{tests:['One']}]}],start:async(receipt,profile)=>{assert.equal(receipt.revision,3);assert.equal(profile,'registered');starts++;return {status:'completed',report:{tests:{baseline:{status:'failed'},candidate:{status:'passed'}}}};},inspect:async()=>{reads++;return {status:'incomplete'};}};
 createTestsUI(vscode,service,{selectedDraft:token=>{if(token!=='minted')throw new Error('UNKNOWN_VIEW_HANDLE');return {revision:3};}},{subscriptions:[]},true);
 await assert.rejects(commands.get('rentgen.testDraft')('forged'),/UNKNOWN_VIEW_HANDLE/);
 await assert.rejects(commands.get('rentgen.testDraft')('minted','foreign'),/TEST_PROFILE_UNAVAILABLE/);
 await commands.get('rentgen.testDraft')('minted');assert.equal(choices[0].label,'Own tests');assert.equal(starts,1);
 await commands.get('rentgen.testResult')('saved');assert.equal(reads,1);assert.equal(starts,1);
 assert.ok(messages.some(m=>m.includes('исходного кода: есть ошибки')&&m.includes('предложенной версии: пройдены')));
 assert.ok(messages.some(m=>m.includes('Повторного запуска не было')));
 vscode.workspace.isTrusted=false;await assert.rejects(commands.get('rentgen.testDraft')('minted'),/TRUST_REQUIRED/);
});

function deferred(){let resolve;const promise=new Promise(done=>{resolve=done;});return {promise,resolve};}
function pendingTests(status='completed'){
 const commands=new Map(),messages=[],errors=[],opened=[],shown=[],contexts=[],handles=new Handles();
 const receipt={draft_id:'draft',revision:3,proposal_content_id:'a'.repeat(64)};
 const token=handles.add(receipt),started=deferred(),completed=deferred();
 const result={run_id:'run-v3',status,report:{tests:{baseline:{status:'failed'},candidate:{status:'passed'}}},failure:{code:'TEST_NATIVE_FAILED'}};
 let starts=0,reads=0;
 const vscode={workspace:{isTrusted:true,openTextDocument:async value=>{opened.push(value);return value;}},
  ProgressLocation:{Notification:15},commands:{registerCommand:(name,fn)=>{commands.set(name,fn);return {dispose(){}};},executeCommand:async(...args)=>contexts.push(args)},
  window:{showTextDocument:async value=>shown.push(value),showInformationMessage:value=>messages.push(value),
   showErrorMessage:value=>errors.push(value),withProgress:async(_,fn)=>fn({}, {isCancellationRequested:false,onCancellationRequested:()=>({dispose(){}})})}};
 const service={running:false,dispose(){},cancel(){},profiles:async()=>[{profile_id:'registered',name:'Own tests',modules:[{tests:['One']}]}],
  start:async(selected,profile)=>{assert.deepEqual(selected,receipt);assert.equal(profile,'registered');starts++;started.resolve();await completed.promise;return result;},
  inspect:async id=>{assert.equal(id,result.run_id);reads++;return result;}};
 createTestsUI(vscode,service,{selectedDraft:selected=>handles.get(selected)},{subscriptions:[]},true);
 return {commands,vscode,handles,token,receipt,result,started,completed,messages,errors,opened,shown,contexts,counts:()=>({starts,reads})};
}

for(const status of ['completed','incomplete','failed'])test(`an invalidated ${status} test run remains recoverable without automatic presentation`,async()=>{
 const f=pendingTests(status),pending=f.commands.get('rentgen.testDraft')(f.token,'registered');
 await f.started.promise;f.handles.clear();f.handles.add({...f.receipt,revision:4});
 f.completed.resolve();assert.equal(await pending,f.result);
 assert.deepEqual(f.opened,[]);assert.deepEqual(f.shown,[]);assert.deepEqual(f.messages,[]);assert.deepEqual(f.errors,[]);
 assert.equal(await f.commands.get('rentgen.testResult')(f.result.run_id),f.result);
 assert.equal(f.shown.length,1);assert.equal(f.messages.length,1);assert.deepEqual(f.counts(),{starts:1,reads:1});
});

test('draft invalidation while the test report loads suppresses automatic display',async()=>{
 const f=pendingTests(),loading=deferred(),loaded=deferred();
 f.vscode.workspace.openTextDocument=async value=>{f.opened.push(value);loading.resolve();return loaded.promise;};
 const pending=f.commands.get('rentgen.testDraft')({token:f.token},'registered');
 await f.started.promise;f.completed.resolve();await loading.promise;f.handles.clear();loaded.resolve({language:'json'});
 assert.equal(await pending,f.result);assert.equal(f.opened.length,1);
 assert.deepEqual(f.shown,[]);assert.deepEqual(f.messages,[]);assert.deepEqual(f.errors,[]);
});

test('test result freshness binds the complete receipt rather than only its revision',async()=>{
 const f=pendingTests(),pending=f.commands.get('rentgen.testDraft')(f.token,'registered');
 await f.started.promise;f.handles.records.set(f.token,{...f.receipt,proposal_content_id:'b'.repeat(64)});
 f.completed.resolve();assert.equal(await pending,f.result);
 assert.deepEqual(f.opened,[]);assert.deepEqual(f.shown,[]);assert.deepEqual(f.messages,[]);
});

test('a valid historical test run is shown despite a newer revision and an equal receipt object',async()=>{
 const f=pendingTests();f.handles.add({...f.receipt,revision:4});
 const pending=f.commands.get('rentgen.testDraft')(f.token,'registered');
 await f.started.promise;f.handles.records.set(f.token,{...f.receipt});
 f.completed.resolve();assert.equal(await pending,f.result);
 assert.equal(f.shown.length,1);assert.equal(f.messages.length,1);assert.deepEqual(f.counts(),{starts:1,reads:0});
});

test('test run stays busy through display and suppresses a stale late success message',async()=>{
 const f=pendingTests(),displaying=deferred(),displayed=deferred();
 f.vscode.window.showTextDocument=async value=>{f.shown.push(value);displaying.resolve();await displayed.promise;};
 const pending=f.commands.get('rentgen.testDraft')(f.token,'registered');
 await f.started.promise;f.completed.resolve();await displaying.promise;
 await assert.rejects(f.commands.get('rentgen.testDraft')(f.token,'registered'),/TEST_RUNNING/);
 f.handles.clear();displayed.resolve();assert.equal(await pending,f.result);
 // The already submitted display cannot be recalled, but no late pass is announced.
 assert.equal(f.shown.length,1);assert.deepEqual(f.messages,[]);assert.deepEqual(f.counts(),{starts:1,reads:0});
 assert.deepEqual(f.contexts.at(-1),['setContext','rentgen.testsRunning',false]);
 assert.equal(await f.commands.get('rentgen.testResult')(f.result.run_id),f.result);
 assert.deepEqual(f.counts(),{starts:1,reads:1});
});

test('an unexpected receipt lookup failure propagates and clears the busy state',async()=>{
 const f=pendingTests(),pending=f.commands.get('rentgen.testDraft')(f.token,'registered');
 await f.started.promise;f.handles.get=()=>{throw new Error('UNEXPECTED_RECEIPT_FAILURE');};f.completed.resolve();
 await assert.rejects(pending,/UNEXPECTED_RECEIPT_FAILURE/);
 assert.deepEqual(f.opened,[]);assert.deepEqual(f.messages,[]);
 assert.deepEqual(f.errors,['Рентген: UNEXPECTED_RECEIPT_FAILURE']);
 assert.deepEqual(f.contexts.at(-1),['setContext','rentgen.testsRunning',false]);
 assert.equal(await f.commands.get('rentgen.testResult')(f.result.run_id),f.result);
 assert.deepEqual(f.counts(),{starts:1,reads:1});
});
