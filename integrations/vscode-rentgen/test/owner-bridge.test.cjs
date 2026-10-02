'use strict';
// Focused Source controls. All byte/clock/lease objects here are synthetic.
// No editor, socket, pipe, native, model, SDK or process effect is exercised.
const test = require('node:test'), assert = require('node:assert/strict');
const {createOwnerBridge, bridgeBootstrapOptions} = require('../lib/owner_bridge.cjs');
const {createOwnerBootstrap, createOwnerBootstrapForBridge} = require('../lib/owner-bootstrap.cjs');
const expected = Object.freeze({generation:7, run_nonce:'a'.repeat(32), request_id:'b'.repeat(32), bindings_sha256:'c'.repeat(64)});
const request = Object.freeze({generation:7, scope:'constructed-ordering-only'});
function fixture(overrides = {}, selectedLease = {}) {
  const clock = {at:10n, fault:null, hook:null};
  const limits = {frame_bytes:1024, aggregate_bytes:4096, retained_storage_bytes:4096,
    max_chunk_bytes:512, receive_calls:64, queue_slots:1,
    connect_until_ns:100n, hello_until_ns:200n, cancel_until_ns:300n, closure_until_ns:400n, ...overrides};
  const bridge = createOwnerBridge({expected, limits, lease:selectedLease, now() {
    if (clock.hook) clock.hook();
    if (clock.fault !== null) throw clock.fault;
    return clock.at;
  }});
  return {bridge, lease:selectedLease, limits, clock};
}
function packet(value = {}) {
  const payload = {schema:'rentgen-owner-bootstrap-observation/1', type:'REFUSAL', run_nonce:expected.run_nonce,
    connection_generation:expected.generation, sequence:2, request_id:expected.request_id,
    bindings_sha256:expected.bindings_sha256, code:'DAILY_ROOT_EDITOR_OWNER_REQUIRED', ...value};
  return textPacket(JSON.stringify(payload));
}
function textPacket(text) {
  const body = Buffer.from(text, 'utf8'), result = Buffer.alloc(body.length+4);
  result.writeUInt32BE(body.length); body.copy(result,4); return result;
}
function authorityFalse(bridge) {
  const value = bridge.snapshot();
  for (const field of ['kernel_authority','runtime_verified','ready','peer_bound','native_completion',
                       'Root_lease_settled','model_loading_allowed','native_allowed']) assert.equal(value[field], false);
  assert.equal(value.loading_grant, null); assert.equal(value.native_grant, null);
}
test('default bridge and production callback remain unavailable, with no data/native authority', async () => {
  const bridge = createOwnerBridge(), owner = createOwnerBootstrap();
  await assert.rejects(bridge.bootstrap(request), /OWNER_ENDPOINT_UNAVAILABLE/);
  await assert.rejects(bridge.execute('python', ['anything']), /OWNER_TRANSPORT_NOT_ADMITTED/);
  let initialized = 0;
  await assert.rejects(owner.activate({}, () => initialized++), /OWNER_ENDPOINT_UNAVAILABLE/);
  assert.equal(initialized, 0); assert.equal(bridge.snapshot().tx_frames, 0);
  assert.equal(bridge.snapshot().lease_consumed, false); authorityFalse(bridge);
  assert.throws(() => bridgeBootstrapOptions({...bridge}), /OWNER_BACKEND_INVALID/);
});
test('fragmented refusal shares the whole initializer promise and consumes one lease only', async () => {
  const f = fixture(), owner = createOwnerBootstrapForBridge(f.bridge), context = {};
  let initialized = 0;
  const activation = owner.activate(context, () => initialized++);
  const raced = owner.activate(context, () => {throw new Error('second initializer forbidden');});
  assert.equal(activation, raced);
  const rejected = assert.rejects(activation, /DAILY_ROOT_EDITOR_OWNER_REQUIRED/);
  await Promise.resolve(); // existing bootstrap coordinator's queued callback
  const direct = f.bridge.bootstrap(request);
  assert.equal(direct, f.bridge.bootstrap(request));
  const outbound = f.bridge.outbound(f.lease);
  assert.equal(outbound.readUInt32BE(0), outbound.length-4);
  const decoded = JSON.parse(outbound.subarray(4).toString('utf8'));
  assert.deepEqual(decoded, {schema:'rentgen-owner-bootstrap-observation/1', type:'BOOTSTRAP',
    run_nonce:expected.run_nonce, connection_generation:7, sequence:1, request_id:expected.request_id,
    bindings_sha256:expected.bindings_sha256});
  assert.equal(f.bridge.outbound(f.lease), null); // no duplicate send/retry
  const reply = packet();
  for (const part of [reply.subarray(0,1), reply.subarray(1,3), reply.subarray(3,12), reply.subarray(12)]) {
    assert.equal(f.bridge.receive(part), true);
  }
  await rejected;
  assert.equal(initialized, 0); assert.equal(owner.snapshot().state, 'REVOKED');
  assert.equal(owner.snapshot().initialized, false);
  const snapshot = f.bridge.snapshot();
  assert.equal(snapshot.tx_frames,1); assert.equal(snapshot.rx_frames,1);
  assert.equal(snapshot.outbound_copies,1); assert.equal(snapshot.lease_consumed,true);
  assert.ok(snapshot.internal_byte_buffers <= f.limits.retained_storage_bytes);
  assert.equal(snapshot.state,'CLOSURE_PENDING'); authorityFalse(f.bridge);
  const duplicate = fixture({}, f.lease);
  await assert.rejects(duplicate.bridge.bootstrap(request), /OWNER_BRIDGE_LEASE_REUSED/);
  assert.equal(duplicate.bridge.snapshot().tx_frames,0);
  assert.throws(() => f.bridge.closeLocal({}), /OWNER_BRIDGE_CONTRACT_INVALID/);
  assert.equal(f.bridge.cancel(), false); assert.equal(f.bridge.cancel(), false);
  assert.equal(f.bridge.snapshot().cancel_requests,1);
  assert.equal(f.bridge.closeLocal(f.lease),true); assert.equal(f.bridge.closeLocal(f.lease),true);
  assert.equal(f.bridge.snapshot().local_closes,1);
  assert.equal(f.bridge.snapshot().internal_byte_buffers,0); authorityFalse(f.bridge);
  assert.equal(f.bridge.receive(reply),false);
  await assert.rejects(f.bridge.execute('python', []), /OWNER_TRANSPORT_NOT_ADMITTED/);
});
test('wire authority, duplicate keys, malformed scalars and correlations are refused', async () => {
  const valid = packet().subarray(4).toString('utf8');
  const variants = [
    packet({peer_bound:true}), packet({ready:true}), packet({connection_generation:8}),
    packet({request_id:'d'.repeat(32)}), packet({bindings_sha256:'d'.repeat(64)}),
    packet({sequence:1}), packet({type:'RESULT'}), packet({role:'extension-host'}),
    textPacket(valid.replace('"connection_generation":7','"connection_generation":true')),
    textPacket(valid.replace('"connection_generation":7','"connection_generation":7e0')),
    textPacket(valid.replace('"schema":','"\\u0073chema":"shadow","schema":')),
    textPacket(valid+' {}'), textPacket('{"schema":{"nested":true}}'),
    textPacket('{"schema":"rentgen-owner-constructed-binding/1","generation":7,"peer_bound":true}')
  ];
  const invalidUTF8 = Buffer.from([0,0,0,1,255]); variants.push(invalidUTF8);
  for (const bytes of variants) {
    const f = fixture(), promise = f.bridge.bootstrap(request);
    const rejected = assert.rejects(promise);
    f.bridge.receive(bytes); await rejected;
    assert.equal(f.bridge.snapshot().rx_frames,0); authorityFalse(f.bridge);
    assert.ok(f.bridge.snapshot().internal_byte_buffers <= f.limits.retained_storage_bytes);
    assert.equal(f.bridge.closeLocal(f.lease),true);
  }
  const trailing = fixture(), promise = trailing.bridge.bootstrap(request);
  const rejected = assert.rejects(promise);
  trailing.bridge.receive(Buffer.concat([packet(),Buffer.from([0])]));
  await rejected; assert.equal(trailing.bridge.snapshot().rx_frames,0);
});
test('length, chunks, cumulative bytes, storage and receive counters remain bounded', async () => {
  const zero = fixture(), zeroPromise = zero.bridge.bootstrap(request), zeroRejected = assert.rejects(zeroPromise,/FRAME_LIMIT/);
  zero.bridge.receive(Buffer.alloc(4)); await zeroRejected;
  const tooBig = fixture(), bigPromise = tooBig.bridge.bootstrap(request), bigRejected = assert.rejects(bigPromise,/FRAME_LIMIT/);
  const prefix = Buffer.alloc(4); prefix.writeUInt32BE(1025); tooBig.bridge.receive(prefix); await bigRejected;
  const partial = fixture(), partialPromise = partial.bridge.bootstrap(request), partialRejected = assert.rejects(partialPromise,/TRUNCATED/);
  partial.bridge.receive(Buffer.from([0,0])); partial.bridge.end(); await partialRejected;
  const calls = fixture({receive_calls:2}), callsPromise = calls.bridge.bootstrap(request), callsRejected = assert.rejects(callsPromise,/INPUT_LIMIT/);
  calls.bridge.receive(Buffer.from([0])); calls.bridge.receive(Buffer.from([0])); calls.bridge.receive(Buffer.from([0]));
  await callsRejected; assert.equal(calls.bridge.snapshot().receive_calls,2); assert.equal(calls.bridge.snapshot().received_bytes,2);
  const chunk = fixture({max_chunk_bytes:1}), chunkPromise = chunk.bridge.bootstrap(request), chunkRejected = assert.rejects(chunkPromise,/INPUT_LIMIT/);
  chunk.bridge.receive(Buffer.from([0,0])); await chunkRejected; assert.equal(chunk.bridge.snapshot().received_bytes,0);
  const aggregate = fixture({aggregate_bytes:1024}), aggregatePromise = aggregate.bridge.bootstrap(request), aggregateRejected = assert.rejects(aggregatePromise,/INPUT_LIMIT/);
  const unfinished = Buffer.alloc(512); unfinished.writeUInt32BE(1024);
  aggregate.bridge.receive(unfinished); aggregate.bridge.receive(Buffer.alloc(512)); await aggregateRejected;
  assert.equal(aggregate.bridge.snapshot().received_bytes,512);
  const storage = fixture({aggregate_bytes:1024,retained_storage_bytes:1024});
  await assert.rejects(storage.bridge.bootstrap(request), /STORAGE_LIMIT/);
  assert.equal(storage.bridge.snapshot().tx_frames,0); assert.equal(storage.bridge.snapshot().internal_byte_buffers,0);
  assert.throws(() => fixture({queue_slots:2}), /POLICY_INVALID/);
  assert.throws(() => fixture({frame_bytes:65537}), /POLICY_INVALID/);
  let reads = 0;
  const accessor = {frame_bytes:1024,aggregate_bytes:4096,retained_storage_bytes:4096,max_chunk_bytes:512,
    receive_calls:64,queue_slots:1,connect_until_ns:100n,hello_until_ns:200n,cancel_until_ns:300n,closure_until_ns:400n};
  Object.defineProperty(accessor,'frame_bytes',{enumerable:true,get(){reads++;return 1024;}});
  assert.throws(() => createOwnerBridge({expected, limits:accessor, lease:{}, now:()=>10n}), /POLICY_INVALID/);
  assert.equal(reads,0);
});
test('cancel and frozen deadlines preserve pending buffers and cannot imply native closure', async () => {
  const f = fixture(), pending = f.bridge.bootstrap(request), rejected = assert.rejects(pending,/CANCELLED/);
  f.bridge.cancel(); await rejected; const before = f.bridge.snapshot();
  assert.equal(before.cancel_requests,1); assert.ok(before.internal_byte_buffers > 0);
  f.bridge.cancel(); assert.equal(f.bridge.snapshot().cancel_requests,1);
  f.clock.at = 400n; f.limits.closure_until_ns = 900n; // original captured end remains 400n
  assert.equal(f.bridge.closeLocal(f.lease),false);
  assert.ok(f.bridge.snapshot().internal_byte_buffers > 0); authorityFalse(f.bridge);
  assert.equal(f.bridge.receive(packet()),false); assert.equal(f.bridge.snapshot().rx_frames,0);
  const hello = fixture(), helloPending = hello.bridge.bootstrap(request), helloRejected = assert.rejects(helloPending,/EXPIRED/);
  hello.clock.at = 200n; hello.bridge.receive(packet()); await helloRejected;
  assert.equal(hello.bridge.snapshot().rx_frames,0); assert.ok(hello.bridge.snapshot().internal_byte_buffers > 0);
  const crossing = fixture(), crossingPending = crossing.bridge.bootstrap(request), crossingRejected = assert.rejects(crossingPending,/EXPIRED/);
  let samples = 0;
  crossing.clock.hook = () => {samples++; if (samples === 2) crossing.clock.at = 200n;};
  crossing.bridge.receive(packet()); await crossingRejected;
  assert.equal(crossing.bridge.snapshot().rx_frames,0); assert.ok(crossing.bridge.snapshot().internal_byte_buffers > 0);
  const lateSend = fixture(), lateSendPending = lateSend.bridge.bootstrap(request), lateSendRejected = assert.rejects(lateSendPending,/EXPIRED/);
  lateSend.clock.at = 200n; assert.equal(lateSend.bridge.outbound(lateSend.lease),null); await lateSendRejected;
  assert.equal(lateSend.bridge.snapshot().outbound_copies,0);
  const cancelEnd = fixture(), cancelPending = cancelEnd.bridge.bootstrap(request), cancelRejected = assert.rejects(cancelPending,/CANCELLED/);
  cancelEnd.clock.at = 300n; cancelEnd.bridge.cancel(); await cancelRejected;
  assert.equal(cancelEnd.bridge.snapshot().cancel_requests,0);
  const connect = fixture(); connect.clock.at = 100n;
  await assert.rejects(connect.bridge.bootstrap(request),/EXPIRED/);
  assert.equal(connect.bridge.snapshot().lease_consumed,false); assert.equal(connect.bridge.snapshot().tx_frames,0);
});
test('reentrancy and secondary cleanup errors never restore state or replace the first error', async () => {
  const f = fixture(); let nested;
  f.clock.hook = () => {f.clock.hook = null; nested = f.bridge.bootstrap(request); f.bridge.cancel();};
  const promise = f.bridge.bootstrap(request);
  assert.equal(nested,promise); await assert.rejects(promise,/CANCELLED/);
  assert.equal(f.bridge.snapshot().tx_frames,0); assert.equal(f.bridge.snapshot().lease_consumed,false);
  assert.equal(f.bridge.receive(packet()),false);
  const held = fixture(), original = new Error('primary clock observation failure'), secondary = new Error('secondary cleanup failure');
  const heldPromise = held.bridge.bootstrap(request), heldRejected = assert.rejects(heldPromise, error=>error===original);
  held.clock.fault = original; held.bridge.receive(Buffer.from([0])); await heldRejected;
  held.clock.fault = secondary;
  held.bridge.cancel(); assert.equal(held.bridge.closeLocal(held.lease),false);
  await assert.rejects(held.bridge.bootstrap(request), error=>error===original);
  assert.ok(held.bridge.snapshot().internal_byte_buffers > 0);
  assert.equal(held.bridge.snapshot().local_closed,false); authorityFalse(held.bridge);
});

