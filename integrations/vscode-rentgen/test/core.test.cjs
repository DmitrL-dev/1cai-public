'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { createClient, sourceText, draftText, profileConfig } = require('../lib/core.cjs');
const project = '00000000-0000-4000-8000-000000000001';
const draft = '00000000-0000-4000-8000-000000000002';
const bytes = Buffer.from('\uFEFFПроцедура Проверка()\r\nКонецПроцедуры\r\n');
const hash = createHash('sha256').update(bytes).digest('hex');
const ref = {snapshot: {project_id: project, snapshot_id: 'a'.repeat(64), manifest_hash: 'a'.repeat(64)}, layer_id: 'base', relative_path: 'Модуль $(not-code).bsl', raw_sha256: hash};
const config = {schema: 1, python: "C:\\путь ' $()\\python.exe", registry: 'C:\\registry.sqlite3', project_id: project, core_version: '0.1.0.dev4'};
const output = value => ({code: 0, stdout: Buffer.from(JSON.stringify({result: value}))});

test('a profile without context_tokens resolves to the legacy 32768 context', () => {
  assert.equal(profileConfig(config).context_tokens, 32768);
});

for (const context_tokens of [8192, 16384, 32768]) {
  test(`profile retains explicit context_tokens=${context_tokens}`, () => {
    assert.equal(profileConfig({...config, context_tokens}).context_tokens, context_tokens);
  });
}

for (const context_tokens of [true, false, '8192', 8192.5, null, 0, 4096, 65536, [], {}]) {
  test(`profile rejects invalid context_tokens=${JSON.stringify(context_tokens)}`, () => {
    assert.throws(() => profileConfig({...config, context_tokens}), /INVALID_EDITOR_PROFILE/);
  });
}

test('an unqualified future core profile is refused', () => {
  assert.throws(() => createClient({...config, core_version: '0.1.0.dev999'}, {execute: async () => output({})}), /INVALID_EDITOR_PROFILE/);
});

test('source text preserves BOM/CRLF and rejects altered bytes or reference', () => {
  const value = {ref, raw_sha256: hash, size_bytes: bytes.length, encoding: 'base64', data: bytes.toString('base64')};
  assert.equal(sourceText(value, ref), bytes.toString('utf8'));
  assert.throws(() => sourceText({...value, data: '%%%not-base64'}, ref));
  assert.throws(() => sourceText({...value, size_bytes: bytes.length + 1}, ref));
  assert.throws(() => sourceText({...value, ref: {...ref, layer_id: 'other'}}, ref));
  const invalid = Buffer.from([0xff]);
  const badHash = createHash('sha256').update(invalid).digest('hex');
  assert.throws(() => sourceText({...value, ref: {...ref, raw_sha256: badHash}, raw_sha256: badHash, data: '/w==', size_bytes: 1}, {...ref, raw_sha256: badHash}));
});

test('draft binds requested identity/revision, original ref and replacement hash', () => {
  const receipt = {project_id: project, draft_id: draft, revision: 2, source_ref: ref, proposal_content_id: 'b'.repeat(64)};
  const proposal = {content_id: 'b'.repeat(64), source_ref: ref, original: {raw_sha256: hash}, replacement: {base64: bytes.toString('base64'), raw_sha256: hash, size_bytes: bytes.length}};
  const value = {receipt, proposal};
  assert.equal(draftText(value, project, draft, 2), bytes.toString('utf8'));
  assert.throws(() => draftText(value, project, draft, 1));
  assert.throws(() => draftText({...value, proposal: {...proposal, source_ref: {...ref, relative_path: 'other.bsl'}}}, project, draft, 2));
});

test('no process is started without trust or for foreign source/project', async () => {
  let starts = 0;
  const execute = async () => { starts++; return output({}); };
  const denied = createClient(config, {execute, trusted: () => false});
  await assert.rejects(denied.head(), /TRUST_REQUIRED/);
  const client = createClient(config, {execute});
  await assert.rejects(client.source({...ref, snapshot: {...ref.snapshot, project_id: draft}}), /PROJECT_MISMATCH/);
  assert.equal(starts, 0);
});

