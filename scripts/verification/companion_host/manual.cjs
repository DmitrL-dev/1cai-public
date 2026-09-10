'use strict';
const vscode=require('vscode'),fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {promisify}=require('node:util'),execute=promisify(require('node:child_process').execFile);
exports.run=async()=>{
 const root=process.env.RENTGEN_EDITOR_PROFILE;if(!root)throw new Error('Explicit synthetic profile required');
 const scenario=JSON.parse(await fs.readFile(path.join(root,'daily-scenario.json'),'utf8'));
 const config=JSON.parse(await fs.readFile(path.join(root,'profile.json'),'utf8'));
 const prior=JSON.parse(await fs.readFile(path.join(root,'daily-acceptance.json'),'utf8'));
 const extension=vscode.extensions.getExtension('rentgen.project-companion');assert.equal(extension?.packageJSON.version,'0.1.6');
 const api=await extension.activate();assert.equal(api.ready,true);
 const report={accepted:false,model_calls:0,companion:'0.1.6',vscode:vscode.version};
 const cli=async(command,...extra)=>JSON.parse((await execute(config.python,['-I','-m','rentgen_core',command,'--registry',config.registry,'--project',config.project_id,...extra.map(String)],{windowsHide:true,timeout:30000,maxBuffer:2097153,encoding:'utf8'})).stdout).result;
 try{
  const source=path.join(root,'source',scenario.module),original=await fs.readFile(source),runs=await api.repairRuns();
  assert.equal(runs.length,1);const modelEvents=path.join(root,'repair-runs',prior.repair.id,'result/events.jsonl'),events=await fs.readFile(modelEvents);
  const before=await cli('draft-get','--draft-id',prior.repair.receipt.draft_id,'--revision',2);
  const row=(await api.drafts()).find(r=>r.receipt?.draft_id===prior.repair.receipt.draft_id);assert.equal(row.receipt.revision,2);
  const first=await vscode.commands.executeCommand('rentgen.editDraft',row.token);
  const stale=await vscode.commands.executeCommand('rentgen.editDraft',row.token);
  const fixed=original.toString('utf8').replace('    Исключение\r\n','    Исключение\r\n        ВызватьИсключение;\r\n');
  const edit=async session=>{
   const doc=await vscode.workspace.openTextDocument(vscode.Uri.file(session.file));await vscode.window.showTextDocument(doc,{preview:false});
   const change=new vscode.WorkspaceEdit();change.replace(doc.uri,new vscode.Range(doc.positionAt(0),doc.positionAt(doc.getText().length)),fixed.replace(/^\uFEFF/,''));
   assert.equal(await vscode.workspace.applyEdit(change),true);assert.equal(doc.isDirty,true);
   return vscode.commands.executeCommand('rentgen.saveDraftEdit');
  };
  report.saved=await edit(first);assert.equal(report.saved.status,'saved');assert.equal(report.saved.receipt.revision,3);
  const saved=await cli('draft-get','--draft-id',row.receipt.draft_id,'--revision',3);
  assert.deepEqual(Buffer.from(saved.proposal.replacement.base64,'base64'),Buffer.from(fixed,'utf8'));
  assert.deepEqual(await cli('draft-get','--draft-id',row.receipt.draft_id,'--revision',2),before);
  report.conflict=await edit(stale);assert.equal(report.conflict.status,'unresolved');assert.equal(report.conflict.error,'DRAFT_CONFLICT');
  const attempts=await fs.readdir(path.join(root,'edit-sessions',stale.id,'attempts'));
  assert.equal((await vscode.commands.executeCommand('rentgen.saveDraftEdit')).status,'unresolved');
  assert.deepEqual(await fs.readdir(path.join(root,'edit-sessions',stale.id,'attempts')),attempts);
  assert.deepEqual(await fs.readFile(stale.file),Buffer.from(fixed,'utf8'));
  const latest=(await api.drafts()).find(r=>r.receipt?.draft_id===row.receipt.draft_id);assert.equal(latest.receipt.revision,3);
  report.platform=await vscode.commands.executeCommand('rentgen.platformCheck',latest.token,scenario.platform);
  assert.equal(report.platform.report.analysis.candidate.status,'passed');assert.equal(report.platform.report.analysis.baseline.status,'passed');
  assert.equal(report.platform.report.proposal_content_id,saved.receipt.proposal_content_id);
  assert.deepEqual((await vscode.commands.executeCommand('rentgen.editResult',first.id)).receipt,saved.receipt);
  assert.deepEqual(await fs.readFile(source),original);assert.deepEqual(await cli('project-head'),scenario.head);
  assert.deepEqual(await fs.readFile(modelEvents),events);assert.deepEqual(await api.repairRuns(),runs);
  await fs.writeFile(path.join(root,'manual-proposal.json'),JSON.stringify(saved.proposal),{flag:'wx'});
  report.sessions={first:first.id,stale:stale.id};report.history_preserved=true;report.live_source_unchanged=true;report.accepted=true;
 }catch(error){report.error=error.stack;throw error;}
 finally{await fs.writeFile(path.join(root,'manual-acceptance.json'),JSON.stringify(report,null,2),{flag:'wx'});}
};
