'use strict';
// Real service/CLI integration. No editor API, OS gate, principal, or store mocks.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {randomUUID} = require('node:crypto');
const input = JSON.parse(require('node:fs').readFileSync(process.env.RENTGEN_DRAFT_TEST_INPUT, 'utf8'));
const lib = path.join(input.source, 'integrations/vscode-rentgen/lib');
const {createRunner} = require(path.join(lib, 'process.cjs'));
const {createClient} = require(path.join(lib, 'core.cjs'));
const {createEditService} = require(path.join(lib, 'edit.cjs'));

test('real draft store preserves receipts and rejects stale cross-client edits', {timeout: 120000}, async t => {
  assert.equal(process.platform, 'win32', 'A skipped or emulated run cannot satisfy this gate');
  const root = input.fixture_root;
  assert.ok(root && path.isAbsolute(root) && (await fs.stat(root)).isDirectory());
  const runner = createRunner({timeout: 20000});
  const pending = new Set();
  async function run(command, args) {
    const task = runner.execute(command, args);
    pending.add(task);
    try { return await task; } finally { pending.delete(task); }
  }
  t.after(async () => {
    runner.dispose();
    await Promise.allSettled([...pending]);
    await fs.rm(root, {recursive: true, force: true, maxRetries: 5, retryDelay: 100});
  });
  const setup = await run(input.python, ['-I', path.join(__dirname, 'verify.py'), 'fixture',
    input.manifest, root, input.scanner]);
  assert.equal(setup.code, 0, setup.stdout.toString('utf8'));
  const fixture = JSON.parse(setup.stdout.toString('utf8'));
  const {config, ref} = fixture;
  const original = Buffer.from(fixture.original_base64, 'base64');
  const secondBytes = Buffer.from(original.toString('utf8').replace('Возврат 1;', 'Возврат 2;'));
  const thirdBytes = Buffer.from(original.toString('utf8').replace('Возврат 1;', 'Возврат 3;'));
  const editsFile = path.join(root, 'exact-edits.json');
  await fs.writeFile(editsFile, JSON.stringify([{old_text: 'Возврат 1;\r\n', new_text: 'Возврат 2;\r\n'}]));
  const editOperation = randomUUID();
  let firstReceipt, secondReceipt, editArgs, dropReply = true, saveCalls = 0;

  async function cli(command, args) {
    const result = await run(config.python, ['-I', '-m', 'rentgen_core', command,
      '--registry', config.registry, '--project', config.project_id, ...args]);
    const envelope = JSON.parse(result.stdout.toString('utf8'));
    assert.equal(result.code, 0, JSON.stringify(envelope));
    assert.ok(Object.hasOwn(envelope, 'result'));
    return envelope.result;
  }
  async function execute(command, args) {
    if (args[3] === 'draft-save') saveCalls++;
    const result = await run(command, args);
    if (dropReply && args[3] === 'draft-save' && result.code === 0) {
      dropReply = false;
      firstReceipt = JSON.parse(result.stdout.toString('utf8')).result;
      assert.equal(firstReceipt.revision, 1);
      editArgs = ['--snapshot', ref.snapshot.snapshot_id, '--draft-id', firstReceipt.draft_id,
        '--expected-revision', '1', '--edits-json', editsFile, '--operation-id', editOperation];
      secondReceipt = await cli('draft-edit', editArgs);
      assert.equal(secondReceipt.revision, 2);
      // Inject only a lost acknowledgement, after the actual save and CLI v2.
      throw new Error('CLI_TIMEOUT');
    }
    return result;
  }

  const client = createClient(config, {execute});
  t.after(() => client.dispose());
  const serviceRoot = path.join(root, 'sessions');
  let service = createEditService({root: serviceRoot, config, client});
  const firstSession = await service.start(ref, '--help');
  assert.deepEqual((await client.drafts()).items, []);
  assert.deepEqual(await fs.readFile(firstSession.file), original);
  const saved = await service.save(firstSession.id);
  assert.equal(saved.status, 'saved');
  assert.deepEqual(saved.receipt, firstReceipt);
  assert.deepEqual(await client.receipt(firstReceipt.operation_id), firstReceipt);
  assert.deepEqual((await client.history(firstReceipt.draft_id)).items, [secondReceipt, firstReceipt]);

  service.dispose();
  service = createEditService({root: serviceRoot, config, client});
  assert.deepEqual((await service.inspect(firstSession.id)).receipt, firstReceipt);
  const staleBytes = Buffer.from(original.toString('utf8').replace('Возврат 1;', 'Возврат 99;'));
  await fs.writeFile(firstSession.file, staleBytes);
  const rejected = await service.save(firstSession.id);
  assert.equal(rejected.status, 'unresolved');
  assert.equal(rejected.error, 'DRAFT_CONFLICT');
  assert.ok(rejected.operation_id);
  assert.equal(await client.receipt(rejected.operation_id), null);
  const callsBeforeRepeat = saveCalls;
  const repeated = await service.save(firstSession.id);
  assert.equal(repeated.status, 'unresolved');
  assert.equal(repeated.operation_id, rejected.operation_id);
  assert.equal(saveCalls, callsBeforeRepeat);
  assert.deepEqual(await fs.readFile(firstSession.file), staleBytes);
  assert.deepEqual((await client.history(firstReceipt.draft_id)).items, [secondReceipt, firstReceipt]);

  const currentSession = await service.open(secondReceipt);
  assert.deepEqual(await fs.readFile(currentSession.file), secondBytes);
  await fs.writeFile(currentSession.file, thirdBytes);
  const third = await service.save(currentSession.id);
  assert.equal(third.status, 'saved');
  assert.equal(third.receipt.revision, 3);
  assert.deepEqual(await cli('draft-edit', editArgs), secondReceipt);
  assert.deepEqual((await client.history(firstReceipt.draft_id)).items, [third.receipt, secondReceipt, firstReceipt]);
  for (const [revision, bytes] of [[1, original], [2, secondBytes], [3, thirdBytes]]) {
    const stored = await client.proposal(firstReceipt.draft_id, revision);
    assert.deepEqual(stored.receipt.source_ref, ref);
    assert.deepEqual(Buffer.from(stored.proposal.replacement.base64, 'base64'), bytes);
    assert.equal(stored.proposal.policy.bom, true);
    assert.equal(stored.proposal.policy.newline, 'crlf');
  }
  assert.deepEqual(await fs.readFile(fixture.module), original);
  assert.equal(saveCalls, 3);
  service.dispose();
  const evidence = {accepted: true, revisions: [1, 2, 3], draft_save_calls: saveCalls,
    bound_packages: fixture.bound_packages, python_version: fixture.python_version,
    scanner_sha256: fixture.scanner_sha256, editor_gui: 'NOT_RUN',
    transport: 'actual Companion runner and isolated Python CLI processes',
    injection: 'one lost acknowledgement after a real commit'};
  await fs.writeFile(path.join(input.output, 'scenario.json'), JSON.stringify(evidence, null, 2) + '\n');
  t.diagnostic(JSON.stringify(evidence));
});
