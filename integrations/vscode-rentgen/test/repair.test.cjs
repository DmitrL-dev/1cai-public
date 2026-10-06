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

test('interrupted preparation does not block recovery or the next repair', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'rentgen-repair-interrupted-'));
  t.after(() => fs.rm(root, {recursive:true, force:true}));
  await fs.mkdir(path.join(root, 'repair-runs', randomUUID()), {recursive:true});
  let executions = 0;
  const service = createRepairService({root, extensionRoot:root, config, client:{},
    runnerFactory:() => ({dispose(){}, async execute(){executions++; return {code:1};}})});
  t.after(() => service.dispose());
  assert.deepEqual(await service.list(), []);
  const run = await service.start(ref, {model:'qwen3.5:9b', instruction:'Fix'});
  assert.equal(run.status, 'unresolved');
  assert.equal((await service.list()).length, 1);
  assert.equal(executions, 1);
});

test('unfinished repair directories still count toward the storage limit', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'rentgen-repair-limit-'));
  t.after(() => fs.rm(root, {recursive:true, force:true}));
  const home = path.join(root, 'repair-runs');
  await fs.mkdir(home);
  for (let i = 0; i < 200; i++) await fs.mkdir(path.join(home, randomUUID()));
  const service = createRepairService({root, extensionRoot:root, config, client:{},
    runnerFactory:() => {throw new Error('Unexpected process');}});
  t.after(() => service.dispose());
  assert.deepEqual(await service.list(), []);
  await assert.rejects(service.start(ref, {model:'qwen3.5:9b', instruction:'Fix'}), /REPAIR_RUN_LIMIT/);
  assert.equal((await fs.readdir(home)).length, 200);
});

test('a failed repair retains its bounded error code without changing recovery status or replaying', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'rentgen-repair-error-'));
  t.after(() => fs.rm(root, {recursive:true, force:true}));
  let output, executions = 0;
  const service = createRepairService({root, extensionRoot:root, config, client:{},
    runnerFactory:() => ({dispose(){}, async execute(_, args){
      executions++;
      output = args[args.indexOf('--output') + 1]; await fs.mkdir(output);
      await fs.writeFile(path.join(output, 'result.json'), JSON.stringify({status:'failed', error:'MODEL_SOURCE_LIMIT'}));
      return {code:1};
    }})});
  t.after(() => service.dispose());
  const run = await service.start(ref, {model:'qwen3.5:9b', instruction:'Fix'});
  assert.equal(run.status, 'unresolved'); assert.equal(run.error, 'MODEL_SOURCE_LIMIT');
  assert.equal((await service.reconcile(run.id)).error, 'MODEL_SOURCE_LIMIT');
  await fs.writeFile(path.join(output, 'result.json'), JSON.stringify({status:'failed', error:'Private code\n'.repeat(100)}));
  assert.equal((await service.reconcile(run.id)).error, undefined);
  assert.equal(executions, 1);
});

for (const core_version of ['0.1.0.dev7','0.1.0.dev8','0.1.0.dev9','0.1.0.dev10','0.1.0.dev11','0.1.0.dev12','0.1.0.dev13','0.1.0.dev14','0.1.0.dev15','0.1.0.dev16','0.1.0.dev17','0.1.0.dev18']) {
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

for (const context_tokens of [undefined, 8192]) {
  const expected = context_tokens ?? 32768;
  test(`repair journals frozen ${expected} context and asserts it in runner argv`, async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'rentgen-repair-context-'));
    const selectedConfig = context_tokens === undefined ? {...config} : {...config, context_tokens};
    let args, executions = 0;
    const runner = {dispose(){}, async execute(_, value) { executions++; args = value; return {code:1}; }};
    const service = createRepairService({root, extensionRoot:root, config:selectedConfig, client:{}, runnerFactory:()=>runner});
    selectedConfig.context_tokens = 16384;
    const run = await service.start(ref, {model:'qwen3.5:9b', instruction:'Fix'});
    const request = JSON.parse(await fs.readFile(path.join(root, 'repair-runs', run.id, 'request.json'), 'utf8'));
    assert.equal(request.context_tokens, expected);
    assert.equal(args.filter(value => value === '--context-tokens').length, 1);
    assert.equal(args[args.indexOf('--context-tokens')+1], String(expected));
    assert.equal(executions, 1);
    service.dispose();
  });
}

