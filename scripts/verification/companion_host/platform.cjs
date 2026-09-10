'use strict';
// Read-only host acceptance after native service acceptance in an owned fixture.
const vscode = require('vscode');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
exports.run = async () => {
  const root = process.env.RENTGEN_EDITOR_PROFILE;
  if (!root) throw new Error('Explicit synthetic profile required');
  const proof = JSON.parse(await fs.readFile(path.join(root,'service-acceptance.json'),'utf8'));
  assert.equal(proof.accepted,true);
  const extension = vscode.extensions.getExtension('rentgen.project-companion');
  assert.equal(extension?.packageJSON.version,'0.1.5');
  const api = await extension.activate(); assert.equal(api.ready,true);
  const rows = await api.drafts(); assert.equal(rows.length,2);
  assert.throws(()=>api.selectedDraft('forged'),/UNKNOWN_VIEW_HANDLE/);
  for (const row of rows) assert.deepEqual(api.selectedDraft(row.token),row.receipt);
  const before = await api.platformRuns(); assert.equal(before.length,2);
  for (const item of proof.checks) {
    const result = await vscode.commands.executeCommand('rentgen.platformResult',item.id);
    assert.equal(result.status,'completed');
    assert.equal(result.report.analysis.candidate.status,item.status);
    const shown = vscode.window.activeTextEditor.document;
    assert.equal(shown.languageId,'json');
    assert.deepEqual(JSON.parse(shown.getText()),result);
    assert.equal(shown.isUntitled,true);
  }
  assert.deepEqual(await api.platformRuns(),before);
  await fs.writeFile(path.join(root,'host-platform-acceptance.json'),JSON.stringify({
    accepted:true,vscode:vscode.version,companion:extension.packageJSON.version,
    recovered_reports:2,new_checks:0,model_calls:0,manual_picker_tested:false,
  },null,2));
};
