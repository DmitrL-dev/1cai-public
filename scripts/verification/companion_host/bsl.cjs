'use strict';
const vscode=require('vscode'),fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {promisify}=require('node:util'),execute=promisify(require('node:child_process').execFile);
exports.run=async()=>{
 const root=process.env.RENTGEN_EDITOR_PROFILE,out=process.env.RENTGEN_BSL_ACCEPTANCE_OUTPUT;
 assert.ok(root&&out);const extension=vscode.extensions.getExtension('rentgen.project-companion');
 assert.equal(extension?.packageJSON.version,'0.1.7');const api=await extension.activate();assert.equal(api.ready,true);
 const prior=JSON.parse(await fs.readFile(path.join(root,'manual-acceptance.json'),'utf8'));assert.equal(prior.accepted,true);
 const config=JSON.parse(await fs.readFile(path.join(root,'profile.json'),'utf8'));
 const scenario=JSON.parse(await fs.readFile(path.join(root,'daily-scenario.json'),'utf8'));
 const cli=async(command,...extra)=>JSON.parse((await execute(config.python,['-I','-m','rentgen_core',command,'--registry',config.registry,'--project',config.project_id,...extra.map(String)],{windowsHide:true,timeout:30000,maxBuffer:2097153,encoding:'utf8'})).stdout).result;
 const head=await cli('project-head'),drafts=await api.drafts();assert.deepEqual(head,scenario.head);
 const selected=drafts.find(row=>row.receipt?.draft_id===prior.saved.receipt.draft_id);assert.equal(selected.receipt.revision,3);
 const repairRuns=await api.repairRuns(),modelEvents=path.join(root,'repair-runs',repairRuns[0].id,'result/events.jsonl');
 const modelBefore=await fs.readFile(modelEvents),sourceFile=path.join(root,'source',scenario.module),sourceBefore=await fs.readFile(sourceFile);
 let report={accepted:false,model_calls:0};
 try{
  if(process.env.RENTGEN_BSL_ACCEPTANCE_PRIOR){
   const completed=JSON.parse(await fs.readFile(process.env.RENTGEN_BSL_ACCEPTANCE_PRIOR,'utf8'));assert.equal(completed.accepted,true);
   const before=await fs.readdir(path.join(root,'bsl-runs'));
   for(const key of ['bad','fixed'])assert.deepEqual(await vscode.commands.executeCommand('rentgen.bslResult',completed[key].run_id),completed[key]);
   assert.deepEqual(await fs.readdir(path.join(root,'bsl-runs')),before);
   report={...report,recovered:true,analysis_runs:0};
  }else{
   const history=await api.history(selected.token),bad=history.find(row=>row.receipt?.revision===2);assert.ok(bad);
   await assert.rejects(vscode.commands.executeCommand('rentgen.bslCheck','forged'),/UNKNOWN_VIEW_HANDLE/);
   report.bad=await vscode.commands.executeCommand('rentgen.bslCheck',bad.token);
   assert.equal(report.bad.report.diagnostic.diagnostics_status,'diagnostics_present');
   assert.ok(report.bad.report.diagnostic.analysis.diagnostics.some(item=>item.code==='DeprecatedMessage'));
   report.fixed=await vscode.commands.executeCommand('rentgen.bslCheck',selected.token);
   assert.equal(report.fixed.report.diagnostic.diagnostics_status,'clean');
   assert.equal(report.fixed.receipt.revision,3);
   assert.equal(report.fixed.report.diagnostic.proposal_content_id,prior.saved.receipt.proposal_content_id);
   assert.equal(report.fixed.report.diagnostic.analysis.runtime_verified,true);
   assert.equal(report.fixed.report.tests.status,'not_run');report.analysis_runs=2;
  }
  assert.deepEqual(await fs.readFile(modelEvents),modelBefore);assert.deepEqual(await api.repairRuns(),repairRuns);
  assert.deepEqual(await fs.readFile(sourceFile),sourceBefore);
  assert.deepEqual(await cli('project-head'),head);assert.equal((await api.drafts()).find(row=>row.receipt?.draft_id===selected.receipt.draft_id).receipt.revision,3);
  report.accepted=true;
 }catch(error){report.error=error.stack;throw error;}
 finally{await fs.writeFile(out,JSON.stringify(report,null,2),{flag:'wx'});}
};
