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
  const binding={job:'owned-job',input_sha256:'a'.repeat(64)};
  const reply={...binding,search:'owned-search',query:'Товар',status:'ready',result:{input:{input_sha256:binding.input_sha256},objects:[]}};
  assert.ok(searchReplyMatches(binding,'owned-search','Товар',reply));
  assert.equal(searchReplyMatches(binding,'owned-search','Товар',{...reply,result:{}}),false);
  for(const [key,value] of [['job','old-job'],['input_sha256','b'.repeat(64)],['search','old-search'],['query','Other']])assert.equal(searchReplyMatches(binding,'owned-search','Товар',{...reply,[key]:value}),false);
  assert.equal(searchReplyMatches(binding,'owned-search','Товар',{...reply,result:{...reply.result,input:{input_sha256:'b'.repeat(64)}}}),false);
  assert.equal(searchReplyMatches(binding,'owned-search','Товар',{...reply,result:{...reply.result,objects:Array(201).fill({})}}),false);
});
