'use strict';
const vscode=require('vscode'),fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {promisify}=require('node:util'),execute=promisify(require('node:child_process').execFile),{createHash}=require('node:crypto');
exports.run=async()=>{
 const root=process.env.RENTGEN_EDITOR_PROFILE,out=process.env.RENTGEN_TESTS_ACCEPTANCE_OUTPUT;assert.ok(root&&out);
 const extension=vscode.extensions.getExtension('rentgen.project-companion');assert.equal(extension?.packageJSON.version,'0.1.8');
 const api=await extension.activate();assert.equal(api.ready,true);
 const config=JSON.parse(await fs.readFile(path.join(root,'profile.json'),'utf8')),scenario=JSON.parse(await fs.readFile(path.join(root,'tests-scenario.json'),'utf8'));
 const cli=async(command,...extra)=>JSON.parse((await execute(config.python,['-I','-m','rentgen_core',command,'--registry',config.registry,'--project',config.project_id,...extra.map(String)],{windowsHide:true,timeout:30000,maxBuffer:2097153,encoding:'utf8'})).stdout).result;
 const head=await cli('project-head');assert.deepEqual(head,scenario.head);
 const sourceFile=path.join(root,'source',scenario.module),sourceBefore=await fs.readFile(sourceFile),draft=(await api.drafts()).find(row=>row.receipt?.draft_id===scenario.latest.draft_id);assert.deepEqual(draft.receipt,scenario.latest);
 let report={accepted:false,model_calls:0};
 try{
  if(process.env.RENTGEN_TESTS_ACCEPTANCE_PRIOR){
   const prior=JSON.parse(await fs.readFile(process.env.RENTGEN_TESTS_ACCEPTANCE_PRIOR,'utf8'));assert.equal(prior.accepted,true);
   const runs=await api.testRuns(),folder=path.join(root,'state/test-runs',prior.result.run_id),hashes={};
   for(const name of ['request.json','report.json'])hashes[name]=createHash('sha256').update(await fs.readFile(path.join(folder,name))).digest('hex');
   await cli('test-profile-disable','--profile-id',scenario.profile.profile_id);
   assert.deepEqual(await vscode.commands.executeCommand('rentgen.testResult',prior.result.run_id),prior.result);
   assert.deepEqual(await api.testRuns(),runs);
   for(const [name,hash]of Object.entries(hashes))assert.equal(createHash('sha256').update(await fs.readFile(path.join(folder,name))).digest('hex'),hash);
   report={...report,recovered:true,test_runs:0,disabled_profile_readable:true,result:prior.result};
  }else{
   await assert.rejects(vscode.commands.executeCommand('rentgen.testDraft','forged',scenario.profile.profile_id),/UNKNOWN_VIEW_HANDLE/);
   const history=await api.history(draft.token),selected=history.find(row=>row.receipt?.revision===scenario.selected.revision);assert.deepEqual(selected.receipt,scenario.selected);
   const result=await vscode.commands.executeCommand('rentgen.testDraft',selected.token,scenario.profile.profile_id);
   assert.equal(result.report.tests.baseline.status,'failed');assert.equal(result.report.tests.candidate.status,'passed');assert.equal(result.report.tests.candidate.counts.passed,1);
   assert.equal(result.report.proposal_content_id,scenario.selected.proposal_content_id);assert.notEqual(result.report.proposal_content_id,scenario.latest.proposal_content_id);
   assert.equal(result.report.profile_id,scenario.profile.profile_id);assert.equal(result.report.tests.isolated_infobases,true);
   report={...report,result,test_runs:1,selected_revision:scenario.selected.revision,current_revision:scenario.latest.revision};
  }
  assert.deepEqual(await fs.readFile(sourceFile),sourceBefore);assert.deepEqual(await cli('project-head'),head);assert.deepEqual((await api.drafts()).find(row=>row.receipt?.draft_id===scenario.latest.draft_id).receipt,scenario.latest);
  assert.deepEqual(await api.repairRuns(),[]);report.accepted=true;
 }catch(error){report.error=error.stack;throw error;}finally{await fs.writeFile(out,JSON.stringify(report,null,2),{flag:'wx'});}
};
