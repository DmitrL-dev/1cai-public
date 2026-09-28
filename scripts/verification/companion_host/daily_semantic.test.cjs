'use strict';
// Every report, receipt and journal here is constructed; this suite launches no runtime.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {createHash}=require('node:crypto');
const {createDailySemantic}=require('./daily_semantic.cjs');
const {validateTests}=require('../../../integrations/vscode-rentgen/lib/tests-result.cjs');
const {sourceRef}=require('../../../integrations/vscode-rentgen/lib/core.cjs');
const semantic=createDailySemantic({validateTests,sourceRef});
const {selectedRepairVerdict}=semantic;
const project='11111111-1111-4111-8111-111111111111';
const draft='22222222-2222-4222-8222-222222222222';
const operation='33333333-3333-4333-8333-333333333333';
const source_ref={snapshot:{project_id:project,snapshot_id:'1'.repeat(64),manifest_hash:'1'.repeat(64)},layer_id:'base',relative_path:'CommonModules/RentgenPlatformProbe/Ext/Module.bsl',raw_sha256:'2'.repeat(64)};
const ai={project_id:project,draft_id:draft,operation_id:operation,revision:2,source_ref,proposal_content_id:'3'.repeat(64),action:'draft.saved',outcome:'committed',status:'active',recorded_at:'2026-01-01T00:00:00Z',actor:{id:'constructed',authority:'local_os'},title:'Constructed AI receipt'};
const manual={...structuredClone(ai),revision:3,operation_id:'44444444-4444-4444-8444-444444444444',proposal_content_id:'4'.repeat(64),title:'Constructed manual control'};
const aiHash='a'.repeat(64),manualHash='d'.repeat(64);
const hash=file=>createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const profile={profile_id:'b'.repeat(64),name:'Constructed immutable profile contract',enabled:true,
 modules:[{name:'ЮТРентгенПроверка',sha256:hash(path.join(__dirname,'../../../packaging/test-profiles/yaxunit-25.12/ОшибкаЗаписи.bsl')),tests:['ОшибкаЗаписиПередается']}]};
function phase(outcome) {
  const count={tests:1,passed:0,failures:0,errors:0,skipped:0};
  count[{passed:'passed',failure:'failures',error:'errors',skipped:'skipped'}[outcome]]=1;
  return {status:count.failures||count.errors?'failed':count.skipped?'incomplete':'passed',module_text_verified:true,counts:count,
    cases:[{classname:'ЮТРентгенПроверка.ОшибкаЗаписиПередается',name:'ОшибкаЗаписиПередается',context:'Сервер',outcome}]};
}
function input(receipt=ai,candidateHash=aiHash,outcome='failure') {
  const run='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
  return {repairReceipt:structuredClone(receipt),selectedReceipt:structuredClone(receipt),
    proposal:{content_id:receipt.proposal_content_id,replacement:{raw_sha256:candidateHash}},profile:structuredClone(profile),
    result:{run_id:run,status:'completed',report:{schema:1,run_id:run,source_ref:structuredClone(receipt.source_ref),
      proposal_content_id:receipt.proposal_content_id,candidate_sha256:candidateHash,profile_id:profile.profile_id,
      report_sha256:'c'.repeat(64),apply:{status:'unavailable'},evidence:'local_unattested',runtime_dependencies:'not_fully_pinned',
      tests:{isolated_infobases:true,status:phase(outcome).status,baseline:phase('failure'),candidate:phase(outcome)},
      fixture_origin:'constructed_for_contract_only'}}};
}
test('constructed candidate failure remains failed for the exact constructed AI revision',()=>{
  const result=selectedRepairVerdict(input());assert.equal(result.semantic_verdict,'failed');assert.equal(result.revision,2);
});
test('constructed manual positive control is admitted separately from the AI revision',()=>{
  const result=selectedRepairVerdict(input(manual,manualHash,'passed'));assert.equal(result.semantic_verdict,'passed');assert.equal(result.revision,3);
});
test('manual revision cannot replace the selected AI revision',()=>{
  const value=input();value.selectedReceipt=manual;assert.throws(()=>selectedRepairVerdict(value),/DAILY_AI_REVISION_MISMATCH/);
});
for (const [name,mutate] of [
  ['foreign proposal',v=>v.result.report.proposal_content_id=manual.proposal_content_id],
  ['foreign candidate bytes',v=>v.result.report.candidate_sha256=manualHash],
  ['foreign immutable profile',v=>v.result.report.profile_id='d'.repeat(64)],
  ['foreign snapshot',v=>v.result.report.source_ref.snapshot.snapshot_id='e'.repeat(64)],
  ['missing expected oracle case',v=>v.result.report.tests.candidate.cases=[]],
  ['counts do not match actual listed cases',v=>v.result.report.tests.candidate.counts.failures=0]
]) test('refuses '+name,()=>{const value=input();mutate(value);assert.throws(()=>selectedRepairVerdict(value),/TEST_RESULT_MISMATCH/);});
test('compilation-only not_run cannot establish functional success',()=>{
  const value=input();value.result.report.tests.candidate={status:'not_run',reason:'compiler_diagnostics'};value.result.report.tests.status='not_run';
  assert.equal(selectedRepairVerdict(value).semantic_verdict,'unproven');
});
test('skipped oracle case cannot establish functional success',()=>{
  const value=input(ai,aiHash,'skipped');assert.equal(selectedRepairVerdict(value).semantic_verdict,'unproven');
});
test('a passed baseline is not a demonstrated negative control',()=>{
  const value=input(manual,manualHash,'passed');value.result.report.tests.baseline=phase('passed');
  assert.equal(selectedRepairVerdict(value).semantic_verdict,'unproven');
});
test('native infrastructure error is not a semantic failure',()=>{
  const value=input();value.result.report.tests.baseline=phase('error');assert.equal(selectedRepairVerdict(value).semantic_verdict,'unproven');
});
test('candidate framework error is not a semantic failure',()=>{
  const value=input(ai,aiHash,'error');assert.equal(selectedRepairVerdict(value).semantic_verdict,'unproven');
});
for(const status of ['failed','incomplete'])test('unfinished execution '+status+' is unproven',()=>{
  const value=input();value.result.status=status;const result=selectedRepairVerdict(value);assert.equal(result.contract_admitted,false);assert.equal(result.semantic_verdict,'unproven');
});

