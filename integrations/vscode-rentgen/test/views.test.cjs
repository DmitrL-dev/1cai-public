'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { Page, Handles } = require('../lib/state.cjs');
const { createViews } = require('../lib/views.cjs');

// Use the same versioned source/draft shape as the tree-view flow fixtures.
const project = '00000000-0000-4000-8000-000000000001';
const snapshot = {project_id: project, snapshot_id: 'a'.repeat(64), manifest_hash: 'a'.repeat(64)};
const sourceRef = {snapshot, layer_id: 'base', relative_path: 'Module.bsl', raw_sha256: 'c'.repeat(64)};
const receipt = revision => ({project_id: project, draft_id: '00000000-0000-4000-8000-000000000002',
  revision, status: 'active', title: 'Fix', source_ref: sourceRef, proposal_content_id: 'd'.repeat(64)});
function deferred() {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return {promise, resolve, reject};
}
function viewFixture() {
  const commands = new Map(), comparisons = [], minted = [], loaded = [], context = {subscriptions: []};
  let provider;
  const client = {
    source: async () => 'original',
    draft: async (_, revision) => ({receipt: receipt(revision), text: `version ${revision}`}),
    drafts: async () => ({items: [receipt(3)], next_after: null}),
    history: async () => ({items: [receipt(2)], next_before: null}),
  };
  const vscode = {
    EventEmitter: class { event = () => {}; fire() {} dispose() {} },
    TreeItemCollapsibleState: {Collapsed: 1, None: 0}, TreeItem: class {}, ThemeIcon: class {},
    Uri: {from: value => { const uri = {query: '', fragment: '', ...value}; minted.push(uri); return uri; }},
    commands: {registerCommand: (name, fn) => { commands.set(name, fn); return {dispose() {}}; },
      executeCommand: async (...args) => comparisons.push(args)},
    workspace: {registerTextDocumentContentProvider: (_, value) => { provider = value; return {dispose() {}}; },
      onDidCloseTextDocument: () => ({dispose() {}}),
      openTextDocument: async uri => { loaded.push(uri); return {uri, text: await provider.provideTextDocumentContent(uri)}; }},
    window: {createTreeView: () => ({dispose() {}}), showErrorMessage() {}},
  };
  const views = createViews(vscode, client, context);
  return {views, client, vscode, commands, comparisons, minted, loaded,
    read: uri => provider.provideTextDocumentContent(uri)};
}

test('a late page cannot overwrite a refreshed filter or append twice', async () => {
  const page = new Page(); let finish, calls = 0;
  const old = page.load(() => { calls++; return new Promise(resolve => { finish = resolve; }); });
  const duplicate = page.load(() => { throw new Error('duplicate read'); });
  await new Promise(resolve => setImmediate(resolve));
  page.reset();
  await page.load(async () => ({items: ['new-filter'], next: null}));
  finish({items: ['old-filter'], next: 'old-cursor'});
  await Promise.all([old, duplicate]);
  assert.deepEqual(page.items, ['new-filter']);
  assert.equal(page.next, null); assert.equal(calls, 1);
});

test('paging refuses cyclic cursors and bounds retained rows', async () => {
  const page = new Page(2);
  await page.load(async () => ({items: ['a'], next: 'cursor'}));
  await assert.rejects(page.load(async () => ({items: ['b'], next: 'cursor'}), true), /INVALID_PAGE_CURSOR/);
  assert.deepEqual(page.items, ['a']);
  await assert.rejects(page.load(async () => ({items: ['b', 'c'], next: null}), true), /VIEW_ROW_LIMIT/);
});

test('only minted handles work, resets expire them and memory is bounded', () => {
  const handles = new Handles(2);
  const a = handles.add({value: 'a'}), b = handles.add({value: 'b'});
  assert.equal(handles.get(a).value, 'a');
  assert.throws(() => handles.get('file:///C:/secret'), /UNKNOWN_VIEW_HANDLE/);
  assert.throws(() => handles.add({}), /VIEW_HANDLE_LIMIT/);
  handles.delete(a); handles.add({value: 'c'});
  assert.equal(handles.get(b).value, 'b');
  handles.clear(); assert.throws(() => handles.get(b), /UNKNOWN_VIEW_HANDLE/);
});

