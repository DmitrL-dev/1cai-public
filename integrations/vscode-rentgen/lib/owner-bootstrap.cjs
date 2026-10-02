'use strict';
// A0 constructed ordering seam. This module has no native/process/transport API
// and cannot attest a kernel peer, authorize a real READY or issue a grant.
function createOwnerBootstrap({generation = null, bootstrap = null} = {}) {
  if (bootstrap !== null && typeof bootstrap !== 'function') throw new Error('OWNER_BACKEND_INVALID');
  if (bootstrap && (!Number.isSafeInteger(generation) || generation < 1)) throw new Error('OWNER_GENERATION_INVALID');
  let state = bootstrap ? 'OWNER_ENDPOINT_AVAILABLE' : 'OWNER_ENDPOINT_UNAVAILABLE';
  let context = null, activation = null, initialized = false;
  function terminalError() {
    if (state === 'COMPLETION_PENDING') return new Error('OWNER_COMPLETION_PENDING');
    if (state === 'REVOKED') return new Error('OWNER_REVOKED');
    return null;
  }
  function assertBound(expected = context) {
    const stopped = terminalError(); if (stopped) throw stopped;
    if (expected !== context) throw new Error('OWNER_CONTEXT_MISMATCH');
    if (state !== 'PEER_BOUND') throw new Error('OWNER_PEER_NOT_BOUND');
  }
  function revoke() {
    if (state !== 'COMPLETION_PENDING') state = 'REVOKED';
  }
  function activate(selected, initialize) {
    const stopped = terminalError(); if (stopped) return Promise.reject(stopped);
    if (!selected || typeof selected !== 'object' || Array.isArray(selected)) return Promise.reject(new Error('OWNER_CONTEXT_INVALID'));
    if (typeof initialize !== 'function') return Promise.reject(new Error('OWNER_INITIALIZER_INVALID'));
    if (state === 'OWNER_ENDPOINT_UNAVAILABLE') return Promise.reject(new Error('OWNER_ENDPOINT_UNAVAILABLE'));
    if (context && selected !== context) return Promise.reject(new Error('OWNER_CONTEXT_MISMATCH'));
    if (activation) return activation;
    context = selected;
    state = 'HANDSHAKE_PENDING';
    // Store the promise before calling caller code, including a synchronous
    // backend. A reentrant activate must share this current-generation promise.
    activation = Promise.resolve().then(async () => {
      const stoppedBeforeStart = terminalError(); if (stoppedBeforeStart) throw stoppedBeforeStart;
      const binding = await bootstrap(Object.freeze({generation, scope: 'constructed-ordering-only'}));
      const stoppedAfterBinding = terminalError(); if (stoppedAfterBinding) throw stoppedAfterBinding;
      if (!binding || typeof binding !== 'object' || Array.isArray(binding) ||
          Object.keys(binding).sort().join(',') !== 'generation,peer_bound,schema' ||
          binding.schema !== 'rentgen-owner-constructed-binding/1' || binding.generation !== generation || binding.peer_bound !== true) {
        throw new Error('OWNER_BINDING_INVALID');
      }
      // A constructed backend can reenter via a binding getter/proxy.
      const stoppedAfterValidation = terminalError(); if (stoppedAfterValidation) throw stoppedAfterValidation;
      state = 'PEER_BOUND';
      const value = await initialize();
      assertBound(selected);
      initialized = true;
      return value;
    }).catch(error => {revoke(); throw error;});
    return activation;
  }
  return Object.freeze({
    activate, assertBound, revoke,
    completionPending() {state = 'COMPLETION_PENDING';},
    snapshot() {return Object.freeze({state, generation, initialized, scope: 'constructed-ordering-only',
      kernel_authority: false, runtime_verified: false, ready: false, model_loading_allowed: false, native_allowed: false});}
  });
}
module.exports = {createOwnerBootstrap};
