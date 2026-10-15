'use strict';
// This module is loaded only by the real Electron Extension Host, never a mock.
const vscode = require('vscode');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
const {createHash, randomUUID} = require('node:crypto');
const {execFile} = require('node:child_process');
const {promisify} = require('node:util');
const {checkpoint, failure} = require('./phase.cjs');
const execute = promisify(execFile);
const sha = value => createHash('sha256').update(value).digest('hex');
const read = async file => JSON.parse(await fs.readFile(file, 'utf8'));
const write = async (file, value) => fs.writeFile(file, JSON.stringify(value, null, 2) + '\n', {flag: 'wx'});
// VS Code URI.fsPath lowercases Windows drive letters; Python paths need not.
const editorPath = value => path.resolve(vscode.Uri.file(value).fsPath);
exports.activate = () => ({});

function cliFor(config) {
  return async (command, ...extra) => {
    const result = await execute(config.python, ['-I', '-m', 'rentgen_core', command,
      '--registry', config.registry, '--project', config.project_id, ...extra.map(String)],
    {windowsHide: true, timeout: 90000, maxBuffer: 2097153, encoding: 'utf8'});
    const envelope = JSON.parse(result.stdout);
    assert.ok(!envelope.error && Object.hasOwn(envelope, 'result'));
    return envelope.result;
  };
}

async function replace(document, text) {
  assert.equal(document.uri.scheme, 'file');
  const edit = new vscode.WorkspaceEdit();
  edit.replace(document.uri, new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length)), text);
  assert.equal(await vscode.workspace.applyEdit(edit), true);
  assert.equal(document.getText(), text);
  assert.equal(await document.save(), true);
  assert.equal(document.isDirty, false);
}

async function moduleRow(api, scenario) {
  const groups = await api.metadataSearch('WorkbenchProbe');
  assert.ok(groups.length > 0 && groups.every(row => row.kind === 'metadata-type'));
  const rows = (await Promise.all(groups.map(group => api.metadataChildren(group.token)))).flat();
  const object = rows.find(row => row.kind === 'metadata-object' && row.object.name === 'WorkbenchProbe');
  assert.ok(object, 'Real metadata search did not find the owned descriptor');
  const children = await api.metadataChildren(object.token);
  const module = children.find(row => row.kind === 'source' && row.ref.relative_path === scenario.module);
  assert.ok(module, 'Metadata object did not mint the expected module handle');
  assert.deepEqual(module.ref, scenario.ref);
  return module;
}

async function problems(api, receipt, result) {
  assert.equal(result.status, 'completed');
  assert.deepEqual(result.receipt, receipt);
  const analysis = result.report.diagnostic.analysis;
  assert.equal(analysis.status, 'completed');
  assert.equal(analysis.runtime_verified, true);
  assert.equal(result.report.diagnostic.proposal_content_id, receipt.proposal_content_id);
  assert.equal(result.report.tests.status, 'not_run');
  assert.equal(result.report.apply.status, 'unavailable');
  assert.ok(analysis.diagnostics.some(item => item.code === 'DeprecatedMessage'));
  const exact = await api.draftDocument(receipt);
  assert.deepEqual(exact.receipt, receipt);
  const document = await vscode.workspace.openTextDocument(exact.uri);
  assert.equal(sha(Buffer.from(document.getText(), 'utf8')), analysis.candidate_sha256);
  const displayed = vscode.languages.getDiagnostics(exact.uri);
  assert.equal(displayed.length, analysis.diagnostics.length, 'Problems must target the exact saved revision');
  for (const item of analysis.diagnostics) {
    assert.ok(displayed.some(d => (typeof d.code === 'object' ? d.code.value : d.code) === item.code &&
      d.range.start.line === item.start.line && d.range.start.character === item.start.character &&
      d.range.end.line === item.end.line && d.range.end.character === item.end.character), 'Missing bound diagnostic ' + item.code);
  }
  return {candidate_sha256: analysis.candidate_sha256, diagnostics: displayed.length,
    profile_id: analysis.profile_id, report_sha256: analysis.report_sha256,
    runtime_manifest_sha256: analysis.runtime_manifest_sha256};
}

async function proposal(cli, root, ref, text, label) {
  const refFile = path.join(root, label + '-ref.json');
  const replacement = path.join(root, label + '-replacement.bsl');
  await write(refFile, ref);
  await fs.writeFile(replacement, text, {flag: 'wx'});
  return (await cli('proposal-create', '--snapshot', ref.snapshot.snapshot_id,
    '--source-ref-json', refFile, '--replacement-file', replacement)).proposal;
}

