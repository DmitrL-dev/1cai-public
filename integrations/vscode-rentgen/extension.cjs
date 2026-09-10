'use strict';
const vscode = require('vscode');
const fs = require('node:fs/promises');
const path = require('node:path');
const { createClient, profileConfig } = require('./lib/core.cjs');
const { createRunner } = require('./lib/process.cjs');
const { createViews } = require('./lib/views.cjs');
const { createRepairService } = require('./lib/repair.cjs');
const { createRepairUI } = require('./lib/repair-ui.cjs');
const { createPlatformService } = require('./lib/platform.cjs');
const { createPlatformUI } = require('./lib/platform-ui.cjs');
const { createEditService } = require('./lib/edit.cjs');
const { createEditUI } = require('./lib/edit-ui.cjs');

exports.activate = async context => {
  const initialSubscriptions = context.subscriptions.length;
  await vscode.commands.executeCommand('setContext', 'rentgen.ready', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.repairAvailable', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.repairRunning', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.platformAvailable', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.platformRunning', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.editAvailable', false);
  if (!vscode.workspace.isTrusted) return Object.freeze({ready: false, error: 'TRUST_REQUIRED'});
  const root = process.env.RENTGEN_EDITOR_PROFILE;
  if (!root) return Object.freeze({ready: false, error: 'EDITOR_PROFILE_REQUIRED'});
  let runner;
  try {
    if (process.platform !== 'win32' || !path.isAbsolute(root)) throw new Error('WINDOWS_PROFILE_REQUIRED');
    const file = await fs.open(path.join(root, 'profile.json'), 'r');
    let config;
    try {
      if ((await file.stat()).size > 65536) throw new Error('INVALID_EDITOR_PROFILE');
      const bytes = Buffer.alloc(65537);
      const read = await file.read(bytes, 0, bytes.length, 0);
      if (read.bytesRead > 65536) throw new Error('INVALID_EDITOR_PROFILE');
      config = profileConfig(JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes.subarray(0, read.bytesRead))));
    } finally { await file.close(); }
    runner = createRunner(); context.subscriptions.push(runner);
    const client = createClient(config, {execute: runner.execute, trusted: () => vscode.workspace.isTrusted});
    context.subscriptions.push(client);
    const views = createViews(vscode, client, context);
    // Authorize the project before making its panels available.
    await views.refreshSources();
    const repairAvailable = ['0.1.0.dev7','0.1.0.dev8'].includes(config.core_version);
    const repair = createRepairUI(vscode, createRepairService({root,extensionRoot:context.extensionPath,config,client,trusted:()=>vscode.workspace.isTrusted}),views,context,repairAvailable);
    const edit=createEditUI(vscode,createEditService({root,config,client,trusted:()=>vscode.workspace.isTrusted}),views,context,repairAvailable);
    let nativeRunner;
    const nativeClient = createClient(config,{trusted:()=>vscode.workspace.isTrusted,execute:async(command,args)=>{
      const owned = createRunner({timeout:args[3]==='proposal-platform-check'?660000:30000});
      nativeRunner = owned;
      try {return await owned.execute(command,args);} finally {owned.dispose();if(nativeRunner===owned) nativeRunner=null;}
    }});
    context.subscriptions.push(nativeClient);
    const platform = createPlatformUI(vscode,createPlatformService({root,config,client:nativeClient,
      trusted:()=>vscode.workspace.isTrusted,cancel:()=>nativeRunner?.dispose()}),views,context,config.core_version==='0.1.0.dev8');
    await vscode.commands.executeCommand('setContext', 'rentgen.ready', true);
    await vscode.commands.executeCommand('setContext','rentgen.repairAvailable',repairAvailable);
    await vscode.commands.executeCommand('setContext','rentgen.platformAvailable',config.core_version==='0.1.0.dev8');
    await vscode.commands.executeCommand('setContext','rentgen.editAvailable',repairAvailable);
    return Object.freeze({ready: true, projectId: config.project_id, ...views,repairRuns:repair.runs,platformRuns:platform.runs,editSessions:edit.sessions});
  } catch (error) {
    for (const subscription of context.subscriptions.splice(initialSubscriptions).reverse()) subscription.dispose();
    void vscode.window.showErrorMessage('Рентген: не удалось открыть профиль. ' + error.message);
    return Object.freeze({ready: false, error: error.message});
  }
};
