'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {createWorkbenchState, WORKBENCH_STATE_KEY, MAX_STATE_BYTES} = require('../lib/workbench-state.cjs');

const project = '00000000-0000-4000-8000-000000000001';
const draft = '00000000-0000-4000-8000-000000000002';
const config = {schema: 1, project_id: project, core_version: '0.1.0.dev19', python: 'C:\\core\\python.exe', registry: 'C:\\profile\\registry.sqlite3'};
const snapshot = {project_id: project, snapshot_id: 'a'.repeat(64), manifest_hash: 'a'.repeat(64)};
const ref = {snapshot, layer_id: 'base', relative_path: 'ОбщиеМодули/Модуль.bsl', raw_sha256: 'c'.repeat(64)};
const source = () => structuredClone({snapshot, query: 'Модуль', selection: {kind: 'source', ref}});
const draftState = () => structuredClone({snapshot, query: '', selection: {kind: 'draft', draft_id: draft, revision: 7}});
function memory(initial) {
  let value = initial;
  const writes = [];
  return {writes, get stored() { return value; }, replace(next) { value = next; },
    get(key) { assert.equal(key, WORKBENCH_STATE_KEY); return value; },
    async update(key, next) { assert.equal(key, WORKBENCH_STATE_KEY); writes.push(next); value = next; }};
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return {promise, resolve, reject};
}
const invalid = failure => failure.message === 'WORKBENCH_STATE_INVALID' && failure.code === failure.message;

test('absent state is distinct from a persisted empty workbench', async () => {
  const storage = memory(), state = createWorkbenchState(storage, config);
  assert.equal(await state.load(), null);
  await state.save({snapshot: null, query: ''});
  assert.deepEqual(await state.load(), {snapshot: null, query: '', selection: null});
  await state.clear();
  assert.equal(storage.stored, undefined);
  assert.equal(await state.load(), null);
});

test('source and exact draft revision restore across service instances', async () => {
  for (const input of [source(), draftState()]) {
    const storage = memory();
    await createWorkbenchState(storage, config).save(input);
    assert.deepEqual(await createWorkbenchState(storage, config).load(), input);
    assert.equal(storage.stored.schema, 1);
    assert.match(storage.stored.profile_hash, /^[0-9a-f]{64}$/);
    assert.ok(Buffer.byteLength(JSON.stringify(storage.stored)) <= MAX_STATE_BYTES);
  }
});

test('profile binding is canonical and retains no executable, registry or tokens', async () => {
  const storage = memory();
  await createWorkbenchState(storage, {...config, context_tokens: 8192}).save(source());
  const reordered = Object.fromEntries(Object.entries({...config, context_tokens: 32768}).reverse());
  assert.deepEqual(await createWorkbenchState(storage, reordered).load(), source());
  const serialized = JSON.stringify(storage.stored);
  for (const secret of [config.python, config.registry, 'context_tokens', 'authority', 'token']) assert.ok(!serialized.includes(JSON.stringify(secret).slice(1, -1)));
  assert.deepEqual(Object.keys(storage.stored).sort(), ['schema', 'profile_hash', 'snapshot', 'query', 'selection'].sort());
});

for (const [field, value] of Object.entries({project_id: draft, core_version: '0.1.0.dev17', python: 'D:\\core\\python.exe', registry: 'C:\\other\\registry.sqlite3'})) {
  test(`a changed trusted ${field} requires explicit reset`, async () => {
    const storage = memory();
    await createWorkbenchState(storage, config).save(source());
    const original = storage.stored, state = createWorkbenchState(storage, {...config, [field]: value});
    await assert.rejects(state.load(), /WORKBENCH_PROFILE_MISMATCH/);
    await assert.rejects(state.save({snapshot: null, query: ''}), /WORKBENCH_PROFILE_MISMATCH/);
    assert.equal(storage.stored, original);
    await state.clear();
    await state.save({snapshot: null, query: ''});
    assert.deepEqual(await state.load(), {snapshot: null, query: '', selection: null});
  });
}

