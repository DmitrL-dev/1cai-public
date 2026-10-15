'use strict';
// Constructed TreeView surface; no claim of an actual editor run.
const test=require('node:test'),assert=require('node:assert/strict');
const {createMetadataView}=require('../lib/metadata-view.cjs');
const project='00000000-0000-4000-8000-000000000001';
const snapshot=char=>({project_id:project,snapshot_id:char.repeat(64),manifest_hash:char.repeat(64)});
const ref=(selected,path)=>({snapshot:selected,layer_id:'base',relative_path:path,raw_sha256:'b'.repeat(64)});
function deferred(){let resolve;const promise=new Promise(done=>{resolve=done;});return {promise,resolve};}
function fixture(options={}){
 const commands=new Map(),panels=new Map(),minted=new Map(),requests=[],events=[],context={subscriptions:[]};
 let selected=snapshot('a'),trusted=true,counter=0;
 class EventEmitter{constructor(){this.listeners=new Set();this.event=fn=>{this.listeners.add(fn);return {dispose:()=>this.listeners.delete(fn)};};}fire(){for(const fn of this.listeners)fn();}dispose(){}}
 const changed=new EventEmitter();
 const views={selectedSnapshot:()=>selected,onDidChangeContext:changed.event,
  registerSource:reference=>{assert.deepEqual(reference.snapshot,selected);const node={kind:'source',ref:reference,token:'source-'+(++counter)};minted.set(node.token,node.ref);return node;},
  selectedSource:token=>{if(!minted.has(token))throw new Error('UNKNOWN_VIEW_HANDLE');return minted.get(token);}};
 const client={metadataSearch:async(s,{query})=>{
  requests.push(['search',s,query]);return {snapshot:s,objects:[{type:'Catalog',name:'Одинаковое имя',source_ref:ref(s,'Catalogs/Первый.xml')},
   {type:'Document',name:'Одинаковое имя',source_ref:ref(s,'Documents/Первый.xml')}],returned:2,total_matches:2,truncated:false,completeness:'supported_layer_inventory'};
 },metadataObject:async(s,reference)=>{
  requests.push(['object',s,reference]);return {object:{modules:{items:[{source_ref:ref(s,reference.relative_path.replace('.xml','/Ext/Module.bsl'))}],truncated:false,total:1}}};
 }};
 const vscode={EventEmitter,TreeItemCollapsibleState:{Collapsed:1,None:0},TreeItem:class{constructor(label,state){this.label=label;this.collapsibleState=state;}},ThemeIcon:class{},
  commands:{registerCommand:(name,fn)=>{commands.set(name,fn);return {dispose(){}};}},
  window:{createTreeView:(id,value)=>{const panel={...value,dispose(){}};panels.set(id,panel);return panel;},showErrorMessage:message=>events.push(message),showInputBox:async()=>undefined}};
 const metadata=createMetadataView(vscode,client,views,context,{...options,trusted:()=>trusted});
 return {metadata,commands,panels,client,requests,minted,events,
  select:value=>{selected=value;minted.clear();changed.fire();},trust:value=>{trusted=value;},
  dispose:()=>context.subscriptions.slice().reverse().forEach(item=>item.dispose())};
}
test('real object grouping leads to exact module source handles, never equal display labels',async()=>{
 const f=fixture(),groups=await f.metadata.roots();assert.deepEqual(groups.map(g=>g.type),['Catalog','Document']);
 const object=(await f.metadata.children(groups[0].token))[0];
 assert.equal(object.object.name,'Одинаковое имя');
 const modules=await f.metadata.children(object.token);assert.equal(modules[0].ref.relative_path,'Catalogs/Первый/Ext/Module.bsl');
 const provider=f.panels.get('rentgen.metadata').treeDataProvider;
 const item=provider.getTreeItem(modules[0]);assert.equal(item.contextValue,'rentgen.source');
 assert.deepEqual(item.command,{command:'rentgen.openSelection',title:'Открыть сохранённый модуль',arguments:[modules[0].token]});
 await assert.rejects(f.metadata.children(object.object.name),/UNKNOWN_VIEW_HANDLE/);
 assert.equal(f.requests.filter(r=>r[0]==='object').length,1);
});
test('same group expansion reuses bounded object handles while module reads reauthorize',async()=>{
 const f=fixture(),group=(await f.metadata.roots())[0];
 const first=await f.metadata.children(group.token),again=await f.metadata.children(group.token);assert.equal(first,again);
 await f.metadata.children(first[0].token);await f.metadata.children(first[0].token);
 assert.equal(f.requests.filter(r=>r[0]==='object').length,2);
});
test('search is bounded and literal, and partial matches are explicitly visible',async()=>{
 const f=fixture();f.client.metadataSearch=async(s,{query})=>{
  assert.equal(query,'--help');return {snapshot:s,objects:[],returned:0,total_matches:500,truncated:true,completeness:'unsupported_layers'};
 };
 assert.deepEqual(await f.commands.get('rentgen.searchMetadata')('--help'),[]);
 assert.match(f.panels.get('rentgen.metadata').message,/неполный/);
 for(const query of ['\n','x'.repeat(257),{},null])await assert.rejects(f.metadata.search(query),/INVALID_SEARCH/);
});
test('disabled legacy Core never receives a new metadata command',async()=>{
 const f=fixture({enabled:false});assert.deepEqual(await f.metadata.roots(),[]);assert.deepEqual(f.requests,[]);
 assert.match(f.panels.get('rentgen.metadata').message,/не предоставляет/);
});
test('new snapshot invalidates previous object handles and late search results',async()=>{
 const f=fixture(),old=(await f.metadata.roots())[0],waiting=deferred(),began=deferred();
 f.client.metadataSearch=async()=>{began.resolve();return waiting.promise;};
 const pending=f.metadata.refresh();await began.promise;f.select(snapshot('b'));
 waiting.resolve({objects:[{type:'Catalog',name:'Old',source_ref:ref(snapshot('a'),'Catalogs/Old.xml')}],returned:1,total_matches:1,truncated:false,completeness:'supported_layer_inventory'});
 assert.deepEqual(await pending,[]);await assert.rejects(f.metadata.children(old.token),/UNKNOWN_VIEW_HANDLE/);
 assert.equal(f.minted.size,0);
});
test('late object expansion cannot register a module under a newer snapshot',async()=>{
 const f=fixture(),group=(await f.metadata.roots())[0],object=(await f.metadata.children(group.token))[0],waiting=deferred(),began=deferred();
 f.client.metadataObject=async()=>{began.resolve();return waiting.promise;};
 const pending=f.metadata.children(object.token);await began.promise;f.select(snapshot('b'));
 waiting.resolve({object:{modules:{items:[{source_ref:ref(snapshot('a'),'secret.bsl')}],truncated:false,total:1}}});
 assert.deepEqual(await pending,[]);assert.equal(f.minted.size,0);
});
test('Core denial clears handles and does not start an automatic retry loop',async()=>{
 const f=fixture(),group=(await f.metadata.roots())[0],object=(await f.metadata.children(group.token))[0];
 const provider=f.panels.get('rentgen.metadata').treeDataProvider;let notifications=0;
 provider.onDidChangeTreeData(()=>notifications++);
 f.client.metadataObject=async()=>{throw new Error('PROJECT_FORBIDDEN');};
 await assert.rejects(f.metadata.children(object.token),/PROJECT_FORBIDDEN/);assert.match(f.panels.get('rentgen.metadata').message,/PROJECT_FORBIDDEN/);
 await assert.rejects(f.metadata.children(object.token),/UNKNOWN_VIEW_HANDLE/);assert.deepEqual(await f.metadata.roots(),[]);
 assert.equal(f.requests.filter(r=>r[0]==='search').length,1);
 assert.equal(notifications,1);assert.deepEqual(await provider.getChildren(),[]);
 assert.throws(()=>provider.getTreeItem(object),/UNKNOWN_VIEW_HANDLE/);
});
test('trust loss or disposal during a request prevents publishing metadata rows',async()=>{
 for(const action of ['trust','dispose']){
  const f=fixture(),waiting=deferred();f.client.metadataSearch=()=>waiting.promise;
  const pending=f.metadata.roots();await new Promise(done=>setImmediate(done));
  if(action==='trust')f.trust(false);else f.dispose();
  waiting.resolve({objects:[],returned:0,total_matches:0,truncated:false,completeness:'supported_layer_inventory'});
  await assert.rejects(pending,/TRUST_REQUIRED/);assert.equal(f.minted.size,0);
 }
});