function historyApi(pages, selected=ai) {
 let calls=0;const seen=[];
 return {seen,get calls(){return calls;},drafts:async()=>[{kind:'draft',receipt:manual,token:'root'}],
 history:async(token,more)=>{seen.push([token,more]);return pages[Math.min(calls++,pages.length-1)];},
 selectedDraft:token=>{assert.equal(token,'ai-version');return structuredClone(selected);}};
}
const version=(receipt,token='ai-version')=>({kind:'version',receipt:structuredClone(receipt),token});
test('history selects full AI receipt after a later manual row on an earlier page',async()=>{
 const api=historyApi([[version(manual,'manual'),{kind:'moreHistory'}],[version(manual,'manual'),version(ai)]]);
 const row=await semantic.selectRepairRevision(api,ai);assert.deepEqual(row.receipt,ai);assert.equal(row.token,'ai-version');assert.deepEqual(api.seen,[['root',false],['root',true]]);
});
test('missing exact AI receipt refuses selection',async()=>{
 await assert.rejects(semantic.selectRepairRevision(historyApi([[version(manual,'manual')]]),ai),/DAILY_AI_REVISION_UNAVAILABLE/);
});
test('duplicate exact AI receipts refuse selection',async()=>{
 await assert.rejects(semantic.selectRepairRevision(historyApi([[version(ai),version(ai,'duplicate')]]),ai),/DAILY_AI_REVISION_AMBIGUOUS/);
});
test('receipt with same CID and revision but a foreign operation is not selected',async()=>{
 const foreign={...ai,operation_id:manual.operation_id};await assert.rejects(semantic.selectRepairRevision(historyApi([[version(foreign)]]),ai),/DAILY_AI_REVISION_UNAVAILABLE/);
});
test('stale minted version token refuses before any test execution',async()=>{
 await assert.rejects(semantic.selectRepairRevision(historyApi([[version(ai)]],manual),ai),/DAILY_AI_REVISION_MISMATCH/);
});
test('history pagination is bounded at forty pages',async()=>{
 const api=historyApi([[{kind:'moreHistory'}]]);await assert.rejects(semantic.selectRepairRevision(api,ai),/DAILY_HISTORY_LIMIT/);assert.equal(api.calls,40);
});
test('a lost response uses only one newly saved matching request, never an older run',()=>{
 const before=[{id:'old',profile_id:profile.profile_id}],after=[...before,{id:'new',profile_id:profile.profile_id},{id:'unrelated',profile_id:'e'.repeat(64)}];
 assert.equal(semantic.uniqueNewRun(before,after,r=>r.profile_id===profile.profile_id).id,'new');
 assert.equal(semantic.uniqueNewRun(before,before,r=>r.profile_id===profile.profile_id),null);
});
test('several new matching requests refuse recovery',()=>{
 assert.throws(()=>semantic.uniqueNewRun([],[{id:'one'},{id:'two'}],()=>true),/DAILY_RUN_AMBIGUOUS/);
});
function originInput(){
 const request={id:'55555555-5555-4555-8555-555555555555',project_id:project,source_ref:structuredClone(source_ref),model:'constructed:model'};
 const start='66666666-6666-4666-8666-666666666666',created={...structuredClone(ai),revision:1,operation_id:start,proposal_content_id:'5'.repeat(64)};
 const metrics={model:request.model,done:true,done_reason:'stop',request_bytes:3,response_bytes:9,response_sha256:'9'.repeat(64)};
 const before={receipt:structuredClone(created)};
 const report={receipt:structuredClone(ai),status:'analysis_clean',candidate_sha256:aiHash,model:structuredClone(metrics),before,after:{receipt:structuredClone(ai)}};
 const events=[{phase:'start_requested',project_id:project,draft_id:draft,operation_id:start,source_ref:structuredClone(source_ref)},
  {phase:'draft_created',receipt:created},{phase:'baseline_checked',check:structuredClone(before)},{phase:'model_requested',candidate_sha256:source_ref.raw_sha256},
  {phase:'model_responded',metrics},{phase:'edit_requested',project_id:project,draft_id:draft,operation_id:operation,expected_revision:1,candidate_sha256:aiHash},
  {phase:'draft_saved',receipt:structuredClone(ai)},{phase:'finished',status:report.status,receipt:structuredClone(ai)}];
 return {request,events,repair:{id:request.id,status:report.status,receipt:structuredClone(ai),truncated:false},report,proposal:{content_id:ai.proposal_content_id,replacement:{raw_sha256:aiHash}}};
}
test('one complete ordered journal attributes the exact saved candidate to its model attempt',()=>{
 const result=semantic.repairOrigin(originInput());assert.equal(result.ai_origin,'verified');assert.equal(result.model_requests,1);assert.equal(result.model_responses,1);
});
for(const [label,mutate] of [
 ['duplicate model request',v=>v.events.splice(4,0,structuredClone(v.events[3]))],
 ['foreign edit operation',v=>v.events[5].operation_id=manual.operation_id],
 ['candidate SHA drift',v=>v.events[5].candidate_sha256=manualHash],
 ['missing model response',v=>v.events.splice(4,1)],
 ['truncated journal',v=>v.repair.truncated=true]
])test('AI origin remains unproven for '+label,()=>{const value=originInput();mutate(value);assert.equal(semantic.repairOrigin(value).ai_origin,'unproven');});
const baseline='// Preserved comment\nПроцедура СохранитьДокумент(ДокументОбъект) Экспорт\n    Попытка\n        ДокументОбъект.Записать();\n    Исключение\n    КонецПопытки;\nКонецПроцедуры\n';
test('recognized rethrow preserves the fixture through BOM and CRLF conversion',()=>{
 const candidate=baseline.replace('    Исключение\n','    Исключение\n        ВызватьИсключение;\n');assert.equal(semantic.recognizedSafeTransform('\uFEFF'+baseline.replace(/\n/g,'\r\n'),candidate),true);
});
test('recognized direct write preserves the fixture comments and signature',()=>{
 const candidate=baseline.replace('    Попытка\n        ДокументОбъект.Записать();\n    Исключение\n    КонецПопытки;','    ДокументОбъект.Записать();');assert.equal(semantic.recognizedSafeTransform(baseline,candidate),true);
});
test('unfamiliar transform or a baseline without an empty handler remains unrecognized',()=>{
 assert.equal(semantic.recognizedSafeTransform(baseline,baseline.replace('    Исключение\n','    Исключение\n        Сообщить(ОписаниеОшибки());\n')),false);
 assert.equal(semantic.recognizedSafeTransform('НетОбработчика;','НетОбработчика;'),false);
});

