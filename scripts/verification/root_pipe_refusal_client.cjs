'use strict';
// Root-private known fixture client. No Editor, CLI/Core/SDK/model/native backend.
const fs = require('node:fs'), path = require('node:path');
const crypto = require('node:crypto'), Module = require('node:module');
const net = require('node:net');
function need(ok, code) {if (!ok) throw new Error(code);}
function exact(v, keys) {return v && typeof v === 'object' && !Array.isArray(v) &&
  Object.keys(v).sort().join(',') === keys.slice().sort().join(',');}
function pinned(ref, limit) {
  need(exact(ref, ['path','bytes','sha256']) && path.isAbsolute(ref.path) &&
    Number.isSafeInteger(ref.bytes) && ref.bytes > 0 && ref.bytes <= limit &&
    typeof ref.sha256 === 'string' && /^[a-f0-9]{64}$/.test(ref.sha256), 'CLIENT_PIN');
  const fd = fs.openSync(ref.path, 'r');
  let raw;
  try {
    need(fs.fstatSync(fd).size === ref.bytes, 'CLIENT_PIN_SIZE');
    raw = Buffer.alloc(ref.bytes);
    let at = 0;
    while (at < raw.length) {
      const n = fs.readSync(fd, raw, at, raw.length - at, at);
      need(n > 0, 'CLIENT_PIN_EOF'); at += n;
    }
    need(fs.readSync(fd, Buffer.alloc(1), 0, 1, at) === 0, 'CLIENT_PIN_EXTRA');
  } finally {fs.closeSync(fd);}
  need(crypto.createHash('sha256').update(raw).digest('hex') === ref.sha256, 'CLIENT_PIN_SHA');
  return raw;
}
function loadFrozen(ref, basename) {
  need(path.basename(ref.path) === basename, 'CLIENT_MODULE_NAME');
  const raw = pinned(ref, 65536);
  const filename = path.resolve(ref.path);
  const mod = new Module(filename);
  mod.filename = filename;
  mod.paths = Module._nodeModulePaths(path.dirname(filename));
  require.cache[filename] = mod;
  // Compile only the exact hashed ordinary Source bytes. Root admits this known
  // fixture separately. Never evaluate wire/config text as code.
  mod._compile(raw.toString('utf8'), filename);
  mod.loaded = true;
  return mod.exports;
}
need(process.platform === 'win32' && process.argv.length === 5 &&
  path.isAbsolute(process.argv[2]) && /^[1-9][0-9]{0,3}$/.test(process.argv[3]),
  'PRIVATE_FIXTURE_ENTRY');
const configPath = path.resolve(process.argv[2]);
const configBytes = pinned({path:configPath, bytes:Number(process.argv[3]),
  sha256:process.argv[4]}, 8192);
const cfg = JSON.parse(configBytes.toString('utf8'));
need(exact(cfg, ['schema','pipe_name','bridge','bootstrap','expected','report','client_window_ms']) &&
  cfg.schema === 'rentgen-root-pipe-refusal-client/1', 'CLIENT_CONFIG');
need(typeof cfg.pipe_name === 'string' &&
  /^\\\\\.\\pipe\\rentgen-refusal-[a-f0-9]{32}$/.test(cfg.pipe_name), 'CLIENT_LOCAL_PIPE');
need(typeof cfg.report === 'string' && path.isAbsolute(cfg.report) &&
  Number.isSafeInteger(cfg.client_window_ms) && cfg.client_window_ms >= 100 &&
  cfg.client_window_ms <= 5000, 'CLIENT_BOUNDS');
need(path.dirname(cfg.bridge.path) === path.dirname(cfg.bootstrap.path), 'CLIENT_MODULE_PAIR');
const codec = loadFrozen(cfg.bridge, 'owner_bridge.cjs');
const coordinator = loadFrozen(cfg.bootstrap, 'owner-bootstrap.cjs');
const now = () => process.hrtime.bigint(), started = now();
const end = started + BigInt(cfg.client_window_ms) * 1000000n;
// A local clock ceiling only. Root's independent frozen native deadlines remain
// authoritative; this local interval never renews Root budgets.
const lease = Object.freeze({scope:'Root-known-fixture-local-view-only'});
const bridge = codec.createOwnerBridge({expected:cfg.expected, lease, now,
  limits:{frame_bytes:4096, aggregate_bytes:8200, retained_storage_bytes:16400,
    max_chunk_bytes:1024, receive_calls:4100, queue_slots:1,
    connect_until_ns:end, hello_until_ns:end, cancel_until_ns:end, closure_until_ns:end}});
