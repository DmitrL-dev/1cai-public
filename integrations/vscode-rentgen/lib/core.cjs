'use strict';
const {NATIVE_CORE_VERSIONS,PROFILE_CORE_VERSIONS}=require('./core-versions.cjs');
const { createHash } = require('node:crypto');
const { win32 } = require('node:path');
const {PROFILE,validateBsl}=require('./bsl-result.cjs');
const {validateProfiles,validateTests,validateQualification}=require('./tests-result.cjs');

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
  requireValue(hash.test(value.snapshot_id) && value.manifest_hash === value.snapshot_id);
  return Object.freeze({ project_id: project, snapshot_id: value.snapshot_id, manifest_hash: value.manifest_hash });
}
function sourceRef(value, project) {
  const selected = snapshot(value?.snapshot, project);
  requireValue(typeof value.layer_id === 'string' && value.layer_id.length > 0 &&
    value.layer_id.length <= 256 && !controls.test(value.layer_id));
  requireValue(typeof value.relative_path === 'string' && value.relative_path.length <= 4096 &&
    !controls.test(value.relative_path) && !value.relative_path.includes('\\') &&
    value.relative_path.split('/').every(part => part && part !== '.' && part !== '..'));
  requireValue(hash.test(value.raw_sha256));
  return Object.freeze({ snapshot: selected, layer_id: value.layer_id, relative_path: value.relative_path, raw_sha256: value.raw_sha256 });
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
function draftTitle(value) {
  requireValue(typeof value === 'string' && value.trim() && [...value].length <= 240 &&
    Buffer.byteLength(value, 'utf8') <= 960 && !controls.test(value), 'INVALID_DRAFT_TITLE');
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
  requireValue(value?.schema === 1 && PROFILE_CORE_VERSIONS.includes(value.core_version) && uuid.test(value.project_id), 'INVALID_EDITOR_PROFILE');
  for (const name of ['python', 'registry']) {
    requireValue(typeof value[name] === 'string' && win32.isAbsolute(value[name]) &&
      /^[A-Za-z]:\\/.test(value[name]) && !controls.test(value[name]), 'INVALID_EDITOR_PROFILE');
  }
  const context_tokens = Object.hasOwn(value, 'context_tokens') ? value.context_tokens : 32768;
  requireValue(Number.isInteger(context_tokens) && [8192, 16384, 32768].includes(context_tokens), 'INVALID_EDITOR_PROFILE');
  return Object.freeze({ schema: 1, core_version: value.core_version, python: value.python, registry: value.registry, project_id: value.project_id, context_tokens });
}
function metadataEnvelope(value, selected, {objectRef = null, limit = 100, layer = null} = {}) {
  const valid = condition => requireValue(condition, 'INVALID_METADATA_RESPONSE');
  const text = (value, maximum, nullable = false) => valid(nullable && value === null ||
    typeof value === 'string' && value.length <= maximum && !controls.test(value));
  valid(value?.schema === 1 && value.identity_status === 'source_path_only');
  valid(JSON.stringify(snapshot(value.snapshot, selected.project_id)) === JSON.stringify(selected));
  valid(typeof value.truncated === 'boolean'); text(value.completeness, 128);
  valid(Array.isArray(value.parser_profiles) && value.parser_profiles.length <= 8);
  value.parser_profiles.forEach(item => text(item, 128));
  valid(Array.isArray(value.layers) && value.layers.length <= 64);
  const layers = new Set();
  for (const item of value.layers) {
    text(item.layer_id, 64); valid(!layers.has(item.layer_id)); layers.add(item.layer_id);
    valid(['supported', 'unsupported'].includes(item.status)); text(item.completeness, 128);
    if (layer !== null) valid(item.layer_id === layer);
  }
  valid(Array.isArray(value.source_refs) && value.source_refs.length <= 10000);
  const refKey = ref => {
    const normalized = sourceRef(ref, selected.project_id);
    valid(JSON.stringify(normalized.snapshot) === JSON.stringify(selected) && layers.has(normalized.layer_id));
    return JSON.stringify(normalized);
  };
  const verified = new Set(value.source_refs.map(refKey));
  const reference = ref => valid(verified.has(refKey(ref)));
  const preview = item => {
    valid(item && typeof item === 'object'); reference(item.source_ref);
    text(item.type, 128); text(item.name, 1024, true); text(item.synonym, 4096, true);
    valid(item.uuid_status === 'unverified'); text(item.observed_uuid, 128, true);
  };
  if (Object.hasOwn(value, 'objects')) {
    valid(Array.isArray(value.objects) && value.objects.length <= limit &&
      value.returned === value.objects.length && Number.isSafeInteger(value.total_matches) &&
      value.total_matches >= value.returned && value.total_matches <= 20000 &&
      value.truncated === (value.total_matches > value.returned));
    value.objects.forEach(preview);
  }
  if (objectRef) {
    preview(value.object); sameRef(value.object.source_ref, objectRef, selected.project_id);
    const modules = value.object.modules;
    valid(Array.isArray(modules?.items) && modules.items.length <= 200 &&
      Number.isSafeInteger(modules.total) && modules.total >= modules.items.length &&
      modules.total <= 20000 && modules.truncated === (modules.total > modules.items.length));
    for (const item of modules.items) {
      reference(item.source_ref); valid(item.source_ref.layer_id === objectRef.layer_id &&
        item.status === 'verified_bytes' && Number.isSafeInteger(item.size_bytes) &&
        item.size_bytes >= 0 && item.size_bytes <= 16 * 1024 * 1024);
    }
  }
  return value;
}
function createClient(config, { execute, trusted = () => true }) {
  config = profileConfig(config);
  let tail = Promise.resolve(), pending = 0, disposed = false;
  const trust = () => requireValue(!disposed && trusted(), 'TRUST_REQUIRED');
  async function call(command, args = [], scoped = true) {
    trust();
    requireValue(pending < 8, 'CLI_QUEUE_FULL');
    pending++;
    const request = tail.then(async () => {
      trust();
      const result = await execute(config.python, ['-I', '-m', 'rentgen_core', command,
        ...(scoped ? ['--registry', config.registry, '--project', config.project_id] : []), ...args]);
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
    async navigationCapability() {
      const value = await call('capabilities', [], false);
      requireValue(value?.contract_version === 1 && value.platform === 'win32' &&
        value.scope === 'os-adapter-support', 'INVALID_CAPABILITIES_RESPONSE');
      const retained = value.capabilities?.['snapshot.retained.read'];
      requireValue(retained && typeof retained.supported === 'boolean' &&
        Array.isArray(retained.operations) && retained.operations.length <= 200 &&
        retained.operations.every(item => typeof item === 'string' && /^[a-z][a-z0-9-]{0,80}$/.test(item)),
        'INVALID_CAPABILITIES_RESPONSE');
      return Object.freeze({supported:retained.supported &&
        ['metadata-summary','metadata-search','metadata-object'].every(name => retained.operations.includes(name))});
    },
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
      if (query) args.push('--query='+query);
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
      const value = await call('source-read', ['--snapshot', ref.snapshot.snapshot_id, '--layer='+ref.layer_id, '--path='+ref.relative_path, '--base64']);
      return sourceText(value, ref);
    },
    async metadataSummary(selected, {layer = null} = {}) {
      selected = snapshot(selected, config.project_id);
      requireValue(layer === null || typeof layer === 'string' && /^[a-z][a-z0-9_-]{0,63}$/.test(layer), 'INVALID_SEARCH');
      const args = ['--snapshot', selected.snapshot_id];
      if (layer !== null) args.push('--layer='+layer);
      return metadataEnvelope(await call('metadata-summary', args), selected, {layer});
    },
    async metadataSearch(selected, {query = '', type = null, layer = null} = {}) {
      selected = snapshot(selected, config.project_id);
      for (const value of [query, ...(type === null ? [] : [type])]) requireValue(
        typeof value === 'string' && [...value].length <= 256 && Buffer.byteLength(value) <= 1024 && !controls.test(value), 'INVALID_SEARCH');
      requireValue(layer === null || typeof layer === 'string' && /^[a-z][a-z0-9_-]{0,63}$/.test(layer), 'INVALID_SEARCH');
      const args = ['--snapshot', selected.snapshot_id, '--query='+query, '--limit', '100'];
      if (type !== null) args.push('--type='+type);
      if (layer !== null) args.push('--layer='+layer);
      const value = metadataEnvelope(await call('metadata-search', args), selected, {layer});
      requireValue(Array.isArray(value.objects), 'INVALID_METADATA_RESPONSE');
      return value;
    },
    async metadataObject(selected, ref) {
      selected = snapshot(selected, config.project_id); ref = sourceRef(ref, config.project_id);
      requireValue(JSON.stringify(ref.snapshot) === JSON.stringify(selected), 'SOURCE_REF_MISMATCH');
      return metadataEnvelope(await call('metadata-object', ['--snapshot', selected.snapshot_id,
        '--layer='+ref.layer_id, '--path='+ref.relative_path]), selected, {objectRef:ref, layer:ref.layer_id});
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
    async proposal(id, revision) {
      requireValue(uuid.test(id) && Number.isSafeInteger(revision) && revision > 0);
      const value = await call('draft-get', ['--draft-id', id, '--revision', String(revision)]);
      draftText(value, config.project_id, id, revision);
      return value;
    },
    async createProposal(ref, refFile, replacementFile) {
      ref=sourceRef(ref,config.project_id);
      for(const value of [refFile,replacementFile]) requireValue(typeof value==='string'&&/^[A-Za-z]:\\/.test(value)&&!controls.test(value),'INVALID_EDIT_PATH');
      const value=(await call('proposal-create',['--snapshot',ref.snapshot.snapshot_id,'--source-ref-json',refFile,'--replacement-file',replacementFile])).proposal;
      sameRef(value?.source_ref,ref,config.project_id);requireValue(hash.test(value.content_id)&&value.original?.raw_sha256===ref.raw_sha256);
      decode(value.replacement?.base64,value.replacement?.size_bytes,value.replacement?.raw_sha256);
      return value;
    },
    async saveDraft(base, proposalFile, contentId, operation) {
      receipt(base,config.project_id);requireValue(uuid.test(operation)&&hash.test(contentId));
      requireValue(typeof proposalFile==='string'&&/^[A-Za-z]:\\/.test(proposalFile)&&!controls.test(proposalFile),'INVALID_EDIT_PATH');
      const value=await call('draft-save',['--draft-id',base.draft_id,'--operation-id',operation,'--expected-revision',String(base.revision),
        '--snapshot',base.source_ref.snapshot.snapshot_id,'--proposal-json',proposalFile,'--title='+base.title]);
      receipt(value,config.project_id);sameRef(value.source_ref,base.source_ref,config.project_id);
      requireValue(value.draft_id===base.draft_id&&value.revision===base.revision+1&&value.operation_id===operation&&value.proposal_content_id===contentId,'DRAFT_REVISION_MISMATCH');
      return value;
    },
    async createDraft(ref, id, title, proposalFile, contentId, operation) {
      ref=sourceRef(ref,config.project_id);draftTitle(title);
      requireValue(uuid.test(id)&&uuid.test(operation)&&hash.test(contentId));
      requireValue(typeof proposalFile==='string'&&/^[A-Za-z]:\\/.test(proposalFile)&&!controls.test(proposalFile),'INVALID_EDIT_PATH');
      const value=await call('draft-save',['--draft-id',id,'--operation-id',operation,'--expected-revision','0',
        '--snapshot',ref.snapshot.snapshot_id,'--proposal-json',proposalFile,'--title='+title]);
      receipt(value,config.project_id);sameRef(value.source_ref,ref,config.project_id);
      requireValue(value.draft_id===id&&value.revision===1&&value.operation_id===operation&&value.proposal_content_id===contentId&&
        value.title===title&&value.outcome==='committed'&&value.action==='draft.saved'&&value.status==='active','DRAFT_REVISION_MISMATCH');
      return value;
    },
    async bslCheck({receipt: saved, proposal, file}) {
      receipt(saved,config.project_id);
      requireValue(NATIVE_CORE_VERSIONS.includes(config.core_version),'BSL_REQUIRES_DEV8');
      requireValue(typeof file==='string'&&/^[A-Za-z]:\\/.test(file)&&!controls.test(file),'INVALID_BSL_PATH');
      const value=await call('proposal-check',['--snapshot',saved.source_ref.snapshot.snapshot_id,
        '--proposal-json',file,'--diagnostics-profile',PROFILE]);
      validateBsl(value,saved,proposal);return value;
    },
    async testProfiles() {
      requireValue(NATIVE_CORE_VERSIONS.includes(config.core_version),'TEST_REQUIRES_DEV8');
      return validateProfiles(await call('test-profile-list'));
    },
    async testCheck({id, receipt:saved, proposal, file, profile}) {
      requireValue(NATIVE_CORE_VERSIONS.includes(config.core_version),'TEST_REQUIRES_DEV8');
      receipt(saved,config.project_id);requireValue(uuid.test(id),'INVALID_OPERATION_ID');validateProfiles([profile]);
      requireValue(profile.enabled,'TEST_PROFILE_UNAVAILABLE');
      requireValue(typeof file==='string'&&/^[A-Za-z]:\\/.test(file)&&!controls.test(file),'INVALID_TEST_PATH');
      return validateTests(await call('proposal-test',['--snapshot',saved.source_ref.snapshot.snapshot_id,'--proposal-json',file,'--test-profile',profile.profile_id,'--operation-id',id]),id,saved,proposal,profile);
    },
    async testQualifyCapability() {
      const value = await call('capabilities', [], false);
      requireValue(value?.contract_version === 1 && typeof value.platform === 'string' &&
        value.scope === 'os-adapter-support', 'INVALID_CAPABILITIES_RESPONSE');
      const group = value.capabilities?.['native.evidence.read'];
      // Advertised operation admits the read-only action; the Core version number does not.
      return Object.freeze({supported: group?.supported === true && Array.isArray(group.operations) &&
        group.operations.length <= 200 && group.operations.includes('test-run-qualify')});
    },
    async testQualify(id) {
      requireValue(uuid.test(id), 'INVALID_OPERATION_ID');
      return validateQualification(await call('test-run-qualify', ['--operation-id', id]), id, config.project_id);
    },
    async testResult(id) {
      requireValue(NATIVE_CORE_VERSIONS.includes(config.core_version),'TEST_REQUIRES_DEV8');requireValue(uuid.test(id),'INVALID_OPERATION_ID');
      const value=await call('proposal-test-result',['--operation-id',id]);
      requireValue(value?.run_id===id&&['completed','failed','incomplete'].includes(value.status),'TEST_RESULT_MISMATCH');
      return value;
    },
    async platformCheck({id, ref, contentId, proposal, platform, platformHash}) {
      requireValue(NATIVE_CORE_VERSIONS.includes(config.core_version), 'PLATFORM_REQUIRES_DEV8');
      requireValue(uuid.test(id) && hash.test(platformHash) && hash.test(contentId));
      ref = sourceRef(ref, config.project_id);
      for (const value of [proposal, platform]) requireValue(typeof value === 'string' &&
        /^[A-Za-z]:\\/.test(value) && !controls.test(value), 'INVALID_PLATFORM_PATH');
      const value = await call('proposal-platform-check', ['--snapshot', ref.snapshot.snapshot_id,
        '--proposal-json', proposal, '--platform', platform, '--platform-sha256', platformHash, '--operation-id', id]);
      requireValue(value?.run_id === id && value.proposal_content_id === contentId &&
        value.platform_executable_sha256 === platformHash, 'PLATFORM_RESULT_MISMATCH');
      sameRef(value.source_ref, ref, config.project_id);
      return value;
    },
    async platformResult(id) {
      requireValue(NATIVE_CORE_VERSIONS.includes(config.core_version), 'PLATFORM_REQUIRES_DEV8');
      requireValue(uuid.test(id), 'INVALID_OPERATION_ID');
      const value = await call('proposal-platform-result', ['--operation-id', id]);
      requireValue(value?.run_id === id && ['completed', 'failed', 'incomplete'].includes(value.status), 'PLATFORM_RESULT_MISMATCH');
      if (value.request !== null) requireValue(value.request?.run_id === id && value.request.project_id === config.project_id, 'PLATFORM_RESULT_MISMATCH');
      if (value.status === 'completed') {
        requireValue(value.report?.run_id === id && hash.test(value.report.report_sha256), 'PLATFORM_RESULT_MISMATCH');
        sourceRef(value.report.source_ref, config.project_id);
      }
      if (value.status === 'failed') requireValue(value.failure?.run_id === id && value.failure.project_id === config.project_id, 'PLATFORM_RESULT_MISMATCH');
      return value;
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
module.exports = { createClient, sourceText, draftText, sourceRef, draftTitle, profileConfig, MAX_OUTPUT };
