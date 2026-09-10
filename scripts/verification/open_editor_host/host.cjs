const vscode = require('vscode');
const fs = require('node:fs/promises');
const path = require('node:path');
exports.activate = () => ({});

exports.run = async () => {
  const root = process.env.RENTGEN_EDITOR_ACCEPTANCE;
  if (!root) throw new Error('Explicit acceptance profile is required');
  const profile = JSON.parse(await fs.readFile(path.join(root, 'profile.json'), 'utf8'));
  const cline = vscode.extensions.getExtension('saoudrizwan.claude-dev');
  if (!cline || cline.packageJSON.version !== profile.cline_version) {
    throw new Error('Pinned Cline extension is missing');
  }
  const api = await cline.activate();
  let companion;
  if (profile.companion_version) {
    const extension = vscode.extensions.getExtension('rentgen.project-companion');
    if (!extension || extension.packageJSON.version !== profile.companion_version) throw new Error('Pinned companion is missing');
    companion = await extension.activate();
    if (!companion.ready || companion.projectId !== profile.project_id) throw new Error('Companion startup failed');
  }
  const report = {
    vscode: vscode.version, cline: cline.packageJSON.version, active: cline.isActive,
    extensionPath: cline.extensionPath, workspace: vscode.workspace.workspaceFolders[0].uri.fsPath,
    clineData: process.env.CLINE_DATA_DIR, project_id: profile.project_id,
    clineBundle: process.env.CLINE_BUNDLE_OVERRIDE,
    appName: vscode.env.appName,
    phase: 'activated',
    companionReady: companion?.ready,
  };
  const reportPath = path.join(root, 'host-acceptance.json');
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2));
  if (process.env.RENTGEN_EDITOR_PROMPT_FILE) {
    const tasks = path.join(root, 'editor/User/globalStorage/saoudrizwan.claude-dev/tasks');
    const previous = new Set(await fs.readdir(tasks).catch(() => []));
    const prompt = await fs.readFile(process.env.RENTGEN_EDITOR_PROMPT_FILE, 'utf8');
    await api.startNewTask(prompt);
    report.phase = 'task-started';
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2));
    // Stop on completion or a connection failure, and cap the entire attempt.
    // Model completion does not assert that the requested durable result exists.
    const captureMarker = process.env.RENTGEN_EDITOR_REQUEST_CAPTURE;
    const deadline = Date.now() + (captureMarker ? 30000 : 240000);
    report.phase = 'observation-timeout';
    outer: while (Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      for (const task of await fs.readdir(tasks).catch(() => [])) {
        if (previous.has(task)) continue;
        const file = path.join(tasks, task, 'ui_messages.json');
        const messages = await fs.readFile(file, 'utf8').then(JSON.parse).catch(() => []);
        report.task_id = task;
        if (captureMarker && await fs.access(captureMarker).then(() => true).catch(() => false)) {
          report.phase = 'transport-captured';
          report.modelExecution = 'not-run';
          break outer;
        }
        if (messages.some(m => m.ask === 'completion_result')) {
          report.phase = 'model-completed';
          break outer;
        }
        const history = await fs.readFile(path.join(tasks, task, 'api_conversation_history.json'), 'utf8').catch(() => '');
        if (history.includes('No connection found for server: rentgen')) {
          report.phase = 'mcp-connection-failed';
          break outer;
        }
        if (messages.filter(m => m.say === 'api_req_started').length >= 9) {
          report.phase = 'request-limit';
          break outer;
        }
      }
    }
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2));
  }
};
