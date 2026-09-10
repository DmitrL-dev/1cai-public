'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const {randomUUID, createHash} = require('node:crypto');
const {isDeepStrictEqual} = require('node:util');
const {profileConfig, sourceRef} = require('./core.cjs');
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

async function regular(file, max) {
  const stat = await fs.lstat(file);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > max) throw new Error('PLATFORM_FILE_INVALID');
}
async function writeNew(file, value, max) {
  const bytes = Buffer.from(JSON.stringify(value));
  if (bytes.length > max) throw new Error('PLATFORM_FILE_LIMIT');
  const handle = await fs.open(file, 'wx');
  try { await handle.writeFile(bytes); await handle.sync(); } finally { await handle.close(); }
}
async function readRequest(file) {
  await regular(file, 32768);
  const handle = await fs.open(file, 'r');
  try {
    const bytes = Buffer.alloc(32769), {bytesRead} = await handle.read(bytes, 0, bytes.length, 0);
    if (bytesRead > 32768) throw new Error('PLATFORM_FILE_LIMIT');
    return JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(bytes.subarray(0, bytesRead)));
  } finally { await handle.close(); }
}
async function executableHash(file) {
  if (!path.isAbsolute(file) || path.basename(file).toLowerCase() !== '1cv8.exe') throw new Error('FULL_PLATFORM_REQUIRED');
  await regular(file, 256 * 1024 * 1024);
  const handle = await fs.open(file, 'r'), hash = createHash('sha256');
  try {
    const buffer = Buffer.alloc(65536); let total = 0;
    for (;;) {
      const {bytesRead} = await handle.read(buffer, 0, buffer.length, null);
      if (!bytesRead) break;
      total += bytesRead;
      if (total > 256 * 1024 * 1024) throw new Error('PLATFORM_FILE_LIMIT');
      hash.update(buffer.subarray(0, bytesRead));
    }
    return hash.digest('hex');
  } finally { await handle.close(); }
}
function createPlatformService({root, config, client, trusted = () => true, cancel = () => {}}) {
  config = profileConfig(config);
  const directory = path.join(root, 'platform-runs');
  let busy = false, disposed = false, cancelled = false;
  function check() {
    if (disposed || !trusted()) throw new Error('TRUST_REQUIRED');
    if (config.core_version !== '0.1.0.dev8') throw new Error('PLATFORM_REQUIRES_DEV8');
  }
  async function safeDirectory(file) {
    const stat = await fs.lstat(file);
    if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error('PLATFORM_DIRECTORY_INVALID');
  }
  async function list() {
    check();
    try { await safeDirectory(directory); } catch (error) { if (error.code === 'ENOENT') return []; throw error; }
    const rows = [];
    const dir = await fs.opendir(directory);
    let count = 0;
    for await (const entry of dir) {
      if (++count > 1000) throw new Error('PLATFORM_HISTORY_LIMIT');
      if (!uuid.test(entry.name)) continue;
      const run = path.join(directory, entry.name); await safeDirectory(run);
      let value;
      try { value = await readRequest(path.join(run, 'request.json')); }
      catch (error) { if (error.code === 'ENOENT') continue; throw error; }
      if (value.id !== entry.name || value.receipt?.project_id !== config.project_id ||
        !uuid.test(value.receipt.draft_id) || !Number.isSafeInteger(value.receipt.revision) || value.receipt.revision < 1 ||
        typeof value.created_at !== 'string' || !Number.isFinite(Date.parse(value.created_at))) throw new Error('PLATFORM_REQUEST_INVALID');
      sourceRef(value.receipt.source_ref, config.project_id);
      rows.push(value);
    }
    check(); return rows.sort((a,b)=>b.created_at.localeCompare(a.created_at));
  }
  async function start(receipt, platform) {
    check(); if (busy) throw new Error('PLATFORM_RUNNING'); busy = true; cancelled = false;
    let id;
    try {
      sourceRef(receipt.source_ref, config.project_id);
      const saved = await client.proposal(receipt.draft_id, receipt.revision);
      if (!isDeepStrictEqual(saved.receipt, receipt)) throw new Error('DRAFT_REVISION_MISMATCH');
      const platformHash = await executableHash(platform); check();
      if (cancelled) throw new Error('PLATFORM_CANCELLED');
      await fs.mkdir(directory, {recursive:true}); await safeDirectory(directory);
      if ((await list()).length >= 1000) throw new Error('PLATFORM_HISTORY_LIMIT');
      id = randomUUID(); const run = path.join(directory, id); await fs.mkdir(run);
      const proposal = path.join(run, 'proposal.json');
      await writeNew(proposal, saved.proposal, 1536 * 1024);
      await writeNew(path.join(run, 'request.json'), {id, receipt, platform, platformHash, created_at:new Date().toISOString()}, 32768);
      check(); if (cancelled) throw new Error('PLATFORM_CANCELLED');
      const report = await client.platformCheck({id, ref:receipt.source_ref, contentId:receipt.proposal_content_id, proposal, platform, platformHash});
      check(); return {run_id:id, status:'completed', report};
    } catch (error) {
      if (id) throw new Error(`${error.message}; запуск ${id}. Получите сохранённый результат по этому номеру.`, {cause:error});
      throw error;
    } finally { busy = false; }
  }
  return {start, list, get running() {return busy;},
    async inspect(id) { check(); if (!uuid.test(id)) throw new Error('INVALID_OPERATION_ID'); const result=await client.platformResult(id); check(); return result; },
    cancel() {cancelled = true; if (busy) cancel();},
    dispose() {disposed = true; if (busy) cancel();},
  };
}
module.exports = {createPlatformService};