for (const pendingDocument of ['original', 'candidate']) {
  test(`an automatic diff made stale while loading the ${pendingDocument} is suppressed and releases only its handles`, async () => {
    const f = viewFixture(), waiting = deferred(), entered = deferred();
    const existing = await f.views.openDraft(receipt(1));
    f.comparisons.length = 0;
    f.minted.length = 0;
    f.loaded.length = 0;
    const load = f.vscode.workspace.openTextDocument;
    f.vscode.workspace.openTextDocument = async uri => {
      const candidate = uri.path.startsWith('/[v');
      if (candidate === (pendingDocument === 'candidate')) {
        entered.resolve();
        await waiting.promise;
      }
      return load(uri);
    };
    let current = true;
    const pending = f.views.openDraft(receipt(3), () => current);
    await entered.promise;
    current = false;
    waiting.resolve();
    assert.equal(await pending, null);
    assert.deepEqual(f.comparisons, []);
    assert.equal(f.loaded.length, pendingDocument === 'original' ? 1 : 2);
    assert.equal(f.minted.length, 2);
    for (const uri of f.minted) await assert.rejects(f.read(uri), /UNKNOWN_VIEW_HANDLE/);
    assert.equal(await f.read(existing[0]), 'original');
    assert.equal(await f.read(existing[1]), 'version 1');

    const [draft] = await f.views.drafts();
    const [historical] = await f.views.history(draft.token);
    const [, candidate] = await f.commands.get('rentgen.openSelection')(historical.token);
    assert.equal(await f.read(candidate), 'version 2');
    assert.equal(f.comparisons.length, 1);
    assert.match(f.comparisons[0][3], /v2/);
  });
}

test('an already stale automatic diff performs no document load or display', async () => {
  const f = viewFixture();
  assert.equal(await f.views.openDraft(receipt(3), () => false), null);
  assert.deepEqual(f.loaded, []);
  assert.deepEqual(f.comparisons, []);
  for (const uri of f.minted) await assert.rejects(f.read(uri), /UNKNOWN_VIEW_HANDLE/);
});

test('a current automatic diff validates both documents and displays the exact revision', async () => {
  const f = viewFixture();
  const uris = await f.views.openDraft(receipt(3), () => true);
  assert.deepEqual(f.loaded, uris);
  assert.equal(f.comparisons.length, 1);
  assert.deepEqual(f.comparisons[0].slice(0, 3), ['vscode.diff', ...uris]);
  assert.equal(await f.read(uris[0]), 'original');
  assert.equal(await f.read(uris[1]), 'version 3');
});

test('the public historical selection command ignores extra predicate arguments', async () => {
  const f = viewFixture(), [draft] = await f.views.drafts();
  const [historical] = await f.views.history(draft.token);
  const [, candidate] = await f.commands.get('rentgen.openSelection')(historical.token,
    () => { throw new Error('COMMAND_ARGUMENT_MUST_NOT_RUN'); });
  assert.equal(await f.read(candidate), 'version 2');
  assert.equal(f.comparisons.length, 1);
});

test('automatic diff document failures propagate and release document handles', async () => {
  const f = viewFixture(), failure = new Error('DOCUMENT_READ_FAILED');
  f.client.draft = async () => { throw failure; };
  await assert.rejects(f.views.openDraft(receipt(3), () => true), error => error === failure);
  assert.deepEqual(f.comparisons, []);
  for (const uri of f.minted) await assert.rejects(f.read(uri), /UNKNOWN_VIEW_HANDLE/);
});

test('a diff already submitted to VS Code retains its displayed document handles', async () => {
  const f = viewFixture(), submitted = deferred(), finish = deferred();
  f.vscode.commands.executeCommand = (...args) => {
    f.comparisons.push(args);
    submitted.resolve();
    return finish.promise;
  };
  let current = true;
  const pending = f.views.openDraft(receipt(3), () => current);
  await submitted.promise;
  current = false;
  finish.resolve();
  const uris = await pending;
  assert.equal(f.comparisons.length, 1);
  assert.equal(await f.read(uris[0]), 'original');
  assert.equal(await f.read(uris[1]), 'version 3');
});