async function phaseOne(api, config, scenario, root, report) {
  const cli = cliFor(config);
  checkpoint(report, 'first.snapshot');
  assert.deepEqual(api.selectedSnapshot(), scenario.snapshot);
  await api.selectSnapshot(scenario.snapshot);
  checkpoint(report, 'first.metadata');
  const module = await moduleRow(api, scenario);
  report.opened_project = true; report.metadata_search = true;
  checkpoint(report, 'first.forged-handle');
  await assert.rejects(vscode.commands.executeCommand('rentgen.editSource', 'forged-source-handle', {title: 'Refused'}), /UNKNOWN_VIEW_HANDLE/);
  report.forged_handle_refused = true;
  checkpoint(report, 'first.manual-draft');
  await vscode.commands.executeCommand('rentgen.openSelection', module.token);
  assert.equal(sha(Buffer.from(vscode.window.activeTextEditor.document.getText(), 'utf8')), scenario.original_sha256);
  const sourceBefore = await fs.readFile(path.join(scenario.source, scenario.module));
  const session = await vscode.commands.executeCommand('rentgen.editSource', module.token, {title: 'Owned manual workbench draft'});
  assert.ok(session.id && session.file);
  await replace(vscode.window.activeTextEditor.document, scenario.edited);
  const saved = await vscode.commands.executeCommand('rentgen.saveDraftEdit');
  assert.equal(saved.status, 'saved'); assert.equal(saved.receipt.revision, 1);
  assert.equal(saved.receipt.source_ref.snapshot.snapshot_id, scenario.snapshot.snapshot_id);
  assert.deepEqual(await fs.readFile(path.join(scenario.source, scenario.module)), sourceBefore);
  const manual = saved.receipt;
  assert.equal((await cli('draft-history', '--draft-id', manual.draft_id)).items.length, 1);
  report.manual_draft_saved = true;
  checkpoint(report, 'first.bsl');
  await api.refreshDrafts();
  let row = (await api.drafts()).find(item => item.receipt?.draft_id === manual.draft_id);
  assert.deepEqual(row.receipt, manual);
  const bsl = await vscode.commands.executeCommand('rentgen.bslCheck', row.token);
  report.bsl = await problems(api, manual, bsl);
  report.real_bsl = true; report.problems_exact_revision = true;

  checkpoint(report, 'first.concurrent-edit');
  const stale = await vscode.commands.executeCommand('rentgen.editDraft', row.token);
  const staleDocument = vscode.window.activeTextEditor.document;
  await replace(staleDocument, scenario.edited + '// stale local edit\r\n');
  const concurrent = await proposal(cli, root, scenario.ref, scenario.later, 'concurrent');
  const concurrentFile = path.join(root, 'concurrent-proposal.json'); await write(concurrentFile, concurrent);
  const concurrentReceipt = await cli('draft-save', '--draft-id', manual.draft_id, '--operation-id', randomUUID(),
    '--expected-revision', 1, '--snapshot', scenario.snapshot.snapshot_id, '--proposal-json', concurrentFile, '--title', manual.title);
  assert.equal(concurrentReceipt.revision, 2);
  const staleResult = await vscode.commands.executeCommand('rentgen.saveDraftEdit');
  assert.equal(staleResult.status, 'unresolved'); assert.equal(staleResult.error, 'DRAFT_CONFLICT');
  assert.equal((await cli('draft-history', '--draft-id', manual.draft_id)).items.length, 2);
  assert.equal(staleDocument.getText(), scenario.edited + '// stale local edit\r\n');
  assert.equal((await vscode.commands.executeCommand('rentgen.editResult', stale.id)).status, 'unresolved');
  report.concurrent_cli = true; report.stale_refused = true;

  checkpoint(report, 'first.revocation');
  await api.refreshDrafts();
  row = (await api.drafts()).find(item => item.receipt?.draft_id === manual.draft_id);
  const revoked = await vscode.commands.executeCommand('rentgen.editDraft', row.token);
  const revokedDocument = vscode.window.activeTextEditor.document;
  const revokedText = scenario.later + '// revoked write must remain local\r\n';
  await replace(revokedDocument, revokedText);
  const revision = (await cli('membership-list')).revision;
  const access = await cli('membership-set', '--principal-json', path.join(root, 'principal.json'),
    '--permissions-json', path.join(root, 'read-admin-permissions.json'), '--operation-id', randomUUID(), '--expected-revision', revision);
  try {
    await assert.rejects(vscode.commands.executeCommand('rentgen.saveDraftEdit'), /PROJECT_FORBIDDEN/);
    assert.equal(revokedDocument.getText(), revokedText);
  } finally {
    await cli('membership-set', '--principal-json', path.join(root, 'principal.json'),
      '--permissions-json', path.join(root, 'owner-permissions.json'), '--operation-id', randomUUID(), '--expected-revision', access.revision);
  }
  assert.equal((await cli('draft-history', '--draft-id', manual.draft_id)).items.length, 2);
  assert.equal((await api.editSessions()).some(item => item.id === revoked.id), true);
  report.revoked_write_refused = true;

  // Explicit crash-stage fixture: actual journal intent + actual CLI commit.
  // Its receipt is deliberately never passed to a UI save presenter.
  checkpoint(report, 'first.unobserved-commit');
  const crashModule = await moduleRow(api, scenario);
  await vscode.commands.executeCommand('rentgen.openSelection', crashModule.token);
  const crash = await vscode.commands.executeCommand('rentgen.editSource', crashModule.token, {title: 'Unobserved commit fixture'});
  const crashDocument = vscode.window.activeTextEditor.document;
  await replace(crashDocument, scenario.edited + '// durable intent commit unobserved\r\n');
  const folder = path.join(path.dirname(crash.file), 'attempts', '0000');
  await fs.mkdir(folder);
  await fs.copyFile(crash.file, path.join(folder, 'replacement.bsl'));
  await write(path.join(folder, 'source-ref.json'), scenario.ref);
  const prepared = (await cli('proposal-create', '--snapshot', scenario.snapshot.snapshot_id,
    '--source-ref-json', path.join(folder, 'source-ref.json'), '--replacement-file', path.join(folder, 'replacement.bsl'))).proposal;
  await write(path.join(folder, 'proposal.json'), prepared);
  const base = {project_id: config.project_id, draft_id: crash.draft_id, revision: 0,
    title: crash.title, source_ref: crash.source_ref, proposal_content_id: null};
  const intent = {operation_id: randomUUID(), base, content_id: prepared.content_id, sha256: prepared.replacement.raw_sha256};
  await write(path.join(folder, 'intent.json'), intent);
  const committed = await cli('draft-save', '--draft-id', crash.draft_id, '--operation-id', intent.operation_id,
    '--expected-revision', 0, '--snapshot', scenario.snapshot.snapshot_id, '--proposal-json', path.join(folder, 'proposal.json'), '--title', crash.title);
  assert.equal(committed.operation_id, intent.operation_id); assert.equal(committed.revision, 1);
  assert.equal((await cli('draft-history', '--draft-id', crash.draft_id)).items.length, 1);
  report.crash_stage_committed = true;

  // Advance actual Core HEAD without refreshing the explicitly selected snapshot.
  checkpoint(report, 'first.advance-head');
  await fs.writeFile(path.join(scenario.source, scenario.module), scenario.later);
  await cli('capture', '--scanner', scenario.scanner);
  const newer = await cli('project-head');
  assert.notEqual(newer.snapshot.snapshot_id, scenario.snapshot.snapshot_id);
  checkpoint(report, 'first.persist-selection');
  await api.openDraft(manual);
  assert.deepEqual(api.selectedSnapshot(), scenario.snapshot);
  const persisted = api.workbenchSnapshot();
  assert.equal(persisted.selection.kind, 'draft');
  assert.equal(persisted.selection.draft_id, manual.draft_id); assert.equal(persisted.selection.revision, 1);
  report.snapshot_pinned_before_restart = true;
  checkpoint(report, 'first.handoff');
  await write(path.join(root, 'phase1-handoff.json'), {schema: 1, pid: process.pid, snapshot: scenario.snapshot,
    selection: persisted.selection, manual, bsl_run_id: bsl.run_id,
    newer_head: newer, crash: {id: crash.id, draft_id: crash.draft_id, operation_id: intent.operation_id,
      proposal_content_id: prepared.content_id}, current_source_sha256: sha(Buffer.from(scenario.later))});
}

