'use strict';
// Local application bytes only. No socket, pipe, process, native or model API.
// A lease is a Root-controlled Node view; neither this view nor wire data is
// a kernel peer proof. Python alone retains/settles its native IO bundle.
const SCHEMA = 'rentgen-owner-bootstrap-observation/1';
const instances = new WeakMap(), consumedLeases = new WeakSet();
const MAX_FRAME = 65536, MAX_CHUNK = 16384, MAX_CALLS = MAX_FRAME + 4;
const common = ['bindings_sha256','connection_generation','request_id','run_nonce','schema','sequence','type'];
const codes = new Set(['DAILY_ROOT_EDITOR_OWNER_REQUIRED','OWNER_TRANSPORT_NOT_ADMITTED']);
const codeError = code => new Error(code);
function exact(value, keys) {
  return value !== null && typeof value === 'object' && !Array.isArray(value) &&
    Object.keys(value).sort().join(',') === keys.slice().sort().join(',');
}
function dataRecord(value, keys, code) {
  if (!exact(value, keys)) throw codeError(code);
  const result = Object.create(null);
  for (const key of keys) {
    const field = Object.getOwnPropertyDescriptor(value,key);
    if (!field || !Object.hasOwn(field,'value')) throw codeError(code);
    result[key] = field.value;
  }
  return result;
}
function scalarObject(text) {
  // Deliberately one flat scalar object: duplicate keys are never overwritten.
  let at = 0; const value = Object.create(null);
  const string = /"(?:[^"\\\u0000-\u001f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"/y;
  const number = /(?:0|[1-9][0-9]*)/y;
  const bad = () => { throw codeError('OWNER_BRIDGE_FRAME_INVALID'); };
  const space = () => { while (at < text.length && /[ \t\r\n]/.test(text[at])) at++; };
  function token(pattern) {pattern.lastIndex = at; const found = pattern.exec(text); if (!found) bad(); at = pattern.lastIndex; return found[0];}
  space(); if (text[at++] !== '{') bad(); space();
  if (text[at] !== '}') while (true) {
    const key = JSON.parse(token(string)); space();
    if (Object.hasOwn(value, key) || text[at++] !== ':') bad(); space();
    const item = text[at] === '"' ? JSON.parse(token(string)) : Number(token(number));
    value[key] = item; space();
    if (text[at] === '}') break;
    if (text[at++] !== ',') bad(); space();
  }
  if (text[at++] !== '}') bad(); space(); if (at !== text.length) bad();
  return value;
}
function expectedContext(value) {
  value = dataRecord(value, ['generation','run_nonce','request_id','bindings_sha256'], 'OWNER_BRIDGE_CONTEXT_INVALID');
  if (
      !Number.isSafeInteger(value.generation) || value.generation < 1 ||
      typeof value.run_nonce !== 'string' || !/^[a-f0-9]{32}$/.test(value.run_nonce) ||
      typeof value.request_id !== 'string' || !/^[a-f0-9]{32}$/.test(value.request_id) ||
      typeof value.bindings_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(value.bindings_sha256)) {
    throw codeError('OWNER_BRIDGE_CONTEXT_INVALID');
  }
  return Object.freeze({generation:value.generation, run_nonce:value.run_nonce,
    request_id:value.request_id, bindings_sha256:value.bindings_sha256});
}
function policy(value) {
  const byteKeys = ['frame_bytes','aggregate_bytes','retained_storage_bytes','max_chunk_bytes','receive_calls','queue_slots'];
  const ends = ['connect_until_ns','hello_until_ns','cancel_until_ns','closure_until_ns'];
  value = dataRecord(value, [...byteKeys,...ends], 'OWNER_BRIDGE_POLICY_INVALID');
  if (byteKeys.some(key => !Number.isSafeInteger(value[key]) || value[key] < 1) ||
      value.frame_bytes > MAX_FRAME || value.max_chunk_bytes > MAX_CHUNK ||
      value.receive_calls > MAX_CALLS || value.queue_slots !== 1 ||
      !(value.frame_bytes <= value.aggregate_bytes && value.aggregate_bytes <= value.retained_storage_bytes) ||
      value.aggregate_bytes > 2 * (MAX_FRAME + 4) || value.retained_storage_bytes > 3 * (MAX_FRAME + 4) ||
      ends.some(key => typeof value[key] !== 'bigint' || value[key] <= 0n) ||
      !(value.connect_until_ns <= value.hello_until_ns && value.hello_until_ns <= value.cancel_until_ns &&
        value.cancel_until_ns <= value.closure_until_ns)) throw codeError('OWNER_BRIDGE_POLICY_INVALID');
  const result = {}; for (const key of [...byteKeys,...ends]) result[key] = value[key];
  return Object.freeze(result);
}
function requestFrame(context, limit) {
  const body = Buffer.from(JSON.stringify({schema:SCHEMA, type:'BOOTSTRAP', run_nonce:context.run_nonce,
    connection_generation:context.generation, sequence:1, request_id:context.request_id,
    bindings_sha256:context.bindings_sha256}), 'utf8');
  if (body.length < 1 || body.length > limit) throw codeError('OWNER_BRIDGE_FRAME_LIMIT');
  const framed = Buffer.alloc(body.length + 4); framed.writeUInt32BE(body.length); body.copy(framed,4);
  return framed;
}
function refusal(body, expected) {
  const value = scalarObject(new TextDecoder('utf-8', {fatal:true}).decode(body));
  if (!exact(value, [...common,'code']) || value.schema !== SCHEMA || value.type !== 'REFUSAL' ||
      value.connection_generation !== expected.generation || value.sequence !== 2 ||
      value.run_nonce !== expected.run_nonce || value.request_id !== expected.request_id ||
      value.bindings_sha256 !== expected.bindings_sha256 || !codes.has(value.code)) {
    throw codeError('OWNER_BRIDGE_FRAME_INVALID');
  }
  return Object.freeze({code:value.code});
}
function createOwnerBridge(options) {
  const unavailable = options === undefined;
  let context = null, limits = null, lease = null, now = null;
  if (!unavailable) {
    options = dataRecord(options, ['expected','limits','lease','now'], 'OWNER_BRIDGE_CONTRACT_INVALID');
    if (!options.lease ||
        typeof options.lease !== 'object' || Array.isArray(options.lease) || typeof options.now !== 'function') {
      throw codeError('OWNER_BRIDGE_CONTRACT_INVALID');
    }
    context = expectedContext(options.expected); limits = policy(options.limits);
    lease = options.lease; now = options.now;
  }
  let promise = null, reject = null, stopped = false, failure, consumed = false;
  let state = unavailable ? 'UNAVAILABLE' : 'LOCAL_OBSERVATION_AVAILABLE';
  let tx = null, rx = null, received = 0, txBytes = 0, declared = null, lastTime = null;
  let receiveCalls = 0, txFrames = 0, rxFrames = 0, outboundAttempted = false, outboundCopies = 0, copyBytes = 0;
  let cancelAttempted = false, cancelRequests = 0, localClosing = false, localClosed = false, localCloses = 0;
  let observedCode = null;
  function stop(error) {
    if (!stopped) {
      // Retire the same local view even when no bytes were queued.
      if (lease !== null) consumedLeases.add(lease);
      stopped = true; failure = error; state = consumed ? 'CLOSURE_PENDING' : 'REFUSED';
    }
    if (reject) reject(failure);
  }
  function clock() {
    const at = now();
    if (typeof at !== 'bigint' || at < 0n || (lastTime !== null && at < lastTime)) throw codeError('OWNER_BRIDGE_CLOCK_INVALID');
    lastTime = at; return at;
  }
  function bootstrap(request) {
    if (promise) return promise;
    if (unavailable) return Promise.reject(codeError('OWNER_ENDPOINT_UNAVAILABLE'));
    if (stopped || localClosed) return Promise.reject(failure);
    // Before caller clock/getter code: reentrant bootstrap shares this promise.
    promise = new Promise((resolve, no) => {reject = no;});
    try {
      request = dataRecord(request, ['generation','scope'], 'OWNER_BRIDGE_CONTEXT_INVALID');
      if (request.generation !== context.generation ||
          request.scope !== 'constructed-ordering-only') throw codeError('OWNER_BRIDGE_CONTEXT_INVALID');
      if (stopped) throw failure;
      const at = clock(); if (stopped) throw failure;
      if (at >= limits.connect_until_ns) throw codeError('OWNER_BRIDGE_EXPIRED');
      if (consumedLeases.has(lease)) throw codeError('OWNER_BRIDGE_LEASE_REUSED');
      consumedLeases.add(lease); consumed = true;
      const packet = requestFrame(context, limits.frame_bytes);
      // Include the one outbound copy in the conservative logical byte budget.
      if (packet.length > limits.aggregate_bytes || limits.frame_bytes + 4 + 2 * packet.length > limits.retained_storage_bytes) {
        throw codeError('OWNER_BRIDGE_STORAGE_LIMIT');
      }
      rx = Buffer.alloc(limits.frame_bytes + 4); tx = packet; txBytes = packet.length;
      txFrames = 1; state = 'BOOTSTRAP_PENDING';
    } catch (error) {stop(error);}
    return promise;
  }
  function outbound(selectedLease) {
    if (unavailable || selectedLease !== lease) throw codeError('OWNER_BRIDGE_CONTRACT_INVALID');
    if (stopped || localClosed || !tx || outboundAttempted) return null;
    outboundAttempted = true; // before reentrant clock code; never retry this send
    try {
      const at = clock(); if (stopped || localClosed) return null;
      if (at >= limits.hello_until_ns) throw codeError('OWNER_BRIDGE_EXPIRED');
      const copy = Buffer.from(tx); outboundCopies = 1; copyBytes = copy.length;
      return copy; // one bounded local copy; no native write happens here
    } catch (error) {stop(error); return null;}
  }
  function receive(chunk) {
    if (unavailable || stopped || localClosed || !consumed) return false;
    try {
      const at = clock(); if (stopped) return false;
      if (at >= limits.hello_until_ns) throw codeError('OWNER_BRIDGE_EXPIRED');
      if (!Buffer.isBuffer(chunk) || chunk.length < 1 || chunk.length > limits.max_chunk_bytes ||
          receiveCalls >= limits.receive_calls || txBytes + received + chunk.length > limits.aggregate_bytes ||
          !rx || received + chunk.length > rx.length) throw codeError('OWNER_BRIDGE_INPUT_LIMIT');
      receiveCalls++; chunk.copy(rx,received); received += chunk.length;
      if (received >= 4 && declared === null) {
        declared = rx.readUInt32BE(0);
        if (declared < 1 || declared > limits.frame_bytes) throw codeError('OWNER_BRIDGE_FRAME_LIMIT');
      }
      if (declared === null || received < declared + 4) return true;
      if (received !== declared + 4 || rxFrames !== 0) throw codeError('OWNER_BRIDGE_FRAME_INVALID');
      const observation = refusal(rx.subarray(4,received), context);
      const finishedAt = clock(); if (stopped || localClosed) return false;
      if (finishedAt >= limits.hello_until_ns) throw codeError('OWNER_BRIDGE_EXPIRED');
      rxFrames = 1; observedCode = observation.code;
      stop(codeError(observation.code)); // observation/refusal only; never a binding
      return true;
    } catch (error) {stop(error); return false;}
  }
  function end() {
    if (unavailable || stopped || localClosed || !consumed) return false;
    stop(codeError('OWNER_BRIDGE_TRUNCATED')); return false;
  }
  function cancel() {
    if (unavailable || localClosed) return false;
    stop(codeError('OWNER_BRIDGE_CANCELLED')); // local revocation BEFORE clock/cancel notice
    if (!consumed || cancelAttempted) return false;
    cancelAttempted = true;
    try {const at = clock(); if (!localClosed && at < limits.cancel_until_ns) cancelRequests = 1;} catch (error) { /* keep the first failure */ }
    return false; // at most one local notice; never physical/native completion
  }
  function closeLocal(selectedLease) {
    if (unavailable) return false;
    if (selectedLease !== lease) throw codeError('OWNER_BRIDGE_CONTRACT_INVALID');
    if (localClosed) return true;
    if (localClosing) return false;
    localClosing = true;
    stop(codeError('OWNER_BRIDGE_LOCAL_CLOSED')); // revoke before caller clock code
    try {
      if (clock() >= limits.closure_until_ns) {stop(codeError('OWNER_BRIDGE_EXPIRED')); return false;}
      tx = null; rx = null; localClosed = true; localCloses = 1; state = 'LOCAL_CLOSED'; return true;
    } catch (error) {stop(error); return false;} finally {localClosing = false;}
  }
  const bridge = Object.freeze({
    bootstrap, outbound, receive, end, cancel, closeLocal,
    execute() {return Promise.reject(codeError('OWNER_TRANSPORT_NOT_ADMITTED'));},
    snapshot() {return Object.freeze({scope:'bootstrap-application-observation-only', state,
      generation:context === null ? null : context.generation, lease_consumed:consumed,
      tx_frames:txFrames, rx_frames:rxFrames, tx_bytes:txBytes, received_bytes:received,
      receive_calls:receiveCalls, outbound_attempted:outboundAttempted, outbound_copies:outboundCopies, outbound_copy_bytes_ever:copyBytes,
      internal_byte_buffers:(tx ? tx.length : 0) + (rx ? rx.length : 0),
      cancel_attempted:cancelAttempted, cancel_requests:cancelRequests, local_closes:localCloses,
      local_closed:localClosed, observation_code:observedCode, kernel_authority:false,
      runtime_verified:false, ready:false, peer_bound:false, native_completion:false,
      Root_lease_settled:false, model_loading_allowed:false, native_allowed:false,
      loading_grant:null, native_grant:null});}
  });
  instances.set(bridge, {generation:context === null ? null : context.generation,
    bootstrap:unavailable ? null : bootstrap});
  return bridge;
}
function bridgeBootstrapOptions(bridge) {
  const value = instances.get(bridge);
  if (!value) throw codeError('OWNER_BACKEND_INVALID');
  return Object.freeze({generation:value.generation, bootstrap:value.bootstrap});
}
module.exports = {createOwnerBridge, bridgeBootstrapOptions};
