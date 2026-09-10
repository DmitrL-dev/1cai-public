'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createEditUI}=require('../lib/edit-ui.cjs');
function fixture(){
 const commands=new Map(),calls=[],session={id:'session',file:'C:\\profile\\module.bsl',receipt:{revision:2}};
 const service={running:false,dispose(){},open:async()=>session,list:async()=>[session],inspect:async()=>({status:'editing',...session}),
  forFile:async file=>{if(file!==session.file)throw new Error('UNKNOWN_EDIT_DOCUMENT');return session;},
  save:async()=>{calls.push('publish');return {id:session.id,status:'saved',receipt:{revision:3}};}};
 const document={uri:{scheme:'file',fsPath:session.file},isDirty:true,save:async()=>{calls.push('save-buffer');return true;}};
 const vscode={workspace:{isTrusted:true,openTextDocument:async uri=>({uri})},Uri:{file:fsPath=>({scheme:'file',fsPath})},
  commands:{registerCommand:(n,f)=>{commands.set(n,f);return {dispose(){}};}},window:{activeTextEditor:{document},
   showTextDocument:async()=>calls.push('open'),showInformationMessage:m=>calls.push(m),showErrorMessage:m=>calls.push(m),showQuickPick:async rows=>rows[0]}};
 const views={selectedDraft:token=>{if(token!=='minted')throw new Error('UNKNOWN_VIEW_HANDLE');return session.receipt;},refreshDrafts(){},openDraft:async()=>calls.push('diff')};
 createEditUI(vscode,service,views,{subscriptions:[]},true);return {commands,calls,document,service,vscode};
}
test('foreign documents and cancelled buffer save never publish',async()=>{
 const f=fixture();await assert.rejects(f.commands.get('rentgen.editDraft')('forged'),/UNKNOWN_VIEW_HANDLE/);
 f.document.uri.fsPath='C:\\user-file.bsl';await assert.rejects(f.commands.get('rentgen.saveDraftEdit')(),/UNKNOWN_EDIT_DOCUMENT/);
 assert.equal(f.calls.includes('save-buffer'),false);assert.equal(f.calls.includes('publish'),false);
 f.document.uri.fsPath='C:\\profile\\module.bsl';f.document.save=async()=>false;
 await assert.rejects(f.commands.get('rentgen.saveDraftEdit')(),/EDIT_BUFFER_NOT_SAVED/);assert.equal(f.calls.includes('publish'),false);
});
test('publish follows buffer save; inspecting a session never publishes',async()=>{
 const f=fixture();await f.commands.get('rentgen.editDraft')('minted');
 await f.commands.get('rentgen.saveDraftEdit')();assert.ok(f.calls.indexOf('save-buffer')<f.calls.indexOf('publish'));
 await f.commands.get('rentgen.editResult')('session');assert.equal(f.calls.filter(c=>c==='publish').length,1);
});