test('literal argv uses explicit snapshot and never a shell/output file', async () => {
  let seen;
  const client = createClient(config, {execute: async (command, args) => { seen = {command, args}; return output({ref, raw_sha256: hash, size_bytes: bytes.length, encoding: 'base64', data: bytes.toString('base64')}); }});
  assert.equal(await client.source(ref), bytes.toString('utf8'));
  assert.equal(seen.command, config.python);
  assert.deepEqual(seen.args, ['-I', '-m', 'rentgen_core', 'source-read', '--registry', config.registry, '--project', project, '--snapshot', ref.snapshot.snapshot_id, '--layer=base', '--path='+ref.relative_path, '--base64']);
});

test('queued read rechecks trust after earlier process and after output', async () => {
  let trusted = true, complete, starts = 0;
  const client = createClient(config, {trusted: () => trusted, execute: () => { starts++; return new Promise(resolve => { complete = resolve; }); }});
  const first = client.head(); const second = client.head();
  await new Promise(resolve => setImmediate(resolve));
  trusted = false; complete(output({project_id: project, snapshot: null}));
  await assert.rejects(first, /TRUST_REQUIRED/);
  await assert.rejects(second, /TRUST_REQUIRED/);
  assert.equal(starts, 1);
});

test('malformed or failed CLI output never becomes a successful result', async () => {
  for (const reply of [{code: 0, stdout: Buffer.from('not json')}, {code: 2, stdout: Buffer.from('{"result":{}}')}, {code: 0, stdout: Buffer.from([0xff])}]) {
    const client = createClient(config, {execute: async () => reply});
    await assert.rejects(client.head());
  }
});

test('receipt lookup uses literal operation identity and refuses a foreign reply', async () => {
  const operation = '00000000-0000-4000-8000-000000000003';
  let reply = null, seen;
  const client = createClient(config, {execute:async (_,args)=>{seen=args;return output(reply);}});
  assert.equal(await client.receipt(operation),null);
  assert.deepEqual(seen.slice(3),['draft-receipt','--registry',config.registry,'--project',project,'--operation-id',operation]);
  const saved = {project_id:project,draft_id:draft,revision:2,source_ref:ref,proposal_content_id:'b'.repeat(64),operation_id:operation};
  reply = saved; assert.deepEqual(await client.receipt(operation),saved);
  reply = {...saved,operation_id:draft}; await assert.rejects(client.receipt(operation));
  reply = {...saved,project_id:draft}; await assert.rejects(client.receipt(operation));
});

test('native result lookup is a read without snapshot or executable and rejects foreign results',async()=>{
  const id='00000000-0000-4000-8000-000000000003';let seen;
  let reply={run_id:id,request:null,status:'incomplete'};
  const client=createClient({...config,core_version:'0.1.0.dev8'},{execute:async(_,args)=>{seen=args;return output(reply);}});
  assert.deepEqual(await client.platformResult(id),reply);
  assert.deepEqual(seen.slice(3),['proposal-platform-result','--registry',config.registry,'--project',project,'--operation-id',id]);
  reply={...reply,status:'completed',report:{run_id:id,report_sha256:'b'.repeat(64),source_ref:{...ref,snapshot:{...ref.snapshot,project_id:draft}}}};
  await assert.rejects(client.platformResult(id),/PROJECT_MISMATCH/);
  reply={run_id:draft,request:null,status:'incomplete'};
  await assert.rejects(client.platformResult(id),/PLATFORM_RESULT_MISMATCH/);
});

for (const core_version of ['0.1.0.dev9','0.1.0.dev10','0.1.0.dev11','0.1.0.dev12','0.1.0.dev13','0.1.0.dev14','0.1.0.dev15','0.1.0.dev16','0.1.0.dev17','0.1.0.dev18']) test(`${core_version} profile can use native result lookup and test profile listing`,async()=>{
  const id='00000000-0000-4000-8000-000000000003';
  const commands=[];
  const client=createClient({...config,core_version},{execute:async(_,args)=>{
    commands.push(args[3]);
    return output(args[3]==='proposal-platform-result'?{run_id:id,request:null,status:'incomplete'}:[]);
  }});
  assert.equal((await client.platformResult(id)).status,'incomplete');
  assert.deepEqual(await client.testProfiles(),[]);
  assert.deepEqual(commands,['proposal-platform-result','test-profile-list']);
});

