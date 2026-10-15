'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const {createEditService} = require('../lib/edit.cjs');
const {createRepairService} = require('../lib/repair.cjs');
const {createPlatformService} = require('../lib/platform.cjs');
const {createBslService} = require('../lib/bsl.cjs');
const {createTestService} = require('../lib/testing.cjs');

const config = {schema:1, core_version:'0.1.0.dev19',
  project_id:'00000000-0000-4000-8000-000000000001',
  python:'C:\\installed\\python.exe', registry:'C:\\registry.sqlite3'};
const capabilities = [
  ['edit', createEditService, '0.1.0.dev7', '0.1.0.dev6', /EDIT_REQUIRES_DEV7_OR_DEV8/],
  ['repair', createRepairService, '0.1.0.dev7', '0.1.0.dev6', /REPAIR_REQUIRES_DEV7_OR_DEV8/],
  ['platform', createPlatformService, '0.1.0.dev8', '0.1.0.dev7', /PLATFORM_REQUIRES_DEV8/],
  ['BSL', createBslService, '0.1.0.dev8', '0.1.0.dev7', /BSL_REQUIRES_DEV8/],
  ['tests', createTestService, '0.1.0.dev8', '0.1.0.dev7', /TEST_REQUIRES_DEV8/],
];

for (const [name, factory, minimum, earlier, refusal] of capabilities) {
  test(`${name}: current candidate and original minimum remain admitted; dev18 and unknown versions are refused`, async t => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'rentgen-version-admission-'));
    t.after(() => fs.rm(root, {recursive:true, force:true}));
    const unexpected = () => {throw new Error('UNEXPECTED_CORE_EXECUTION');};
    let reads = 0;
    const client = {async head() {reads++; return {};}};
    for (const core_version of [minimum, '0.1.0.dev17', '0.1.0.dev19', earlier, '0.1.0.dev18', '0.1.0.dev999']) {
      const makeService = () => {
        const service = factory({root, extensionRoot:root, config:{...config, core_version}, client,
          runnerFactory:unexpected});
        t.after(() => service.dispose?.());
        return service;
      };
      if ([minimum, '0.1.0.dev17', '0.1.0.dev19'].includes(core_version)) {
        assert.deepEqual(await makeService().list(), []);
      } else {
        const before = reads;
        // Admission must fail before either input validation or execution.
        await assert.rejects(async () => makeService().start(),
          new RegExp(refusal.source + '|INVALID_EDITOR_PROFILE'));
        assert.equal(reads, before);
      }
    }
    assert.deepEqual(await fs.readdir(root), []);
  });
}
