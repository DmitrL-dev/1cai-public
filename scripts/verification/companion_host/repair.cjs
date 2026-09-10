'use strict';
const vscode=require('vscode');
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
const {createHash}=require('node:crypto');
const {promisify}=require('node:util');
const runFile=promisify(require('node:child_process').execFile);

exports.run=async(root,mode,runId)=>{
  if (!root || !/^[a-z0-9-]{1,40}$/.test(runId)) throw new Error('Explicit artificial acceptance profile required');
  const config=JSON.parse(await fs.readFile(path.join(root,'profile.json'),'utf8'));
  const scenario=JSON.parse(await fs.readFile(path.join(root,'diagnostic-scenario.json'),'utf8'));
  const report={accepted:false,mode,checks:[],inputAutomation:'registered-command-arguments',manualInputTested:false,platform1cTested:false};
  const reportFile=path.join(root,`companion-${runId}-acceptance.json`);
  const checkpoint=async name=>{report.checks.push(name);await fs.writeFile(reportFile,JSON.stringify(report,null,2));};
  try {
    assert.equal(vscode.workspace.isTrusted,true);
    const extension=vscode.extensions.getExtension('rentgen.project-companion'); assert.ok(extension);
    assert.equal(extension.packageJSON.version,'0.1.4');
    assert.equal(vscode.extensions.getExtension('saoudrizwan.claude-dev')?.isActive ?? false,false);
    const api=await extension.activate(); assert.equal(api.ready,true);assert.equal(api.projectId,scenario.project_id);
    const cli=async(command,...extra)=>JSON.parse((await runFile(config.python,['-I','-m','rentgen_core',command,'--registry',config.registry,
      '--project',config.project_id,...extra.map(String)],{windowsHide:true,timeout:45000,maxBuffer:2097153,encoding:'utf8'})).stdout).result;
    const original=Buffer.from(scenario.original,'base64');
    let result;
    if (mode==='repair') {
      assert.deepEqual(await api.repairRuns(),[]);
      const sources=await api.sources();assert.equal(sources.length,1);
      await assert.rejects(vscode.commands.executeCommand('rentgen.repairSource','forged-handle',{model:'qwen3.5:9b',instruction:'Never run'}),/UNKNOWN_VIEW_HANDLE/);
      const instruction=await fs.readFile(path.join(root,'managed-repair-instruction.txt'),'utf8');
      await checkpoint('installed-dev7-companion-and-minted-source');
      result=await vscode.commands.executeCommand('rentgen.repairSource',sources[0].token,{model:'qwen3.5:9b',instruction});
      await fs.writeFile(path.join(root,'repair-editor-result.json'),JSON.stringify(result,null,2),{flag:'wx'});
    } else {
      const prior=JSON.parse(await fs.readFile(path.join(root,'repair-editor-result.json'),'utf8'));
      const runs=await api.repairRuns();assert.equal(runs.length,1);assert.equal(runs[0].id,prior.id);
      result=await vscode.commands.executeCommand('rentgen.repairResult',prior.id);
      assert.deepEqual(result,prior);
      await checkpoint('fresh-session-reconciles-existing-operation-without-new-run');
    }
    report.result=result;assert.equal(result.status,'analysis_clean');assert.equal(result.receipt.revision,2);
    const saved=await cli('draft-get','--draft-id',result.receipt.draft_id,'--revision',2);
    assert.deepEqual(saved.receipt,result.receipt);
    const candidate=Buffer.from(saved.proposal.replacement.base64,'base64');
    assert.notDeepEqual(candidate,original);
    const diffs=vscode.window.tabGroups.all.flatMap(g=>g.tabs).filter(t=>t.input instanceof vscode.TabInputTextDiff);
    assert.equal(diffs.length,1);
    const left=await vscode.workspace.openTextDocument(diffs[0].input.original),right=await vscode.workspace.openTextDocument(diffs[0].input.modified);
    assert.equal(left.getText(),original.toString('utf8').replace(/^\uFEFF/,''));
    assert.equal(right.getText(),candidate.toString('utf8').replace(/^\uFEFF/,''));
    const editor=await vscode.window.showTextDocument(right,{preview:false});const before=editor.document.getText();
    await vscode.commands.executeCommand('type',{text:'// forbidden\n'});
    assert.equal(editor.document.getText(),before);assert.equal(editor.document.isDirty,false);
    assert.deepEqual(await fs.readFile(scenario.source),original);assert.deepEqual(await cli('project-head'),config.head_at_setup);
    await checkpoint('actual-revision-diff-readonly-and-source-head-unchanged');
    const events=(await fs.readFile(path.join(root,'repair-runs',result.id,'result/events.jsonl'),'utf8')).trim().split('\n').map(JSON.parse);
    assert.equal(events.filter(e=>e.phase==='model_requested').length,1);
    assert.equal(events.filter(e=>e.phase==='edit_requested').length,1);
    report.modelRequests=1;report.model=events.find(e=>e.phase==='model_responded')?.metrics;
    report.candidateSha256=createHash('sha256').update(candidate).digest('hex');
    report.version=extension.packageJSON.version;report.vscode=vscode.version;report.extensionPath=extension.extensionPath;
    report.adapterHashes={};for (const name of ['run_repair.py','repair_model.py','repair_workflow.py']) {
      report.adapterHashes[name]=createHash('sha256').update(await fs.readFile(path.join(extension.extensionPath,'repair',name))).digest('hex');
    }
    await checkpoint('one-model-request-and-one-edit-in-persisted-journal');
    report.accepted=true;
  } catch(error) {report.error=error.stack;throw error;}
  finally {await fs.writeFile(reportFile,JSON.stringify(report,null,2));}
};
