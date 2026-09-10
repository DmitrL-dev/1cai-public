'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createBslUI}=require('../lib/bsl-ui.cjs');
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
