'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const { createRepairService } = require('../lib/repair.cjs');
const { createHash } = require('node:crypto');
const project = '00000000-0000-4000-8000-000000000001';
const ref = {snapshot: {project_id: project, snapshot_id: 'a'.repeat(64), manifest_hash: 'a'.repeat(64)}, layer_id:'base', relative_path:'Module.bsl', raw_sha256:'b'.repeat(64)};
const config = {schema:1, core_version:'0.1.0.dev7', project_id:project, python:'C:\\installed\\python.exe', registry:'C:\\registry.sqlite3'};

for (const core_version of ['0.1.0.dev7','0.1.0.dev8']) {
test(`${core_version}: lost process reply is reconciled from receipts with no second execution`, async () => {
  const selectedConfig = {...config,core_version};
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'rentgen-repair-'));
  const operation = randomUUID(), draft = randomUUID(); let executions = 0;
  const saved = {project_id:project, draft_id:draft, revision:2, operation_id:operation, source_ref:ref, proposal_content_id:'c'.repeat(64)};
  const runner = {dispose(){}, async execute(command, args) {
    executions++; assert.equal(command, config.python); assert.equal(args[0], '-I');
    const output = args[args.indexOf('--output')+1]; await fs.mkdir(output);
    await fs.writeFile(path.join(output, 'events.jsonl'), JSON.stringify({phase:'edit_requested', project_id:project, draft_id:draft, operation_id:operation, expected_revision:1})+'\n');
    throw new Error('CLI_DISPOSED');
  }};
  const client = {async receipt(id) { assert.equal(id, operation); return saved; }};
  const service = createRepairService({root, extensionRoot:root, config:selectedConfig, client, runnerFactory:()=>runner});
  const run = await service.start(ref, {model:'qwen3.5:9b', instruction:'Исправь запись'});
  assert.equal(run.receipt.revision,2); assert.equal(run.status,'saved_unverified');
  service.dispose();
  const reopened = createRepairService({root, extensionRoot:root, config:selectedConfig, client, runnerFactory:()=>{throw new Error('Must not execute again');}});
  const list = await reopened.list(); assert.equal(list.length,1);
  assert.deepEqual((await reopened.reconcile(list[0].id)).receipt,saved);
  assert.equal(executions,1); reopened.dispose();
});
}

test('foreign selection is refused before writing or starting a process', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'rentgen-repair-refused-'));
  const service = createRepairService({root,extensionRoot:root,config,client:{},runnerFactory:()=>{throw new Error('Unexpected process');}});
  await assert.rejects(service.start({...ref,snapshot:{...ref.snapshot,project_id:randomUUID()}},{model:'qwen3.5:9b',instruction:'Fix'}),/PROJECT_MISMATCH/);
  assert.deepEqual(await fs.readdir(root),[]); service.dispose();
});

test('a valid long Unicode source identity stays inspectable after restart', async () => {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'rentgen-repair-unicode-'));
  const service=createRepairService({root,extensionRoot:root,config,client:{},runnerFactory:()=>({dispose(){},async execute(){return {code:1};}})});
  const longRef={...ref,relative_path:'я'.repeat(4080)+'.bsl'};
  const run=await service.start(longRef,{model:'qwen3.5:9b',instruction:'Fix'});
  assert.equal(run.status,'unresolved');service.dispose();
  const reopened=createRepairService({root,extensionRoot:root,config,client:{}});
  assert.deepEqual((await reopened.list())[0].source_ref,longRef);
  assert.equal((await reopened.reconcile(run.id)).status,'unresolved');reopened.dispose();
});

test('missing receipt and truncated journal remain unresolved', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'rentgen-repair-unresolved-'));
  const runner = {dispose(){}, async execute(command,args) {
    const output=args[args.indexOf('--output')+1]; await fs.mkdir(output);
    await fs.writeFile(path.join(output,'events.jsonl'), JSON.stringify({phase:'start_requested',project_id:project,draft_id:randomUUID(),operation_id:randomUUID(),source_ref:ref})+'\n{"phase":');
    return {code:1,stdout:Buffer.alloc(0)};
  }};
  const service=createRepairService({root,extensionRoot:root,config,client:{async receipt(){return null;}},runnerFactory:()=>runner});
  const result=await service.start(ref,{model:'qwen3.5:9b',instruction:'Fix'});
  assert.equal(result.status,'unresolved'); assert.equal(result.receipt,null); assert.equal(result.truncated,true); service.dispose();
});

