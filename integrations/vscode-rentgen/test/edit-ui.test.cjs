'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createEditUI}=require('../lib/edit-ui.cjs');
function fixture(){
 const commands=new Map(),calls=[],session={id:'session',file:'C:\\profile\\module.bsl',receipt:{revision:2}};
 const service={running:false,dispose(){},open:async()=>session,list:async()=>[session],inspect:async()=>({status:'editing',...session}),
  forFile:async file=>{if(file!==session.file)throw new Error('UNKNOWN_EDIT_DOCUMENT');return session;},
  save:async()=>{calls.push('publish');return {id:session.id,status:'saved',receipt:{revision:3}};}};
 const document={uri:{scheme:'file',fsPath:session.file},version:1,isClosed:false,isDirty:true,save:async()=>{calls.push('save-buffer');document.isDirty=false;return true;}};
 const vscode={workspace:{isTrusted:true,openTextDocument:async uri=>({uri})},Uri:{file:fsPath=>({scheme:'file',fsPath})},
  commands:{registerCommand:(n,f)=>{commands.set(n,f);return {dispose(){}};}},window:{activeTextEditor:{document},
   showTextDocument:async()=>calls.push('open'),showInformationMessage:m=>calls.push(m),showErrorMessage:m=>calls.push(m),showQuickPick:async rows=>rows[0]}};
 const views={selectedDraft:token=>{if(token!=='minted')throw new Error('UNKNOWN_VIEW_HANDLE');return session.receipt;},refreshDrafts(){calls.push('refresh-drafts');},openDraft:async(_,current=()=>true)=>{if(!current())return null;calls.push('diff');return ['original','candidate'];}};
 createEditUI(vscode,service,views,{subscriptions:[]},true);return {commands,calls,document,service,vscode,views};
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

test('a selected source opens a manual working copy without a model or draft mutation',async()=>{
 const f=fixture(),ref={relative_path:'Catalogs/Товары/Ext/ObjectModule.bsl'};let seen;
 f.views.selectedSource=token=>{assert.equal(token,'source-token');return ref;};
 f.vscode.window.showInputBox=async options=>{assert.equal(options.value,'ObjectModule.bsl');assert.equal(options.validateInput('Title'),undefined);return 'Ручная правка';};
 f.service.start=async(...args)=>{seen=args;return {id:'new-session',file:'C:\\profile\\new.bsl',kind:'source',source_ref:ref};};
 const value=await f.commands.get('rentgen.editSource')({token:'source-token'});
 assert.deepEqual(seen,[ref,'Ручная правка']);assert.equal(value.id,'new-session');assert.equal(value.receipt,undefined);
 assert.equal(f.calls.filter(c=>c==='open').length,1);assert.equal(f.calls.includes('publish'),false);assert.equal(f.calls.includes('diff'),false);
});

test('cancelled manual-source dialog and revoked trust do not create a session',async()=>{
 const f=fixture();let starts=0;f.views.selectedSource=()=>({relative_path:'Module.bsl'});f.service.start=async()=>{starts++;};
 f.vscode.window.showInputBox=async()=>undefined;assert.equal(await f.commands.get('rentgen.editSource')('source'),null);
 f.vscode.window.showInputBox=async()=>{f.vscode.workspace.isTrusted=false;return 'Title';};
 await assert.rejects(f.commands.get('rentgen.editSource')('source'),/TRUST_REQUIRED/);assert.equal(starts,0);
});

test('a new unsaved source session is discoverable through existing edit recovery',async()=>{
 const f=fixture(),session={id:'new-session',file:'C:\\profile\\new.bsl',kind:'source',source_ref:{relative_path:'Module.bsl'},created_at:'now'};
 f.service.list=async()=>[session];f.service.inspect=async id=>{assert.equal(id,session.id);return {...session,status:'editing'};};
 f.vscode.window.showQuickPick=async rows=>{assert.match(rows[0].label,/Из модуля.*Module.bsl/);return rows[0];};
 assert.equal((await f.commands.get('rentgen.editResult')()).id,session.id);
 assert.equal(f.calls.filter(c=>c==='open').length,1);assert.equal(f.calls.includes('publish'),false);
});

test('manual source command is contributed to the source tree without requiring a model',()=>{
 const manifest=require('../package.json'),command=manifest.contributes.commands.find(c=>c.command==='rentgen.editSource');
 assert.ok(command);assert.equal(command.enablement,'rentgen.ready && rentgen.editAvailable');
 const menu=manifest.contributes.menus['view/item/context'].find(c=>c.command==='rentgen.editSource');
 assert.match(menu.when,/view == rentgen.sources/);assert.match(menu.when,/viewItem == rentgen.source/);
 assert.equal(menu.when.includes('repair'),false);
});

test('a source handle invalidated during the title dialog cancels before reading a module',async()=>{
 const f=fixture(),ref={relative_path:'Module.bsl'};let valid=true,starts=0;
 f.views.selectedSource=()=>{if(!valid)throw new Error('UNKNOWN_VIEW_HANDLE');return ref;};
 f.vscode.window.showInputBox=async()=>{valid=false;return 'Title';};f.service.start=async()=>{starts++;};
 assert.equal(await f.commands.get('rentgen.editSource')('source'),null);assert.equal(starts,0);assert.equal(f.calls.includes('open'),false);
});

for(const boundary of ['source-read','document-open'])test(`late manual source preparation preserves the session without changing editor after ${boundary}`,async()=>{
 const f=fixture(),ref={relative_path:'Module.bsl'},gate=deferred(),began=deferred();
 const session={id:'new-session',file:'C:\\profile\\new.bsl',kind:'source',source_ref:ref};
 f.views.selectedSource=()=>ref;f.vscode.window.showInputBox=async()=> 'Title';
 f.service.start=async()=>{if(boundary==='source-read'){began.resolve();await gate.promise;}return session;};
 f.vscode.workspace.openTextDocument=async uri=>{if(boundary==='document-open'){began.resolve();await gate.promise;}return {uri};};
 const pending=f.commands.get('rentgen.editSource')('source');await began.promise;
 f.vscode.window.activeTextEditor={document:{uri:{scheme:'file',fsPath:'C:\\other.bsl'},version:1}};gate.resolve();
 assert.equal((await pending).id,session.id);assert.equal(f.calls.includes('open'),false);assert.equal(f.calls.includes('publish'),false);
});

for(const status of ['saved','unresolved'])test(`recovering a ${status} session reopens the editable working copy without publishing`,async()=>{
 const f=fixture(),session=await f.service.open();
 f.service.inspect=async()=>({...session,status});
 const shown=[];
 f.vscode.window.showTextDocument=async document=>shown.push(document.uri.fsPath);
 const result=await f.commands.get('rentgen.editResult')(session.id);
 assert.equal(result.status,status);
 assert.deepEqual(shown,[session.file]);
 assert.equal(f.calls.includes('publish'),false);
 assert.equal(f.calls.includes('save-buffer'),false);
});

function deferred(){let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};}
function changed(f,{dirty=true}={}){f.document.version++;f.document.isDirty=dirty;}
function infos(f){return f.calls.filter(c=>typeof c==='string'&&c.startsWith('Рентген: сохранена'));}

