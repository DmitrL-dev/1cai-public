'use strict';
const { createHash } = require('node:crypto');
const { profileConfig, sourceRef } = require('./core.cjs');

const WORKBENCH_STATE_KEY = 'rentgen.workbenchState';
const MAX_STATE_BYTES = 16384;
const sha = /^[0-9a-f]{64}$/;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const controls = /[\p{Cc}\p{Cf}\p{Cs}]/u;
const INVALID = 'WORKBENCH_STATE_INVALID';
const MISMATCH = 'WORKBENCH_PROFILE_MISMATCH';

function error(code) { return Object.assign(new Error(code), {code}); }
function requireValue(ok) { if (!ok) throw error(INVALID); }
function fields(value, required, optional = []) {
  requireValue(value !== null && typeof value === 'object' &&
    [Object.prototype, null].includes(Object.getPrototypeOf(value)));
  const own = Object.getOwnPropertyDescriptors(value);
  requireValue(Reflect.ownKeys(own).every(key => typeof key === 'string' &&
    [...required, ...optional].includes(key) && Object.hasOwn(own[key], 'value')) &&
    required.every(key => Object.hasOwn(own, key)));
  return value;
}
function freeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}
function snapshot(value, project) {
  fields(value, ['project_id', 'snapshot_id', 'manifest_hash']);
  requireValue(value.project_id === project && typeof value.snapshot_id === 'string' &&
    sha.test(value.snapshot_id) && value.manifest_hash === value.snapshot_id);
  return {project_id: project, snapshot_id: value.snapshot_id, manifest_hash: value.manifest_hash};
}
function descriptor(value, project) {
  fields(value, ['snapshot', 'query'], ['selection']);
  const selected = value.snapshot === null ? null : snapshot(value.snapshot, project);
  requireValue(typeof value.query === 'string' && [...value.query].length <= 256 &&
    Buffer.byteLength(value.query, 'utf8') <= 1024 && !controls.test(value.query));
  let selection = null;
  if (value.selection !== null && value.selection !== undefined) {
    requireValue(selected !== null);
    fields(value.selection, ['kind'], ['ref', 'draft_id', 'revision']);
    if (value.selection.kind === 'source') {
      fields(value.selection, ['kind', 'ref']);
      fields(value.selection.ref, ['snapshot', 'layer_id', 'relative_path', 'raw_sha256']);
      const bound = snapshot(value.selection.ref.snapshot, project);
      requireValue(bound.snapshot_id === selected.snapshot_id &&
        typeof value.selection.ref.raw_sha256 === 'string' && sha.test(value.selection.ref.raw_sha256));
      const ref = sourceRef(value.selection.ref, project);
      selection = {kind: 'source', ref};
    } else {
      fields(value.selection, ['kind', 'draft_id', 'revision']);
      requireValue(value.selection.kind === 'draft' && typeof value.selection.draft_id === 'string' &&
        uuid.test(value.selection.draft_id) && Number.isSafeInteger(value.selection.revision) && value.selection.revision > 0);
      selection = {kind: 'draft', draft_id: value.selection.draft_id, revision: value.selection.revision};
    }
  }
  return {snapshot: selected, query: value.query, selection};
}
function validate(callback) {
  try { return callback(); }
  catch (failure) { throw error(failure?.code === MISMATCH ? MISMATCH : INVALID); }
}

// Only descriptors survive a restart. The trusted startup profile supplies all
// executable/configuration paths; the hash is a binding, never an authority.
// A restored descriptor still requires a fresh Core lookup before opening it.
function createWorkbenchState(storage, config) {
  if (!storage || typeof storage.get !== 'function' || typeof storage.update !== 'function') throw error(INVALID);
  const trusted = profileConfig(config);
  // Fixed key order is the canonical representation of these five fields.
  const profile_hash = createHash('sha256').update(JSON.stringify({
    core_version: trusted.core_version, project_id: trusted.project_id,
    python: trusted.python, registry: trusted.registry, schema: trusted.schema,
  })).digest('hex');
  let tail = Promise.resolve(), latest = tail, blocked = null;
  function enqueue(callback) {
    const result = tail.then(callback);
    tail = result.then(() => undefined, () => undefined);
    latest = result;
    return result;
  }
  function record(value) {
    return validate(() => {
      fields(value, ['schema', 'profile_hash', 'snapshot', 'query', 'selection']);
      requireValue(value.schema === 1 && typeof value.profile_hash === 'string' && sha.test(value.profile_hash) &&
        value.selection !== undefined);
      if (value.profile_hash !== profile_hash) throw error(MISMATCH);
      const data = descriptor({snapshot: value.snapshot, query: value.query, selection: value.selection}, trusted.project_id);
      const saved = {schema: 1, profile_hash, ...data};
      requireValue(Buffer.byteLength(JSON.stringify(saved), 'utf8') <= MAX_STATE_BYTES);
      return freeze(data);
    });
  }
  async function existing() {
    if (blocked) throw error(blocked);
    const value = await storage.get(WORKBENCH_STATE_KEY);
    if (value === undefined) return null;
    try { return record(value); }
    catch (failure) { blocked = failure.code; throw failure; }
  }
  return Object.freeze({
    load() { return enqueue(existing); },
    async save(value) {
      // Clone before joining the queue, so callers cannot alter a pending save.
      const data = validate(() => descriptor(value, trusted.project_id));
      const saved = freeze({schema: 1, profile_hash, ...data});
      validate(() => requireValue(Buffer.byteLength(JSON.stringify(saved), 'utf8') <= MAX_STATE_BYTES));
      return enqueue(async () => {
        await existing();
        await storage.update(WORKBENCH_STATE_KEY, saved);
      });
    },
    clear() {
      return enqueue(async () => {
        await storage.update(WORKBENCH_STATE_KEY, undefined);
        blocked = null;
      });
    },
    async drain() { await latest; },
  });
}

module.exports = {createWorkbenchState, WORKBENCH_STATE_KEY, MAX_STATE_BYTES};
