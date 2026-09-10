'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { createRunner } = require('../lib/process.cjs');

test('owned CLI process gets literal arguments; failures and output remain bounded', async () => {
  const runner = createRunner({timeout: 5000, maxOutput: 1024});
  try {
    const value = "Кириллица ' $(not-code)";
    const result = await runner.execute(process.execPath, ['-e', 'process.stdout.write(process.argv[1])', value]);
    assert.equal(result.code, 0); assert.equal(result.stdout.toString('utf8'), value);
    await assert.rejects(runner.execute(process.execPath, ['-e', 'process.stdout.write("x".repeat(100000)); setInterval(()=>{},1000)']), /CLI_OUTPUT_LIMIT/);
    await assert.rejects(runner.execute('C:\\rentgen-missing-test-executable.exe', []), /CLI_START_FAILED/);
  } finally { runner.dispose(); }
});

test('timeout stops the real owned Windows parent and child', {skip: process.platform !== 'win32'}, async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'rentgen-companion-test-'));
  const marker = path.join(directory, 'pids.json');
  const runner = createRunner({timeout: 1500});
  const script = 'const {spawn}=require("node:child_process"); const child=spawn(process.execPath,["-e","setInterval(()=>{},1000)"],{windowsHide:true,stdio:"ignore"}); require("node:fs").writeFileSync(process.argv[1],JSON.stringify([process.pid,child.pid])); setInterval(()=>{},1000);';
  try {
    await assert.rejects(runner.execute(process.execPath, ['-e', script, marker]), /CLI_TIMEOUT/);
    const pids = JSON.parse(await fs.readFile(marker, 'utf8'));
    for (const pid of pids) assert.throws(() => process.kill(pid, 0), {code: 'ESRCH'});
  } finally {
    runner.dispose();
    await fs.unlink(marker).catch(() => {}); await fs.rmdir(directory);
  }
});