test('caller mutation cannot change a queued save or the trusted binding', async () => {
  const entered = deferred(), release = deferred(), storage = memory();
  const underlying = storage.update.bind(storage);
  storage.update = async (...args) => { entered.resolve(); await release.promise; await underlying(...args); };
  const mutableConfig = {...config}, state = createWorkbenchState(storage, mutableConfig);
  const input = source(), saving = state.save(input);
  input.query = 'changed'; input.selection.ref.relative_path = 'different.bsl'; input.snapshot.snapshot_id = 'f'.repeat(64);
  mutableConfig.python = 'D:\\untrusted.exe';
  await entered.promise;
  release.resolve(); await saving;
  const loaded = await state.load();
  assert.deepEqual(loaded, source());
  assert.ok(Object.isFrozen(loaded) && Object.isFrozen(loaded.selection.ref.snapshot));
  assert.throws(() => { loaded.selection.ref.relative_path = 'changed.bsl'; }, TypeError);
  assert.deepEqual(await createWorkbenchState(storage, config).load(), source());
});

test('storage updates serialize even when the first save is pending; the latest save wins', async () => {
  const storage = memory(), entered = deferred(), release = deferred();
  const underlying = storage.update.bind(storage);
  let calls = 0;
  storage.update = async (...args) => {
    if (++calls === 1) { entered.resolve(); await release.promise; }
    await underlying(...args);
  };
  const state = createWorkbenchState(storage, config), first = state.save(source());
  await entered.promise;
  const second = state.save(draftState()), reading = state.load();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls, 1);
  release.resolve();
  await Promise.all([first, second]);
  assert.deepEqual(await reading, draftState());
  await state.drain();
  assert.deepEqual(storage.writes.map(value => value.selection.kind), ['source', 'draft']);
});

test('clear queues after pending saves and permits a subsequent fresh save', async () => {
  const storage = memory(), state = createWorkbenchState(storage, config);
  await Promise.all([state.save(source()), state.clear(), state.save(draftState())]);
  assert.deepEqual(storage.writes.map(value => value?.selection.kind), ['source', undefined, 'draft']);
  assert.deepEqual(await state.load(), draftState());
});

test('malformed persisted state is quarantined until clear, even if storage is externally removed', async () => {
  for (const malformed of [null, 'text', {}, {schema: 99}, []]) {
    const storage = memory(malformed), state = createWorkbenchState(storage, config);
    await assert.rejects(state.load(), invalid);
    storage.replace(undefined);
    await assert.rejects(state.save(source()), invalid);
    assert.equal(storage.writes.length, 0);
    await state.clear(); await state.save(source());
    assert.deepEqual(await state.load(), source());
  }
});

test('save checks pre-existing corrupt state without requiring an earlier load', async () => {
  const valid = memory(); await createWorkbenchState(valid, config).save(source());
  for (const change of [
    saved => { saved.schema = 2; }, saved => { saved.profile_hash = 'bad'; },
    saved => { delete saved.selection; }, saved => { saved.selection = undefined; },
    saved => { saved.selection.ref.snapshot.manifest_hash = 'b'.repeat(64); },
    saved => { saved.query = 'x'.repeat(100000); },
  ]) {
    const existing = structuredClone(valid.stored); change(existing);
    const storage = memory(existing), state = createWorkbenchState(storage, config);
    await assert.rejects(state.save(draftState()), invalid);
    assert.equal(storage.stored, existing); assert.equal(storage.writes.length, 0);
    await assert.rejects(state.load(), invalid);
  }
});

test('state cannot introduce authority, credentials, executable settings or raw document text', async () => {
  for (const [location, field, value] of [
    ['root', 'authority', 'minted-handle'], ['root', 'token', 'secret'], ['root', 'python', 'D:\\evil.exe'],
    ['root', 'registry', 'D:\\foreign.sqlite3'], ['root', 'text', 'Процедура Код()'],
    ['selection', 'authority', 'file:///secret'], ['ref', 'content', 'source text'], ['snapshot', 'registry', 'D:\\registry'],
  ]) {
    const input = source();
    (location === 'root' ? input : location === 'ref' ? input.selection.ref : input[location])[field] = value;
    const storage = memory(), state = createWorkbenchState(storage, config);
    await assert.rejects(state.save(input), invalid);
    assert.equal(storage.writes.length, 0);
  }
  const storage = memory();
  await createWorkbenchState(storage, config).save(source());
  storage.replace({...storage.stored, python: 'D:\\evil.exe'});
  await assert.rejects(createWorkbenchState(storage, config).load(), invalid);
});