test('buffer changed during session lookup refuses submission and preserves the edit',async()=>{
 const f=fixture(),gate=deferred(),began=deferred(),lookup=f.service.forFile;
 f.service.forFile=async file=>{began.resolve();await gate.promise;return lookup(file);};
 const pending=f.commands.get('rentgen.saveDraftEdit')();await began.promise;changed(f);gate.resolve();
 await assert.rejects(pending,/EDIT_BUFFER_CHANGED/);
 assert.equal(f.calls.includes('publish'),false);assert.equal(f.calls.includes('save-buffer'),false);assert.equal(f.document.isDirty,true);
});

test('successful buffer save that leaves newer dirty edits must not submit old disk bytes',async()=>{
 const f=fixture(),gate=deferred(),began=deferred();
 f.document.save=async()=>{began.resolve();await gate.promise;return true;};
 const pending=f.commands.get('rentgen.saveDraftEdit')();await began.promise;changed(f);gate.resolve();
 await assert.rejects(pending,/EDIT_BUFFER_NOT_SAVED/);
 assert.equal(f.calls.includes('publish'),false);assert.equal(f.document.isDirty,true);
});

test('format-on-save may change version when the saved buffer is clean',async()=>{
 const f=fixture();f.document.save=async()=>{f.document.version++;f.document.isDirty=false;return true;};
 const result=await f.commands.get('rentgen.saveDraftEdit')();
 assert.equal(result.receipt.revision,3);assert.equal(f.calls.filter(c=>c==='publish').length,1);assert.equal(infos(f).length,1);
});