test('legacy request without context remains inspectable without a retrospective claim or replay', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'rentgen-repair-legacy-context-'));
  const operation = randomUUID(), draft = randomUUID(); let executions = 0;
  const saved = {project_id:project, draft_id:draft, revision:2, operation_id:operation, source_ref:ref, proposal_content_id:'c'.repeat(64)};
  const runner = {dispose(){}, async execute(_, args) {
    executions++;
    const output = args[args.indexOf('--output')+1]; await fs.mkdir(output);
    await fs.writeFile(path.join(output, 'events.jsonl'), JSON.stringify({phase:'edit_requested', project_id:project, draft_id:draft, operation_id:operation})+'\n');
    throw new Error('CLI_DISPOSED');
  }};
  const client = {async receipt(id) { assert.equal(id, operation); return saved; }};
  const service = createRepairService({root, extensionRoot:root, config, client, runnerFactory:()=>runner});
  const run = await service.start(ref, {model:'qwen3.5:9b', instruction:'Fix'});
  assert.equal(run.status, 'saved_unverified'); service.dispose();
  const file = path.join(root, 'repair-runs', run.id, 'request.json');
  const journal = JSON.parse(await fs.readFile(file, 'utf8'));
  delete journal.context_tokens; await fs.writeFile(file, JSON.stringify(journal));
  const reopened = createRepairService({root, extensionRoot:root, config:{...config, context_tokens:8192}, client,
    runnerFactory:()=>{throw new Error('Legacy reconciliation must not replay');}});
  const rows = await reopened.list();
  assert.equal(rows.length, 1); assert.equal(Object.hasOwn(rows[0], 'context_tokens'), false);
  const recovered = await reopened.reconcile(run.id);
  assert.equal(recovered.status, 'saved_unverified'); assert.deepEqual(recovered.receipt, saved);
  assert.equal(executions, 1); reopened.dispose();
});

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

test('clean analysis requires matching model context, saved bytes, coverage and receipt', async () => {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'rentgen-repair-binding-'));
  const operation=randomUUID(), draft=randomUUID(), candidate='\uFEFFПроцедура Проверка()\r\nКонецПроцедуры\r\n';
  const saved={project_id:project,draft_id:draft,operation_id:operation,revision:2,source_ref:ref,proposal_content_id:'c'.repeat(64)};
  const digest=createHash('sha256').update(candidate,'utf8').digest('hex');
  const report={status:'analysis_clean',receipt:saved,candidate_sha256:digest,model:{num_ctx:32768},tests:{status:'not_run'},apply:{status:'unavailable'},
    after:{receipt:saved,diagnostic:{source_ref:ref,proposal_content_id:saved.proposal_content_id,evidence:'ephemeral_unattested',
      analysis:{candidate_sha256:digest,status:'completed',exit_code:0,runtime_verified:true,diagnostics_complete:true,coverage:'exact_one',diagnostics:[]}}}};
  let output, receipt=saved;
  const runner={dispose(){},async execute(_,args){output=args[args.indexOf('--output')+1];await fs.mkdir(output);
    await fs.writeFile(path.join(output,'events.jsonl'),JSON.stringify({phase:'edit_requested',project_id:project,draft_id:draft,operation_id:operation})+'\n');
    await fs.writeFile(path.join(output,'result.json'),JSON.stringify(report));return {code:0};}};
  const client={receipt:async()=>receipt,draft:async()=>({receipt:saved,text:candidate})};
  const service=createRepairService({root,extensionRoot:root,config,client,runnerFactory:()=>runner});
  const run=await service.start(ref,{model:'qwen3.5:9b',instruction:'Fix'});assert.equal(run.status,'analysis_clean');
  report.model.num_ctx=8192;
  await fs.writeFile(path.join(output,'result.json'),JSON.stringify(report));
  const wrongContext=await service.reconcile(run.id);
  assert.equal(wrongContext.status,'saved_unverified');assert.deepEqual(wrongContext.receipt,saved);
  delete report.model;
  await fs.writeFile(path.join(output,'result.json'),JSON.stringify(report));
  assert.equal((await service.reconcile(run.id)).status,'saved_unverified');
  report.model={num_ctx:32768};
  report.candidate_sha256='d'.repeat(64);
  await fs.writeFile(path.join(output,'result.json'),JSON.stringify(report));
  assert.equal((await service.reconcile(run.id)).status,'saved_unverified');
  report.candidate_sha256=digest;report.after.diagnostic.analysis.diagnostics_complete=false;
  await fs.writeFile(path.join(output,'result.json'),JSON.stringify(report));
  assert.equal((await service.reconcile(run.id)).status,'saved_unverified');
  receipt={...saved,operation_id:randomUUID()};await assert.rejects(service.reconcile(run.id),/REPAIR_RECEIPT_MISMATCH/);
  service.dispose();
});
