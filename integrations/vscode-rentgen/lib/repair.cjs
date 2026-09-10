'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const { randomUUID, createHash } = require('node:crypto');
const { isDeepStrictEqual: same } = require('node:util');
const { sourceRef, profileConfig } = require('./core.cjs');
const { createRunner } = require('./process.cjs');
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const decode = raw => new TextDecoder('utf-8', {fatal:true}).decode(raw);
const requireValue = (condition, code) => { if (!condition) throw new Error(code); };

async function readBounded(file, limit, optional = false) {
  let handle;
  try {
    const stat = await fs.lstat(file);
    requireValue(stat.isFile() && !stat.isSymbolicLink() && stat.size <= limit, 'INVALID_REPAIR_FILE');
    handle = await fs.open(file, 'r');
    const raw = Buffer.alloc(limit + 1), {bytesRead} = await handle.read(raw, 0, raw.length, 0);
    requireValue(bytesRead <= limit, 'REPAIR_FILE_LIMIT');
    return raw.subarray(0, bytesRead);
  } catch (error) { if (optional && error.code === 'ENOENT') return null; throw error; }
  finally { if (handle) await handle.close(); }
}
async function writeNew(file, value) {
  const handle = await fs.open(file, 'wx');
  try { await handle.writeFile(value, 'utf8'); await handle.sync(); }
  finally { await handle.close(); }
}
function createRepairService({root, extensionRoot, config, client, trusted = () => true, runnerFactory = () => createRunner({timeout:450000})}) {
  config = profileConfig(config);
  const directory = path.join(root, 'repair-runs');
  let busy = false, active = null, disposed = false, cancelled = false;
  const trust = () => requireValue(!disposed && trusted(), 'TRUST_REQUIRED');
  async function runPath(id) {
    requireValue(uuid.test(id), 'INVALID_REPAIR_RUN');
    const folder = path.join(directory, id);
    for (const candidate of [directory, folder]) {
      const stat = await fs.lstat(candidate);
      requireValue(stat.isDirectory() && !stat.isSymbolicLink(), 'INVALID_REPAIR_DIRECTORY');
    }
    return folder;
  }
  async function request(id) {
    const folder = await runPath(id);
    // SourceRef permits 4096 Unicode characters, which can exceed 8 KiB in JSON.
    const value = JSON.parse(decode(await readBounded(path.join(folder, 'request.json'), 32768)));
    requireValue(value.id === id && value.project_id === config.project_id, 'PROJECT_MISMATCH');
    sourceRef(value.source_ref, config.project_id);
    requireValue(typeof value.created_at === 'string' && Number.isFinite(Date.parse(value.created_at)), 'INVALID_REPAIR_RUN');
    return {folder, value};
  }
  async function list() {
    trust();
    let entries;
    try {
      const stat = await fs.lstat(directory);
      requireValue(stat.isDirectory() && !stat.isSymbolicLink(), 'INVALID_REPAIR_DIRECTORY');
      entries = await fs.readdir(directory, {withFileTypes:true});
    } catch (error) { if (error.code === 'ENOENT') return []; throw error; }
    requireValue(entries.length <= 200, 'REPAIR_RUN_LIMIT');
    const rows = [];
    for (const entry of entries) if (uuid.test(entry.name)) rows.push((await request(entry.name)).value);
    trust();
    return rows.sort((a,b) => b.created_at.localeCompare(a.created_at));
  }
  async function reconcile(id) {
    trust(); requireValue(!active, 'REPAIR_RUNNING');
    const {folder, value} = await request(id);
    try {
      const stat = await fs.lstat(path.join(folder,'result'));
      requireValue(stat.isDirectory() && !stat.isSymbolicLink(), 'INVALID_REPAIR_DIRECTORY');
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    const raw = await readBounded(path.join(folder, 'result/events.jsonl'), 2097152, true);
    const last = raw ? raw.lastIndexOf(10) + 1 : 0;
    const truncated = Boolean(raw && last < raw.length);
    const events = raw ? decode(raw.subarray(0,last)).split('\n').filter(Boolean).map(JSON.parse) : [];
    requireValue(events.length <= 64, 'REPAIR_EVENT_LIMIT');
    const intents = events.filter(event => ['start_requested','edit_requested'].includes(event.phase));
    requireValue(intents.length <= 2, 'INVALID_REPAIR_JOURNAL');
    let receipt = null, missing = false, draft = null;
    for (const event of intents) {
      requireValue(event.project_id === config.project_id && uuid.test(event.operation_id) && uuid.test(event.draft_id), 'INVALID_REPAIR_JOURNAL');
      requireValue(!draft || draft === event.draft_id, 'INVALID_REPAIR_JOURNAL'); draft = event.draft_id;
      const saved = await client.receipt(event.operation_id); trust();
      if (saved === null) { missing = true; continue; }
      requireValue(saved.project_id === config.project_id && saved.draft_id === draft && saved.operation_id === event.operation_id &&
        saved.revision === (event.phase === 'start_requested' ? 1 : 2) && same(sourceRef(saved.source_ref, config.project_id), sourceRef(value.source_ref, config.project_id)), 'REPAIR_RECEIPT_MISMATCH');
      receipt = saved;
    }
    let status = receipt && !missing && !truncated ? 'saved_unverified' : 'unresolved';
    let result = null;
    const report = await readBounded(path.join(folder, 'result/result.json'), 2097152, true);
    if (report) { try { result = JSON.parse(decode(report)); } catch { /* Preserve the actual receipt, never claim analysis. */ } }
    if (receipt && status === 'saved_unverified' && result && ['analysis_clean','diagnostics_present'].includes(result.status) && same(result.receipt, receipt)) {
      const saved = await client.draft(receipt.draft_id, receipt.revision); trust();
      requireValue(same(saved.receipt, receipt), 'REPAIR_RECEIPT_MISMATCH');
      const digest = createHash('sha256').update(Buffer.from(saved.text,'utf8')).digest('hex');
      const after = result.after, diagnostic = after?.diagnostic, analysis = diagnostic?.analysis;
      if (same(after?.receipt, receipt) && same(diagnostic?.source_ref, receipt.source_ref) && diagnostic?.proposal_content_id === receipt.proposal_content_id &&
        result.candidate_sha256 === digest && analysis?.candidate_sha256 === digest && analysis.status === 'completed' && analysis.exit_code === 0 &&
        analysis.runtime_verified === true && analysis.diagnostics_complete === true && analysis.coverage === 'exact_one' && Array.isArray(analysis.diagnostics) &&
        diagnostic.evidence === 'ephemeral_unattested' && result.tests?.status === 'not_run' && result.apply?.status === 'unavailable') {
        status = analysis.diagnostics.length ? 'diagnostics_present' : 'analysis_clean';
      }
    }
    return {id, status, receipt, truncated, resultPath:path.join(folder,'result/result.json')};
  }
  async function start(ref, options) {
    trust(); requireValue(config.core_version === '0.1.0.dev7', 'REPAIR_REQUIRES_DEV7');
    requireValue(!busy, 'REPAIR_RUNNING');
    ref = sourceRef(ref, config.project_id);
    requireValue(options && typeof options.model === 'string' && /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$/.test(options.model), 'INVALID_MODEL_NAME');
    requireValue(typeof options.instruction === 'string' && options.instruction.trim() && Buffer.byteLength(options.instruction,'utf8') <= 4096, 'INVALID_INSTRUCTION');
    busy = true; cancelled = false;
    let id;
    try {
      requireValue((await list()).length < 200, 'REPAIR_RUN_LIMIT'); trust();
      await fs.mkdir(directory, {recursive:true});
      const stat = await fs.lstat(directory); requireValue(stat.isDirectory() && !stat.isSymbolicLink(), 'INVALID_REPAIR_DIRECTORY');
      id = randomUUID(); const folder = path.join(directory,id); await fs.mkdir(folder);
      const value = {id,project_id:config.project_id,source_ref:ref,model:options.model,created_at:new Date().toISOString()};
      await writeNew(path.join(folder,'request.json'),JSON.stringify(value));
      await writeNew(path.join(folder,'source-ref.json'),JSON.stringify(ref));
      await writeNew(path.join(folder,'instruction.txt'),options.instruction);
      trust(); requireValue(!cancelled, 'REPAIR_CANCELLED'); active = runnerFactory();
      try {
        await active.execute(config.python, ['-I',path.join(extensionRoot,'repair/run_repair.py'),'--profile',root,'--source-ref',path.join(folder,'source-ref.json'),
          '--instruction',path.join(folder,'instruction.txt'),'--output',path.join(folder,'result'),'--model',options.model]);
      } catch { /* A closed process does not prove whether a draft was committed. */ }
      finally { active.dispose(); active = null; }
      trust(); return await reconcile(id);
    } finally { busy = false; }
  }
  return {start,reconcile,list,cancel(){cancelled=true;active?.dispose();},get running(){return busy;},dispose(){disposed=true;active?.dispose();}};
}
module.exports = {createRepairService};
