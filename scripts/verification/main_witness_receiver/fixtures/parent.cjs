'use strict';
// Synthetic exact HELLO-only fixture. It grants no Main/Editor/Owner role.
const {spawn} = require('node:child_process');
const {Socket} = require('node:net');
const {TextDecoder} = require('node:util');
const {performance} = require('node:perf_hooks');
const instance = process.env.RWR_INSTANCE, nonce = process.env.RWR_NONCE;
const run = process.env.RWR_RUN, generation = process.env.RWR_GENERATION;
const sourceCopyPin = process.env.RWR_SOURCE_PIN;
if (!/^[0-9a-f]{32}$/.test(instance || '') || !/^[0-9a-f]{32}$/.test(nonce || '') ||
    !/^[A-Za-z0-9._-]{1,128}$/.test(run || '') || !/^[1-9][0-9]{0,19}$/.test(generation || '') ||
    BigInt(generation) > 18446744073709551615n || !/^[0-9a-f]{64}$/.test(sourceCopyPin || ''))
  throw new Error('FROZEN_CONFIG');
const hello = {schema:'root-main-witness-control/1',kind:'hello',instance,nonce,run,generation,sourceCopyPin};
const child = spawn(process.execPath, [process.argv[2]], {
  detached:true, stdio:'ignore',
  env:{NODE_OPTIONS:'',NODE_PATH:'',SystemRoot:process.env.SystemRoot}
});
let socket = null, primary = null, dead = false, closed = false;
let connectProducerEnded = true, writeProducerEnded = true, callbackEnded = true, wire = null;
let rx = Buffer.alloc(1028), used = 0, required = 4, acked = false;
let helloAt = null, deadline = performance.now() + 5000;
const decoder = new TextDecoder('utf-8', {fatal:true,ignoreBOM:true});
let timer = setTimeout(() => stop(new Error('INITIAL_DEADLINE')), 5000);
function retire() {
  if (!dead || !closed || !connectProducerEnded || !writeProducerEnded || !callbackEnded) return;
  if (wire) { wire.fill(0); wire = null; }
  if (rx) { rx.fill(0); rx = null; }
}
function stop(error) {
  dead = true;
  if (!primary) primary = error || new Error('LOCAL_CLOSED');
  if (timer !== null) { clearTimeout(timer); timer = null; }
  if (!socket) closed = true;
  else if (!closed) socket.destroy();
  retire();
}
function receive(chunk) {
  try {
    if (dead || acked || !Buffer.isBuffer(chunk) || !chunk.length || chunk.length > 4096 ||
        performance.now() >= deadline) throw new Error('INBOUND');
    let pos = 0;
    while (pos < chunk.length) {
      const n = Math.min(required-used,chunk.length-pos);
      chunk.copy(rx,used,pos,pos+n); used += n; pos += n;
      if (used !== required) continue;
      if (required === 4) {
        const size = rx.readUInt32LE(0);
        if (!size || size > 1024) throw new Error('ACK_LENGTH');
        required = size + 4;
      } else {
        const raw = rx.subarray(4,required);
        if (raw[0] === 239 && raw[1] === 187 && raw[2] === 191) throw new Error('BOM');
        const text = decoder.decode(raw), o = JSON.parse(text);
        const keys = ['schema','kind','instance','nonce','run','generation','sourceCopyPin','remainingMs'];
        if (!o || Object.getPrototypeOf(o) !== Object.prototype || JSON.stringify(o) !== text ||
            Object.keys(o).length !== keys.length || keys.some(k => !Object.hasOwn(o,k)) ||
            o.schema !== hello.schema || o.kind !== 'ack' || o.instance !== instance ||
            o.nonce !== nonce || o.run !== run || o.generation !== generation ||
            o.sourceCopyPin !== sourceCopyPin || !Number.isSafeInteger(o.remainingMs) ||
            o.remainingMs < 1 || o.remainingMs > 5000 || pos !== chunk.length || helloAt === null)
          throw new Error('ACK_BINDING');
        deadline = Math.min(deadline, helloAt + o.remainingMs);
        if (dead || performance.now() >= deadline) throw new Error('ACK_EXPIRED');
        acked = true; rx.fill(0);
        clearTimeout(timer); timer = setTimeout(() => stop(new Error('DEADLINE')),
                                               Math.ceil(deadline-performance.now()));
      }
    }
  } catch (error) { stop(error); }
}
child.once('error', error => stop(error));
child.once('exit', () => stop(new Error('CHILD_EXIT')));
child.once('spawn', () => {
  if (dead) return;
  socket = new Socket();
  socket.on('data', receive);
  socket.on('error', error => stop(error));
  socket.on('end', () => stop(new Error(used && !acked ? 'PARTIAL_EOF' : 'EOF')));
  socket.on('close', () => { closed = true; stop(primary || new Error('CLOSED')); retire(); });
  socket.once('connect', () => {
    if (dead || performance.now() >= deadline) { stop(new Error('DEADLINE')); return; }
    helloAt = performance.now();
    let body = null;
    try {
      body = Buffer.from(JSON.stringify(hello),'utf8');
      if (!body.length || body.length > 1024) throw new Error('HELLO_CAP');
      wire = Buffer.alloc(body.length+4); wire.writeUInt32LE(body.length,0); body.copy(wire,4);
    } catch (error) { stop(error); return; }
    finally { if (body) body.fill(0); }
    writeProducerEnded = false; callbackEnded = false;
    try {
      socket.write(wire, error => {
        callbackEnded = true;
        if (error) stop(error);
        retire();
      });
    } catch (error) { stop(error); }
    finally { writeProducerEnded = true; retire(); }
  });
  // One attempt; Root already created the fresh original server before birth.
  connectProducerEnded = false;
  try { socket.connect({path:'\\\\.\\pipe\\rentgen-main-witness-'+instance}); }
  catch (error) { stop(error); }
  finally { connectProducerEnded = true; retire(); }
});
