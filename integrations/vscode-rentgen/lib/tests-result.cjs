'use strict';
const {isDeepStrictEqual}=require('node:util');
const hash=/^[0-9a-f]{64}$/,name=/^[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё_0-9]{0,79}$/;
const fail=()=>{throw new Error('TEST_RESULT_MISMATCH');};
function validateProfiles(rows){
 if(!Array.isArray(rows)||rows.length>128)fail();const ids=new Set();
 for(const p of rows){
  if(!hash.test(p?.profile_id)||ids.has(p.profile_id)||typeof p.name!=='string'||!p.name.length||p.name.length>128||typeof p.enabled!=='boolean'||!Array.isArray(p.modules)||!p.modules.length||p.modules.length>8)fail();ids.add(p.profile_id);
  let count=0;const names=new Set();
  for(const m of p.modules){
   if(!name.test(m?.name)||names.has(m.name.toLowerCase())||!hash.test(m.sha256)||!Array.isArray(m.tests)||!m.tests.length||m.tests.some(t=>!name.test(t))||new Set(m.tests.map(t=>t.toLowerCase())).size!==m.tests.length)fail();
   names.add(m.name.toLowerCase());count+=m.tests.length;
  }if(count>128)fail();
 }return rows;
}
function validateTests(report,id,receipt,proposal,profile){
 validateProfiles([profile]);
 if(report?.schema!==1||report.run_id!==id||!isDeepStrictEqual(report.source_ref,receipt.source_ref)||report.proposal_content_id!==receipt.proposal_content_id||proposal.content_id!==receipt.proposal_content_id||report.profile_id!==profile.profile_id||report.candidate_sha256!==proposal.replacement.raw_sha256||!hash.test(report.report_sha256)||report.apply?.status!=='unavailable'||report.evidence!=='local_unattested'||report.runtime_dependencies!=='not_fully_pinned'||report.tests?.isolated_infobases!==true)fail();
 const expected=new Set(profile.modules.flatMap(m=>m.tests.map(t=>JSON.stringify([m.name+'.'+t,t,'Сервер']))));
 for(const phase of [report.tests.baseline,report.tests.candidate]){
  if(phase?.status==='not_run'){if(phase.reason!=='compiler_diagnostics')fail();continue;}
  if(!phase||phase.module_text_verified!==true||!Array.isArray(phase.cases)||phase.cases.length!==expected.size)fail();
  const seen=new Set(),counts={tests:phase.cases.length,passed:0,failures:0,errors:0,skipped:0};
  for(const item of phase.cases){
   const key=JSON.stringify([item.classname,item.name,item.context]),outcome={passed:'passed',failure:'failures',error:'errors',skipped:'skipped'}[item.outcome];
   if(!expected.has(key)||seen.has(key)||!outcome)fail();seen.add(key);counts[outcome]++;
  }
  if(!isDeepStrictEqual(counts,phase.counts))fail();
  const status=counts.failures||counts.errors?'failed':counts.skipped?'incomplete':'passed';
  if(phase.status!==status)fail();
 }
 if(report.tests.status!==report.tests.candidate.status)fail();return report;
}
const checks=['report_identity','profile_definition','input_inventories','native_roundtrip','step_sequence','runner_settings','junit_exit','engine_source','scratch_cleanup'];
const states=new Set(['verified','mismatch','missing','not_applicable']),outcomes=new Set(['passed','failed','incomplete','not_run']);
const code=/^[A-Z][A-Z0-9_]{0,79}$/,uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
// The dossier is local_unattested consistency evidence, never native or apply authority.
function validateQualification(d,id,project){
 if(d?.schema!==1||d.kind!=='yaxunit-retained-run-qualification'||d.run_id!==id||!uuid.test(id)||d.project_id!==project||!['completed','failed','incomplete'].includes(d.run_status)||!['consistent','inconsistent','incomplete'].includes(d.qualification)||d.evidence!=='local_unattested'||d.execution!=='not_performed'||d.apply?.status!=='unavailable'||!hash.test(d.dossier_sha256)||!Array.isArray(d.checks)||d.checks.length!==checks.length||!Array.isArray(d.limitations))fail();
 d.checks.forEach((row,i)=>{if(row?.id!==checks[i]||!states.has(row.status)||(row.detail!==null&&!code.test(row.detail))||(row.status==='verified')!==(row.detail===null))fail();});
 const seen=new Set(d.checks.map(row=>row.status));
 const expected=d.run_status!=='completed'?'incomplete':seen.has('mismatch')?'inconsistent':seen.has('missing')?'incomplete':'consistent';
 if(d.qualification!==expected||(d.run_status!=='completed')!==seen.has('not_applicable'))fail();
 if(d.failure_code!==null&&(d.run_status!=='failed'||!code.test(d.failure_code)))fail();
 if(d.test_result!==null&&(d.run_status!=='completed'||!['status','baseline','candidate'].every(k=>outcomes.has(d.test_result[k]))||d.test_result.status!==d.test_result.candidate||!hash.test(d.candidate_sha256)||!hash.test(d.report_sha256)))fail();
 if(d.profile!==null&&(!hash.test(d.profile?.profile_id)||typeof d.profile.enabled!=='boolean'))fail();
 return d;
}
module.exports={validateProfiles,validateTests,validateQualification};
