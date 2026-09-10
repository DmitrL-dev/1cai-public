'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { createClient, sourceText, draftText } = require('../lib/core.cjs');
const project = '00000000-0000-4000-8000-000000000001';
const draft = '00000000-0000-4000-8000-000000000002';
const bytes = Buffer.from('\uFEFFПроцедура Проверка()\r\nКонецПроцедуры\r\n');
const hash = createHash('sha256').update(bytes).digest('hex');
const ref = {snapshot: {project_id: project, snapshot_id: 'a'.repeat(64), manifest_hash: 'a'.repeat(64)}, layer_id: 'base', relative_path: 'Модуль $(not-code).bsl', raw_sha256: hash};
const config = {schema: 1, python: "C:\\путь ' $()\\python.exe", registry: 'C:\\registry.sqlite3', project_id: project, core_version: '0.1.0.dev4'};
const output = value => ({code: 0, stdout: Buffer.from(JSON.stringify({result: value}))});

test('source text preserves BOM/CRLF and rejects altered bytes or reference', () => {
  const value = {ref, raw_sha256: hash, size_bytes: bytes.length, encoding: 'base64', data: bytes.toString('base64')};
  assert.equal(sourceText(value, ref), bytes.toString('utf8'));
  assert.throws(() => sourceText({...value, data: '%%%not-base64'}, ref));
  assert.throws(() => sourceText({...value, size_bytes: bytes.length + 1}, ref));
  assert.throws(() => sourceText({...value, ref: {...ref, layer_id: 'other'}}, ref));
  const invalid = Buffer.from([0xff]);
  const badHash = createHash('sha256').update(invalid).digest('hex');
  assert.throws(() => sourceText({...value, ref: {...ref, raw_sha256: badHash}, raw_sha256: badHash, data: '/w==', size_bytes: 1}, {...ref, raw_sha256: badHash}));
});

test('draft binds requested identity/revision, original ref and replacement hash', () => {
  const receipt = {project_id: project, draft_id: draft, revision: 2, source_ref: ref, proposal_content_id: 'b'.repeat(64)};
  const proposal = {content_id: 'b'.repeat(64), source_ref: ref, original: {raw_sha256: hash}, replacement: {base64: bytes.toString('base64'), raw_sha256: hash, size_bytes: bytes.length}};
  const value = {receipt, proposal};
  assert.equal(draftText(value, project, draft, 2), bytes.toString('utf8'));
  assert.throws(() => draftText(value, project, draft, 1));
  assert.throws(() => draftText({...value, proposal: {...proposal, source_ref: {...ref, relative_path: 'other.bsl'}}}, project, draft, 2));
});

test('no process is started without trust or for foreign source/project', async () => {
  let starts = 0;
  const execute = async () => { starts++; return output({}); };
  const denied = createClient(config, {execute, trusted: () => false});
  await assert.rejects(denied.head(), /TRUST_REQUIRED/);
  const client = createClient(config, {execute});
  await assert.rejects(client.source({...ref, snapshot: {...ref.snapshot, project_id: draft}}), /PROJECT_MISMATCH/);
  assert.equal(starts, 0);
});

test('literal argv uses explicit snapshot and never a shell/output file', async () => {
  let seen;
  const client = createClient(config, {execute: async (command, args) => { seen = {command, args}; return output({ref, raw_sha256: hash, size_bytes: bytes.length, encoding: 'base64', data: bytes.toString('base64')}); }});
  assert.equal(await client.source(ref), bytes.toString('utf8'));
  assert.equal(seen.command, config.python);
  assert.deepEqual(seen.args, ['-I', '-m', 'rentgen_core', 'source-read', '--registry', config.registry, '--project', project, '--snapshot', ref.snapshot.snapshot_id, '--layer', 'base', '--path', ref.relative_path, '--base64']);
});

test('queued read rechecks trust after earlier process and after output', async () => {
  let trusted = true, complete, starts = 0;
  const client = createClient(config, {trusted: () => trusted, execute: () => { starts++; return new Promise(resolve => { complete = resolve; }); }});
  const first = client.head(); const second = client.head();
  await new Promise(resolve => setImmediate(resolve));
  trusted = false; complete(output({project_id: project, snapshot: null}));
  await assert.rejects(first, /TRUST_REQUIRED/);
  await assert.rejects(second, /TRUST_REQUIRED/);
  assert.equal(starts, 1);
});

test('malformed or failed CLI output never becomes a successful result', async () => {
  for (const reply of [{code: 0, stdout: Buffer.from('not json')}, {code: 2, stdout: Buffer.from('{"result":{}}')}, {code: 0, stdout: Buffer.from([0xff])}]) {
    const client = createClient(config, {execute: async () => reply});
    await assert.rejects(client.head());
  }
});

test('receipt lookup uses literal operation identity and refuses a foreign reply', async () => {
  const operation = '00000000-0000-4000-8000-000000000003';
  let reply = null, seen;
  const client = createClient(config, {execute:async (_,args)=>{seen=args;return output(reply);}});
  assert.equal(await client.receipt(operation),null);
  assert.deepEqual(seen.slice(3),['draft-receipt','--registry',config.registry,'--project',project,'--operation-id',operation]);
  const saved = {project_id:project,draft_id:draft,revision:2,source_ref:ref,proposal_content_id:'b'.repeat(64),operation_id:operation};
  reply = saved; assert.deepEqual(await client.receipt(operation),saved);
  reply = {...saved,operation_id:draft}; await assert.rejects(client.receipt(operation));
  reply = {...saved,project_id:draft}; await assert.rejects(client.receipt(operation));
});