for (const core_version of ['0.1.0.dev8', '0.1.0.dev18']) test(`${core_version}: native check binds selected snapshot, proposal and executable; old profiles cannot launch it`,async()=>{
  const options={id:draft,ref,contentId:'b'.repeat(64),proposal:'C:\\путь $()\\proposal.json',platform:'C:\\1cv8.exe',platformHash:'c'.repeat(64)};
  let seen,reply={run_id:draft,source_ref:ref,proposal_content_id:options.contentId,platform_executable_sha256:options.platformHash};
  const execute=async(_,args)=>{seen=args;return output(reply);};
  await assert.rejects(createClient(config,{execute}).platformCheck(options),/PLATFORM_REQUIRES_DEV8/);assert.equal(seen,undefined);
  const client=createClient({...config,core_version},{execute});
  assert.deepEqual(await client.platformCheck(options),reply);
  assert.equal(seen[3],'proposal-platform-check');assert.equal(seen[seen.indexOf('--snapshot')+1],ref.snapshot.snapshot_id);
  reply={...reply,proposal_content_id:'d'.repeat(64)};
  await assert.rejects(client.platformCheck(options),/PLATFORM_RESULT_MISMATCH/);
});

test('manual publication binds expected revision and operation; foreign receipt is refused',async()=>{
  const base={project_id:project,draft_id:draft,revision:2,title:'Правка',source_ref:ref,proposal_content_id:'b'.repeat(64)};
  const operation='00000000-0000-4000-8000-000000000003';let args;
  let reply={...base,revision:3,operation_id:operation,proposal_content_id:'c'.repeat(64)};
  const client=createClient({...config,core_version:'0.1.0.dev8'},{execute:async(_,value)=>{args=value;return output(reply);}});
  assert.deepEqual(await client.saveDraft(base,'C:\\owned\\proposal.json','c'.repeat(64),operation),reply);
  assert.equal(args[3],'draft-save');assert.equal(args[args.indexOf('--expected-revision')+1],'2');
  assert.equal(args[args.indexOf('--operation-id')+1],operation);
  reply={...reply,revision:4};await assert.rejects(client.saveDraft(base,'C:\\owned\\proposal.json','c'.repeat(64),operation),/DRAFT_REVISION_MISMATCH/);
});

for (const core_version of ['0.1.0.dev8', '0.1.0.dev17', '0.1.0.dev18']) test(`${core_version}: saved test result lookup retains exact operation binding`, async () => {
  const id='00000000-0000-4000-8000-000000000003';
  let args, reply={run_id:id,status:'incomplete',request:null};
  const client=createClient({...config,core_version},{execute:async(_,argv)=>{args=argv;return output(reply);}});
  assert.deepEqual(await client.testResult(id),reply);
  assert.deepEqual(args.slice(3),['proposal-test-result','--registry',config.registry,'--project',project,'--operation-id',id]);
  reply={...reply,run_id:draft};
  await assert.rejects(client.testResult(id),/TEST_RESULT_MISMATCH/);
});

