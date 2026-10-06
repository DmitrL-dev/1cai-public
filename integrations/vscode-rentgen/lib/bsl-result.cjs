'use strict';
const {isDeepStrictEqual}=require('node:util');
const PROFILE='bsl-ls-1.0.5-temurin21.0.12.1-win64-bmp-default-v1';
const CONFIG_SHA256='e56b86d4187a301a6e17e7e46906d4e7fcf6e84166d648684b6d5f1bd540af72';
const RUNTIME_MANIFEST_SHA256='2835e1a268e67be020e99ecd8d2a64c7b390e3752ed99c89d71a5340eb792ca5';
// Applicability to the supported analyzer dependencies, not authentication of JSON.
function dependenciesMatch(analysis,sizeBytes){
 return Boolean(analysis)&&analysis.profile_id===PROFILE&&analysis.config_sha256===CONFIG_SHA256&&
  analysis.runtime_manifest_sha256===RUNTIME_MANIFEST_SHA256&&analysis.scope==='single_module_isolated'&&
  Number.isSafeInteger(sizeBytes)&&sizeBytes>=0&&Number.isSafeInteger(analysis.candidate_size_bytes)&&
  analysis.candidate_size_bytes===sizeBytes;
}
function validateBsl(value,receipt,proposal){
 const diagnostic=value?.diagnostic,analysis=diagnostic?.analysis;
 const fail=()=>{throw new Error('BSL_RESULT_MISMATCH');};
 if(!diagnostic||!analysis||!isDeepStrictEqual(diagnostic.source_ref,receipt.source_ref)||
  diagnostic.proposal_content_id!==receipt.proposal_content_id||proposal.content_id!==receipt.proposal_content_id||
  analysis.candidate_sha256!==proposal.replacement.raw_sha256||!dependenciesMatch(analysis,proposal.replacement.size_bytes)||
  diagnostic.tests_status!=='not_run'||diagnostic.apply_status!=='unavailable'||diagnostic.evidence!=='ephemeral_unattested'||
  value.tests?.status!=='not_run'||value.apply?.status!=='unavailable'||
  !Array.isArray(analysis.diagnostics)||analysis.diagnostics.length>128)fail();
 if(analysis.status==='completed'){
  if(analysis.runtime_verified!==true||analysis.coverage!=='exact_one'||
   typeof analysis.diagnostics_complete!=='boolean'||!Number.isSafeInteger(analysis.total_diagnostics)||
   analysis.total_diagnostics<analysis.diagnostics.length)fail();
  if(analysis.diagnostics_complete&&analysis.total_diagnostics!==analysis.diagnostics.length)fail();
  const clean=analysis.diagnostics_complete&&analysis.total_diagnostics===0;
  if(diagnostic.diagnostics_status!==(clean?'clean':'diagnostics_present'))fail();
 }else if(!['failed','unsupported'].includes(analysis.status)||diagnostic.diagnostics_status!==analysis.status)fail();
}
module.exports={PROFILE,validateBsl,dependenciesMatch};