test('snapshot identities and selected source must belong to this exact snapshot', async () => {
  const mutations = [
    input => { input.snapshot.project_id = draft; },
    input => { input.snapshot.snapshot_id = 'b'.repeat(64); },
    input => { input.snapshot.manifest_hash = 'A'.repeat(64); },
    input => { input.selection.ref.snapshot.project_id = draft; },
    input => { input.selection.ref.snapshot = {...snapshot, snapshot_id: 'b'.repeat(64), manifest_hash: 'b'.repeat(64)}; },
    input => { input.selection.ref.raw_sha256 = 'invalid'; },
    input => { input.selection.ref.relative_path = '../secret.bsl'; },
    input => { input.selection.ref.relative_path = 'C:\\secret.bsl'; },
    input => { input.snapshot = null; },
  ];
  for (const mutate of mutations) {
    const input = source(); mutate(input);
    await assert.rejects(createWorkbenchState(memory(), config).save(input), invalid);
  }
});

test('query accepts bounded Unicode and refuses controls, surrogates or excess characters', async () => {
  const state = createWorkbenchState(memory(), config);
  for (const query of ['', '😀'.repeat(256), 'Модуль/Строка']) await state.save({...source(), query});
  for (const query of ['x'.repeat(257), '😀'.repeat(257), '\n', '\u0000', '\u202e', '\ud800', 1, null]) {
    await assert.rejects(state.save({...source(), query}), invalid);
  }
});

test('large descriptors remain under the whole UTF-8 record cap and oversized input is refused', async () => {
  const input = source(), storage = memory(), state = createWorkbenchState(storage, config);
  input.query = '😀'.repeat(256); input.selection.ref.layer_id = '界'.repeat(256);
  input.selection.ref.relative_path = '界'.repeat(4096);
  await state.save(input);
  assert.ok(Buffer.byteLength(JSON.stringify(storage.stored), 'utf8') <= MAX_STATE_BYTES);
  // Per-field bounds are deliberately tighter than the whole-record byte cap.
  input.selection.ref.relative_path = '😀'.repeat(4096);
  assert.ok(Buffer.byteLength(JSON.stringify(input), 'utf8') > MAX_STATE_BYTES);
  await assert.rejects(state.save(input), invalid);
});

test('draft selection requires exact UUID and positive safe integer revision', async () => {
  const state = createWorkbenchState(memory(), config);
  for (const changed of [
    {draft_id: draft.toUpperCase() + 'a'}, {draft_id: '../draft'}, {draft_id: null},
    {revision: 0}, {revision: -1}, {revision: 1.5}, {revision: Number.MAX_SAFE_INTEGER + 1}, {revision: '7'},
    {kind: 'uri'}, {token: 'authority'},
  ]) await assert.rejects(state.save({...draftState(), selection: {...draftState().selection, ...changed}}), invalid);
  await state.save({...draftState(), selection: {...draftState().selection, revision: Number.MAX_SAFE_INTEGER}});
});

test('stored descriptors are cloned and frozen, without getters, custom prototypes or toJSON', async () => {
  const state = createWorkbenchState(memory(), config);
  let invoked = false;
  for (const input of [
    {...source(), toJSON() { invoked = true; return source(); }},
    Object.assign(Object.create({authority: 'inherited'}), source()),
    {...source(), get query() { invoked = true; return ''; }},
    {...source(), selection: {get kind() { invoked = true; return 'source'; }, ref}},
    {...source(), selection: {kind: 'source', ref: {...ref, raw_sha256: {toString() { invoked = true; return 'c'.repeat(64); }}}}},
  ]) await assert.rejects(state.save(input), invalid);
  assert.equal(invoked, false);
  const storage = memory(); await createWorkbenchState(storage, config).save(source());
  const original = structuredClone(storage.stored); storage.replace(original);
  const loaded = await createWorkbenchState(storage, config).load();
  original.selection.ref.relative_path = 'external mutation.bsl';
  assert.equal(loaded.selection.ref.relative_path, ref.relative_path);
});

test('storage failures propagate and a failed clear does not discard quarantine', async () => {
  const storage = memory(null), state = createWorkbenchState(storage, config);
  await assert.rejects(state.load(), invalid);
  const failure = new Error('storage unavailable'), underlying = storage.update.bind(storage);
  storage.update = async () => { throw failure; };
  await assert.rejects(state.clear(), error => error === failure);
  await assert.rejects(state.save(source()), invalid);
  storage.update = underlying;
  await state.clear(); await state.save(source());
  storage.update = async () => { throw failure; };
  await assert.rejects(state.save(draftState()), error => error === failure);
  await assert.rejects(state.drain(), error => error === failure);
  assert.deepEqual(await state.load(), source());
  storage.get = () => { throw failure; };
  await assert.rejects(state.load(), error => error === failure);
});
