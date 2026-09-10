'use strict';
const { posix } = require('node:path');
const { Page, Handles } = require('./state.cjs');

function createViews(vscode, client, context) {
  const sources = new Page(), drafts = new Page(1000);
  const sourceHandles = new Handles(), draftHandles = new Handles();
  const documents = new Handles(128), histories = new Map();
  const sourceEvents = new vscode.EventEmitter(), draftEvents = new vscode.EventEmitter();
  let selected = null, query = '', status = 'active', selectionGeneration = 0;
  const subscribe = item => { context.subscriptions.push(item); return item; };
  subscribe(sourceEvents); subscribe(draftEvents);
  function row(kind, data, handles) {
    const token = handles.add({kind, ...data});
    return Object.freeze({kind, ...data, token});
  }
  function sourceRows() {
    const rows = sources.items.slice();
    if (sources.next !== null) rows.push({kind: 'moreSources', label: 'Ещё модули…'});
    return rows;
  }
  async function loadSources(more = false) {
    if (!selected) return [];
    const snap = selected, filter = query, generation = sources.generation;
    await sources.load(async cursor => {
      const result = await client.sources(snap, {query: filter, cursor});
      // Handles from obsolete replies must not outlive the corresponding page.
      if (generation !== sources.generation) return {items: [], next: null};
      return {items: result.entries.map(entry => row('source', {ref: entry.ref}, sourceHandles)), next: result.next_cursor};
    }, more);
    return sourceRows();
  }
  async function loadDrafts(more = false) {
    const filter = status, generation = drafts.generation;
    await drafts.load(async after => {
      const result = await client.drafts({status: filter, after});
      if (generation !== drafts.generation) return {items: [], next: null};
      return {items: result.items.map(receipt => row('draft', {receipt}, draftHandles)), next: result.next_after};
    }, more);
    const rows = drafts.items.slice();
    if (drafts.next !== null) rows.push({kind: 'moreDrafts', label: 'Ещё черновики…'});
    return rows;
  }
  async function loadHistory(token, more = false) {
    const root = draftHandles.get(token);
    if (root.kind !== 'draft') throw new Error('UNKNOWN_VIEW_HANDLE');
    let page = histories.get(token);
    if (!page) { page = new Page(1000); histories.set(token, page); }
    const generation = drafts.generation;
    await page.load(async before => {
      const result = await client.history(root.receipt.draft_id, {before});
      if (generation !== drafts.generation) return {items: [], next: null};
      return {items: result.items.map(receipt => row('version', {receipt}, draftHandles)), next: result.next_before};
    }, more);
    if (generation !== drafts.generation) return [];
    const rows = page.items.slice();
    if (page.next !== null) rows.push({kind: 'moreHistory', token, label: 'Ещё версии…'});
    return rows;
  }
  function getTreeItem(node) {
    const expanded = node.kind === 'draft' ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None;
    let label = node.label, description, tooltip, command;
    if (node.kind === 'source') {
      label = posix.basename(node.ref.relative_path);
      description = node.ref.layer_id + ' · ' + node.ref.relative_path;
      tooltip = `${node.ref.layer_id}/${node.ref.relative_path}\nСнимок ${node.ref.snapshot.snapshot_id}\nSHA256 ${node.ref.raw_sha256}`;
      command = 'rentgen.openSelection';
    } else if (node.receipt) {
      const saved = node.receipt;
      label = node.kind === 'draft' ? saved.title : `Версия ${saved.revision}`;
      description = node.kind === 'draft' ? `v${saved.revision} · ${saved.source_ref.relative_path}` : `${saved.action} · ${saved.recorded_at}`;
      tooltip = `${saved.draft_id}\nВерсия ${saved.revision} · ${saved.status}\nСнимок ${saved.source_ref.snapshot.snapshot_id}`;
      command = 'rentgen.openSelection';
    } else command = 'rentgen.' + node.kind;
    const item = new vscode.TreeItem(label, expanded);
    item.id = node.token ? node.kind + ':' + node.token : node.kind;
    item.contextValue = node.kind === 'source' ? 'rentgen.source' : node.kind;
    item.description = description; item.tooltip = tooltip;
    item.command = {command, title: node.receipt ? 'Сравнить с исходником' : 'Открыть', arguments: node.token ? [node.token] : []};
    item.iconPath = new vscode.ThemeIcon(node.kind === 'source' ? 'file-code' : node.receipt ? 'git-compare' : 'ellipsis');
    return item;
  }
  const sourceView = subscribe(vscode.window.createTreeView('rentgen.sources', {treeDataProvider: {
    onDidChangeTreeData: sourceEvents.event, getTreeItem, getChildren: node => node ? [] : loadSources(),
  }}));
  const draftView = subscribe(vscode.window.createTreeView('rentgen.drafts', {treeDataProvider: {
    onDidChangeTreeData: draftEvents.event, getTreeItem,
    getChildren: node => !node ? loadDrafts() : node.kind === 'draft' ? loadHistory(node.token) : [],
  }}));
  function sourceDescription() {
    sourceView.description = selected ? selected.snapshot_id.slice(0, 12) + (query ? ' · ' + query : '') : 'Нет снимка';
    sourceView.message = !selected ? 'Сначала создайте снимок проекта через capture.' :
      `Снимок ${selected.snapshot_id.slice(0, 12)}. Новый снимок открывается кнопкой «Обновить снимок».`;
  }
  async function refreshSources() {
    const generation = ++selectionGeneration;
    const head = await client.head();
    if (generation !== selectionGeneration) return;
    selected = head.snapshot;
    sourceHandles.clear(); sources.reset(); sourceDescription(); sourceEvents.fire();
  }
  function search(value) {
    query = value; sourceHandles.clear(); sources.reset(); sourceDescription(); sourceEvents.fire();
  }
  function refreshDrafts(value = status) {
    if (!['active', 'archived'].includes(value)) throw new Error('INVALID_DRAFT_STATUS');
    status = value; draftHandles.clear(); drafts.reset(); histories.clear();
    draftView.description = status === 'active' ? 'Активные' : 'Архив'; draftEvents.fire();
  }
  function document(record, basename) {
    const token = documents.add(record);
    return vscode.Uri.from({scheme: 'rentgen-view', authority: token, path: '/' + basename});
  }
  subscribe(vscode.workspace.registerTextDocumentContentProvider('rentgen-view', {
    async provideTextDocumentContent(uri) {
      const record = documents.get(uri.authority);
      if (uri.query || uri.fragment || uri.path !== '/' + record.basename) throw new Error('UNKNOWN_VIEW_HANDLE');
      if (record.kind === 'source') return client.source(record.ref);
      const result = await client.draft(record.receipt.draft_id, record.receipt.revision);
      // A revision from a list/history may never be substituted under its URI.
      if (JSON.stringify(result.receipt) !== JSON.stringify(record.receipt)) throw new Error('DRAFT_REVISION_MISMATCH');
      return result.text;
    },
  }));
  subscribe(vscode.workspace.onDidCloseTextDocument(doc => {
    if (doc.uri.scheme === 'rentgen-view') documents.delete(doc.uri.authority);
  }));
  async function openSelection(token) {
    let record;
    try { record = sourceHandles.get(token); } catch { record = draftHandles.get(token); }
    if (record.kind === 'source') {
      const basename = `[${record.ref.snapshot.snapshot_id.slice(0, 12)}] ${posix.basename(record.ref.relative_path)}`;
      const uri = document({...record, basename}, basename);
      try { await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(uri), {preview: false}); }
      catch (error) { documents.delete(uri.authority); throw error; }
      return [uri];
    }
    if (!['draft', 'version'].includes(record.kind)) throw new Error('UNKNOWN_VIEW_HANDLE');
    const saved = record.receipt, name = posix.basename(saved.source_ref.relative_path);
    const originalName = `[${saved.source_ref.snapshot.snapshot_id.slice(0, 12)}] ${name}`;
    const basename = `[v${saved.revision}] ${name}`;
    const original = document({kind: 'source', ref: saved.source_ref, basename: originalName}, originalName);
    let candidate;
    try {
      candidate = document({kind: 'draft', receipt: saved, basename}, basename);
      // Validate both documents before displaying the comparison.
      await vscode.workspace.openTextDocument(original);
      await vscode.workspace.openTextDocument(candidate);
      await vscode.commands.executeCommand('vscode.diff', original, candidate,
        `${saved.title} · v${saved.revision} · ${saved.source_ref.snapshot.snapshot_id.slice(0, 12)}`, {preview: false});
    } catch (error) {
      documents.delete(original.authority);
      if (candidate) documents.delete(candidate.authority);
      throw error;
    }
    return [original, candidate];
  }
  function register(name, callback) {
    subscribe(vscode.commands.registerCommand(name, async (...args) => {
      try { return await callback(...args); }
      catch (error) { void vscode.window.showErrorMessage('Рентген: ' + error.message); throw error; }
    }));
  }
  register('rentgen.openSelection', openSelection);
  register('rentgen.refreshSources', refreshSources);
  register('rentgen.refreshDrafts', () => refreshDrafts());
  register('rentgen.moreSources', async () => { await loadSources(true); sourceEvents.fire(); });
  register('rentgen.moreDrafts', async () => { await loadDrafts(true); draftEvents.fire(); });
  register('rentgen.moreHistory', async token => { await loadHistory(token, true); draftEvents.fire(); });
  register('rentgen.searchSources', async () => {
    const value = await vscode.window.showInputBox({title: 'Найти модуль в текущем снимке', prompt: 'Часть пути. Пустая строка снимает фильтр.', value: query,
      validateInput: input => [...input].length > 256 || /[\p{Cc}\p{Cf}\p{Cs}]/u.test(input) ? 'До 256 символов без управляющих знаков' : undefined});
    if (value !== undefined) search(value);
  });
  register('rentgen.draftStatus', async () => {
    const choice = await vscode.window.showQuickPick([{label: 'Активные', status: 'active'}, {label: 'Архив', status: 'archived'}], {title: 'Показать черновики'});
    if (choice) refreshDrafts(choice.status);
  });
  subscribe({dispose() { selectionGeneration++; sourceHandles.clear(); draftHandles.clear(); documents.clear(); histories.clear(); sources.reset(); drafts.reset(); }});
  refreshDrafts(); sourceDescription();
  // Read-only automation API uses the same providers and minted command handles.
  return Object.freeze({refreshSources, refreshDrafts, search, sources: loadSources, drafts: loadDrafts, history: loadHistory,
    selectedSource(token) { const record = sourceHandles.get(token); if (record.kind !== 'source') throw new Error('UNKNOWN_VIEW_HANDLE'); return record.ref; },
    selectedDraft(token) { const record = draftHandles.get(token); if (!['draft','version'].includes(record.kind)) throw new Error('UNKNOWN_VIEW_HANDLE'); return record.receipt; },
    openDraft(receipt) { return openSelection(row('version', {receipt}, draftHandles).token); },
  });
}
module.exports = { createViews };
