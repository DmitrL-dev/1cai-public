'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { Page, Handles } = require('../lib/state.cjs');

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
