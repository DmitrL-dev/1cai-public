import test from 'node:test';
import assert from 'node:assert/strict';
import {boundedMetadataQuery,searchReplyMatches} from '../../rentgen_core/gui_assets/model.js';

test('metadata query limit is UTF-8 bytes, with explicit empty/Unicode boundaries',()=>{
  assert.deepEqual(boundedMetadataQuery('  '),{query:'',valid:true});
  assert.equal(boundedMetadataQuery('я'.repeat(128)).valid,true);
  assert.equal(boundedMetadataQuery('я'.repeat(129)).valid,false);
  assert.equal(boundedMetadataQuery('😀'.repeat(64)).valid,true);
  assert.equal(boundedMetadataQuery('😀'.repeat(65)).valid,false);
  assert.equal(boundedMetadataQuery('a'.repeat(256)).valid,true);
  assert.equal(boundedMetadataQuery('a'.repeat(257)).valid,false);
});
test('metadata search reply cannot cross job, archive, query or search generation',()=>{
  const binding={job:'owned-job',input_sha256:'a'.repeat(64),kind:'metadata',object_path:null,offset:0};
  const reply={...binding,search:'owned-search',prefix:null,query:'Товар',status:'ready',result:{input:{input_sha256:binding.input_sha256},objects:[],matching_objects:0,page:{offset:0,limit:200,total:0,returned:0,has_previous:false,has_next:false}}};
  assert.ok(searchReplyMatches(binding,'owned-search','Товар',reply));
  assert.equal(searchReplyMatches(binding,'owned-search','Товар',{...reply,result:{}}),false);
  for(const [key,value] of [['job','old-job'],['input_sha256','b'.repeat(64)],['search','old-search'],['query','Other']])assert.equal(searchReplyMatches(binding,'owned-search','Товар',{...reply,[key]:value}),false);
  assert.equal(searchReplyMatches(binding,'owned-search','Товар',{...reply,result:{...reply.result,input:{input_sha256:'b'.repeat(64)}}}),false);
  assert.equal(searchReplyMatches(binding,'owned-search','Товар',{...reply,result:{...reply.result,objects:Array(201).fill({})}}),false);
});

test('module discovery reply binds kind and related object and bounds module hits',()=>{
  const binding={job:'job',input_sha256:'a'.repeat(64),kind:'modules',object_path:'Catalogs/Late.xml',offset:0};
  const reply={...binding,search:'search',prefix:'Catalogs/Late/',query:'модуль',status:'ready',result:{input:{input_sha256:binding.input_sha256},modules:[],matching_modules:0,page:{offset:0,limit:200,total:0,returned:0,has_previous:false,has_next:false}}};
  assert.ok(searchReplyMatches(binding,'search','модуль',reply));
  for(const update of [{prefix:'Catalogs/LateNeighbor/'},{kind:'metadata'},{object_path:null},{object_path:'Catalogs/Other.xml'},{result:{...reply.result,modules:Array(201).fill({})}},{result:{...reply.result,objects:[],modules:undefined}}])assert.equal(searchReplyMatches(binding,'search','модуль',{...reply,...update}),false);
});

test('page replies bind offsets, exact range counts and navigation flags',()=>{
  const binding={job:'job',input_sha256:'a'.repeat(64),kind:'metadata',object_path:null,offset:400};
  const page={offset:400,limit:200,total:401,returned:1,has_previous:true,has_next:false};
  const result={input:{input_sha256:binding.input_sha256},objects:[{}],matching_objects:401,page};
  const reply={...binding,search:'search',prefix:null,query:'',status:'ready',result};
  assert.ok(searchReplyMatches(binding,'search','',reply));
  assert.equal(searchReplyMatches(binding,'search','',{...reply,offset:200}),false);
  for(const update of [{offset:200},{limit:201},{total:402},{returned:0},{has_previous:false},{has_next:true}])assert.equal(searchReplyMatches(binding,'search','',{...reply,result:{...result,page:{...page,...update}}}),false);
  assert.equal(searchReplyMatches(binding,'search','',{...reply,result:{...result,objects:[]}}),false);
  assert.equal(searchReplyMatches(binding,'search','',{...reply,result:{...result,matching_objects:400}}),false);
});
