'use strict';
// Constructed ordering only. No editor, process, transport or kernel APIs.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const {existsSync} = require('node:fs');
const file = path.join(__dirname, '../lib/owner-bootstrap.cjs');
const implementation = existsSync(file) ? require(file) : {};
function create(options) {
  assert.equal(typeof implementation.createOwnerBootstrap, 'function', 'OWNER_BOOTSTRAP_SEAM_REQUIRED');
  return implementation.createOwnerBootstrap(options);
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}
function fixture() {
  const binding = deferred(), events = [], context = {}, generation = 7;
  const owner = create({generation, bootstrap: async () => {events.push('bootstrap'); return binding.promise;}});
  return {owner, binding, events, context, generation,
    bind: () => binding.resolve({schema: 'rentgen-owner-constructed-binding/1', generation, peer_bound: true})};
}
test('missing owner denies before initializer and caller markers never create a backend', async () => {
  for (const options of [undefined, {}, {accepted: true, pid: 42, nonce: 'marker', allow: true}]) {
    const owner = create(options); let initialized = 0;
    await assert.rejects(owner.activate({}, () => {initialized++;}), /OWNER_ENDPOINT_UNAVAILABLE/);
    assert.equal(initialized, 0); assert.equal(owner.snapshot().state, 'OWNER_ENDPOINT_UNAVAILABLE');
    assert.equal(owner.snapshot().runtime_verified, false);
  }
});
test('first explicit activation starts handshake without a completed-peer prerequisite', async () => {
  const f = fixture();
  const activation = f.owner.activate(f.context, async () => {f.events.push('initialize'); return 'constructed';});
  await Promise.resolve(); assert.deepEqual(f.events, ['bootstrap']);
  assert.equal(f.owner.snapshot().state, 'HANDSHAKE_PENDING');
  assert.throws(() => f.owner.assertBound(), /OWNER_PEER_NOT_BOUND/);
  f.bind(); assert.equal(await activation, 'constructed');
  assert.deepEqual(f.events, ['bootstrap', 'initialize']); f.owner.assertBound();
  const state = f.owner.snapshot(); assert.equal(state.state, 'PEER_BOUND');
  for (const key of ['kernel_authority', 'runtime_verified', 'ready', 'model_loading_allowed', 'native_allowed']) assert.equal(state[key], false);
});
test('racing automatic and explicit activation share the same promise and initializer', async () => {
  const f = fixture(); let initialized = 0;
  const first = f.owner.activate(f.context, () => ++initialized);
  const second = f.owner.activate(f.context, () => {throw new Error('second initializer forbidden');});
  assert.equal(first, second); f.bind(); assert.equal(await first, 1); assert.equal(await second, 1);
  assert.equal(initialized, 1); assert.deepEqual(f.events, ['bootstrap']);
  assert.equal(f.owner.activate(f.context, () => {throw new Error('duplicate initializer');}), first);
});
test('another context cannot reuse a current-generation activation or binding', async () => {
  const f = fixture(); const first = f.owner.activate(f.context, () => true);
  await assert.rejects(f.owner.activate({}, () => {throw new Error('foreign initializer');}), /OWNER_CONTEXT_MISMATCH/);
  f.bind(); assert.equal(await first, true); f.owner.assertBound(f.context);
  assert.throws(() => f.owner.assertBound({}), /OWNER_CONTEXT_MISMATCH/);
});
for (const [name, value] of [
  ['wrong generation', {schema:'rentgen-owner-constructed-binding/1',generation:8,peer_bound:true}],
  ['missing generation', {schema:'rentgen-owner-constructed-binding/1',peer_bound:true}],
  ['unbound peer', {schema:'rentgen-owner-constructed-binding/1',generation:7,peer_bound:false}],
  ['wrong schema', {schema:'accepted-runtime',generation:7,peer_bound:true}],
  ['marker authority', {schema:'rentgen-owner-constructed-binding/1',generation:7,peer_bound:true,kernel_authority:true}],
  ['null binding', null]
]) test('refuses '+name+' before initializing metadata', async () => {
  const f = fixture(); let initialized = 0;
  const activation = f.owner.activate(f.context, () => initialized++); f.binding.resolve(value);
  await assert.rejects(activation, /OWNER_BINDING_INVALID/); assert.equal(initialized, 0);
  assert.equal(f.owner.snapshot().state, 'REVOKED');
});
for (const reason of ['disconnect', 'owner_loss', 'expiry', 'stop']) test(reason+' before binding blocks late bootstrap and new activation', async () => {
  const f = fixture(); let initialized = 0;
  const activation = f.owner.activate(f.context, () => initialized++);
  f.owner.revoke(reason); f.bind(); await assert.rejects(activation, /OWNER_REVOKED/);
  assert.equal(initialized, 0); assert.equal(f.owner.snapshot().state, 'REVOKED');
  await assert.rejects(f.owner.activate(f.context, () => initialized++), /OWNER_REVOKED/);
  assert.throws(() => f.owner.assertBound(), /OWNER_REVOKED/);
});
test('revocation during delayed initializer prevents a successful activation result', async () => {
  const f = fixture(), initialization = deferred(), entered = deferred(); let initialized = 0;
  const activation = f.owner.activate(f.context, async () => {initialized++; entered.resolve(); return initialization.promise;});
  f.bind(); await entered.promise;
  assert.equal(initialized, 1); f.owner.revoke('disconnect'); initialization.resolve({ready:true});
  await assert.rejects(activation, /OWNER_REVOKED/); assert.equal(f.owner.snapshot().ready, false);
});
test('completion pending is irreversible and cannot become bound on a late result', async () => {
  const f = fixture(); let initialized = 0;
  const activation = f.owner.activate(f.context, () => initialized++);
  f.owner.completionPending('late native completion'); f.bind();
  await assert.rejects(activation, /OWNER_COMPLETION_PENDING/); assert.equal(initialized, 0);
  assert.equal(f.owner.snapshot().state, 'COMPLETION_PENDING');
  assert.throws(() => f.owner.assertBound(), /OWNER_COMPLETION_PENDING/);
  f.owner.revoke('later stop'); assert.equal(f.owner.snapshot().state, 'COMPLETION_PENDING');
});
test('refused bootstrap and initializer failure stay refused and are never retried', async () => {
  for (const phase of ['bootstrap', 'initialize']) {
    const error = new Error('constructed '+phase+' failure'); let calls = 0;
    const owner = create({generation:1, bootstrap: async () => {calls++; if(phase==='bootstrap') throw error; return {schema:'rentgen-owner-constructed-binding/1',generation:1,peer_bound:true};}});
    const context = {};
    await assert.rejects(owner.activate(context, () => {throw error;}), candidate => candidate === error);
    await assert.rejects(owner.activate(context, () => true), /OWNER_REVOKED/);
    assert.equal(calls, 1); assert.equal(owner.snapshot().state, 'REVOKED');
  }
});
test('invalid context, initializer and generation are rejected without starting bootstrap', async () => {
  for (const generation of [0, -1, 1.1, '1', Number.MAX_SAFE_INTEGER + 1]) assert.throws(() => create({generation, bootstrap:async()=>{}}), /OWNER_GENERATION_INVALID/);
  let calls = 0; const owner = create({generation:1, bootstrap:async()=>{calls++;}});
  await assert.rejects(owner.activate(null, () => true), /OWNER_CONTEXT_INVALID/);
  await assert.rejects(owner.activate({}, null), /OWNER_INITIALIZER_INVALID/); assert.equal(calls, 0);
});
test('only a separately constructed generation can start again after terminal revocation', async () => {
  const first = fixture(); first.owner.revoke('stop');
  const next = create({generation:8, bootstrap:async()=>({schema:'rentgen-owner-constructed-binding/1',generation:8,peer_bound:true})});
  assert.equal(await next.activate({}, () => 'next constructed generation'), 'next constructed generation');
  assert.equal(first.owner.snapshot().state, 'REVOKED'); assert.equal(next.snapshot().runtime_verified, false);
});
test('synchronous backend reentrancy shares the stored activation without starting a second handshake', async () => {
  const context = {}; let owner, nested, calls = 0;
  owner = create({generation:1, bootstrap:() => {
    calls++; nested = owner.activate(context, () => {throw new Error('reentrant initializer forbidden');});
    return {schema:'rentgen-owner-constructed-binding/1',generation:1,peer_bound:true};
  }});
  const first = owner.activate(context, () => 'constructed'); assert.equal(await first, 'constructed');
  assert.equal(nested, first); assert.equal(calls, 1);
});
test('stop before the queued first handshake prevents even the bootstrap callback', async () => {
  let calls = 0; const owner = create({generation:1, bootstrap:() => {calls++;}});
  const activation = owner.activate({}, () => {throw new Error('initializer forbidden');});
  owner.revoke('stop'); await assert.rejects(activation, /OWNER_REVOKED/); assert.equal(calls, 0);
});
for (const [transition, code] of [['revoke', 'OWNER_REVOKED'], ['completionPending', 'OWNER_COMPLETION_PENDING']]) test('reentrant '+transition+' during binding validation cannot restore a bound state', async () => {
  let owner, initialized = 0;
  owner = create({generation:1, bootstrap:() => ({schema:'rentgen-owner-constructed-binding/1',
    get generation(){owner[transition](); return 1;}, peer_bound:true})});
  await assert.rejects(owner.activate({}, () => initialized++), new RegExp(code));
  assert.equal(initialized, 0); assert.notEqual(owner.snapshot().state, 'PEER_BOUND');
});
