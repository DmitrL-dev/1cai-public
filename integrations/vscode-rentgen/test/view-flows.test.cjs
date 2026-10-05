'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {createViews} = require('../lib/views.cjs');
const project = '00000000-0000-4000-8000-000000000001';
const snapshot = letter => ({project_id:project, snapshot_id:letter.repeat(64), manifest_hash:letter.repeat(64)});
const ref = selected => ({snapshot:selected, layer_id:'base', relative_path:'Module.bsl', raw_sha256:'c'.repeat(64)});
const receipt = (revision, status = 'active') => ({project_id:project, draft_id:'00000000-0000-4000-8000-000000000002',
  revision, status, title:'Fix', source_ref:ref(snapshot('a')), proposal_content_id:'d'.repeat(64)});
function fixture() {
  const commands = new Map(), panels = new Map(), shown = [], comparisons = [], context = {subscriptions:[]};
  let provider, closeDocument;
  const client = {
    head:async () => ({snapshot:snapshot('a')}),
    sources:async selected => ({entries:[{ref:ref(selected)}], next_cursor:null}),
    source:async source => source.snapshot.snapshot_id,
    drafts:async ({status}) => ({items:[receipt(3, status)], next_after:null}),
    history:async () => ({items:[receipt(2)], next_before:null}),
    draft:async (_, revision) => ({receipt:receipt(revision), text:`version ${revision}`}),
  };
  const vscode = {
    EventEmitter:class {event = () => {}; fire() {} dispose() {}},
    TreeItemCollapsibleState:{Collapsed:1, None:0}, TreeItem:class {}, ThemeIcon:class {},
    Uri:{from:value => ({query:'', fragment:'', ...value})},
    commands:{registerCommand:(name, fn) => {commands.set(name, fn); return {dispose(){}};},
      executeCommand:async (...args) => comparisons.push(args)},
    workspace:{registerTextDocumentContentProvider:(_, value) => {provider = value; return {dispose(){}};},
      onDidCloseTextDocument:fn => {closeDocument = fn; return {dispose(){}};},
      openTextDocument:async uri => ({uri, text:await provider.provideTextDocumentContent(uri)})},
    window:{createTreeView:(name, {treeDataProvider}) => {const panel = {treeDataProvider, dispose(){}}; panels.set(name, panel); return panel;},
      showTextDocument:async document => shown.push(document), showErrorMessage(){}, showInputBox:async () => undefined,
      showQuickPick:async () => undefined},
  };
  const views = createViews(vscode, client, context);
  return {views, client, commands, panels, shown, comparisons, read:uri => provider.provideTextDocumentContent(uri), close:uri => closeDocument({uri})};
}

test('a late head reply cannot replace a newer explicit snapshot refresh', async () => {
  const f = fixture(), replies = [];
  f.client.head = () => new Promise(resolve => replies.push(resolve));
  const older = f.views.refreshSources(), newer = f.views.refreshSources();
  replies[1]({snapshot:snapshot('b')}); await newer;
  replies[0]({snapshot:snapshot('a')}); await older;
  const rows = await f.views.sources();
  assert.equal(f.views.selectedSource(rows[0].token).snapshot.snapshot_id, 'b'.repeat(64));
  assert.match(f.panels.get('rentgen.sources').description, /^bbbbbbbbbbbb/);
});

test('refresh expires old selection while an open source remains bound to its original snapshot', async () => {
  const f = fixture();
  await f.views.refreshSources();
  const oldRow = (await f.views.sources())[0];
  const [oldUri] = await f.commands.get('rentgen.openSelection')(oldRow.token);
  f.client.head = async () => ({snapshot:snapshot('b')});
  await f.views.refreshSources();
  assert.throws(() => f.views.selectedSource(oldRow.token), /UNKNOWN_VIEW_HANDLE/);
  assert.equal(await f.read(oldUri), 'a'.repeat(64));
  const newRow = (await f.views.sources())[0];
  await f.commands.get('rentgen.openSelection')(newRow.token);
  assert.deepEqual(f.shown.map(document => document.text), ['a'.repeat(64), 'b'.repeat(64)]);
  f.close(oldUri);
  await assert.rejects(f.read(oldUri), /UNKNOWN_VIEW_HANDLE/);
});

test('switching draft status discards a late page and opening history preserves the selected version', async () => {
  const f = fixture(); let finish;
  f.client.drafts = ({status}) => status === 'active' ? new Promise(resolve => {finish = resolve;}) :
    Promise.resolve({items:[receipt(3, status)], next_after:null});
  const pending = f.views.drafts();
  await new Promise(resolve => setImmediate(resolve));
  f.views.refreshDrafts('archived');
  const archived = await f.views.drafts();
  finish({items:[receipt(99)], next_after:null}); await pending;
  assert.deepEqual((await f.views.drafts()).map(row => row.receipt.status), ['archived']);
  const version = (await f.views.history(archived[0].token))[0];
  const [, candidate] = await f.commands.get('rentgen.openSelection')(version.token);
  assert.equal(await f.read(candidate), 'version 2');
  assert.match(f.comparisons[0][3], /v2/);
  f.client.draft = async () => ({receipt:receipt(4), text:'newer version'});
  await assert.rejects(f.read(candidate), /DRAFT_REVISION_MISMATCH/);
});
