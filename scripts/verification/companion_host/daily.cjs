'use strict';
const vscode=require('vscode'),fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {createHash}=require('node:crypto');
exports.run=async()=>{
  const root=process.env.RENTGEN_EDITOR_PROFILE;
  if(!root)throw new Error('Explicit synthetic profile required');
  const scenario=JSON.parse(await fs.readFile(path.join(root,'daily-scenario.json'),'utf8'));
  const extension=vscode.extensions.getExtension('rentgen.project-companion');
  assert.equal(extension?.packageJSON.version,'0.1.5');
  const api=await extension.activate();assert.equal(api.ready,true);
  const record={accepted:false,vscode:vscode.version,companion:'0.1.5',model_calls:null,input:'registered-command-arguments',manual_picker_tested:false};
  const save=()=>fs.writeFile(path.join(root,'daily-acceptance.json'),JSON.stringify(record,null,2));
  try {
    const source=path.join(root,'source',scenario.module),original=await fs.readFile(source);
    const sources=await api.sources(),selected=sources.find(row=>row.ref?.relative_path===scenario.module);
    assert.ok(selected);assert.deepEqual(await api.repairRuns(),[]);
    record.repair=await vscode.commands.executeCommand('rentgen.repairSource',selected.token,{model:scenario.model,instruction:scenario.instruction});
    await save();assert.equal(record.repair.receipt.revision,2);
    const folder=path.join(root,'repair-runs',record.repair.id,'result');
    const events=(await fs.readFile(path.join(folder,'events.jsonl'),'utf8')).trim().split('\n').map(JSON.parse);
    record.model_calls=events.filter(e=>e.phase==='model_requested').length;assert.equal(record.model_calls,1);
    assert.equal(events.filter(e=>e.phase==='edit_requested').length,1);
    const model=events.find(e=>e.phase==='model_responded');record.model_metrics=model.metrics;
    const repair=JSON.parse(await fs.readFile(path.join(folder,'result.json'),'utf8'));
    record.diagnostics_before=repair.before.diagnostic.analysis.diagnostics;
    record.diagnostics_after=repair.after.diagnostic.analysis.diagnostics;
    // Conservative fixture postcondition: accepting clean diagnostics alone
    // would miss a handler that still swallows the original exception.
    const [,candidateUri]=await api.openDraft(record.repair.receipt);
    const normalize=text=>text.replace(/^\uFEFF/,'').replace(/\r\n/g,'\n');
    const candidate=normalize((await vscode.workspace.openTextDocument(candidateUri)).getText());
    const originalText=normalize(original.toString('utf8'));
    const rethrow=originalText.replace('    Исключение\n','    Исключение\n        ВызватьИсключение;\n');
    const direct=originalText.replace('    Попытка\n        ДокументОбъект.Записать();\n    Исключение\n    КонецПопытки;','    ДокументОбъект.Записать();');
    record.fixture_postcondition=candidate===rethrow || candidate===direct;
    await save();assert.equal(record.fixture_postcondition,true,'Fixture must preserve exception propagation');
    await save();assert.equal(record.repair.status,'analysis_clean');
    assert.ok(repair.before.diagnostic.analysis.diagnostics.length>0);
    assert.equal(repair.after.diagnostic.analysis.diagnostics.length,0);
    const drafts=await api.drafts(),draft=drafts.find(row=>row.receipt?.draft_id===record.repair.receipt.draft_id);
    assert.ok(draft);assert.deepEqual(api.selectedDraft(draft.token),record.repair.receipt);
    record.platform=await vscode.commands.executeCommand('rentgen.platformCheck',draft.token,scenario.platform);
    await save();assert.equal(record.platform.status,'completed');
    assert.equal(record.platform.report.analysis.baseline.status,'passed');
    assert.equal(record.platform.report.analysis.candidate.status,'passed');
    assert.deepEqual(record.platform.report.source_ref,record.repair.receipt.source_ref);
    assert.equal(record.platform.report.proposal_content_id,record.repair.receipt.proposal_content_id);
    assert.equal(record.platform.report.candidate_sha256,repair.candidate_sha256);
    const recovered=await vscode.commands.executeCommand('rentgen.platformResult',record.platform.run_id);
    assert.deepEqual(recovered.report,record.platform.report);
    const shown=vscode.window.activeTextEditor.document;assert.equal(shown.languageId,'json');assert.deepEqual(JSON.parse(shown.getText()),recovered);
    assert.deepEqual(await fs.readFile(source),original);
    record.original_sha256=createHash('sha256').update(original).digest('hex');
    record.tests={status:'not_run'};record.apply={status:'unavailable'};record.accepted=true;
  } catch(error){record.error=error.stack;throw error;} finally {await save();}
};