for(const [label,id] of [['missing',undefined],['empty',''],['nonstring',{}]])test('completed test with '+label+' UUID cannot establish a semantic pass',()=>{
 const value=input(manual,manualHash,'passed');value.result.run_id=id;value.result.report.run_id=id;
 assert.throws(()=>semantic.selectedRepairVerdict(value),/DAILY_TEST_RUN_INVALID/);
});
test('missing equal proposal IDs cannot establish a semantic pass',()=>{
 const value=input(manual,manualHash,'passed');delete value.repairReceipt.proposal_content_id;delete value.selectedReceipt.proposal_content_id;delete value.proposal.content_id;delete value.result.report.proposal_content_id;
 assert.throws(()=>semantic.selectedRepairVerdict(value),/DAILY_AI_RECEIPT_INVALID/);
});
test('malformed source hash cannot establish a semantic pass',()=>{
 const value=input(manual,manualHash,'passed');value.repairReceipt.source_ref.raw_sha256='invalid';value.selectedReceipt.source_ref.raw_sha256='invalid';value.result.report.source_ref.raw_sha256='invalid';
 assert.throws(()=>semantic.selectedRepairVerdict(value));
});
for(const [label,mutate] of [
 ['missing equal run IDs',v=>{delete v.request.id;delete v.repair.id;}],
 ['missing equal model names',v=>{delete v.request.model;delete v.events[4].metrics.model;delete v.report.model.model;}],
 ['truncated model completion',v=>{v.events[4].metrics.done_reason='length';v.report.model.done_reason='length';}],
 ['missing model completion reason',v=>{delete v.events[4].metrics.done_reason;delete v.report.model.done_reason;}],
 ['malformed equal edit operation IDs',v=>{for(const receipt of [v.repair.receipt,v.report.receipt,v.report.after.receipt,v.events[6].receipt,v.events[7].receipt])receipt.operation_id='invalid';v.events[5].operation_id='invalid';}]
])test('AI origin remains unproven for '+label,()=>{const value=originInput();mutate(value);assert.equal(semantic.repairOrigin(value).ai_origin,'unproven');});
const earlierHandler='Попытка\n    ВыполнитьДругуюОперацию();\n    Исключение\n        Сообщить(ОписаниеОшибки());\nКонецПопытки;\n';
test('a rethrow in a different earlier handler does not repair the target empty handler',()=>{
 const original=earlierHandler+baseline,candidate=original.replace('    Исключение\n','    Исключение\n        ВызватьИсключение;\n');
 assert.equal(semantic.recognizedSafeTransform(original,candidate),false);
});
test('target-local rethrow is recognized even with a different earlier handler',()=>{
 const candidate=earlierHandler+baseline.replace('    Исключение\n','    Исключение\n        ВызватьИсключение;\n');
 assert.equal(semantic.recognizedSafeTransform(earlierHandler+baseline,candidate),true);
});

