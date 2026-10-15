'use strict';
const {posix} = require('node:path');
const {isDeepStrictEqual} = require('node:util');
const {Handles} = require('./state.cjs');

function createMetadataView(vscode, client, views, context, {enabled = true, reason = '', trusted = () => true} = {}) {
  const handles = new Handles(2000), events = new vscode.EventEmitter(), childrenByGroup = new Map();
  let query = '', generation = 0, loaded = false, groups = [], loading = null, disposed = false, loadError = null;
  const subscribe = value => {context.subscriptions.push(value); return value;};
  const check = () => {if (disposed || !trusted()) throw new Error('TRUST_REQUIRED');};
  function invalidate() {generation++; handles.clear(); childrenByGroup.clear(); groups = []; loaded = false; loading = null; loadError = null;}
  function fail(error) {invalidate(); loadError = error; panel.message = 'Метаданные недоступны: ' + error.message; events.fire();}
  function current(selected, ticket) {return !disposed && trusted() && generation === ticket && isDeepStrictEqual(views.selectedSnapshot(), selected);}
  function row(kind, data) {const token = handles.add({kind, ...data}); return Object.freeze({kind, ...data, token});}
  function notice(result) {
    const incomplete = result.truncated || result.completeness !== 'supported_layer_inventory';
    panel.description = views.selectedSnapshot().snapshot_id.slice(0, 12) + (query ? ' · ' + query : '');
    panel.message = `Показано ${result.returned} из ${result.total_matches} совпадений.` +
      (incomplete ? ' Результат неполный: сузьте поиск и проверьте поддержанные слои.' : ' Проверены поддержанные слои снимка.') +
      ' Это поиск имён, синонимов и путей; семантический индекс не строится.';
  }
  async function roots() {
    check();
    if (loadError) return [];
    if (!enabled) {panel.message = 'Установленный Core не предоставляет проверенный контракт навигации метаданных.' + (reason ? ' ' + reason : ''); return [];}
    const selected = views.selectedSnapshot();
    if (!selected) {panel.message = 'Откройте сохранённый снимок проекта. ZIP-просмотр не заменяет снимок.'; return [];}
    if (loaded) return groups;
    if (loading) return loading;
    const ticket = generation, filter = query;
    const pending = Promise.resolve().then(() => client.metadataSearch(selected, {query:filter})).then(result => {
      check(); if (!current(selected, ticket)) return [];
      const byType = new Map();
      for (const object of result.objects) {
        if (!byType.has(object.type)) byType.set(object.type, []);
        byType.get(object.type).push(object);
      }
      groups = Object.freeze([...byType].sort(([a],[b]) => a.localeCompare(b)).map(([type, objects]) => row('metadata-type', {type, objects:Object.freeze(objects)})));
      loaded = true; notice(result); return groups;
    }).catch(error => {if (ticket === generation) fail(error); throw error;})
      .finally(() => {if (loading === pending) loading = null;});
    loading = pending; return pending;
  }
  async function children(token) {
    check();
    const selected = views.selectedSnapshot(), ticket = generation, record = handles.get(token);
    if (record.kind === 'metadata-type') {
      if (!childrenByGroup.has(token)) {
        const rows = Object.freeze(record.objects.map(object => row('metadata-object', {object})));
        // Handles freeze records, so materialized children live in this private map.
        childrenByGroup.set(token, rows);
      }
      return childrenByGroup.get(token);
    }
    if (record.kind !== 'metadata-object') throw new Error('UNKNOWN_VIEW_HANDLE');
    try {
      const result = await client.metadataObject(selected, record.object.source_ref);
      check(); if (!current(selected, ticket)) return [];
      // Register the very same verified SourceRefs with the existing source and
      // edit commands; display names can never select an executable or object.
      const rows = result.object.modules.items.map(item => views.registerSource(item.source_ref));
      if (result.object.modules.truncated) panel.message = 'Список модулей объекта неполный. Показаны первые ' + rows.length + ' из ' + result.object.modules.total + '.';
      return rows;
    } catch (error) {if (ticket === generation) fail(error); throw error;}
  }
  function treeItem(node) {
    check();
    const record = node.kind === 'source' ? {kind:'source', ref:views.selectedSource(node.token)} : handles.get(node.token);
    const expandable = record.kind !== 'source';
    const label = record.kind === 'metadata-type' ? record.type : record.kind === 'source' ?
      posix.basename(record.ref.relative_path) : record.object.name || posix.basename(record.object.source_ref.relative_path);
    const item = new vscode.TreeItem(label, expandable ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None);
    item.id = record.kind + ':' + node.token;
    item.contextValue = record.kind === 'source' ? 'rentgen.source' : record.kind;
    if (record.kind === 'source') {
      item.description = record.ref.relative_path;
      item.tooltip = `Снимок ${record.ref.snapshot.snapshot_id}\nSHA256 ${record.ref.raw_sha256}`;
      item.command = {command:'rentgen.openSelection', title:'Открыть сохранённый модуль', arguments:[node.token]};
      item.iconPath = new vscode.ThemeIcon('file-code');
    } else if (record.kind === 'metadata-object') {
      item.description = record.object.source_ref.layer_id + (record.object.synonym ? ' · ' + record.object.synonym : '');
      item.tooltip = record.object.source_ref.relative_path + '\nUUID наблюдался в исходнике и не подтверждён платформой.';
      item.iconPath = new vscode.ThemeIcon('symbol-class');
    } else {item.description = String(record.objects.length); item.iconPath = new vscode.ThemeIcon('symbol-namespace');}
    return item;
  }
  subscribe(events);
  const panel = subscribe(vscode.window.createTreeView('rentgen.metadata', {treeDataProvider:{
    onDidChangeTreeData:events.event, getTreeItem:treeItem,
    getChildren:node => !node ? roots() : node.kind === 'source' ? [] : children(node.token),
  }}));
  const refresh = async () => {check(); invalidate(); events.fire(); return roots();};
  async function search(value) {
    check();
    if (value === undefined) value = await vscode.window.showInputBox({title:'Найти объект в выбранном снимке',
      prompt:'Имя, синоним, тип или часть пути. До 100 объектов; сузьте неполный результат.', value:query});
    if (value === undefined) return null;
    if (typeof value !== 'string' || [...value].length > 256 || Buffer.byteLength(value, 'utf8') > 1024 || /[\p{Cc}\p{Cf}\p{Cs}]/u.test(value)) throw new Error('INVALID_SEARCH');
    query = value; return refresh();
  }
  for (const [name, fn] of [['rentgen.refreshMetadata', refresh], ['rentgen.searchMetadata', search]]) {
    subscribe(vscode.commands.registerCommand(name, async (...args) => {
      try {return await fn(...args);} catch (error) {void vscode.window.showErrorMessage('Рентген: ' + error.message); throw error;}
    }));
  }
  subscribe(views.onDidChangeContext(() => {invalidate(); events.fire();}));
  subscribe({dispose() {disposed = true; invalidate();}});
  return Object.freeze({roots, children, search, refresh});
}
module.exports = {createMetadataView};
