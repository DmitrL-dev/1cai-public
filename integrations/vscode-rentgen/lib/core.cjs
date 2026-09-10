'use strict';
const { createHash } = require('node:crypto');
const { win32 } = require('node:path');

const MAX_BYTES = 1048576;
const MAX_OUTPUT = 2097152 + 1; // CLI envelope limit plus newline
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const hash = /^[0-9a-f]{64}$/;
const controls = /[\p{Cc}\p{Cf}\p{Cs}]/u;
const utf8 = bytes => new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
function requireValue(condition, code = 'INVALID_CORE_RESPONSE') {
  if (!condition) throw new Error(code);
}
function freeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}
function snapshot(value, project) {
  requireValue(value?.project_id === project, 'PROJECT_MISMATCH');
  requireValue(hash.test(value.snapshot_id) && hash.test(value.manifest_hash));
  return { project_id: project, snapshot_id: value.snapshot_id, manifest_hash: value.manifest_hash };
}
function sourceRef(value, project) {
  const selected = snapshot(value?.snapshot, project);
  requireValue(typeof value.layer_id === 'string' && value.layer_id.length > 0 &&
    value.layer_id.length <= 256 && !controls.test(value.layer_id));
  requireValue(typeof value.relative_path === 'string' && value.relative_path.length <= 4096 &&
    !controls.test(value.relative_path) && !value.relative_path.includes('\\') &&
    value.relative_path.split('/').every(part => part && part !== '.' && part !== '..'));
  requireValue(hash.test(value.raw_sha256));
  return { snapshot: selected, layer_id: value.layer_id, relative_path: value.relative_path, raw_sha256: value.raw_sha256 };
}
function sameRef(left, right, project) {
  requireValue(JSON.stringify(sourceRef(left, project)) === JSON.stringify(sourceRef(right, project)), 'SOURCE_REF_MISMATCH');
}
function decode(data, size, digest) {
  requireValue(Number.isSafeInteger(size) && size >= 0 && size <= MAX_BYTES, 'DOCUMENT_SIZE_LIMIT');
  requireValue(typeof data === 'string' && data.length <= 4 * Math.ceil(MAX_BYTES / 3) &&
    /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(data));
  const bytes = Buffer.from(data, 'base64');
  requireValue(bytes.length === size && bytes.toString('base64') === data);
  requireValue(hash.test(digest) && createHash('sha256').update(bytes).digest('hex') === digest, 'CONTENT_HASH_MISMATCH');
  try { return utf8(bytes); } catch { throw new Error('DOCUMENT_NOT_UTF8'); }
}
function sourceText(value, ref) {
  sameRef(value?.ref, ref, ref.snapshot.project_id);
  requireValue(value.encoding === 'base64' && value.raw_sha256 === ref.raw_sha256);
  return decode(value.data, value.size_bytes, value.raw_sha256);
}
function receipt(value, project) {
  requireValue(value?.project_id === project, 'PROJECT_MISMATCH');
  requireValue(uuid.test(value.draft_id) && Number.isSafeInteger(value.revision) && value.revision > 0);
  requireValue(hash.test(value.proposal_content_id));
  sourceRef(value.source_ref, project);
  return value;
}
function draftText(value, project, id, revision) {
  const saved = receipt(value?.receipt, project);
  const proposal = value.proposal;
  requireValue(saved.draft_id === id && saved.revision === revision, 'DRAFT_REVISION_MISMATCH');
  sameRef(proposal?.source_ref, saved.source_ref, project);
  requireValue(proposal.content_id === saved.proposal_content_id && proposal.original?.raw_sha256 === saved.source_ref.raw_sha256);
  const replacement = proposal.replacement;
  return decode(replacement?.base64, replacement?.size_bytes, replacement?.raw_sha256);
}
function profileConfig(value) {
  requireValue(value?.schema === 1 && ['0.1.0.dev4', '0.1.0.dev5', '0.1.0.dev6', '0.1.0.dev7'].includes(value.core_version) && uuid.test(value.project_id), 'INVALID_EDITOR_PROFILE');
  for (const name of ['python', 'registry']) {
    requireValue(typeof value[name] === 'string' && win32.isAbsolute(value[name]) &&
      /^[A-Za-z]:\\/.test(value[name]) && !controls.test(value[name]), 'INVALID_EDITOR_PROFILE');
  }
  return Object.freeze({ schema: 1, core_version: value.core_version, python: value.python, registry: value.registry, project_id: value.project_id });
}
function createClient(config, { execute, trusted = () => true }) {
  config = profileConfig(config);
  let tail = Promise.resolve(), pending = 0, disposed = false;
  const trust = () => requireValue(!disposed && trusted(), 'TRUST_REQUIRED');
  async function call(command, args = []) {
    trust();
    requireValue(pending < 8, 'CLI_QUEUE_FULL');
    pending++;
    const request = tail.then(async () => {
      trust();
      const result = await execute(config.python, ['-I', '-m', 'rentgen_core', command, '--registry', config.registry, '--project', config.project_id, ...args]);
      trust();
      requireValue(Buffer.isBuffer(result.stdout) && result.stdout.length <= MAX_OUTPUT, 'CLI_OUTPUT_LIMIT');
      let envelope;
      try { envelope = JSON.parse(utf8(result.stdout)); } catch { throw new Error('INVALID_CLI_OUTPUT'); }
      if (result.code !== 0 || envelope?.error) {
        const code = envelope?.error?.code;
        throw new Error(typeof code === 'string' && /^[A-Z][A-Z0-9_]{1,80}$/.test(code) ? code : 'CLI_FAILED');
      }
      requireValue(envelope && Object.hasOwn(envelope, 'result'), 'INVALID_CLI_OUTPUT');
      return freeze(envelope.result);
    });
    tail = request.catch(() => {}).finally(() => { pending--; });
    return request;
  }
  return Object.freeze({
    dispose() { disposed = true; },
    async head() {
      const value = await call('project-head');
      requireValue(value?.project_id === config.project_id, 'PROJECT_MISMATCH');
      if (value.snapshot !== null) snapshot(value.snapshot, config.project_id);
      return value;
    },
    async sources(selected, { query = '', cursor = null } = {}) {
      selected = snapshot(selected, config.project_id);
      requireValue(typeof query === 'string' && [...query].length <= 256 && Buffer.byteLength(query) <= 1024 && !controls.test(query), 'INVALID_SEARCH');
      const args = ['--snapshot', selected.snapshot_id, '--kind', 'module', '--limit', '100'];
      if (query) args.push('--query', query);
      if (cursor !== null) { requireValue(typeof cursor === 'string' && cursor.length <= 16384); args.push('--cursor', cursor); }
      const value = await call('source-list', args);
      requireValue(Array.isArray(value?.entries) && value.entries.length <= 100 &&
        (value.next_cursor === null || typeof value.next_cursor === 'string'));
      for (const entry of value.entries) {
        const ref = sourceRef(entry.ref, config.project_id);
        requireValue(JSON.stringify(ref.snapshot) === JSON.stringify(selected), 'SOURCE_REF_MISMATCH');
      }
      return value;
    },
    async source(ref) {
      ref = sourceRef(ref, config.project_id);
      const value = await call('source-read', ['--snapshot', ref.snapshot.snapshot_id, '--layer', ref.layer_id, '--path', ref.relative_path, '--base64']);
      return sourceText(value, ref);
    },
    async drafts({ status = 'active', after = null } = {}) {
      requireValue(['active', 'archived'].includes(status));
      const args = ['--status', status, '--limit', '25'];
      if (after !== null) { requireValue(uuid.test(after)); args.push('--after-draft-id', after); }
      const value = await call('draft-list', args);
      requireValue(Array.isArray(value?.items) && value.items.length <= 25 && (value.next_after === null || uuid.test(value.next_after)));
      value.items.forEach(item => { receipt(item, config.project_id); requireValue(item.status === status); });
      return value;
    },
    async history(id, { before = null } = {}) {
      requireValue(uuid.test(id));
      const args = ['--draft-id', id, '--limit', '25'];
      if (before !== null) { requireValue(Number.isSafeInteger(before) && before > 0); args.push('--before-revision', String(before)); }
      const value = await call('draft-history', args);
      requireValue(Array.isArray(value?.items) && value.items.length <= 25 &&
        (value.next_before === null || Number.isSafeInteger(value.next_before) && value.next_before > 0));
      let previous = before ?? Infinity;
      value.items.forEach(item => {
        receipt(item, config.project_id);
        requireValue(item.draft_id === id && item.revision < previous);
        previous = item.revision;
      });
      return value;
    },
    async draft(id, revision) {
      requireValue(uuid.test(id) && Number.isSafeInteger(revision) && revision > 0);
      const value = await call('draft-get', ['--draft-id', id, '--revision', String(revision)]);
      return { receipt: value.receipt, text: draftText(value, config.project_id, id, revision) };
    },
    async receipt(operation) {
      requireValue(uuid.test(operation), 'INVALID_OPERATION_ID');
      const value = await call('draft-receipt', ['--operation-id', operation]);
      if (value !== null) {
        receipt(value, config.project_id);
        requireValue(value.operation_id === operation, 'OPERATION_MISMATCH');
      }
      return value;
    },
  });
}
module.exports = { createClient, sourceText, draftText, sourceRef, profileConfig, MAX_OUTPUT };
