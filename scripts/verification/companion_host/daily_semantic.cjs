'use strict';
// Structured admission only: actual native and model evidence is qualified separately.
const {isDeepStrictEqual:same}=require('node:util');
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const hash=/^[0-9a-f]{64}$/;
function validUuid(value){return typeof value==='string'&&uuid.test(value);}
function createDailySemantic({validateTests,sourceRef}) {
 if(typeof validateTests!=='function'||typeof sourceRef!=='function')throw new TypeError('Exact payload validators required');
 function typedRef(ref,project){
   for(const value of [ref?.snapshot?.snapshot_id,ref?.snapshot?.manifest_hash,ref?.raw_sha256])
     if(typeof value!=='string'||!hash.test(value))throw new Error('DAILY_SOURCE_REF_INVALID');
   return sourceRef(ref,project);
 }
 function receiptIdentity(receipt){
   if(!validUuid(receipt?.project_id)||!validUuid(receipt.draft_id)||!validUuid(receipt.operation_id)||
      !Number.isSafeInteger(receipt.revision)||receipt.revision<1||typeof receipt.proposal_content_id!=='string'||!hash.test(receipt.proposal_content_id))throw new Error('DAILY_AI_RECEIPT_INVALID');
   typedRef(receipt.source_ref,receipt.project_id);
 }
function selectedRepairVerdict({repairReceipt,selectedReceipt,proposal,profile,result}) {
  if (!same(selectedReceipt,repairReceipt)) throw new Error('DAILY_AI_REVISION_MISMATCH');
  if (result?.status !== 'completed') return {contract_admitted:false,semantic_verdict:'unproven'};
  if(!validUuid(result.run_id))throw new Error('DAILY_TEST_RUN_INVALID');
  receiptIdentity(selectedReceipt);
  if(typeof proposal?.replacement?.raw_sha256!=='string'||!hash.test(proposal.replacement.raw_sha256))throw new Error('DAILY_PROPOSAL_INVALID');
  const report=validateTests(result.report,result.run_id,selectedReceipt,proposal,profile);
  const baseline=report.tests.baseline,candidate=report.tests.candidate;
  const validControl=baseline.status==='failed' && baseline.counts.failures===1 && baseline.counts.errors===0 && baseline.counts.skipped===0 && baseline.counts.tests===1;
  let semantic='unproven';
  if (validControl && candidate.status==='failed' && candidate.counts.failures===1 && candidate.counts.errors===0 && candidate.counts.skipped===0) semantic='failed';
  if (validControl && candidate.status==='passed') semantic='passed';
  return {contract_admitted:true,semantic_verdict:semantic,run_id:result.run_id,
          proposal_content_id:report.proposal_content_id,candidate_sha256:report.candidate_sha256,
          profile_id:report.profile_id,revision:selectedReceipt.revision};
}

  async function selectRepairRevision(api, receipt) {
    receiptIdentity(receipt);
    const roots=await api.drafts();
    const matching=roots.filter(row=>row.kind==='draft' && row.receipt?.draft_id===receipt.draft_id);
    if(matching.length!==1)throw new Error(matching.length?'DAILY_AI_REVISION_AMBIGUOUS':'DAILY_AI_REVISION_UNAVAILABLE');
    for(let page=0;page<40;page++) {
      const rows=await api.history(matching[0].token,page>0);
      if(!Array.isArray(rows))throw new Error('DAILY_HISTORY_INVALID');
      const versions=rows.filter(row=>row.kind==='version');
      if(versions.length>1000)throw new Error('DAILY_HISTORY_LIMIT');
      const selected=versions.filter(row=>same(row.receipt,receipt));
      if(selected.length>1)throw new Error('DAILY_AI_REVISION_AMBIGUOUS');
      if(rows.some(row=>row.kind==='moreHistory'))continue;
      if(selected.length!==1)throw new Error('DAILY_AI_REVISION_UNAVAILABLE');
      if(!same(api.selectedDraft(selected[0].token),receipt))throw new Error('DAILY_AI_REVISION_MISMATCH');
      return selected[0];
    }
    throw new Error('DAILY_HISTORY_LIMIT');
  }

  function uniqueNewRun(before, after, matches) {
    if(!Array.isArray(before)||!Array.isArray(after)||before.length>1000||after.length>1000||typeof matches!=='function')throw new Error('DAILY_RUN_HISTORY_INVALID');
    const ids=rows=>{
      const result=new Set();
      for(const row of rows){
        if(typeof row?.id!=='string'||!row.id.length||result.has(row.id))throw new Error('DAILY_RUN_HISTORY_INVALID');
        result.add(row.id);
      }
      return result;
    };
    const old=ids(before);ids(after);
    const selected=after.filter(row=>!old.has(row.id)&&matches(row));
    if(selected.length>1)throw new Error('DAILY_RUN_AMBIGUOUS');
    return selected[0]??null;
  }

  function repairOrigin({request,events,repair,report,proposal}) {
    const unproven={ai_origin:'unproven',model_requests:null,model_responses:null,evidence:'local_unattested'};
    try {
      const phases=['start_requested','draft_created','baseline_checked','model_requested','model_responded','edit_requested','draft_saved','finished'];
      if(!Array.isArray(events)||!same(events.map(event=>event.phase),phases)||repair.truncated!==false)return unproven;
      if(!validUuid(request?.id)||!validUuid(request.project_id)||typeof request.model!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$/.test(request.model))return unproven;
      typedRef(request.source_ref,request.project_id);
      const [start,created,baseline,requested,responded,edit,saved,finished]=events;
      const receipt=repair.receipt,first=created.receipt;
      receiptIdentity(receipt);receiptIdentity(first);
      if(repair.id!==request.id||receipt?.project_id!==request.project_id||receipt.revision!==2||
         receipt.source_ref?.snapshot?.project_id!==request.project_id||!same(receipt.source_ref,request.source_ref)||
         !same(report.receipt,receipt)||report.status!==repair.status||!['analysis_clean','diagnostics_present'].includes(report.status)||
         proposal.content_id!==receipt.proposal_content_id||!hash.test(proposal.content_id)||typeof proposal.replacement?.raw_sha256!=='string'||!hash.test(proposal.replacement.raw_sha256)||
         report.candidate_sha256!==proposal.replacement.raw_sha256)return unproven;
      if(start.project_id!==request.project_id||start.draft_id!==receipt.draft_id||!same(start.source_ref,request.source_ref)||
         first?.project_id!==start.project_id||first.draft_id!==start.draft_id||first.operation_id!==start.operation_id||first.revision!==1||
         !same(first.source_ref,request.source_ref)||!same(report.before?.receipt,first)||!same(baseline.check,report.before)||
         requested.candidate_sha256!==request.source_ref.raw_sha256)return unproven;
      if(edit.project_id!==receipt.project_id||edit.draft_id!==receipt.draft_id||edit.operation_id!==receipt.operation_id||
         edit.expected_revision!==1||edit.candidate_sha256!==report.candidate_sha256||!same(saved.receipt,receipt)||
         !same(finished.receipt,receipt)||finished.status!==report.status||!same(report.after?.receipt,receipt)||
         !same(responded.metrics,report.model)||responded.metrics?.model!==request.model||responded.metrics.done!==true||responded.metrics.done_reason!=='stop'||
         typeof responded.metrics.response_sha256!=='string'||!hash.test(responded.metrics.response_sha256))return unproven;
      for(const key of ['request_bytes','response_bytes'])if(!Number.isSafeInteger(responded.metrics[key])||responded.metrics[key]<=0)return unproven;
      return {ai_origin:'verified',model_requests:1,model_responses:1,evidence:'local_unattested'};
    }catch{return unproven;}
  }

  function recognizedSafeTransform(original,candidate) {
    if(typeof original!=='string'||typeof candidate!=='string')return false;
    const normalize=text=>text.replace(/^\uFEFF/,'').replace(/\r\n/g,'\n');
    const baseline=normalize(original),after=normalize(candidate);
    const empty='    Попытка\n        ДокументОбъект.Записать();\n    Исключение\n    КонецПопытки;';
    const parts=baseline.split(empty);
    if(parts.length!==2)return false;
    const rethrow=empty.replace('    Исключение\n','    Исключение\n        ВызватьИсключение;\n');
    const direct='    ДокументОбъект.Записать();';
    const [prefix,suffix]=parts;
    if(after===prefix+rethrow+suffix||after===prefix+direct+suffix)return true;
    if(!after.startsWith(prefix)||!after.endsWith(suffix))return false;
    const changed=after.slice(prefix.length,after.length-suffix.length);
    const code=[],archived=[],markedCode=[];
    let opened=false,closed=false,task=null;
    for(const line of changed.split('\n')) {
      const marker=line.match(/^[ \t]*\/\/ (\+\+|--)ДелоТех ([^\r\n]{1,160})$/);
      if(marker) {
        const label=marker[2];
        if(label!==label.trim()||/[\u0000-\u001f\u007f-\u009f]/.test(label))return false;
        if(marker[1]==='++') {
          if(opened||closed)return false;
          opened=true;task=label;
        }else {
          if(!opened||closed||task!==label)return false;
          closed=true;
        }
        continue;
      }
      const comment=line.match(/^[ \t]*\/\/[ \t]*(.*)$/);
      if(comment) {
        if(!opened||closed)return false;
        archived.push(comment[1].trim());
        continue;
      }
      code.push(line);
      if(opened&&!closed)markedCode.push(line);
    }
    if(!opened||!closed)return false;
    const stripped=code.join('\n');
    const fullArchive=same(archived,empty.split('\n').map(line=>line.trim()));
    if(stripped===rethrow)return (archived.length===0||fullArchive)&&markedCode.includes('        ВызватьИсключение;');
    return stripped===direct&&fullArchive&&markedCode.includes(direct);
  }

 return Object.freeze({selectedRepairVerdict,selectRepairRevision,uniqueNewRun,repairOrigin,recognizedSafeTransform});
}
module.exports={createDailySemantic};
