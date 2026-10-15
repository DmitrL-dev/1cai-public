'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {createClient} = require('../lib/core.cjs');
const project = '00000000-0000-4000-8000-000000000001';
const selected = {project_id:project, snapshot_id:'a'.repeat(64), manifest_hash:'a'.repeat(64)};
const ref = {snapshot:selected, layer_id:'base', relative_path:'Catalogs/Товары.xml', raw_sha256:'b'.repeat(64)};
const config = {schema:1, core_version:'0.1.0.dev19', project_id:project, python:'C:\\installed\\python.exe', registry:'C:\\registry.sqlite3'};
const preview = () => ({source_ref:ref, type:'Catalog', name:'Товары', synonym:'Номенклатура', observed_uuid:null, uuid_status:'unverified'});
function envelope() {return {schema:1, snapshot:selected, identity_status:'source_path_only', parser_profiles:['designer_xml_v1'],
  layers:[{layer_id:'base', status:'supported', completeness:'supported_layer_inventory'}], source_refs:[ref],
  completeness:'supported_layer_inventory', truncated:false, objects:[preview()], returned:1, total_matches:1};}
function fixture(reply = envelope()) {
  const calls = [], state = {reply};
  const client = createClient(config, {execute:async (command,args) => {
    calls.push({command,args}); return {code:0, stdout:Buffer.from(JSON.stringify({result:state.reply}))};
  }});
  return {client,calls,state};
}
test('metadata search uses the exact snapshot and literal option-like query/type selectors', async () => {
  const f = fixture();
  assert.equal((await f.client.metadataSearch(selected,{query:'--help',type:'--type',layer:'base'})).objects[0].name,'Товары');
  assert.deepEqual(f.calls[0].args,['-I','-m','rentgen_core','metadata-search','--registry',config.registry,'--project',project,
    '--snapshot',selected.snapshot_id,'--query=--help','--limit','100','--type=--type','--layer=base']);
});
for (const [label, change] of [
  ['foreign snapshot', v => v.snapshot={...selected,snapshot_id:'c'.repeat(64),manifest_hash:'c'.repeat(64)}],
  ['foreign source project', v => v.objects[0].source_ref={...ref,snapshot:{...selected,project_id:'00000000-0000-4000-8000-000000000009'}}],
  ['unverified returned ref', v => v.source_refs=[]],
  ['false count', v => v.returned=0],
  ['hidden truncation', v => v.total_matches=101],
  ['unbounded count', v => {v.total_matches=20001;v.truncated=true;}],
  ['wrong schema', v => v.schema=2],
  ['unknown UUID authority', v => v.objects[0].uuid_status='canonical'],
  ['oversized label', v => v.objects[0].name='x'.repeat(1025)],
  ['unqualified layer', v => v.objects[0].source_ref={...ref,layer_id:'other'}],
]) test(`metadata search refuses ${label}`, async () => {
  const value=envelope();change(value);const f=fixture(value);
  await assert.rejects(f.client.metadataSearch(selected));
});
test('metadata object keeps exact path/layer and every module bound to verified refs', async () => {
  const value=envelope(), module={...ref,relative_path:'Catalogs/Товары/Ext/ObjectModule.bsl',raw_sha256:'c'.repeat(64)};
  delete value.objects;delete value.returned;delete value.total_matches;
  value.object={...preview(),modules:{items:[{source_ref:module,status:'verified_bytes',size_bytes:100,encoding:'utf-8'}],total:1,truncated:false}};
  value.source_refs.push(module);value.completeness='parsed_supported_object';
  const f=fixture(value);assert.equal((await f.client.metadataObject(selected,ref)).object.modules.items.length,1);
  assert.deepEqual(f.calls[0].args.slice(8),['--snapshot',selected.snapshot_id,'--layer=base','--path=Catalogs/Товары.xml']);
  f.state.reply=structuredClone(value);f.state.reply.object.modules.items[0].source_ref={...module,raw_sha256:'d'.repeat(64)};
  await assert.rejects(f.client.metadataObject(selected,ref),/INVALID_METADATA_RESPONSE/);
});
test('metadata inputs are rejected before starting Core', async () => {
  const f=fixture();
  for(const query of ['\n','x'.repeat(257),'\ud800'])await assert.rejects(f.client.metadataSearch(selected,{query}),/INVALID_SEARCH/);
  await assert.rejects(f.client.metadataSearch(selected,{layer:'../outside'}),/INVALID_SEARCH/);
  await assert.rejects(f.client.metadataObject(selected,{...ref,snapshot:{...selected,snapshot_id:'c'.repeat(64),manifest_hash:'c'.repeat(64)}}),/SOURCE_REF_MISMATCH/);
  assert.deepEqual(f.calls,[]);
});
for(const available of [false,true])test(`metadata capability admission is advertised by commands, not dev19 version: ${available}`,async()=>{
  const f=fixture({contract_version:1,platform:'win32',scope:'os-adapter-support',capabilities:{'snapshot.retained.read':{
    supported:true,operations:available?['source-list','metadata-summary','metadata-search','metadata-object']:['source-list'],
  }}});
  assert.deepEqual(await f.client.navigationCapability(),{supported:available});
  assert.deepEqual(f.calls[0].args,['-I','-m','rentgen_core','capabilities']);
});
test('an unavailable OS or malformed capability response cannot admit navigation',async()=>{
  const f=fixture({contract_version:1,platform:'linux',scope:'os-adapter-support',capabilities:{}});
  await assert.rejects(f.client.navigationCapability(),/INVALID_CAPABILITIES_RESPONSE/);
});
