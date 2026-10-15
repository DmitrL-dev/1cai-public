'use strict';
// Constructed editor surface; installed Windows Extension Host is a separate gate.
const test = require('node:test'), assert = require('node:assert/strict');
const {createViews} = require('../lib/views.cjs');
const {createWorkbenchState} = require('../lib/workbench-state.cjs');
const {createEditUI} = require('../lib/edit-ui.cjs');
const project = '00000000-0000-4000-8000-000000000001';
const config = {schema:1,core_version:'0.1.0.dev19',project_id:project,python:'C:\\installed\\python.exe',registry:'C:\\registry.sqlite3'};
const snapshot = char => ({project_id:project,snapshot_id:char.repeat(64),manifest_hash:char.repeat(64)});
const ref = selected => ({snapshot:selected,layer_id:'base',relative_path:'CommonModules/Первый/Ext/Module.bsl',raw_sha256:'c'.repeat(64)});
const receipt = revision => ({project_id:project,draft_id:'00000000-0000-4000-8000-000000000002',revision,
  source_ref:ref(snapshot('a')),title:'Manual',proposal_content_id:'d'.repeat(64)});
function memory() {let value;return {get:()=>value,update:async(_,next)=>{value=next;},value:()=>value};}
function fixture(storage=memory()) {
  const commands=new Map(),shown=[],comparisons=[],panels=new Map(),context={subscriptions:[]};
  const state={head:snapshot('a'),headReads:0,sourceReads:[],draftReads:[],denied:null};
  let provider,closed;
  class EventEmitter {
    constructor(){this.listeners=new Set();this.event=fn=>{this.listeners.add(fn);return {dispose:()=>this.listeners.delete(fn)};};}
    fire(value){for(const fn of this.listeners)fn(value);}dispose(){this.listeners.clear();}
  }
  const client={head:async()=>{state.headReads++;if(state.denied)throw state.denied;return {snapshot:state.head};},
    sources:async selected=>{state.sourceReads.push(selected);if(state.denied)throw state.denied;return {entries:[{ref:ref(selected)}],next_cursor:null};},
    source:async value=>{if(state.denied)throw state.denied;return value.snapshot.snapshot_id;},
    draft:async(id,revision)=>{state.draftReads.push([id,revision]);if(state.denied)throw state.denied;return {receipt:receipt(revision),text:'saved '+revision};},
    drafts:async()=>({items:[receipt(3)],next_after:null}),history:async()=>({items:[receipt(2)],next_before:null})};
  const vscode={EventEmitter,TreeItemCollapsibleState:{None:0,Collapsed:1},TreeItem:class{},ThemeIcon:class{},
    Uri:{from:fields=>({query:'',fragment:'',...fields})},
    workspace:{isTrusted:true,registerTextDocumentContentProvider:(_,value)=>{provider=value;return {dispose(){}};},onDidCloseTextDocument:fn=>{closed=fn;return {dispose(){}};},
      openTextDocument:async uri=>({uri,text:await provider.provideTextDocumentContent(uri)})},
    commands:{registerCommand:(id,fn)=>{commands.set(id,fn);return {dispose(){}};},executeCommand:async(...args)=>comparisons.push(args)},
    window:{activeTextEditor:null,createTreeView:(id,opts)=>{const panel={...opts,dispose(){}};panels.set(id,panel);return panel;},
      showTextDocument:async doc=>shown.push(doc),showErrorMessage(){},showInputBox:async()=>undefined,showQuickPick:async()=>undefined}};
  let trusted=true;
  const workbench=createWorkbenchState(storage,config);
  const views=createViews(vscode,client,context,{workbench,projectId:project,trusted:()=>trusted});
  return {views,client,state,vscode,commands,shown,comparisons,storage,context,panels,workbench,
    read:uri=>provider.provideTextDocumentContent(uri),close:uri=>closed({uri}),
    trust:value=>{trusted=value;},dispose:()=>context.subscriptions.slice().reverse().forEach(item=>item.dispose())};
}
test('second process restores exact historical snapshot and selected saved draft without reading newer head',async()=>{
  const storage=memory(),first=fixture(storage);await first.views.initialize();
  await first.views.openDraft(receipt(3));await first.workbench.drain();first.dispose();
  const second=fixture(storage);second.state.head=snapshot('b');await second.views.initialize();
  assert.deepEqual(second.views.selectedSnapshot(),snapshot('a'));assert.equal(second.state.headReads,0);
  assert.deepEqual(second.state.sourceReads,[snapshot('a')]);
  assert.deepEqual(second.views.workbenchSnapshot().selection,{kind:'draft',draft_id:receipt(3).draft_id,revision:3});
  assert.equal(second.comparisons.length,1);assert.match(second.comparisons[0][3],/v3/);
  assert.ok(second.state.draftReads.every(([,revision])=>revision===3));
});
test('restored source is re-read by its exact reference and keeps the saved module query',async()=>{
  const storage=memory(),first=fixture(storage);await first.views.initialize();await first.views.search('Первый');
  const selected=(await first.views.sources())[0];await first.commands.get('rentgen.openSelection')(selected.token);first.dispose();
  const second=fixture(storage);second.state.head=snapshot('b');await second.views.initialize();
  assert.equal(second.views.workbenchSnapshot().query,'Первый');assert.equal(second.shown.length,1);
  assert.equal(second.shown[0].text,'a'.repeat(64));assert.equal(second.state.headReads,0);
});
test('unavailable historical pin fails explicitly and only reset selects the latest head',async()=>{
  const storage=memory(),first=fixture(storage);await first.views.initialize();first.dispose();
  const second=fixture(storage);second.state.head=snapshot('b');second.state.denied=new Error('SNAPSHOT_NOT_FOUND');
  await assert.rejects(second.views.initialize(),/SNAPSHOT_NOT_FOUND/);
  assert.equal(second.state.headReads,0);assert.equal(second.views.selectedSnapshot(),null);
  assert.deepEqual(storage.value().snapshot,snapshot('a'));
  second.state.denied=null;await second.commands.get('rentgen.resetWorkbench')();
  assert.deepEqual(second.views.selectedSnapshot(),snapshot('b'));assert.equal(second.state.headReads,1);
});
test('dirty document survives restoring selection without buffer save, close or focus change',async()=>{
  const storage=memory(),first=fixture(storage);await first.views.initialize();await first.views.openDraft(receipt(3));first.dispose();
  const second=fixture(storage),document={isDirty:true,getText:()=> 'unsaved local change',save:()=>{throw new Error('UNEXPECTED_SAVE');}};
  second.vscode.window.activeTextEditor={document};await second.views.initialize();
  assert.deepEqual(second.shown,[]);assert.deepEqual(second.comparisons,[]);
  assert.equal(second.vscode.window.activeTextEditor.document,document);assert.equal(document.getText(),'unsaved local change');
  assert.equal(second.views.workbenchSnapshot().selection.revision,3);
});
test('corrupt persisted state performs no Core read and cannot be overwritten by selecting a pin',async()=>{
  const storage=memory();await storage.update('',{schema:999});const f=fixture(storage);
  await assert.rejects(f.views.initialize(),/WORKBENCH_STATE_INVALID/);assert.equal(f.state.headReads,0);assert.deepEqual(f.state.sourceReads,[]);
  await assert.rejects(f.views.selectSnapshot(snapshot('a')),/WORKBENCH_STATE_INVALID/);
  assert.deepEqual(storage.value(),{schema:999});await f.commands.get('rentgen.resetWorkbench')();
  assert.equal(storage.value().schema,1);assert.deepEqual(storage.value().snapshot,snapshot('a'));
});
test('late restored snapshot cannot override a subsequent explicit refresh',async()=>{
  const storage=memory(),first=fixture(storage);await first.views.initialize();first.dispose();
  const second=fixture(storage);let resolve,began;
  const started=new Promise(done=>{began=done;});
  second.client.sources=()=>{began();return new Promise(done=>{resolve=done;});};
  const pending=second.views.initialize();await started;
  second.state.head=snapshot('b');await second.views.refreshSources();resolve({entries:[],next_cursor:null});await pending;
  assert.deepEqual(second.views.selectedSnapshot(),snapshot('b'));assert.deepEqual(storage.value().snapshot,snapshot('b'));
});
test('untrusted or disposed workbench never starts additional Core reads',async()=>{
  const f=fixture();await f.views.initialize();const count=f.state.headReads;
  f.trust(false);await assert.rejects(f.views.refreshSources(),/TRUST_REQUIRED/);await assert.rejects(f.views.initialize(),/TRUST_REQUIRED/);
  f.trust(true);f.dispose();await assert.rejects(f.views.initialize(),/TRUST_REQUIRED/);assert.equal(f.state.headReads,count);
});
test('a newer saved revision replaces persistent selection only after a real read/diff',async()=>{
  const f=fixture();await f.views.initialize();await f.views.openDraft(receipt(3));
  assert.equal(f.views.workbenchSnapshot().selection.revision,3);
  assert.equal(await f.views.openDraft(receipt(4),()=>false),null);assert.equal(f.storage.value().selection.revision,3);
  await f.views.openDraft(receipt(4));assert.equal(f.storage.value().selection.revision,4);
  assert.ok(f.state.draftReads.some(([,revision])=>revision===4));
});
test('opening a historical draft keeps its own source snapshot distinct from the pinned tree across restart',async()=>{
  const storage=memory(),first=fixture(storage);await first.views.initialize();await first.views.selectSnapshot(snapshot('b'));
  await first.views.openDraft(receipt(3));
  assert.deepEqual(first.views.selectedSnapshot(),snapshot('b'));
  assert.match(first.comparisons[0][3],/aaaaaaaaaaaa/);
  assert.match(first.panels.get('rentgen.drafts').message,/исходник aaaaaaaaaaaa\. Дерево: bbbbbbbbbbbb/);
  assert.deepEqual(storage.value().snapshot,snapshot('b'));first.dispose();
  const second=fixture(storage);second.state.head=snapshot('c');await second.views.initialize();
  assert.deepEqual(second.state.sourceReads,[snapshot('b')]);assert.equal(second.state.headReads,0);
  assert.deepEqual(second.views.workbenchSnapshot().selection,{kind:'draft',draft_id:receipt(3).draft_id,revision:3});
  assert.match(second.comparisons[0][3],/aaaaaaaaaaaa/);
});
test('workbench projections cannot mutate the pinned snapshot or selected source without a command',async()=>{
  const f=fixture();await f.views.initialize();const source=(await f.views.sources())[0];
  await f.commands.get('rentgen.openSelection')(source.token);
  const state=f.views.workbenchSnapshot(),stored=JSON.stringify(f.storage.value());
  assert.throws(()=>{state.snapshot.snapshot_id='b'.repeat(64);},TypeError);
  assert.throws(()=>{state.selection.ref.snapshot.snapshot_id='b'.repeat(64);},TypeError);
  assert.throws(()=>{state.selection.ref.relative_path='forged.bsl';},TypeError);
  assert.throws(()=>{state.selection={kind:'draft'};},TypeError);
  assert.throws(()=>{f.views.selectedSnapshot().project_id='forged';},TypeError);
  assert.deepEqual(f.views.selectedSnapshot(),snapshot('a'));assert.equal(JSON.stringify(f.storage.value()),stored);
  await f.views.openDraft(receipt(3));const draft=f.views.workbenchSnapshot();
  assert.throws(()=>{draft.selection.revision=999;},TypeError);assert.equal(f.views.workbenchSnapshot().selection.revision,3);
});
test('a source read completing after a new pin cannot steal focus or replace selection',async()=>{
  const f=fixture();await f.views.initialize();const source=(await f.views.sources())[0];let began,finish;
  const started=new Promise(resolve=>{began=resolve;});f.client.source=async()=>{began();return new Promise(resolve=>{finish=resolve;});};
  const pending=f.commands.get('rentgen.openSelection')(source.token);await started;
  await f.views.selectSnapshot(snapshot('b'));finish('old snapshot');assert.equal(await pending,null);
  assert.deepEqual(f.shown,[]);assert.deepEqual(f.storage.value().snapshot,snapshot('b'));assert.equal(f.storage.value().selection,null);
});
test('an older module click completing late cannot replace a newer selection in the same snapshot',async()=>{
  const f=fixture();await f.views.initialize();let began,finish;
  const old=f.views.registerSource({...ref(snapshot('a')),relative_path:'CommonModules/Old/Ext/Module.bsl'});
  const next=f.views.registerSource({...ref(snapshot('a')),relative_path:'CommonModules/New/Ext/Module.bsl'});
  const started=new Promise(resolve=>{began=resolve;});f.client.source=async value=>{
    if(value.relative_path.includes('/Old/')){began();return new Promise(resolve=>{finish=resolve;});}return 'new selection';};
  const pending=f.commands.get('rentgen.openSelection')(old.token);await started;
  await f.commands.get('rentgen.openSelection')(next.token);finish('late old selection');assert.equal(await pending,null);
  assert.deepEqual(f.shown.map(document=>document.text),['new selection']);assert.equal(f.storage.value().selection.ref.relative_path,next.ref.relative_path);
});
test('a draft read completing after explicit refresh never submits the stale diff',async()=>{
  const f=fixture();await f.views.initialize();let began,finish;
  const started=new Promise(resolve=>{began=resolve;});f.client.draft=async()=>{began();return new Promise(resolve=>{finish=resolve;});};
  const pending=f.views.openDraft(receipt(3));await started;f.state.head=snapshot('b');await f.views.refreshSources();
  finish({receipt:receipt(3),text:'old saved draft'});assert.equal(await pending,null);
  assert.deepEqual(f.comparisons,[]);assert.deepEqual(f.storage.value().snapshot,snapshot('b'));assert.equal(f.storage.value().selection,null);
});
test('saved revision reuses one immutable document URI until the actual document closes',async()=>{
  const f=fixture();await f.views.initialize();const first=await f.views.draftDocument(receipt(3));
  const [,shown]=await f.views.openDraft(receipt(3));const again=await f.views.draftDocument(receipt(3));
  assert.equal(first.uri,shown);assert.equal(again.uri,shown);assert.equal(await f.read(shown),'saved 3');
  f.close(shown);await assert.rejects(f.read(shown),/UNKNOWN_VIEW_HANDLE/);
  const reopened=await f.views.draftDocument(receipt(3));assert.notEqual(reopened.uri.authority,shown.authority);
});
test('a failed comparison never revokes an already retained saved revision URI',async()=>{
  const f=fixture();await f.views.initialize();const first=await f.views.draftDocument(receipt(3));
  f.client.source=async()=>{throw new Error('SOURCE_READ_FAILED');};
  await assert.rejects(f.views.openDraft(receipt(3)),/SOURCE_READ_FAILED/);
  assert.equal(await f.read(first.uri),'saved 3');assert.equal((await f.views.draftDocument(receipt(3))).uri,first.uri);
});
test('a real edit presenter retains a commit but never displays or selects it after the user pins a different snapshot',async()=>{
  const f=fixture();await f.views.initialize();let began,finish;
  const started=new Promise(resolve=>{began=resolve;});
  const document={uri:{scheme:'file',fsPath:'C:\\profile\\manual.bsl'},version:1,isDirty:false,isClosed:false};
  f.vscode.window.activeTextEditor={document};
  const service={running:false,dispose(){},forFile:async()=>({id:'manual-session'}),
    save:async()=>{began();return new Promise(resolve=>{finish=resolve;});}};
  createEditUI(f.vscode,service,f.views,f.context,true);
  const pending=f.commands.get('rentgen.saveDraftEdit')();await started;await f.views.selectSnapshot(snapshot('b'));
  finish({status:'saved',receipt:receipt(3)});const saved=await pending;
  assert.equal(saved.status,'saved');assert.equal(saved.receipt.revision,3);assert.deepEqual(f.comparisons,[]);
  assert.deepEqual(f.views.selectedSnapshot(),snapshot('b'));assert.equal(f.storage.value().selection,null);
});
test('mutating a pending pin argument cannot substitute a snapshot that Core did not verify',async()=>{
  const f=fixture();await f.views.initialize();let began,finish,verified;
  const started=new Promise(resolve=>{began=resolve;});f.client.sources=async selected=>{
    verified=selected;began();return new Promise(resolve=>{finish=resolve;});};
  const requested=snapshot('b'),pending=f.views.selectSnapshot(requested);await started;
  Object.assign(requested,snapshot('c'));finish({entries:[],next_cursor:null});await pending;
  assert.deepEqual(verified,snapshot('b'));assert.deepEqual(f.views.selectedSnapshot(),snapshot('b'));
  assert.deepEqual(f.storage.value().snapshot,snapshot('b'));
});