test('cancel during preparation prevents execution and leaves an inspectable unresolved run', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(),'rentgen-repair-cancel-'));
  const service = createRepairService({root,extensionRoot:root,config,client:{},runnerFactory:()=>{throw new Error('Unexpected process');}});
  const started = service.start(ref,{model:'qwen3.5:9b',instruction:'Fix'});
  service.cancel();
  await assert.rejects(service.start(ref,{model:'qwen3.5:9b',instruction:'Again'}),/REPAIR_RUNNING/);
  await assert.rejects(started,/REPAIR_CANCELLED/);
  const runs = await service.list(); assert.equal(runs.length,1);
  assert.equal((await service.reconcile(runs[0].id)).status,'unresolved'); service.dispose();
});

test('cancelling the owned runner reconciles once and never replays a mutation', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(),'rentgen-repair-active-cancel-'));
  let begun, stop, executions=0;
  const ready = new Promise(resolve=>{begun=resolve;});
  const runner = {execute:()=>{executions++;begun();return new Promise((_,reject)=>{stop=()=>reject(new Error('CLI_DISPOSED'));});},dispose:()=>stop?.()};
  const service=createRepairService({root,extensionRoot:root,config,client:{},runnerFactory:()=>runner});
  const run=service.start(ref,{model:'qwen3.5:9b',instruction:'Fix'}); await ready;
  service.cancel(); assert.equal((await run).status,'unresolved');
  assert.equal(executions,1); assert.equal(service.running,false); service.dispose();
});

test('clean analysis requires exact saved bytes, full coverage and matching operation receipt', async () => {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'rentgen-repair-binding-'));
  const operation=randomUUID(), draft=randomUUID(), candidate='\uFEFFПроцедура Проверка()\r\nКонецПроцедуры\r\n';
  const saved={project_id:project,draft_id:draft,operation_id:operation,revision:2,source_ref:ref,proposal_content_id:'c'.repeat(64)};
  const digest=createHash('sha256').update(candidate,'utf8').digest('hex');
  const report={status:'analysis_clean',receipt:saved,candidate_sha256:digest,tests:{status:'not_run'},apply:{status:'unavailable'},
    after:{receipt:saved,diagnostic:{source_ref:ref,proposal_content_id:saved.proposal_content_id,evidence:'ephemeral_unattested',
      analysis:{candidate_sha256:digest,status:'completed',exit_code:0,runtime_verified:true,diagnostics_complete:true,coverage:'exact_one',diagnostics:[]}}}};
  let output, receipt=saved;
  const runner={dispose(){},async execute(_,args){output=args[args.indexOf('--output')+1];await fs.mkdir(output);
    await fs.writeFile(path.join(output,'events.jsonl'),JSON.stringify({phase:'edit_requested',project_id:project,draft_id:draft,operation_id:operation})+'\n');
    await fs.writeFile(path.join(output,'result.json'),JSON.stringify(report));return {code:0};}};
  const service=createRepairService({root,extensionRoot:root,config,client:{receipt:async()=>receipt,draft:async()=>({receipt:saved,text:candidate})},runnerFactory:()=>runner});
  const run=await service.start(ref,{model:'qwen3.5:9b',instruction:'Fix'});assert.equal(run.status,'analysis_clean');
  report.candidate_sha256='d'.repeat(64);
  await fs.writeFile(path.join(output,'result.json'),JSON.stringify(report));
  assert.equal((await service.reconcile(run.id)).status,'saved_unverified');
  report.candidate_sha256=digest;report.after.diagnostic.analysis.diagnostics_complete=false;
  await fs.writeFile(path.join(output,'result.json'),JSON.stringify(report));
  assert.equal((await service.reconcile(run.id)).status,'saved_unverified');
  receipt={...saved,operation_id:randomUUID()};await assert.rejects(service.reconcile(run.id),/REPAIR_RECEIPT_MISMATCH/);
  service.dispose();
});