test('JSON-decoded array response digest cannot establish AI origin',()=>{
 const value=originInput();value.events[4].metrics.response_sha256=['9'.repeat(64)];value.report.model.response_sha256=['9'.repeat(64)];
 assert.equal(semantic.repairOrigin(JSON.parse(JSON.stringify(value))).ai_origin,'unproven');
});
test('shared array candidate digest cannot establish AI origin',()=>{
 const value=originInput(),digest=[aiHash];value.proposal.replacement.raw_sha256=digest;value.report.candidate_sha256=digest;value.events[5].candidate_sha256=digest;
 assert.equal(semantic.repairOrigin(value).ai_origin,'unproven');
});

function arraySourcePins(value,field){
 const decoded=JSON.parse(JSON.stringify(value));
 function walk(item){if(!item||typeof item!=='object')return;for(const [key,child]of Object.entries(item)){if(key==='source_ref'){const target=field==='raw_sha256'?child:child.snapshot;target[field]=[target[field]];}else walk(child);}}
 walk(decoded);return JSON.parse(JSON.stringify(decoded));
}
for(const field of ['snapshot_id','manifest_hash','raw_sha256'])test('JSON-decoded source '+field+' array cannot establish a semantic pass',()=>{
 assert.throws(()=>semantic.selectedRepairVerdict(arraySourcePins(input(manual,manualHash,'passed'),field)),/DAILY_SOURCE_REF_INVALID/);
});
for(const field of ['snapshot_id','manifest_hash'])test('JSON-decoded source '+field+' array cannot establish AI origin',()=>{
 assert.equal(semantic.repairOrigin(arraySourcePins(originInput(),field)).ai_origin,'unproven');
});
