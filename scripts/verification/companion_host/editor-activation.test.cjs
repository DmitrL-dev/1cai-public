'use strict';
// Constructed lifecycle controls only; no editor or persistence acceptance.
const test = require('node:test');
const assert = require('node:assert/strict');
const {start} = require('../editor_workbench/activation.cjs');

test('editor activation returns before the phase and quits only after its completion', async () => {
  let release, completed, running = false, settled = false, quitCount = 0;
  const phase = new Promise(resolve => {release = resolve;});
  const done = new Promise(resolve => {completed = resolve;});
  const result = start(async () => {running = true; await phase; settled = true;}, async () => {
    assert.equal(settled, true); quitCount++; completed();
  });
  assert.equal(result, undefined);
  await Promise.resolve();
  assert.equal(running, true); assert.equal(quitCount, 0);
  release(); await done;
  assert.equal(quitCount, 1);
});

test('a failed phase settles before normal quit and does not become activation acceptance', async () => {
  let completed, settled = false, quitCount = 0;
  const done = new Promise(resolve => {completed = resolve;});
  assert.equal(start(async () => {settled = true; throw new Error('private phase error');}, async () => {
    assert.equal(settled, true); quitCount++; completed();
  }), undefined);
  await done;
  assert.equal(quitCount, 1);
});

test('quit rejection stays contained for the owned process supervisor', async () => {
  let attempted = false;
  start(async () => {}, async () => {attempted = true; throw new Error('quit refused');});
  await new Promise(setImmediate);
  assert.equal(attempted, true);
});
