'use strict';
const test = require('node:test'), assert = require('node:assert/strict'), vm = require('node:vm');
const path = require('node:path'), {readFileSync} = require('node:fs');
const source = readFileSync(path.join(__dirname, '../extension.cjs'), 'utf8');
function fixture(mode, trusted = true) {
  const calls = [], env = {RENTGEN_EDITOR_PROFILE:'C:\\constructed-profile', RENTGEN_EDITOR_OWNER:'{"accepted":true,"pid":42}'};
  if (mode !== undefined) env.RENTGEN_D10_OWNER_MODE = mode;
  const editor = {workspace:{isTrusted:trusted}, commands:{async executeCommand(name, key, value) {calls.push(['context', key, value]);}}, window:{showErrorMessage(){calls.push(['message']);}}};
  const context = vm.createContext({exports:{}, process:{env,platform:'win32'}, Buffer, TextDecoder, require(name) {
    if (name === 'vscode') return editor;
    if (name === 'node:fs/promises') return {async open(){calls.push(['profile-IO']); throw new Error('PROFILE_IO_REACHED');}};
    if (name === 'node:path') return path.win32;
    if (name === './lib/owner-bootstrap.cjs') return require('../lib/owner-bootstrap.cjs');
    if (name === './lib/process.cjs') return {createRunner(){calls.push(['runner']); throw new Error('LOCAL_RUNNER_REACHED');}};
    if (name === './lib/core.cjs') return {profileConfig(value){return value;}, createClient(){calls.push(['Core']); throw new Error('CORE_REACHED');}};
    // No view/service is allowed to start in these refused real activation paths.
    if (name.startsWith('./lib/')) return {};
    throw new Error('Unexpected import: '+name);
  }});
  vm.runInContext(source, context);
  return {env, calls, activate:() => context.exports.activate({subscriptions:[],extensionPath:'C:\\constructed-extension'})};
}
test('cold owner selection denies automatic activation before profile, Core or local runner work', async () => {
  const f = fixture('cold-ready'); const result = await f.activate();
  assert.equal(result.ready, false); assert.equal(result.error, 'OWNER_ENDPOINT_UNAVAILABLE');
  assert.equal(f.calls.filter(([kind]) => ['profile-IO','runner','Core'].includes(kind)).length, 0);
  for (const field of ['runtime_verified','kernel_authority','model_loading_allowed','native_allowed']) assert.equal(result.owner[field], false);
});
for (const mode of ['', 'legacy', '{"accepted":true}']) test('invalid explicit owner mode '+JSON.stringify(mode)+' never falls back', async () => {
  const f = fixture(mode); const result = await f.activate();
  assert.equal(result.ready, false); assert.equal(result.error, 'OWNER_MODE_INVALID');
  assert.equal(f.calls.filter(([kind]) => ['profile-IO','runner','Core'].includes(kind)).length, 0);
});
test('changing the captured owner marker cannot downgrade selected cold activation to legacy', async () => {
  const f = fixture('cold-ready'); delete f.env.RENTGEN_D10_OWNER_MODE;
  const result = await f.activate(); assert.equal(result.error, 'OWNER_ENDPOINT_UNAVAILABLE');
  assert.equal(f.calls.filter(([kind]) => ['profile-IO','runner','Core'].includes(kind)).length, 0);
});
test('absent owner mode preserves the existing trusted-profile route without claiming owner authority', async () => {
  const f = fixture(undefined); const result = await f.activate();
  assert.equal(result.error, 'PROFILE_IO_REACHED'); assert.equal(result.owner, undefined);
  assert.equal(f.calls.filter(([kind]) => kind === 'profile-IO').length, 1);
});
test('the existing trust requirement remains effective when owner mode is absent', async () => {
  const f = fixture(undefined, false); const result = await f.activate();
  assert.equal(result.error, 'TRUST_REQUIRED'); assert.equal(f.calls.filter(([kind]) => kind === 'profile-IO').length, 0);
});