for(const alteration of ['typing','autosave','navigation','closed'])test(`${alteration} while Core saves preserves receipt without stealing focus or replay`,async()=>{
 const f=fixture(),gate=deferred(),began=deferred(),save=f.service.save;
 f.service.save=async()=>{began.resolve();await gate.promise;return save();};
 const pending=f.commands.get('rentgen.saveDraftEdit')();await began.promise;
 if(alteration==='typing')changed(f);
 if(alteration==='autosave')changed(f,{dirty:false});
 if(alteration==='navigation')f.vscode.window.activeTextEditor={document:{uri:{scheme:'file',fsPath:'other.bsl'}}};
 if(alteration==='closed')f.document.isClosed=true;
 gate.resolve();const result=await pending;
 assert.equal(result.status,'saved');assert.equal(result.receipt.revision,3);
 assert.equal(f.calls.filter(c=>c==='publish').length,1);assert.equal(f.calls.includes('refresh-drafts'),true);
 assert.equal(f.calls.includes('diff'),false);assert.equal(infos(f).length,0);
});

test('save command stays busy through deferred diff and passes the document guard',async()=>{
 const f=fixture(),gate=deferred(),began=deferred();
 f.views.openDraft=async(_,current=()=>true)=>{began.resolve();await gate.promise;if(!current())return null;f.calls.push('diff');return ['original','candidate'];};
 const pending=f.commands.get('rentgen.saveDraftEdit')();await began.promise;
 const blocked=assert.rejects(f.commands.get('rentgen.saveDraftEdit')(),/EDIT_RUNNING/);
 changed(f,{dirty:false});gate.resolve();await blocked;assert.equal((await pending).receipt.revision,3);
 assert.equal(f.calls.filter(c=>c==='publish').length,1);assert.equal(f.calls.includes('diff'),false);assert.equal(infos(f).length,0);
});

test('the requested diff may take focus and still report the exact stable saved revision',async()=>{
 const f=fixture();f.views.openDraft=async(_,current=()=>true)=>{
  assert.equal(current(),true);f.calls.push('diff');
  const candidate={toString:()=> 'rentgen-view://candidate/module.bsl'};
  f.vscode.window.activeTextEditor={document:{uri:candidate}};return ['original',candidate];
 };
 assert.equal((await f.commands.get('rentgen.saveDraftEdit')()).receipt.revision,3);
 assert.equal(infos(f).length,1);
});

test('navigation after diff submission suppresses only the late toast, preserving committed receipt',async()=>{
 const f=fixture(),gate=deferred(),began=deferred();
 const candidate={toString:()=> 'rentgen-view://candidate/module.bsl'};
 f.views.openDraft=async(_,current)=>{assert.equal(current(),true);f.calls.push('diff');began.resolve();await gate.promise;return ['original',candidate];};
 const pending=f.commands.get('rentgen.saveDraftEdit')();await began.promise;
 f.vscode.window.activeTextEditor={document:{uri:{toString:()=> 'file:///other.bsl'}}};gate.resolve();
 const result=await pending;assert.equal(result.status,'saved');assert.equal(result.receipt.revision,3);
 assert.equal(f.calls.filter(c=>c==='publish').length,1);assert.equal(f.calls.filter(c=>c==='diff').length,1);assert.equal(infos(f).length,0);
});