const bootstrap = coordinator.createOwnerBootstrapForBridge(bridge);
const context = Object.freeze({scope:'known-fixture-only'});
let initializer = 0, runner = 0, Core = 0;
const initialize = () => {initializer++; runner++; Core++; throw new Error('FORBIDDEN_INITIALIZER');};
const first = bootstrap.activate(context, initialize);
const second = bootstrap.activate(context, initialize);
need(first === second, 'CLIENT_SHARED_INITIALIZER_PROMISE');
let rejected = null, acceptedReply = false, failed = false, published = false;
first.catch(error => {rejected = error.message;});
const socket = net.createConnection({path:cfg.pipe_name});
const timer = setTimeout(() => {failed = true; bridge.cancel(); socket.destroy();}, cfg.client_window_ms);
socket.once('connect', () => {
  try {
    const packet = bridge.outbound(lease);
    need(Buffer.isBuffer(packet) && packet.length <= 4100, 'CLIENT_ONE_BOOTSTRAP');
    socket.write(packet); // exactly one write; no retry/backpressure queue of requests
  } catch (_) {failed = true; bridge.cancel(); socket.destroy();}
});
socket.on('data', raw => {
  try {
    need(!acceptedReply && raw.length > 0 && raw.length <= 4100, 'CLIENT_REPLY_BOUND');
    for (let at = 0; at < raw.length; at += 1024) {
      need(bridge.receive(raw.subarray(at, Math.min(at + 1024, raw.length))), 'CLIENT_REPLY_REFUSED');
    }
    const state = bridge.snapshot();
    if (state.rx_frames === 1) {
      need(state.observation_code === 'DAILY_ROOT_EDITOR_OWNER_REQUIRED', 'CLIENT_REFUSAL_CODE');
      acceptedReply = true;
    }
    // Keep this known process alive until Root's server handle closes, so Root
    // can complete its post-exchange held-peer check. Do not close/end here.
  } catch (_) {failed = true; bridge.cancel(); socket.destroy();}
});
socket.on('error', () => {failed = true; bridge.cancel();});
socket.on('end', () => {if (!acceptedReply) {failed = true; bridge.end();}});
socket.once('close', async () => {
  clearTimeout(timer);
  try {
    let executeDenied = false;
    try {await bridge.execute();} catch (error) {executeDenied = error.message === 'OWNER_TRANSPORT_NOT_ADMITTED';}
    const localClosed = bridge.closeLocal(lease);
    const result = {scope:'one-Root-known-fixture-pipe-client-only',
      shared_whole_initializer_promise:first === second, actual_refusal_parsed:acceptedReply,
      rejected, executeDenied, initializer, runner, Core, localClosed,
      bridge:bridge.snapshot(), coordinator:bootstrap.snapshot(),
      EditorRole:false, model:0, onec:0, native_completion_claim:false};
    need(!failed && acceptedReply && rejected === 'DAILY_ROOT_EDITOR_OWNER_REQUIRED' &&
      executeDenied && localClosed && initializer === 0 && runner === 0 && Core === 0,
      'CLIENT_REFUSAL_NOT_ACCEPTED');
    const text = JSON.stringify(result) + '\n';
    need(Buffer.byteLength(text, 'utf8') <= 4096 && !published, 'CLIENT_REPORT_BOUND');
    published = true;
    const fd = fs.openSync(cfg.report, 'wx', 0o600);
    try {fs.writeFileSync(fd, text, 'utf8');} finally {fs.closeSync(fd);}
    process.exitCode = 0;
  } catch (_) {process.exitCode = 2;}
});
