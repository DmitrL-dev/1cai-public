'use strict';
// Root-only controlled Source harness; no real net/Module fixture execution.
// Author did not run Node. argv[2] must be the exact v2 fixture Source file.
const assert = require('node:assert/strict');
const fs = require('node:fs'), crypto = require('node:crypto');
const vm = require('node:vm'), winpath = require('node:path').win32;
const fixtureRef = {bytes:6771,
  sha256:'8ec9f7c0bb3f51ac6cb418d5d91ea689f8e5d18c52e1d27415df8906db3977c0'};
assert.equal(process.argv.length, 3);
function sha(raw) {return crypto.createHash('sha256').update(raw).digest('hex');}
function exactFixtureSource(filename) {
  const fd = fs.openSync(filename, 'r'), raw = Buffer.alloc(fixtureRef.bytes);
  try {
    assert.equal(fs.fstatSync(fd).size, raw.length);
    let at = 0;
    while (at < raw.length) {
      const n = fs.readSync(fd, raw, at, raw.length-at, at);
      assert(n > 0); at += n;
    }
    assert.equal(fs.readSync(fd, Buffer.alloc(1), 0, 1, at), 0);
  } finally {fs.closeSync(fd);}
  assert.equal(sha(raw), fixtureRef.sha256);
  return raw.toString('utf8');
}
const fixtureSource = exactFixtureSource(process.argv[2]);
const base = 'C:\\controlled-fixture\\';
const configPath = base + 'config.json';
const moduleBytes = Buffer.from('// Controlled bytes. Fake Module must never compile these.\n');
function moduleRef(name) {return {path:base+name,bytes:moduleBytes.length,sha256:sha(moduleBytes)};}
const config = {schema:'rentgen-root-pipe-refusal-client/1',
  pipe_name:'\\\\.\\pipe\\rentgen-refusal-'+'d'.repeat(32),
  bridge:moduleRef('owner_bridge.cjs'), bootstrap:moduleRef('owner-bootstrap.cjs'),
  expected:{generation:1,run_nonce:'a'.repeat(32),request_id:'b'.repeat(32),
    bindings_sha256:'c'.repeat(64)},
  report:base+'report.json',client_window_ms:1000};
const original = Buffer.from(JSON.stringify(config));
const compileBoundary = 'CONTROL_MODULE_COMPILATION_BOUNDARY';
function observe(raw, options = {}) {
  const stats = {configOpens:0, configCloses:0, configRead:0, configMaxRequested:0,
    compiles:0, sockets:0, statPath:0, unboundedRead:0};
  const files = new Map([[configPath,raw],[config.bridge.path,moduleBytes],
    [config.bootstrap.path,moduleBytes]]);
  const held = new Map();
  let next = 10;
  const fakeFs = {
    openSync(filename, flags) {
      assert.equal(flags, 'r');
      assert(files.has(filename));
      const fd = ++next; held.set(fd,filename);
      if (filename === configPath) stats.configOpens++;
      return fd;
    },
    fstatSync(fd) {
      const filename = held.get(fd); assert(filename);
      return {size:filename === configPath ?
        (options.reportedSize === undefined ? raw.length : options.reportedSize) :
        files.get(filename).length};
    },
    readSync(fd, out, at, length, position) {
      const filename = held.get(fd); assert(filename);
      const data = files.get(filename), n = Math.min(length, Math.max(0,data.length-position));
      data.copy(out,at,position,position+n);
      if (filename === configPath) {
        stats.configRead += n;
        stats.configMaxRequested = Math.max(stats.configMaxRequested,length);
      }
      return n;
    },
    closeSync(fd) {
      const filename = held.get(fd); assert(filename);
      if (filename === configPath) stats.configCloses++;
      held.delete(fd);
    },
    statSync() {stats.statPath++; throw Error('FORBIDDEN_PATH_STAT');},
    readFileSync() {stats.unboundedRead++; throw Error('FORBIDDEN_UNBOUNDED_READ');}
  };
  class FakeModule {
    static _nodeModulePaths() {return [];}
    _compile() {stats.compiles++; throw Error(compileBoundary);}
  }
  const fakeNet = {createConnection() {stats.sockets++; throw Error('FORBIDDEN_SOCKET');}};
  const modules = new Map([['node:fs',fakeFs],['node:path',winpath],
    ['node:crypto',crypto],['node:module',FakeModule],['node:net',fakeNet]]);
  function fakeRequire(name) {assert(modules.has(name)); return modules.get(name);}
  fakeRequire.cache = Object.create(null);
  const argv = ['controlled-node.exe','known-client.cjs',configPath,
    String(options.argvBytes === undefined ? original.length : options.argvBytes),
    options.argvHash === undefined ? sha(original) : options.argvHash];
  let error = null;
  try {
    vm.runInNewContext(fixtureSource, {require:fakeRequire,Buffer,
      process:{platform:'win32',argv}}, {timeout:1000,filename:'exact-v2-known-fixture'});
  } catch (caught) {error = caught.message;}
  assert.equal(stats.sockets,0);
  assert.equal(stats.statPath,0);
  assert.equal(stats.unboundedRead,0);
  assert.equal(held.size,0);
  return {error,stats};
}
// Positive control reaches the first pinned-module compilation boundary; the
// fake Module aborts there. It never executes codec/bootstrap or opens a socket.
let seen = observe(original);
assert.equal(seen.error,compileBoundary);
assert.equal(seen.stats.compiles,1);
assert.equal(seen.stats.configOpens,1);
assert.equal(seen.stats.configCloses,1);
assert.equal(seen.stats.configRead,original.length);

// Same-size replacement keeps valid JSON but differs from Root's original hash.
const replaced = Buffer.from(original.toString('utf8').replace('"client_window_ms":1000',
  '"client_window_ms":2000'));
assert.equal(replaced.length,original.length);
seen = observe(replaced);
assert.equal(seen.error,'CLIENT_PIN_SHA');
assert.equal(seen.stats.compiles,0);
assert.equal(seen.stats.configCloses,1);

// Growth after the held-fd size observation reads at most N+1 and fails before
// parse/module compilation. A truncated held file fails on bounded EOF.
seen = observe(Buffer.concat([original,Buffer.alloc(1024,32)]),
  {reportedSize:original.length});
assert.equal(seen.error,'CLIENT_PIN_EXTRA');
assert.equal(seen.stats.configRead,original.length+1);
assert.equal(seen.stats.configMaxRequested,original.length);
assert.equal(seen.stats.compiles,0);
assert.equal(seen.stats.configCloses,1);
seen = observe(original.subarray(0,original.length-2),{reportedSize:original.length});
assert.equal(seen.error,'CLIENT_PIN_EOF');
assert.equal(seen.stats.compiles,0);
assert.equal(seen.stats.configCloses,1);

for (const [options,code] of [
  [{argvBytes:0},'PRIVATE_FIXTURE_ENTRY'],
  [{argvBytes:8193},'CLIENT_PIN'],
  [{argvHash:'not-a-digest'},'CLIENT_PIN']
]) {
  seen = observe(original,options);
  assert.equal(seen.error,code);
  assert.equal(seen.stats.configOpens,0);
  assert.equal(seen.stats.compiles,0);
}
process.stdout.write(JSON.stringify({scope:'controlled-config-pin-Source-harness-only',
  positive_boundary:true,negative_cases:6,real_socket_calls:0,
  real_module_compiles:0,EditorRole:false,runtime_qualified:false})+'\n');
