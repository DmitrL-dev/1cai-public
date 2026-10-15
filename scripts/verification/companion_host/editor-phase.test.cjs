'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {checkpoint, failure} = require('../editor_workbench/phase.cjs');

test('editor diagnostic checkpoint is a closed static identifier', () => {
  const report = {};
  checkpoint(report, 'restart.selection');
  assert.equal(report.checkpoint, 'restart.selection');
  assert.throws(() => checkpoint(report, '/private/source.bsl'), /INVALID_EDITOR_CHECKPOINT/);
  assert.equal(report.checkpoint, 'restart.selection');
});
test('editor assertion diagnostics retain scalar differences without exception text', () => {
  const privateText = '/private/source.bsl: confidential fixture';
  let error;
  try {assert.equal(privateText, 'expected');} catch (caught) {error = caught;}
  const reduced = failure(error);
  assert.equal(reduced.category, 'assertion');
  assert.equal(reduced.operator, 'strictEqual');
  assert.equal(reduced.actual.sha256, createHash('sha256').update(privateText).digest('hex'));
  assert.equal(JSON.stringify(reduced).includes(privateText), false);
  assert.equal(JSON.stringify(reduced).includes('message'), false);
  assert.equal(JSON.stringify(reduced).includes('stack'), false);
});
test('editor object assertions disclose no object fields or source bytes', () => {
  let error;
  try {assert.deepEqual({privateSource: 'secret'}, {privateSource: 'different'});} catch (caught) {error = caught;}
  const reduced = failure(error);
  assert.deepEqual(reduced.actual, {type: 'object'});
  assert.deepEqual(reduced.expected, {type: 'object'});
  assert.equal(JSON.stringify(reduced).includes('privateSource'), false);
});
test('editor error codes and operators cannot carry arbitrary strings', () => {
  const reduced = failure(Object.assign(new Error('private exception'), {code: '/private/code'}));
  assert.equal(reduced.code, null);
  assert.equal(reduced.category, 'error');
  assert.equal(JSON.stringify(reduced).includes('private'), false);
});
test('editor diagnostics bound large string hashing and preserve primitive shape', () => {
  let error;
  try {assert.equal('x'.repeat(1048577), false);} catch (caught) {error = caught;}
  const reduced = failure(error);
  assert.equal(reduced.actual.sha256, null);
  assert.equal(reduced.actual.size_bytes, 1048577);
  assert.deepEqual(reduced.expected, {type: 'boolean', value: false});
  assert.ok(JSON.stringify(reduced).length < 512);
});