async function phaseTwo(api, config, scenario, root, report) {
  checkpoint(report, 'restart.handoff');
  const expected = await read(path.join(root, 'phase1-handoff.json'));
  const cli = cliFor(config);
  checkpoint(report, 'restart.process');
  assert.notEqual(process.pid, expected.pid);
  report.fresh_extension_host = true;
  // These values come from the extension's real workspaceState restoration.
  // The fixture's handoff file is only an assertion oracle, never state input.
  checkpoint(report, 'restart.snapshot');
  assert.deepEqual(api.selectedSnapshot(), expected.snapshot);
  checkpoint(report, 'restart.selection');
  assert.deepEqual(api.workbenchSnapshot().selection, expected.selection);
  checkpoint(report, 'restart.current-head');
  assert.deepEqual((await cli('project-head')).snapshot, expected.newer_head.snapshot);
  assert.notDeepEqual(api.selectedSnapshot(), expected.newer_head.snapshot);
  report.persisted_context_restored = true; report.pinned_snapshot_restored = true;
  checkpoint(report, 'restart.historical-draft');
  const historical = await api.draftDocument(expected.manual);
  assert.equal((await vscode.workspace.openTextDocument(historical.uri)).getText(), scenario.edited);
  report.historical_draft_restored = true;
  checkpoint(report, 'restart.intent-recovery');
  const historyBefore = await cli('draft-history', '--draft-id', expected.crash.draft_id);
  assert.equal(historyBefore.items.length, 1);
  const recovered = await vscode.commands.executeCommand('rentgen.editResult', expected.crash.id);
  assert.equal(recovered.status, 'saved');
  assert.equal(recovered.operation_id, expected.crash.operation_id);
  assert.equal(recovered.receipt.proposal_content_id, expected.crash.proposal_content_id);
  assert.equal(recovered.receipt.revision, 1);
  checkpoint(report, 'restart.receipt-replay');
  const again = await vscode.commands.executeCommand('rentgen.editResult', expected.crash.id);
  assert.deepEqual(again, recovered);
  assert.deepEqual(await cli('draft-history', '--draft-id', expected.crash.draft_id), historyBefore);
  assert.deepEqual(await cli('draft-receipt', '--operation-id', expected.crash.operation_id), recovered.receipt);
  report.reconciled_unobserved_commit = true; report.inspect_did_not_repeat_save = true;
  checkpoint(report, 'restart.historical-bsl');
  const runsBefore = await api.bslRuns();
  const bsl = await vscode.commands.executeCommand('rentgen.bslResult', expected.bsl_run_id);
  report.bsl = await problems(api, expected.manual, bsl);
  assert.deepEqual(await api.bslRuns(), runsBefore);
  report.historical_bsl_bound = true;
  checkpoint(report, 'restart.source');
  assert.equal(sha(await fs.readFile(path.join(scenario.source, scenario.module))), expected.current_source_sha256);
  report.source_unchanged = true;
}