test('first manual draft uses explicit source, draft and operation with revision zero',async()=>{
 const operation='00000000-0000-4000-8000-000000000003',title='Первая ручная правка',content='c'.repeat(64);let seen;
 let reply={project_id:project,draft_id:draft,revision:1,title,source_ref:ref,proposal_content_id:content,operation_id:operation,
  outcome:'committed',action:'draft.saved',status:'active'};
 const client=createClient({...config,core_version:'0.1.0.dev17'},{execute:async(_,args)=>{seen=args;return output(reply);}});
 assert.deepEqual(await client.createDraft(ref,draft,title,'C:\\owned\\proposal.json',content,operation),reply);
 assert.deepEqual(seen.slice(3),['draft-save','--registry',config.registry,'--project',project,'--draft-id',draft,'--operation-id',operation,
  '--expected-revision','0','--snapshot',ref.snapshot.snapshot_id,'--proposal-json','C:\\owned\\proposal.json','--title='+title]);
 const good=reply;
 for(const changed of [{revision:0},{revision:2},{operation_id:draft},{draft_id:operation},{proposal_content_id:'d'.repeat(64)},
  {title:'other'},{outcome:'unknown'},{action:'draft.archived'},{status:'archived'},{source_ref:{...ref,relative_path:'other.bsl'}}]){
  reply={...good,...changed};await assert.rejects(client.createDraft(ref,draft,title,'C:\\owned\\proposal.json',content,operation));
 }
});

test('first manual draft rejects invalid titles, paths and selectors before starting CLI',async()=>{
 let calls=0;const client=createClient({...config,core_version:'0.1.0.dev17'},{execute:async()=>{calls++;return output({});}});
 const operation='00000000-0000-4000-8000-000000000003',content='c'.repeat(64);
 for(const title of ['', ' ', '\n', '\u202eunsafe', 'x'.repeat(241), '\ud800']){
  await assert.rejects(client.createDraft(ref,draft,title,'C:\\owned\\proposal.json',content,operation),/INVALID_DRAFT_TITLE/);
 }
 await assert.rejects(client.createDraft(ref,draft,'Title','relative.json',content,operation),/INVALID_EDIT_PATH/);
 await assert.rejects(client.createDraft(ref,'not-a-uuid','Title','C:\\owned\\proposal.json',content,operation));
 await assert.rejects(client.createDraft({...ref,snapshot:{...ref.snapshot,project_id:draft}},draft,'Title','C:\\owned\\proposal.json',content,operation),/PROJECT_MISMATCH/);
 assert.equal(calls,0);
});

test('option-like module locators and draft titles stay literal CLI values',async()=>{
 const source={...ref,layer_id:'--help',relative_path:'--Module.bsl'},operation='00000000-0000-4000-8000-000000000003',content='c'.repeat(64);
 let seen,reply={ref:source,raw_sha256:hash,size_bytes:bytes.length,encoding:'base64',data:bytes.toString('base64')};
 const client=createClient({...config,core_version:'0.1.0.dev17'},{execute:async(_,args)=>{seen=args;return output(reply);}});
 assert.equal(await client.source(source),bytes.toString('utf8'));
 assert.ok(seen.includes('--layer=--help'));assert.ok(seen.includes('--path=--Module.bsl'));assert.equal(seen.includes('--help'),false);
 for(const title of ['--help','--snapshot','-Правка',' title with spaces ']){
  reply={project_id:project,draft_id:draft,revision:1,title,source_ref:ref,proposal_content_id:content,operation_id:operation,
   outcome:'committed',action:'draft.saved',status:'active'};
  await client.createDraft(ref,draft,title,'C:\\owned\\proposal.json',content,operation);
  assert.ok(seen.includes('--title='+title));assert.equal(seen.includes('--title'),false);
  const base=reply;reply={...base,revision:2};
  await client.saveDraft(base,'C:\\owned\\proposal.json',content,operation);
  assert.ok(seen.includes('--title='+title));assert.equal(seen.includes('--title'),false);
 }
});

test('leading-dash module searches remain literal query values',async()=>{
 let seen;const client=createClient(config,{execute:async(_,args)=>{seen=args;return output({entries:[],next_cursor:null});}});
 for(const query of ['--help','--kind','-Module.bsl','name with spaces']){
  assert.deepEqual(await client.sources(ref.snapshot,{query}),{entries:[],next_cursor:null});
  assert.ok(seen.includes('--query='+query));assert.equal(seen.includes('--query'),false);
  assert.equal(seen[seen.indexOf('--kind')+1],'module');assert.equal(seen[seen.indexOf('--limit')+1],'100');
 }
 await client.sources(ref.snapshot,{query:''});assert.equal(seen.some(value=>value.startsWith('--query')),false);
});
