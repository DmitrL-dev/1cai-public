'use strict';
const { posix } = require('node:path');
const {createHash} = require('node:crypto');
const {isDeepStrictEqual} = require('node:util');
const { Page, Handles } = require('./state.cjs');
const {sourceRef} = require('./core.cjs');

function createViews(vscode, client, context, {workbench = null, trusted = () => true, projectId = null} = {}) {
  const sources = new Page(), drafts = new Page(1000);
  const sourceHandles = new Handles(), draftHandles = new Handles();
  const documents = new Handles(128), histories = new Map(), draftDocuments = new Map();
  const sourceEvents = new vscode.EventEmitter(), draftEvents = new vscode.EventEmitter(), contextEvents = new vscode.EventEmitter();
  let selected = null, query = '', status = 'active', selectionGeneration = 0, contextGeneration = 0, selection = null, disposed = false;
  const check = () => {if (disposed || !trusted()) throw new Error('TRUST_REQUIRED');};
  const subscribe = item => { context.subscriptions.push(item); return item; };
  subscribe(sourceEvents); subscribe(draftEvents); subscribe(contextEvents);
  const persist = () => workbench ? workbench.save({snapshot:selected, query, selection}) : Promise.resolve();
  const sameSnapshot = (left, right) => isDeepStrictEqual(left, right);
  function changed() {contextGeneration++; contextEvents.fire();}
  function unavailable(error) {
    selected = null; selection = null; sourceHandles.clear(); draftHandles.clear();
    sources.reset(); drafts.reset(); histories.clear(); sourceDescription();
    sourceView.message = 'Рабочий контекст недоступен: ' + error.message + '. Повторите открытие или явно выберите последний снимок.';
    sourceEvents.fire(); draftEvents.fire(); changed();
  }
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
    check();
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
    check();
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
    check();
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
    draftView.message = 'Черновики сравниваются с собственным исходным снимком. Выбор черновика не меняет снимок дерева.';
  }
  async function refreshSources() {
    check();
    const generation = ++selectionGeneration;
    let head;
    try {head = await client.head(); check();}
    catch (error) {if (generation === selectionGeneration) unavailable(error); throw error;}
    if (generation !== selectionGeneration) return;
    selected = head.snapshot; selection = null;
    sourceHandles.clear(); sources.reset(); sourceDescription(); sourceEvents.fire(); changed();
    await persist();
  }
  async function selectSnapshot(value) {
    check();
    if (value === undefined) {
      const id = await vscode.window.showInputBox({title:'Открыть сохранённый снимок',
        prompt:'Полный SHA-256 снимка текущего проекта. Последний снимок выбирается отдельной командой обновления.'});
      if (id === undefined) return null;
      value = {project_id:projectId || selected?.project_id, snapshot_id:id, manifest_hash:id};
    }
    const generation = ++selectionGeneration;
    // Own the requested identity before crossing the Core await. The caller's
    // object must not change which snapshot the verified response selects.
    const target = Object.freeze({project_id:value?.project_id, snapshot_id:value?.snapshot_id, manifest_hash:value?.manifest_hash});
    // Capability validation is delegated to Core before the UI adopts identity.
    await client.sources(target, {query}); check();
    if (generation !== selectionGeneration) return null;
    selected = target;
    selection = null; sourceHandles.clear(); sources.reset(); sourceDescription(); sourceEvents.fire(); changed();
    await persist(); return selected;
  }
  function search(value) {
    check();
    if (typeof value !== 'string' || [...value].length > 256 || Buffer.byteLength(value, 'utf8') > 1024 || /[\p{Cc}\p{Cf}\p{Cs}]/u.test(value)) throw new Error('INVALID_SEARCH');
    query = value; sourceHandles.clear(); sources.reset(); sourceDescription(); sourceEvents.fire(); changed();
    return persist();
  }
  function refreshDrafts(value = status) {
    if (!['active', 'archived'].includes(value)) throw new Error('INVALID_DRAFT_STATUS');
    status = value; draftHandles.clear(); drafts.reset(); histories.clear();
    draftView.description = status === 'active' ? 'Активные' : 'Архив'; draftEvents.fire(); changed();
  }
  function document(record, basename) {
    const token = documents.add(record);
    return vscode.Uri.from({scheme: 'rentgen-view', authority: token, path: '/' + basename});
  }
  function draftUri(receipt, basename) {
    const key = JSON.stringify(receipt);
    if (draftDocuments.has(key)) {
      const uri = draftDocuments.get(key);
      try {documents.get(uri.authority); return uri;}
      catch (error) {if (error.message !== 'UNKNOWN_VIEW_HANDLE') throw error; draftDocuments.delete(key);}
    }
    const uri = document({kind:'draft', receipt, basename}, basename);
    draftDocuments.set(key, uri); return uri;
  }
  subscribe(vscode.workspace.registerTextDocumentContentProvider('rentgen-view', {
    async provideTextDocumentContent(uri) {
      check();
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
    if (doc.uri.scheme === 'rentgen-view') {
      documents.delete(doc.uri.authority);
      for (const [key, uri] of draftDocuments) if (uri.authority === doc.uri.authority) draftDocuments.delete(key);
    }
  }));
  async function openSelection(token, isCurrent = () => true) {
    check();
    let record;
    try { record = sourceHandles.get(token); } catch { record = draftHandles.get(token); }
    if (!isCurrent()) return null;
    changed();
    const ticket = contextGeneration;
    const current = (...args) => ticket === contextGeneration && isCurrent(...args);
    if (record.kind === 'source') {
      const basename = `[${record.ref.snapshot.snapshot_id.slice(0, 12)}] ${posix.basename(record.ref.relative_path)}`;
      const uri = document({...record, basename}, basename);
      try {
        const document = await vscode.workspace.openTextDocument(uri); check();
        if (!current()) {documents.delete(uri.authority); return null;}
        await vscode.window.showTextDocument(document, {preview: false}); check();
        if (current([uri]) && sameSnapshot(selected, record.ref.snapshot)) {
          selection = {kind:'source', ref:record.ref}; await persist();
        }
      }
      catch (error) { documents.delete(uri.authority); throw error; }
      return [uri];
    }
    if (!['draft', 'version'].includes(record.kind)) throw new Error('UNKNOWN_VIEW_HANDLE');
    if (!current()) return null;
    const saved = record.receipt, name = posix.basename(saved.source_ref.relative_path);
    const originalName = `[${saved.source_ref.snapshot.snapshot_id.slice(0, 12)}] ${name}`;
    const basename = `[v${saved.revision}] ${name}`;
    const original = document({kind: 'source', ref: saved.source_ref, basename: originalName}, originalName);
    let candidate, candidateOwned = false, displayed = false;
    try {
      const known = draftDocuments.get(JSON.stringify(saved));
      candidateOwned = !known || !documents.records.has(known.authority);
      candidate = draftUri(saved, basename);
      // Validate both documents before displaying the comparison.
      if (!current()) return null;
      await vscode.workspace.openTextDocument(original);
      check();
      if (!current()) return null;
      await vscode.workspace.openTextDocument(candidate);
      check();
      if (!current()) return null;
      await vscode.commands.executeCommand('vscode.diff', original, candidate,
        `${saved.title} · v${saved.revision} · ${saved.source_ref.snapshot.snapshot_id.slice(0, 12)}`, {preview: false});
      // A submitted display cannot be revoked when the caller later changes.
      displayed = true;
      check();
      if (current([original, candidate]) && selected) {
        selection = {kind:'draft', draft_id:saved.draft_id, revision:saved.revision}; await persist();
        draftView.message = `Открыта версия ${saved.revision} · исходник ${saved.source_ref.snapshot.snapshot_id.slice(0, 12)}. Дерево: ${selected.snapshot_id.slice(0, 12)}.`;
      }
    } finally {
      if (!displayed) {
        documents.delete(original.authority);
        if (candidate && candidateOwned) {
          documents.delete(candidate.authority);
          const key = JSON.stringify(saved);
          if (draftDocuments.get(key)?.authority === candidate.authority) draftDocuments.delete(key);
        }
      }
    }
    return [original, candidate];
  }
  function register(name, callback) {
    subscribe(vscode.commands.registerCommand(name, async (...args) => {
      try { return await callback(...args); }
      catch (error) { void vscode.window.showErrorMessage('Рентген: ' + error.message); throw error; }
    }));
  }
  register('rentgen.openSelection', token => openSelection(token));
  register('rentgen.refreshSources', refreshSources);
  register('rentgen.selectSnapshot', selectSnapshot);
  register('rentgen.refreshDrafts', () => refreshDrafts());
  register('rentgen.moreSources', async () => { await loadSources(true); sourceEvents.fire(); });
  register('rentgen.moreDrafts', async () => { await loadDrafts(true); draftEvents.fire(); });
  register('rentgen.moreHistory', async token => { await loadHistory(token, true); draftEvents.fire(); });
  register('rentgen.searchSources', async () => {
    const value = await vscode.window.showInputBox({title: 'Найти модуль в текущем снимке', prompt: 'Часть пути. Пустая строка снимает фильтр.', value: query,
      validateInput: input => [...input].length > 256 || /[\p{Cc}\p{Cf}\p{Cs}]/u.test(input) ? 'До 256 символов без управляющих знаков' : undefined});
    if (value !== undefined) await search(value);
  });
  register('rentgen.draftStatus', async () => {
    const choice = await vscode.window.showQuickPick([{label: 'Активные', status: 'active'}, {label: 'Архив', status: 'archived'}], {title: 'Показать черновики'});
    if (choice) refreshDrafts(choice.status);
  });
  async function initialize() {
    check();
    const generation = ++selectionGeneration;
    try {
      const saved = workbench ? await workbench.load() : null; check();
      if (generation !== selectionGeneration) return;
      if (saved === null) return refreshSources();
      // This request reauthorizes and verifies the saved snapshot. Never replace
      // a missing/forbidden historical snapshot with the current head.
      if (saved.snapshot) await client.sources(saved.snapshot, {query:saved.query});
      else await client.head();
      check(); if (generation !== selectionGeneration) return;
      selected = saved.snapshot; query = saved.query; selection = saved.selection;
      sourceHandles.clear(); sources.reset(); sourceDescription(); sourceEvents.fire(); changed();
      const current = () => generation === selectionGeneration && trusted() && !disposed && !vscode.window.activeTextEditor?.document?.isDirty;
      if (selection?.kind === 'source') {
        const token = row('source', {ref:selection.ref}, sourceHandles).token;
        await openSelection(token, current);
      } else if (selection?.kind === 'draft') {
        const savedDraft = await client.draft(selection.draft_id, selection.revision); check();
        if (current()) await api.openDraft(savedDraft.receipt, current);
      }
    } catch (error) {
      if (generation === selectionGeneration) unavailable(error);
      throw error;
    }
  }
  register('rentgen.resetWorkbench', async () => {
    check(); if (workbench) await workbench.clear();
    await refreshSources(); await vscode.commands.executeCommand('setContext','rentgen.ready',true);
    return selected;
  });
  subscribe({dispose() { disposed = true; selectionGeneration++; sourceHandles.clear(); draftHandles.clear(); documents.clear(); draftDocuments.clear(); histories.clear(); sources.reset(); drafts.reset(); }});
  refreshDrafts(); sourceDescription();
  // Read-only automation API uses the same providers and minted command handles.
  const api = Object.freeze({initialize, refreshSources, selectSnapshot, refreshDrafts, search, sources: loadSources, drafts: loadDrafts, history: loadHistory,
    selectedSnapshot() {check(); return selected ? Object.freeze({...selected}) : null;},
    contextVersion() {check(); return contextGeneration;},
    workbenchSnapshot() {
      check();
      const savedSelection = !selection ? null : selection.kind === 'source' ?
        Object.freeze({kind:'source', ref:sourceRef(selection.ref, selected.project_id)}) :
        Object.freeze({kind:'draft', draft_id:selection.draft_id, revision:selection.revision});
      return Object.freeze({snapshot:api.selectedSnapshot(), query, selection:savedSelection});
    },
    onDidChangeContext:contextEvents.event,
    registerSource(ref) {
      check(); if (!selected) throw new Error('SNAPSHOT_REQUIRED');
      ref = sourceRef(ref, selected.project_id);
      if (!sameSnapshot(selected, ref.snapshot)) throw new Error('SOURCE_REF_MISMATCH');
      return row('source', {ref}, sourceHandles);
    },
    async openSourceRef(ref) {const value = api.registerSource(ref); return openSelection(value.token);},
    async draftDocument(receipt) {
      check();
      const result = await client.draft(receipt.draft_id, receipt.revision); check();
      if (!isDeepStrictEqual(result.receipt, receipt)) throw new Error('DRAFT_REVISION_MISMATCH');
      const basename = `[v${receipt.revision}] ${posix.basename(receipt.source_ref.relative_path)}`;
      const uri = draftUri(receipt, basename);
      const bytes = Buffer.from(result.text, 'utf8');
      return {uri, text:result.text, receipt:result.receipt,
        rawSha256:createHash('sha256').update(bytes).digest('hex'), sizeBytes:bytes.length};
    },
    selectedSource(token) { const record = sourceHandles.get(token); if (record.kind !== 'source') throw new Error('UNKNOWN_VIEW_HANDLE'); return record.ref; },
    selectedDraft(token) { const record = draftHandles.get(token); if (!['draft','version'].includes(record.kind)) throw new Error('UNKNOWN_VIEW_HANDLE'); return record.receipt; },
    async openDraft(receipt, isCurrent = () => true) {
      const token = row('version', {receipt}, draftHandles).token;
      try { return await openSelection(token, isCurrent); }
      finally { draftHandles.delete(token); }
    },
  });
  return api;
}
module.exports = { createViews };
