'use strict';
// Continue inspection of a failed AI attempt, never ask the model again.
const vscode=require('vscode'),fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {promisify}=require('node:util');
const execute=promisify(require('node:child_process').execFile);
exports.run=async()=>{
  const root=process.env.RENTGEN_EDITOR_PROFILE;if(!root)throw new Error('Explicit synthetic profile required');
  const prior=JSON.parse(await fs.readFile(path.join(root,'daily-acceptance.json'),'utf8'));
  const scenario=JSON.parse(await fs.readFile(path.join(root,'daily-scenario.json'),'utf8'));
  const config=JSON.parse(await fs.readFile(path.join(root,'profile.json'),'utf8'));
  assert.equal(prior.accepted,false);assert.equal(prior.repair.status,'diagnostics_present');
  const extension=vscode.extensions.getExtension('rentgen.project-companion');assert.equal(extension?.packageJSON.version,'0.1.5');
  const api=await extension.activate();assert.equal(api.ready,true);
  const report={native_and_recovery_verified:false,ai_task_correct:false,models_started:0};
  try {
    const runs=await api.repairRuns();assert.equal(runs.length,1);
    const eventsFile=path.join(root,'repair-runs',prior.repair.id,'result/events.jsonl');
    const eventsBytes=await fs.readFile(eventsFile),events=eventsBytes.toString('utf8').trim().split('\n').map(JSON.parse);
    report.prior_model_requests=events.filter(e=>e.phase==='model_requested').length;assert.equal(report.prior_model_requests,1);
    report.model_metrics=events.find(e=>e.phase==='model_responded').metrics;
    const result=await vscode.commands.executeCommand('rentgen.repairResult',prior.repair.id);assert.deepEqual(result,prior.repair);
    const draft=(await api.drafts()).find(row=>row.receipt?.draft_id===result.receipt.draft_id);assert.ok(draft);
    const cli=async(command,...extra)=>JSON.parse((await execute(config.python,['-I','-m','rentgen_core',command,'--registry',config.registry,'--project',config.project_id,...extra.map(String)],{windowsHide:true,timeout:30000,maxBuffer:2097153,encoding:'utf8'})).stdout).result;
    const saved=await cli('draft-get','--draft-id',result.receipt.draft_id,'--revision',result.receipt.revision);
    const text=Buffer.from(saved.proposal.replacement.base64,'base64').toString('utf8');
    assert.ok(text.includes('Сообщить('));assert.ok(!text.includes('ВызватьИсключение'));
    report.semantic_failure='The handler displays a message and still swallows the write exception.';
    const original=await fs.readFile(path.join(root,'source',scenario.module));
    assert.deepEqual(await cli('project-head'),scenario.head);assert.deepEqual(await api.platformRuns(),[]);
    report.platform=await vscode.commands.executeCommand('rentgen.platformCheck',draft.token,scenario.platform);
    assert.equal(report.platform.status,'completed');
    assert.equal(report.platform.report.analysis.baseline.status,'passed');
    assert.equal(report.platform.report.analysis.candidate.status,'passed');
    assert.equal(report.platform.report.proposal_content_id,result.receipt.proposal_content_id);
    const recovered=await vscode.commands.executeCommand('rentgen.platformResult',report.platform.run_id);
    assert.deepEqual(recovered.report,report.platform.report);
    assert.deepEqual(await fs.readFile(eventsFile),eventsBytes);assert.deepEqual(await api.repairRuns(),runs);
    assert.deepEqual(await fs.readFile(path.join(root,'source',scenario.module)),original);
    assert.deepEqual(await cli('project-head'),scenario.head);
    report.native_and_recovery_verified=true;
  } catch(error){report.error=error.stack;throw error;}
  finally {await fs.writeFile(path.join(root,'daily-followup.json'),JSON.stringify(report,null,2),{flag:'wx'});}
};
