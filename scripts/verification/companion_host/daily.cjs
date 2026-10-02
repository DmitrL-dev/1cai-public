'use strict';
// One attempt per new owned profile. Native/raw acceptance is qualified separately.
const vscode=require('vscode'),fs=require('node:fs/promises'),path=require('node:path');
const assert=require('node:assert/strict'),{createHash}=require('node:crypto');
const {promisify,isDeepStrictEqual:same}=require('node:util');
const execute=promisify(require('node:child_process').execFile);
const {createDailySemantic}=require('./daily_semantic.cjs');
const {makeReadyIntent}=require('./daily_ready_intent.cjs');
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const validUuid=value=>typeof value==='string'&&uuid.test(value);
const hash=/^[0-9a-f]{64}$/;
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const decode=bytes=>new TextDecoder('utf-8',{fatal:true}).decode(bytes);
function resolvedContext(value){
 const context=Object.hasOwn(value,'context_tokens')?value.context_tokens:32768;
 assert.ok(Number.isInteger(context)&&[8192,16384,32768].includes(context),'DAILY_CONTEXT_INVALID');
 return context;
}
function matchingContext(config,scenario){
 const context=resolvedContext(config);
 assert.equal(resolvedContext(scenario),context,'DAILY_CONTEXT_MISMATCH');
 return context;
}
async function read(file,limit,optional=false){
 let handle;
 try{
  const stat=await fs.lstat(file);
  assert.ok(stat.isFile()&&!stat.isSymbolicLink()&&stat.size<=limit,'DAILY_INPUT_LIMIT');
  assert.equal((await fs.realpath(file)).toLowerCase(),path.resolve(file).toLowerCase(),'DAILY_INPUT_PATH');
  handle=await fs.open(file,'r');const bytes=Buffer.alloc(limit+1),{bytesRead}=await handle.read(bytes,0,bytes.length,0);
  assert.ok(bytesRead<=limit,'DAILY_INPUT_LIMIT');return bytes.subarray(0,bytesRead);
 }catch(error){if(optional&&error.code==='ENOENT')return null;throw error;}finally{await handle?.close();}
}
async function json(file,limit=2097152,optional=false){const bytes=await read(file,limit,optional);return bytes===null?null:JSON.parse(decode(bytes));}
async function inventory(root){
 const result={};let count=0;
 async function walk(folder){
  const stat=await fs.lstat(folder);assert.ok(stat.isDirectory()&&!stat.isSymbolicLink(),'DAILY_SOURCE_DIRECTORY');
  for(const entry of await fs.readdir(folder,{withFileTypes:true})){
   assert.ok(!entry.isSymbolicLink(),'DAILY_SOURCE_LINK');const target=path.join(folder,entry.name);
   if(entry.isDirectory())await walk(target);
   else{assert.ok(entry.isFile()&&++count<=512,'DAILY_SOURCE_LIMIT');const bytes=await read(target,2097152);result[path.relative(root,target).split(path.sep).join('/')]={size:bytes.length,sha256:digest(bytes)};}
  }
 }
 await walk(root);return result;
}
function diagnosticVerdict(side,receipt,candidateSha){
 if(!receipt||typeof receipt!=='object'||Array.isArray(receipt)||!receipt.source_ref||typeof receipt.proposal_content_id!=='string'||!hash.test(receipt.proposal_content_id))return {status:'unproven'};
 const d=side?.diagnostic,a=d?.analysis;
 if(!same(side?.receipt,receipt)||!same(d?.source_ref,receipt.source_ref)||d?.proposal_content_id!==receipt.proposal_content_id||
    a?.status!=='completed'||a.exit_code!==0||a.runtime_verified!==true||a.diagnostics_complete!==true||a.coverage!=='exact_one'||a.candidate_sha256!==candidateSha||!Array.isArray(a.diagnostics))return {status:'unproven'};
 return {status:a.diagnostics.length?'diagnostics_present':'clean',diagnostics:a.diagnostics,candidate_sha256:a.candidate_sha256};
}
function compileVerdict(result){
 if(result?.status!=='completed')return {baseline:{status:'unproven'},candidate:{status:'unproven'}};
 const tests=result.report.tests;assert.ok(Array.isArray(tests.steps)&&tests.steps.length<=32,'DAILY_COMPILE_EVIDENCE_MISMATCH');const output={};
 for(const phase of ['baseline','candidate']){
  const steps=tests.steps.filter(step=>step.name===phase+'-compile');assert.equal(steps.length,1,'DAILY_COMPILE_EVIDENCE_MISMATCH');const step=steps[0],ran=tests[phase];
  assert.ok(Number.isSafeInteger(step.exit_code)&&[0,101].includes(step.exit_code),'DAILY_COMPILE_EVIDENCE_MISMATCH');
  for(const field of ['log_sha256','stdout_sha256','stderr_sha256'])assert.ok(typeof step[field]==='string'&&hash.test(step[field]),'DAILY_COMPILE_EVIDENCE_MISMATCH');
  const blocked=ran.status==='not_run'&&ran.reason==='compiler_diagnostics';assert.equal(step.exit_code===101,blocked,'DAILY_COMPILE_EVIDENCE_MISMATCH');
  output[phase]={status:step.exit_code===0?'passed':'diagnostics_present',exit_code:step.exit_code,log_sha256:step.log_sha256,stdout_sha256:step.stdout_sha256,stderr_sha256:step.stderr_sha256,evidence:'producer_report; raw qualification pending'};
 }
 return output;
}
async function evidence(root,repairId,testId,result,errors=null,repair=null){
 const names=[];
 const failed=(name,error)=>{if(errors===null)throw error;errors.push({path:name,type:error.name,code:error.code??null,message:error.message});};
 if(repairId){
  if(!validUuid(repairId))failed('repair-runs',new Error('DAILY_RUN_ID_INVALID'));
  else{
   const base='repair-runs/'+repairId+'/';
   for(const name of ['request.json','source-ref.json','instruction.txt'])names.push([base+name,2097152,true]);
   names.push([base+'result/events.jsonl',2097152,Boolean(repair?.receipt)]);
   names.push([base+'result/result.json',2097152,['analysis_clean','diagnostics_present'].includes(repair?.status)]);
  }
 }
 if(testId){
  if(!validUuid(testId)){failed('test-runs',new Error('DAILY_RUN_ID_INVALID'));testId=null;}
 }
 if(testId){
  for(const name of ['request.json','proposal.json'])names.push(['test-runs/'+testId+'/'+name,2097152,true]);
  const base='state/test-runs/'+testId+'/',terminal=['completed','failed'].includes(result?.status);
  // A saved companion intent can precede Core startup. Its incomplete request=null has no native files yet.
  names.push([base+'request.json',2097152,terminal||result?.request!=null]);
  names.push([base+'report.json',2097152,result?.status==='completed']);
  names.push([base+'failure.json',2097152,result?.status==='failed']);
  for(const phase of ['baseline','candidate']){
   const ran=['passed','failed'].includes(result?.report?.tests?.[phase]?.status);
   for(const name of [phase+'.junit.xml',phase+'.exit',phase+'-settings.json'])names.push([base+name,name.endsWith('.exit')?32:2097152,ran]);
  }
  const steps=result?.report?.tests?.steps??[];
  if(!Array.isArray(steps)||steps.length>32)failed(base,new Error('DAILY_STEP_INVALID'));
  else for(const step of steps){
   if(typeof step?.name!=='string'||!/^[a-z-]{1,64}$/.test(step.name)){failed(base,new Error('DAILY_STEP_INVALID'));continue;}
   // ibcmd produces exactly two streams for these successful extension-properties steps.
   const twoStream=['baseline-extension-properties','candidate-extension-properties'].includes(step.name)&&!Object.prototype.hasOwnProperty.call(step,'log_sha256');
   const fields=twoStream?['stdout_sha256','stderr_sha256']:['log_sha256','stdout_sha256','stderr_sha256'];
   if(!Number.isSafeInteger(step.exit_code)||(twoStream&&step.exit_code!==0)||fields.some(field=>typeof step[field]!=='string'||!hash.test(step[field]))){failed(base+step.name,new Error('DAILY_STEP_INVALID'));continue;}
   for(const suffix of twoStream?['.stdout','.stderr']:['.log','.stdout','.stderr'])names.push([base+step.name+suffix,2097152,true]);
  }
 }
 const output={};for(const [name,limit,required]of names){try{const bytes=await read(path.join(root,name),limit,!required);if(bytes!==null)output[name]={size:bytes.length,sha256:digest(bytes)};}catch(error){failed(name,error);}}
 return output;
}
async function captureAvailableEvidence({root,record}){
 const errors=[],repairId=record.repair_run_id??(validUuid(record.repair?.id)?record.repair.id:null),testId=record.test_run_id??(validUuid(record.test?.run_id)?record.test.run_id:null);
 const verified=record.preservation_verified===true?record.raw_evidence:null;
 record.raw_evidence={};
 try{record.raw_evidence=await evidence(root,repairId,testId,record.test,errors,record.repair);}catch(error){errors.push({path:null,type:error.name,code:error.code??null,message:error.message});}
 if(verified&&!same(verified,record.raw_evidence))errors.push({path:null,type:'Error',code:null,message:'DAILY_RAW_EVIDENCE_CHANGED'});
 if(errors.length){record.raw_evidence_errors=errors;record.preservation_verified=false;record.eligible_for_raw_qualification=false;if(record.recovered===true)record.recovered=false;if(record.status==='collected'){record.status='unproven';record.reason='Raw evidence collection is incomplete or changed';}}else delete record.raw_evidence_errors;
}
async function environment(mode){
 // No authoritative Root editor-owner backend has been qualified yet.
 // Marker/PID/nonce/caller JSON must not authorize activation or a CLI process.
 if(mode==='ready-intent-only')throw new Error('DAILY_ROOT_EDITOR_OWNER_REQUIRED');
 assert.ok(['attempt','recovery'].includes(mode),'DAILY_MODE_INVALID');
 const root=process.env.RENTGEN_EDITOR_PROFILE,out=process.env.RENTGEN_DAILY_OUTPUT,inputFile=process.env.RENTGEN_DAILY_INPUTS;
 assert.ok(root&&out&&inputFile&&path.isAbsolute(root)&&path.isAbsolute(out)&&path.isAbsolute(inputFile),'DAILY_EXPLICIT_INPUTS_REQUIRED');
 assert.equal(Boolean(process.env.RENTGEN_DAILY_PRIOR),mode==='recovery','DAILY_MODE_MISMATCH');
 const scenarioPath=path.join(root,'daily-scenario.json'),profilePath=path.join(root,'profile.json');
 const scenarioBytes=await read(scenarioPath,2097152),profileBytes=await read(profilePath,65536),inputs=await json(inputFile,4194304);
 const scenario=JSON.parse(decode(scenarioBytes)),config=JSON.parse(decode(profileBytes));
 assert.equal(scenario.schema,1);assert.equal(inputs.mode,mode);assert.deepEqual(scenario.frozen_inputs,inputs.manifest);assert.equal(config.core_version,inputs.core_version);assert.equal(scenario.companion_version,inputs.companion_version);assert.equal(config.python,inputs.files.python.path);
 const context_tokens=matchingContext(config,scenario);
 const hasContext=Object.hasOwn(inputs,'context_tokens'),hasProfileFiles=Object.hasOwn(inputs,'daily_profile_files');
 assert.equal(hasContext,hasProfileFiles,'INPUT_BINDING_MISMATCH');
 if(hasContext){
  assert.equal(inputs.context_tokens,context_tokens,'INPUT_BINDING_MISMATCH');
  assert.deepEqual(inputs.daily_profile_files,{
   profile:{path:path.resolve(profilePath),size:profileBytes.length,sha256:digest(profileBytes)},
   scenario:{path:path.resolve(scenarioPath),size:scenarioBytes.length,sha256:digest(scenarioBytes)}
  },'INPUT_BINDING_MISMATCH');
 }
 const extension=vscode.extensions.getExtension('rentgen.project-companion');assert.equal(extension?.packageJSON.version,inputs.companion_version);
 for(const [name,pin]of [['lib/tests-result.cjs',inputs.validator],['lib/core.cjs',inputs.source_validator]]){
  const bytes=await read(path.join(extension.extensionPath,name),2097152);assert.equal(digest(bytes),pin.sha256,'INPUT_BINDING_MISMATCH');assert.equal(bytes.length,pin.size,'INPUT_BINDING_MISMATCH');
 }
 const {validateTests}=require(path.join(extension.extensionPath,'lib/tests-result.cjs'));
 const {sourceRef}=require(path.join(extension.extensionPath,'lib/core.cjs'));
 const semantic=createDailySemantic({validateTests,sourceRef});
 assert.deepEqual(await read(profilePath,65536),profileBytes,'INPUT_BINDING_MISMATCH');
 assert.deepEqual(await read(scenarioPath,2097152),scenarioBytes,'INPUT_BINDING_MISMATCH');
 const api=await extension.activate();assert.equal(api.ready,true);
 const cli=async(command,...extra)=>JSON.parse((await execute(config.python,['-I','-m','rentgen_core',command,'--registry',config.registry,'--project',config.project_id,...extra.map(String)],{windowsHide:true,timeout:30000,maxBuffer:2097153,encoding:'utf8'})).stdout).result;
 const record={schema:'rentgen-daily-semantic/1',mode,profile_root:root,vscode:vscode.version,companion:inputs.companion_version,core:inputs.core_version,inputs,
  input:'registered-command-arguments',manual_picker_tested:false,pipeline_verified:false,task_accepted:false,raw_qualification:'pending',model_quality:{general_verdict:'unproven'},full_product_ready:false,production_deployment:false,repair:null,test:null};
 const progress=()=>fs.writeFile(path.join(path.dirname(out),'progress.json'),JSON.stringify(record,null,2));
 const terminal=()=>fs.writeFile(out,JSON.stringify(record,null,2),{flag:'wx'});
  return {root,out,scenario,config,context_tokens,inputs,extension,semantic,sourceRef,api,cli,record,progress,terminal};
}
async function readyIntentOnly(){
 const env=await environment('ready-intent-only'),{root,out,scenario,config,inputs,sourceRef,api,cli,record,progress,terminal}=env;
 record.preservation_verified=false;record.eligible_for_raw_qualification=false;
 try{
  const context_tokens=matchingContext(config,scenario);
  assert.equal(env.context_tokens,context_tokens,'DAILY_CONTEXT_MISMATCH');
  assert.equal(inputs.context_tokens,context_tokens,'INPUT_BINDING_MISMATCH');
  const sourceRoot=path.join(root,'source'),original=await read(path.join(sourceRoot,scenario.module),1048576);
  record.source_before=await inventory(sourceRoot);assert.deepEqual(record.source_before,scenario.source_inventory);
  record.head=await cli('project-head');assert.deepEqual(record.head,scenario.head);
  record.repair_requests_before=await api.repairRuns();assert.deepEqual(record.repair_requests_before,[],'DAILY_NEW_PROFILE_REQUIRED');
  record.test_requests_before=await api.testRuns();assert.deepEqual(record.test_requests_before,[],'DAILY_NEW_PROFILE_REQUIRED');
  const sources=await api.sources(),selected=sources.find(row=>row.ref?.relative_path===scenario.module);assert.ok(selected);
  assert.equal(selected.ref.raw_sha256,digest(original));assert.deepEqual(selected.ref.snapshot,record.head.snapshot,'DAILY_SOURCE_HEAD_MISMATCH');
  const checkedBinding={...inputs.daily_profile_files,manifest:inputs.manifest,context_tokens,core_version:inputs.core_version,companion_version:inputs.companion_version};
  const intent=makeReadyIntent({schema:'rentgen-daily-ready-observation/1',mode:'ready-intent-only',ready:api.ready,
   project_id:config.project_id,selected_source_ref:selected.ref,expected_module:scenario.module,expected_raw_sha256:digest(original),
   head:record.head,expected_head:scenario.head,repair_history:record.repair_requests_before,test_history:record.test_requests_before,
   binding:checkedBinding,expected_binding:{...inputs.daily_profile_files,manifest:scenario.frozen_inputs,context_tokens,core_version:config.core_version,companion_version:scenario.companion_version}},sourceRef);
  record.source_ref=intent.source_ref;await progress();
  const file=path.join(path.dirname(out),'ready-intent.json'),bytes=Buffer.from(JSON.stringify(intent));
  await fs.writeFile(file,bytes,{flag:'wx'});
  record.ready_intent={path:file,size:bytes.length,sha256:digest(bytes)};record.status='ready_intent_collected';
  await progress();await terminal();
 }catch(error){record.status='refused';record.error=error.stack;throw error;}
}
async function attempt(){
 const env=await environment('attempt'),{root,scenario,config,api,cli,semantic,record,progress,terminal}=env;
 record.preservation_verified=false;record.eligible_for_raw_qualification=false;
 try{
  const context_tokens=matchingContext(config,scenario);
  if(Object.hasOwn(env,'context_tokens'))assert.equal(env.context_tokens,context_tokens,'DAILY_CONTEXT_MISMATCH');
  const sourceRoot=path.join(root,'source'),source=path.join(sourceRoot,scenario.module),original=await read(source,1048576);
  record.source_before=await inventory(sourceRoot);assert.deepEqual(record.source_before,scenario.source_inventory);record.head=await cli('project-head');assert.deepEqual(record.head,scenario.head);
  record.repair_requests_before=await api.repairRuns();assert.deepEqual(record.repair_requests_before,[],'DAILY_NEW_PROFILE_REQUIRED');record.test_requests_before=await api.testRuns();assert.deepEqual(record.test_requests_before,[],'DAILY_NEW_PROFILE_REQUIRED');
  const sources=await api.sources(),selected=sources.find(row=>row.ref?.relative_path===scenario.module);assert.ok(selected);assert.equal(selected.ref.raw_sha256,digest(original));
  assert.deepEqual(selected.ref.snapshot,record.head.snapshot,'DAILY_SOURCE_HEAD_MISMATCH');
  record.source_ref=selected.ref;record.repair_call_requested=true;await progress();
  try{record.repair=await vscode.commands.executeCommand('rentgen.repairSource',selected.token,{model:scenario.model,instruction:scenario.instruction});}catch(error){record.repair_call_error=error.stack;}
  record.repair_requests_after=await api.repairRuns();const request=semantic.uniqueNewRun(record.repair_requests_before,record.repair_requests_after,row=>row.project_id===env.config.project_id&&same(row.source_ref,record.source_ref)&&row.model===scenario.model);
  if(!request){record.status='unproven';record.reason='No newly saved matching repair request';return;}
  record.repair_run_id=request.id;
  const savedRequest=await json(path.join(root,'repair-runs',request.id,'request.json'),32768);
  assert.deepEqual(savedRequest,request,'DAILY_MODEL_CONTEXT_MISMATCH');
  assert.equal(savedRequest.context_tokens,context_tokens,'DAILY_MODEL_CONTEXT_MISMATCH');
  if(record.repair)assert.equal(record.repair.id,request.id);else record.repair=await vscode.commands.executeCommand('rentgen.repairResult',request.id);
  assert.deepEqual(await vscode.commands.executeCommand('rentgen.repairResult',request.id),record.repair);await progress();
  assert.deepEqual(await read(path.join(root,'repair-runs',request.id,'instruction.txt'),4096),Buffer.from(scenario.instruction));
  const report=await json(path.join(root,'repair-runs',request.id,'result/result.json'),2097152,true),journal=await read(path.join(root,'repair-runs',request.id,'result/events.jsonl'),2097152,true);
  let events=[];if(journal&&journal.at(-1)===10)events=decode(journal).split('\n').filter(Boolean).map(JSON.parse);
  assert.ok(events.length<=64);record.repair_report=report;record.repair_journal_sha256=journal?digest(journal):null;
  if(!record.repair.receipt||record.repair.receipt.revision!==2){record.status='unproven';record.reason='No immutable AI revision2 is readable';return;}
  if(!report||!['analysis_clean','diagnostics_present'].includes(record.repair.status)){
   record.status='unproven';record.reason='No model report qualified for native TestDraft';return;
  }
  assert.equal(report.model?.num_ctx,context_tokens,'DAILY_MODEL_CONTEXT_MISMATCH');
  record.model_context={context_tokens,request_context_tokens:savedRequest.context_tokens,reported_num_ctx:report.model.num_ctx};
  const version=await semantic.selectRepairRevision(api,record.repair.receipt);record.selected_receipt=version.receipt;
  const saved=await cli('draft-get','--draft-id',version.receipt.draft_id,'--revision',version.receipt.revision);assert.deepEqual(saved.receipt,version.receipt);
  const proposal=saved.proposal,candidate=Buffer.from(proposal.replacement.base64,'base64');assert.equal(candidate.toString('base64'),proposal.replacement.base64);assert.equal(digest(candidate),proposal.replacement.raw_sha256);
  record.candidate_sha256=digest(candidate);record.proposal_content_id=proposal.content_id;record.profile_id=scenario.profile.profile_id;
  record.ai_origin=semantic.repairOrigin({request,events,repair:record.repair,report,proposal});
  record.diagnostics={baseline:diagnosticVerdict(report?.before,events.find(row=>row.phase==='draft_created')?.receipt,digest(original)),candidate:diagnosticVerdict(report?.after,version.receipt,digest(candidate))};
  record.latest_before_tests=(await api.drafts()).find(row=>row.receipt?.draft_id===version.receipt.draft_id)?.receipt;
  record.test_call_requested=true;await progress();
  try{record.test=await vscode.commands.executeCommand('rentgen.testDraft',version.token,scenario.profile.profile_id);}catch(error){record.test_call_error=error.stack;}
  record.test_requests_after=await api.testRuns();const intent=semantic.uniqueNewRun(record.test_requests_before,record.test_requests_after,row=>same(row.receipt,version.receipt)&&row.profile.profile_id===scenario.profile.profile_id);
  if(!intent){record.status='unproven';record.reason='No newly saved matching test request';return;}
  record.test_run_id=intent.id;record.test_request=intent;
  if(record.test)assert.equal(record.test.run_id,intent.id);else record.test=await vscode.commands.executeCommand('rentgen.testResult',intent.id);
  const actualProposal=await json(path.join(root,'test-runs',intent.id,'proposal.json'));assert.deepEqual(actualProposal,proposal);
  record.functional=semantic.selectedRepairVerdict({repairReceipt:record.repair.receipt,selectedReceipt:version.receipt,proposal,profile:intent.profile,result:record.test});
  record.compile=compileVerdict(record.test);record.recognized_safe_transform=semantic.recognizedSafeTransform(decode(original),decode(candidate));
  record.test_cached=await vscode.commands.executeCommand('rentgen.testResult',intent.id);assert.deepEqual(record.test_cached,record.test);
  delete record.test_cached;
  record.source_after=await inventory(sourceRoot);assert.deepEqual(record.source_after,record.source_before);assert.deepEqual(await cli('project-head'),record.head);
  assert.deepEqual((await api.drafts()).find(row=>row.receipt?.draft_id===version.receipt.draft_id)?.receipt,record.latest_before_tests);
  assert.deepEqual(await api.repairRuns(),record.repair_requests_after);assert.deepEqual(await api.testRuns(),record.test_requests_after);
  const afterJournal=await read(path.join(root,'repair-runs',request.id,'result/events.jsonl'),2097152,true);assert.deepEqual(afterJournal,journal);
  record.preservation_verified=true;
  record.eligible_for_raw_qualification=record.ai_origin.ai_origin==='verified'&&record.diagnostics.candidate.status==='clean'&&record.compile.baseline.status==='passed'&&record.compile.candidate.status==='passed'&&record.functional.semantic_verdict==='passed'&&record.recognized_safe_transform;
  record.status='collected';
 }catch(error){record.status='refused';record.error=error.stack;throw error;}finally{await captureAvailableEvidence(env);await progress();await terminal();}
}
async function recover(){
 const env=await environment('recovery'),{root,scenario,api,cli,semantic,record,progress,terminal}=env;
 record.preservation_verified=false;record.eligible_for_raw_qualification=false;record.model_requests_started=0;record.test_requests_started=0;
 try{
  const prior=await json(process.env.RENTGEN_DAILY_PRIOR,4194304);assert.equal(prior.schema,record.schema);assert.equal(prior.profile_root,root);const testId=prior.test_run_id??null;assert.ok(validUuid(prior.repair_run_id)&&(testId===null||validUuid(testId)),'DAILY_PRIOR_RUN_REQUIRED');assert.deepEqual(prior.inputs.manifest,env.inputs.manifest);
  for(const key of ['validator','source_validator'])assert.equal(prior.inputs[key].sha256,env.inputs[key].sha256,'INPUT_BINDING_MISMATCH');
  record.repair_run_id=prior.repair_run_id;if(testId)record.test_run_id=testId;else delete record.test_run_id;
  const repairRequests=await api.repairRuns(),testRequests=await api.testRuns(),head=await cli('project-head'),sourceBefore=await inventory(path.join(root,'source'));
  assert.deepEqual(head,prior.head);assert.deepEqual(sourceBefore,scenario.source_inventory);
  record.head=head;record.source_before=sourceBefore;
  const selected=prior.selected_receipt,latestBefore=selected?(await api.drafts()).find(row=>row.receipt?.draft_id===selected.draft_id)?.receipt:null;
  const rawBefore=await evidence(root,prior.repair_run_id,testId,prior.test,null,prior.repair);assert.deepEqual(rawBefore,prior.raw_evidence);
  await progress();
  record.repair=await vscode.commands.executeCommand('rentgen.repairResult',prior.repair_run_id);assert.deepEqual(record.repair,prior.repair);
  if(selected){assert.deepEqual(selected,record.repair?.receipt,'DAILY_PRIOR_REPAIR_BINDING_MISMATCH');const version=await semantic.selectRepairRevision(api,selected);assert.deepEqual(version.receipt,selected);record.selected_receipt=version.receipt;}
  if(testId){
   assert.ok(selected&&prior.test_request,'DAILY_PRIOR_TEST_BINDING_REQUIRED');
   record.test=await vscode.commands.executeCommand('rentgen.testResult',testId);assert.deepEqual(record.test,prior.test);
   const intent=testRequests.find(row=>row.id===testId);assert.deepEqual(intent,prior.test_request);
   const proposal=await json(path.join(root,'test-runs',testId,'proposal.json'));
   record.functional=semantic.selectedRepairVerdict({repairReceipt:record.repair.receipt,selectedReceipt:selected,proposal,profile:intent.profile,result:record.test});
   assert.deepEqual(record.functional,prior.functional);
  }else{record.test=null;record.functional={contract_admitted:false,semantic_verdict:'unproven'};record.recovery_scope='repair_only';}
  assert.deepEqual(await api.repairRuns(),repairRequests);assert.deepEqual(await api.testRuns(),testRequests);assert.deepEqual(await cli('project-head'),head);assert.deepEqual(await inventory(path.join(root,'source')),sourceBefore);
  if(selected)assert.deepEqual((await api.drafts()).find(row=>row.receipt?.draft_id===selected.draft_id)?.receipt,latestBefore);
  record.raw_evidence=await evidence(root,prior.repair_run_id,testId,record.test,null,record.repair);assert.deepEqual(record.raw_evidence,rawBefore);
  if(testId){
   const shown=vscode.window.activeTextEditor?.document;assert.equal(shown?.languageId,'json');assert.deepEqual(JSON.parse(shown.getText()),record.test);
  }else{
   const receipt=record.repair.receipt,saved=await cli('draft-get','--draft-id',receipt.draft_id,'--revision',receipt.revision);
   assert.deepEqual(saved.receipt,receipt,'DAILY_REPAIR_VIEW_RECEIPT');
   const proposal=saved.proposal,replacement=proposal?.replacement;
   assert.equal(proposal?.content_id,receipt.proposal_content_id,'DAILY_REPAIR_VIEW_PROPOSAL');
   assert.equal(typeof replacement?.base64,'string','DAILY_REPAIR_VIEW_BYTES');
   const bytes=Buffer.from(replacement.base64,'base64');
   assert.equal(bytes.toString('base64'),replacement.base64,'DAILY_REPAIR_VIEW_BYTES');
   assert.equal(digest(bytes),replacement.raw_sha256,'DAILY_REPAIR_VIEW_BYTES');
   const basename=`/[v${receipt.revision}] ${path.posix.basename(receipt.source_ref.relative_path)}`;
   const shown=vscode.window.visibleTextEditors.map(editor=>editor.document).filter(doc=>doc.uri.scheme==='rentgen-view'&&doc.uri.authority&&doc.uri.path===basename&&!doc.uri.query&&!doc.uri.fragment);
   assert.equal(shown.length,1,'DAILY_REPAIR_VIEW_REQUIRED');
   assert.equal(shown[0].getText(),decode(bytes),'DAILY_REPAIR_VIEW_TEXT');
  }
  record.preservation_verified=true;record.recovered=true;record.status='collected';
 }catch(error){record.status='refused';record.error=error.stack;throw error;}finally{await captureAvailableEvidence(env);await progress();await terminal();}
}
exports.run=attempt;exports.recover=recover;exports.readyIntentOnly=readyIntentOnly;