test('closure revokes before reentrant caller clock can publish bytes', async () => {
const f = fixture(), pending = f.bridge.bootstrap(request);
const outcome = pending.then(() => {throw new Error('unexpected binding');}, error => error);
let escaped;
f.clock.hook = () => {f.clock.hook = null; escaped = f.bridge.outbound(f.lease);};
assert.equal(f.bridge.closeLocal(f.lease), true);
assert.equal(escaped, null);
assert.equal(f.bridge.snapshot().outbound_copies, 0);
assert.equal(f.bridge.snapshot().local_closes, 1);
assert.equal(f.bridge.snapshot().internal_byte_buffers, 0);
assert.match((await outcome).message, /OWNER_BRIDGE_LOCAL_CLOSED/);
authorityFalse(f.bridge);
});
test('unsent terminal lease view cannot be reused by a second bridge', async () => {
for (const terminal of ['cancel', 'closeLocal', 'connectExpiry']) {
  const f = fixture();
  if (terminal === 'cancel') f.bridge.cancel();
  else if (terminal === 'closeLocal') assert.equal(f.bridge.closeLocal(f.lease), true);
  else {
    f.clock.at = 100n;
    await assert.rejects(f.bridge.bootstrap(request), /EXPIRED/);
  }
  assert.equal(f.bridge.snapshot().lease_consumed, false);
  assert.equal(f.bridge.snapshot().tx_frames, 0);
  const next = fixture({}, f.lease);
  const pending = next.bridge.bootstrap(request);
  const outcome = pending.then(() => {throw new Error('unexpected binding');}, error => error);
  const beforeCleanup = next.bridge.snapshot();
  next.bridge.cancel(); // makes the old broken path settle; no hanging RED
  assert.equal(beforeCleanup.tx_frames, 0);
  assert.match((await outcome).message, /OWNER_BRIDGE_LEASE_REUSED/);
  authorityFalse(f.bridge); authorityFalse(next.bridge);
}
});
