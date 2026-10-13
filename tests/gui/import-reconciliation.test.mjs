import test from 'node:test';
import assert from 'node:assert/strict';
import {reconcileImport,transientImportError} from '../../rentgen_core/gui_assets/model.js';
const immediate=async()=>{};

test('same-job reconciliation returns genuine terminal result without replay',async()=>{
  let reads=0;
  const result={status:'ready',job:'owned'};
  assert.equal(await reconcileImport(async()=>{reads++;return result;},()=>true,immediate),result);
  assert.equal(reads,1);
});
test('one lost read is retried, then committed result is recovered',async()=>{
  let reads=0;
  assert.deepEqual(await reconcileImport(async()=>{if(++reads===1)throw {code:'CONNECTION_LOST'};return {status:'ready'};},()=>true,immediate),{status:'ready'});
  assert.equal(reads,2);
});
test('three-read budget also bounds nonterminal and continuously lost replies',async()=>{
  for(const lost of [false,true]){
    let reads=0,pauses=0;
    await assert.rejects(reconcileImport(async()=>{reads++;if(lost)throw {code:'CONNECTION_LOST'};return {status:'analyzing'};},()=>true,async()=>{pauses++;}),error=>error.code==='IMPORT_OUTCOME_UNCERTAIN');
    assert.equal(reads,3);assert.equal(pauses,2);
  }
});
test('confirmed cancellation/error is returned, never represented as uncertain success',async()=>{
  for(const status of ['cancelled','error'])assert.deepEqual(await reconcileImport(async()=>({status}),()=>true,immediate),{status});
});
test('authorization failures are not retried',async()=>{
  let reads=0;
  await assert.rejects(reconcileImport(async()=>{reads++;throw {code:'FORBIDDEN'};},()=>true,immediate),error=>error.code==='FORBIDDEN');
  assert.equal(reads,1);
});
test('superseded operation cannot read or publish a late response',async()=>{
  let reads=0,current=false;
  await assert.rejects(reconcileImport(async()=>{reads++;},()=>current,immediate),error=>error.code==='STALE_IMPORT');
  assert.equal(reads,0);
  current=true;
  await assert.rejects(reconcileImport(async()=>{current=false;return {status:'ready'};},()=>current,immediate),error=>error.code==='STALE_IMPORT');
});
test('only ambiguous transport/protocol failures qualify for reconciliation',()=>{
  assert.ok(transientImportError({code:'CONNECTION_LOST'}));
  assert.ok(transientImportError({code:'PROTOCOL_ERROR'}));
  for(const code of ['FORBIDDEN','UNAUTHORIZED','CANCELLED','IMPORT_UNSUPPORTED_ARCHIVE'])assert.equal(transientImportError({code}),false);
});
