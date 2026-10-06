'use strict';
// Contract fixtures only. These do not qualify an installed Windows editor or 1C.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const {readFileSync} = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const core = require('../lib/core.cjs');
const {createEditService} = require('../lib/edit.cjs');
const {createBslService} = require('../lib/bsl.cjs');
const {createTestService} = require('../lib/testing.cjs');
const {createPlatformService} = require('../lib/platform.cjs');
const {createRepairService} = require('../lib/repair.cjs');
const project = '00000000-0000-4000-8000-000000000001';
const config = {schema:1, python:'C:\\installed\\python.exe', registry:'C:\\registry.sqlite3', project_id:project};
const versions = Array.from({length:15}, (_, index) => `0.1.0.dev${index + 4}`);

for (const core_version of versions) {
  test(`${core_version} retains exact legacy profile admission`, () => {
    assert.equal(core.profileConfig({...config, core_version}).core_version, core_version);
  });
}

for (const core_version of ['0.1.0.dev3', '0.1.0.dev19', '0.1.0.dev999', '0.1.0.dev18+local', '0.1.0', '*']) {
  test(`${core_version} is refused before service or process creation`, () => {
    const options = {root:'unused', extensionRoot:'unused', config:{...config, core_version}, client:{}};
    const execute = () => {throw new Error('Unexpected process');};
    assert.throws(() => core.createClient(options.config, {execute}), /INVALID_EDITOR_PROFILE/);
    for (const factory of [createEditService, createBslService, createTestService, createPlatformService, createRepairService]) {
      assert.throws(() => factory(options), /INVALID_EDITOR_PROFILE/);
    }
  });
}

for (const dev of Array.from({length:12}, (_, index) => index + 7)) {
  test(`dev${dev} service availability retains reviewed feature floors`, async t => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'rentgen-compatibility-'));
    t.after(() => fs.rm(root, {recursive:true, force:true}));
    const selected = {...config, core_version:`0.1.0.dev${dev}`};
    let reads = 0;
    const client = {async head(){reads++; return {};}};
    const edit = createEditService({root, config:selected, client});
    t.after(() => edit.dispose());
    assert.deepEqual(await edit.list(), []);
    for (const [factory, refusal] of [[createBslService, /BSL_REQUIRES_DEV8/], [createTestService, /TEST_REQUIRES_DEV8/], [createPlatformService, /PLATFORM_REQUIRES_DEV8/]]) {
      const service = factory({root, config:selected, client});
      t.after(() => service.dispose());
      if (dev === 7) await assert.rejects(service.list(), refusal);
      else assert.deepEqual(await service.list(), []);
    }
    assert.equal(reads, dev === 7 ? 0 : 2);
    assert.deepEqual(await fs.readdir(root), []);
  });
}

test('dev18 does not loosen profile schema, path or workspace trust checks', async () => {
  const selected = {...config, core_version:'0.1.0.dev18'};
  for (const patch of [{schema:2}, {python:'/usr/bin/python'}, {registry:'relative'}, {context_tokens:65536}]) {
    assert.throws(() => core.profileConfig({...selected, ...patch}), /INVALID_EDITOR_PROFILE/);
  }
  const execute = () => {throw new Error('Unexpected process');};
  const client = core.createClient(selected, {execute, trusted:() => false});
  await assert.rejects(client.head(), /TRUST_REQUIRED/);
});

function activation(core_version, platform = 'win32') {
  const contexts = new Map();
  const bytes = Buffer.from(JSON.stringify({...config, core_version}));
  let reads = 0, executions = 0;
  const vscode = {workspace:{isTrusted:true}, commands:{async executeCommand(_, name, value){contexts.set(name, value);}}, window:{showErrorMessage(){}}};
  const sandbox = vm.createContext({exports:{}, Buffer, TextDecoder, process:{platform, env:{RENTGEN_EDITOR_PROFILE:'C:\\profile'}}, require(name) {
    if (name === 'vscode') return vscode;
    if (name === 'node:path') return path.win32;
    if (name === 'node:fs/promises') return {async open(){reads++; return {
      async stat(){return {size:bytes.length};}, async read(target){bytes.copy(target); return {bytesRead:bytes.length};}, async close(){}
    };}};
    if (name === './lib/core.cjs') return core;
    if (name === './lib/process.cjs') return {createRunner(){return {dispose(){}, execute(){executions++; throw new Error('Unexpected process');}};}};
    if (name === './lib/views.cjs') return {createViews(){return {async refreshSources(){}};}};
    const ui = {'repair':'createRepairUI', 'edit':'createEditUI', 'bsl':'createBslUI', 'tests':'createTestsUI', 'platform':'createPlatformUI'};
    const match = name.match(/^\.\/lib\/(.*)-ui\.cjs$/);
    if (match && ui[match[1]]) return {[ui[match[1]]](){return {runs:[], sessions:[]};}};
    if (name.startsWith('./lib/')) return require('../' + name.slice(2));
    throw new Error('Unexpected import ' + name);
  }});
  vm.runInContext(readFileSync(path.join(__dirname, '../extension.cjs'), 'utf8'), sandbox);
  return {contexts, reads:() => reads, executions:() => executions, run:() => sandbox.exports.activate({subscriptions:[], extensionPath:'C:\\extension'})};
}

for (const [version, repair, native] of [['0.1.0.dev4', false, false], ['0.1.0.dev7', true, false], ['0.1.0.dev8', true, true], ['0.1.0.dev17', true, true], ['0.1.0.dev18', true, true]]) {
  test(`${version} activation retains repair/native command gates`, async () => {
    const f = activation(version);
    assert.equal((await f.run()).ready, true);
    for (const key of ['repairAvailable', 'editAvailable']) assert.equal(f.contexts.get('rentgen.' + key), repair);
    for (const key of ['platformAvailable', 'bslAvailable', 'testsAvailable']) assert.equal(f.contexts.get('rentgen.' + key), native);
    assert.equal(f.executions(), 0);
  });
}

test('unknown future activation remains unavailable', async () => {
  const f = activation('0.1.0.dev19');
  assert.equal((await f.run()).error, 'INVALID_EDITOR_PROFILE');
  assert.equal(f.contexts.get('rentgen.ready'), false);
  assert.equal(f.executions(), 0);
});

test('dev18 activation keeps the Windows-only editor boundary', async () => {
  const f = activation('0.1.0.dev18', 'linux');
  assert.equal((await f.run()).error, 'WINDOWS_PROFILE_REQUIRED');
  assert.equal(f.reads(), 0);
  assert.equal(f.executions(), 0);
});
