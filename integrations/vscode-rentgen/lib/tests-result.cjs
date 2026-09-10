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
module.exports={validateProfiles,validateTests};
