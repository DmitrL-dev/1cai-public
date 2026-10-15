'use strict';
// Composition against constructed editor/process APIs; never native acceptance.
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const path=require('node:path'),{readFileSync}=require('node:fs'),{createHash}=require('node:crypto');
const root=path.join(__dirname,'..'),source=readFileSync(path.join(root,'extension.cjs'),'utf8');
const project='00000000-0000-4000-8000-000000000001';
const selected={project_id:project,snapshot_id:'a'.repeat(64),manifest_hash:'a'.repeat(64)};
const bytes=Buffer.from('Процедура Проверка()\r\nКонецПроцедуры\r\n');
const moduleRef={snapshot:selected,layer_id:'base',relative_path:'CommonModules/Probe/Ext/Module.bsl',raw_sha256:createHash('sha256').update(bytes).digest('hex')};
const objectRef={...moduleRef,relative_path:'CommonModules/Probe.xml',raw_sha256:'b'.repeat(64)};
const config={schema:1,core_version:'0.1.0.dev19',project_id:project,python:'C:\\installed\\python.exe',registry:'C:\\registry.sqlite3'};
function fixture({metadata=true,stored}={}){
 const calls=[],commands=new Map(),contexts=new Map(),providers=new Map(),panels=new Map(),messages=[];let state=stored;
 class EventEmitter{constructor(){this.rows=new Set();this.event=fn=>{this.rows.add(fn);return {dispose:()=>this.rows.delete(fn)};};}fire(value){for(const fn of this.rows)fn(value);}dispose(){this.rows.clear();}}
 const editor={EventEmitter,TreeItem:class{},ThemeIcon:class{},TreeItemCollapsibleState:{None:0,Collapsed:1},
  Uri:{from:value=>({query:'',fragment:'',...value}),file:fsPath=>({scheme:'file',fsPath})},
  workspace:{isTrusted:true,registerTextDocumentContentProvider:(scheme,provider)=>{providers.set(scheme,provider);return {dispose(){}};},
   onDidCloseTextDocument:()=>({dispose(){}}),onDidChangeTextDocument:()=>({dispose(){}}),
   openTextDocument:async uri=>({uri,getText:()=> '',isDirty:false})},
  languages:{createDiagnosticCollection:()=>({clear(){},dispose(){},set(){}})},
  commands:{registerCommand:(name,fn)=>{commands.set(name,fn);return {dispose:()=>commands.delete(name)};},
   executeCommand:async(name,key,value)=>{if(name==='setContext')contexts.set(key,value);}},
  window:{createTreeView:(id,options)=>{const panel={...options,dispose(){}};panels.set(id,panel);return panel;},
   showTextDocument:async()=>{},showErrorMessage:message=>messages.push(message),showInputBox:async()=>undefined,showQuickPick:async()=>undefined}};
 const descriptor={source_ref:objectRef,type:'CommonModule',name:'Probe',synonym:null,observed_uuid:null,uuid_status:'unverified'};
 const navigation={schema:1,snapshot:selected,identity_status:'source_path_only',parser_profiles:['designer_xml_v1'],
  completeness:'supported_layer_inventory',truncated:false,layers:[{layer_id:'base',status:'supported',completeness:'supported_layer_inventory'}],source_refs:[objectRef,moduleRef]};
 const runner={dispose(){},execute:async(_,args)=>{
  calls.push(args);let value;
  if(args[3]==='project-head')value={project_id:project,snapshot:selected};
  else if(args[3]==='capabilities')value={contract_version:1,platform:'win32',scope:'os-adapter-support',capabilities:{'snapshot.retained.read':{
   supported:true,operations:metadata?['source-list','metadata-summary','metadata-search','metadata-object']:['source-list'],
  }}};
  else if(args[3]==='source-list')value={entries:[{ref:moduleRef}],next_cursor:null};
  else if(args[3]==='metadata-search')value={...navigation,objects:[descriptor],returned:1,total_matches:1};
  else if(args[3]==='metadata-object')value={...navigation,completeness:'parsed_supported_object',object:{...descriptor,
   modules:{items:[{source_ref:moduleRef,status:'verified_bytes',size_bytes:bytes.length,encoding:'utf-8'}],total:1,truncated:false}}};
  else if(args[3]==='source-read')value={ref:moduleRef,raw_sha256:moduleRef.raw_sha256,size_bytes:bytes.length,encoding:'base64',data:bytes.toString('base64')};
  else throw new Error('UNEXPECTED_CLI_COMMAND '+args[3]);
  return {code:0,stdout:Buffer.from(JSON.stringify({result:value}))};
 }};
 const raw=Buffer.from(JSON.stringify(config));
 const sandbox=vm.createContext({exports:{},Buffer,TextDecoder,process:{env:{RENTGEN_EDITOR_PROFILE:'C:\\profile'},platform:'win32'},require:name=>{
  if(name==='vscode')return editor;if(name==='node:path')return path.win32;
  if(name==='node:fs/promises')return {open:async()=>({stat:async()=>({size:raw.length}),read:async buffer=>{raw.copy(buffer);return {bytesRead:raw.length};},close:async()=>{}})};
  if(name==='./lib/process.cjs')return {createRunner:()=>runner};
  if(name.startsWith('./lib/'))return require(path.join(root,name));throw new Error('UNEXPECTED_IMPORT '+name);
 }});
 vm.runInContext(source,sandbox);
 const context={subscriptions:[],extensionPath:root,workspaceState:{get:()=>state,update:async(_,value)=>{state=value;}}};
 return {activate:()=>sandbox.exports.activate(context),commands,contexts,calls,panels,messages,providers,state:()=>state,context};
}
test('published dev19 without navigation commands retains existing modules and draft activation',async()=>{
 const f=fixture({metadata:false}),api=await f.activate();assert.equal(api.ready,true);assert.equal(api.navigationAvailable,false);
 assert.equal(f.contexts.get('rentgen.ready'),true);assert.equal(f.contexts.get('rentgen.metadataAvailable'),false);
 assert.deepEqual(await api.metadataRoots(),[]);assert.equal((await api.sources()).length,1);
 assert.equal(f.calls.some(args=>args[3].startsWith('metadata-')),false);
 assert.ok(f.commands.has('rentgen.editSource'));assert.ok(f.commands.has('rentgen.bslCheck'));
 assert.deepEqual(f.calls.find(args=>args[3]==='capabilities'),['-I','-m','rentgen_core','capabilities']);
});
test('advertised current Core wires actual metadata tree through the same source handles as modules',async()=>{
 const f=fixture(),api=await f.activate();assert.equal(api.ready,true);assert.equal(api.navigationAvailable,true);
 const groups=await api.metadataSearch('Probe'),objects=await api.metadataChildren(groups[0].token);
 assert.equal(objects[0].object.name,'Probe');const modules=await api.metadataChildren(objects[0].token);
 assert.deepEqual(api.selectedSource(modules[0].token),moduleRef);
 const source=await api.openSourceRef(modules[0].ref);
 assert.equal(await f.providers.get('rentgen-view').provideTextDocumentContent(source[0]),bytes.toString('utf8'));
 assert.equal(f.state().selection.kind,'source');assert.deepEqual(f.state().selection.ref,moduleRef);
});
test('corrupt stored context leaves an explicit reset path instead of selecting current head',async()=>{
 const f=fixture({stored:{schema:99}}),api=await f.activate();assert.equal(api.ready,false);assert.equal(api.error,'WORKBENCH_STATE_INVALID');
 assert.equal(f.contexts.get('rentgen.ready'),false);assert.equal(f.contexts.get('rentgen.profileLoaded'),true);
 assert.equal(f.calls.some(args=>args[3]==='project-head'),false);assert.equal(f.state().schema,99);
 await f.commands.get('rentgen.resetWorkbench')();assert.deepEqual(api.selectedSnapshot(),selected);
 assert.equal(f.contexts.get('rentgen.ready'),true);assert.equal(f.state().schema,1);
 assert.ok(f.messages.some(message=>message.includes('WORKBENCH_STATE_INVALID')));
});
