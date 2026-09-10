'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createTestsUI}=require('../lib/tests-ui.cjs');
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