exports.run = async () => {
  assert.equal(process.platform, 'win32');
  const root = process.env.RENTGEN_EDITOR_PROFILE;
  const phase = process.env.RENTGEN_WORKBENCH_PHASE;
  assert.ok(root && ['first', 'restart'].includes(phase));
  const config = await read(path.join(root, 'profile.json'));
  const scenario = await read(path.join(root, 'scenario.json'));
  const launch = await read(process.env.RENTGEN_WORKBENCH_LAUNCH);
  const report = {schema: 1, accepted: false, phase, runtime: 'actual_windows_electron_extension_host',
    process_id: process.pid, editor_api_version: vscode.version, app_name: vscode.env.appName,
    scope: 'automated real editor API execution; no human GUI/accessibility acceptance',
    fault_model: 'durable_intent_commit_unobserved', model_calls: 0, live_1c_apply: false};
  try {
    checkpoint(report, 'environment');
    assert.equal(vscode.version, launch.editor_api_version);
    assert.equal(vscode.workspace.isTrusted, true);
    assert.equal(vscode.workspace.workspaceFolders.length, 1);
    assert.equal(editorPath(vscode.workspace.workspaceFolders[0].uri.fsPath), editorPath(scenario.workspace));
    const extension = vscode.extensions.getExtension(launch.companion_id);
    assert.equal(extension?.packageJSON.version, launch.companion_version);
    assert.equal(editorPath(extension.extensionPath), editorPath(launch.extension_path));
    checkpoint(report, 'activation');
    const api = await extension.activate();
    assert.equal(api.ready, true); assert.equal(api.projectId, config.project_id);
    checkpoint(report, 'initial-inventories');
    for (const name of ['repairRuns', 'platformRuns', 'testRuns']) assert.deepEqual(await api[name](), []);
    if (phase === 'first') await phaseOne(api, config, scenario, root, report);
    else await phaseTwo(api, config, scenario, root, report);
    checkpoint(report, 'final-inventories');
    for (const name of ['repairRuns', 'platformRuns', 'testRuns']) assert.deepEqual(await api[name](), []);
    checkpoint(report, 'complete');
    report.accepted = true;
  } catch (error) {
    report.error = failure(error);
    throw error;
  } finally {
    await write(path.join(root, 'phase-' + phase + '.json'), report);
  }
};
