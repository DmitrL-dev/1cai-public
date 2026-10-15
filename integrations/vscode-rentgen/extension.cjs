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
const {createBslService}=require('./lib/bsl.cjs');
const {createBslUI}=require('./lib/bsl-ui.cjs');
const {createTestService}=require('./lib/testing.cjs');
const {createTestsUI}=require('./lib/tests-ui.cjs');
const {createOwnerBootstrap}=require('./lib/owner-bootstrap.cjs');
const {createWorkbenchState}=require('./lib/workbench-state.cjs');
const {createMetadataView}=require('./lib/metadata-view.cjs');
const {createBslProblems}=require('./lib/bsl-problems.cjs');
// Captured at module load: an explicit D10 selection cannot downgrade to local spawn.
const selectedOwnerMode=process.env.RENTGEN_D10_OWNER_MODE;
const coldOwnerBootstrap=selectedOwnerMode===undefined?null:createOwnerBootstrap();

exports.activate = async context => {
  const initialSubscriptions = context.subscriptions.length;
  await vscode.commands.executeCommand('setContext', 'rentgen.ready', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.profileLoaded', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.metadataAvailable', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.repairAvailable', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.repairRunning', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.platformAvailable', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.platformRunning', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.editAvailable', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.bslAvailable', false);
  await vscode.commands.executeCommand('setContext', 'rentgen.bslRunning', false);
  if (coldOwnerBootstrap) {
    await vscode.commands.executeCommand('setContext', 'rentgen.testsAvailable', false);
    const refusal = error => Object.freeze({ready:false, error, owner:coldOwnerBootstrap.snapshot()});
    if (selectedOwnerMode !== 'cold-ready') return refusal('OWNER_MODE_INVALID');
    try {
      // No real owner transport has been admitted. The initializer remains
      // denied even if a constructed binding were substituted into this seam.
      await coldOwnerBootstrap.activate(context, () => {throw new Error('OWNER_TRANSPORT_NOT_ADMITTED');});
    } catch (error) {return refusal(error.message);}
    return refusal('OWNER_RUNTIME_ADMISSION_REQUIRED');
  }
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
    const workbench = createWorkbenchState(context.workspaceState, config);
    const views = createViews(vscode, client, context, {workbench, trusted:()=>vscode.workspace.isTrusted, projectId:config.project_id});
    await vscode.commands.executeCommand('setContext','rentgen.profileLoaded',true);
    // A damaged or unavailable restored pin never silently falls back to HEAD.
    // Keep the explicit reset command available so the user can resolve it.
    let restorationError = null;
    try {await views.initialize();}
    catch (error) {
      restorationError = error.message;
      void vscode.window.showErrorMessage('Рентген: сохранённый рабочий контекст не открыт. ' + error.message + '. Для явного выбора последнего снимка используйте «Сбросить рабочий контекст».');
    }
    let navigation = {supported:false}, navigationReason = '';
    try {navigation = await client.navigationCapability();}
    catch (error) {navigationReason = error.message;}
    const metadata = createMetadataView(vscode, client, views, context, {
      enabled:navigation.supported, reason:navigationReason, trusted:()=>vscode.workspace.isTrusted});
    const problems = createBslProblems(vscode, {trusted:()=>vscode.workspace.isTrusted, readDraft:views.draftDocument});
    context.subscriptions.push(problems, views.onDidChangeContext(()=>problems.clear('stale')));
    context.subscriptions.push(vscode.workspace.onDidChangeTextDocument(event => {
      if (event.document.uri.scheme === 'file' && event.contentChanges.length) problems.clear('stale');
    }));
    context.subscriptions.push(vscode.workspace.onDidCloseTextDocument(document => {
      if (document.uri.scheme === 'rentgen-view') problems.clear('closed');
    }));
    const repairAvailable = ['0.1.0.dev7','0.1.0.dev8','0.1.0.dev9','0.1.0.dev10','0.1.0.dev11','0.1.0.dev12','0.1.0.dev13','0.1.0.dev14','0.1.0.dev15','0.1.0.dev16','0.1.0.dev17','0.1.0.dev19'].includes(config.core_version);
    const nativeAvailable = ['0.1.0.dev8','0.1.0.dev9','0.1.0.dev10','0.1.0.dev11','0.1.0.dev12','0.1.0.dev13','0.1.0.dev14','0.1.0.dev15','0.1.0.dev16','0.1.0.dev17','0.1.0.dev19'].includes(config.core_version);
    const repair = createRepairUI(vscode, createRepairService({root,extensionRoot:context.extensionPath,config,client,trusted:()=>vscode.workspace.isTrusted}),views,context,repairAvailable);
    const edit=createEditUI(vscode,createEditService({root,config,client,trusted:()=>vscode.workspace.isTrusted}),views,context,repairAvailable);
    let bslRunner;
    const bslClient=createClient(config,{trusted:()=>vscode.workspace.isTrusted,execute:async(command,args)=>{
      const owned=createRunner({timeout:args[3]==='proposal-check'?180000:30000});bslRunner=owned;
      try{return await owned.execute(command,args);}finally{owned.dispose();if(bslRunner===owned)bslRunner=null;}
    }});
    context.subscriptions.push(bslClient);
    const bsl=createBslUI(vscode,createBslService({root,config,client:bslClient,trusted:()=>vscode.workspace.isTrusted,cancel:()=>bslRunner?.dispose()}),views,context,nativeAvailable,{problems});
    let testRunner;
    const testClient=createClient(config,{trusted:()=>vscode.workspace.isTrusted,execute:async(command,args)=>{
      const owned=createRunner({timeout:args[3]==='proposal-test'?1000000:30000});testRunner=owned;
      try{return await owned.execute(command,args);}finally{owned.dispose();if(testRunner===owned)testRunner=null;}
    }});
    context.subscriptions.push(testClient);
    const tests=createTestsUI(vscode,createTestService({root,config,client:testClient,trusted:()=>vscode.workspace.isTrusted,cancel:()=>testRunner?.dispose()}),views,context,nativeAvailable);
    let nativeRunner;
    const nativeClient = createClient(config,{trusted:()=>vscode.workspace.isTrusted,execute:async(command,args)=>{
      const owned = createRunner({timeout:args[3]==='proposal-platform-check'?660000:30000});
      nativeRunner = owned;
      try {return await owned.execute(command,args);} finally {owned.dispose();if(nativeRunner===owned) nativeRunner=null;}
    }});
    context.subscriptions.push(nativeClient);
    const platform = createPlatformUI(vscode,createPlatformService({root,config,client:nativeClient,
      trusted:()=>vscode.workspace.isTrusted,cancel:()=>nativeRunner?.dispose()}),views,context,nativeAvailable);
    await vscode.commands.executeCommand('setContext', 'rentgen.ready', restorationError === null);
    await vscode.commands.executeCommand('setContext','rentgen.metadataAvailable',navigation.supported);
    await vscode.commands.executeCommand('setContext','rentgen.repairAvailable',repairAvailable);
    await vscode.commands.executeCommand('setContext','rentgen.platformAvailable',nativeAvailable);
    await vscode.commands.executeCommand('setContext','rentgen.editAvailable',repairAvailable);
    await vscode.commands.executeCommand('setContext','rentgen.bslAvailable',nativeAvailable);
    await vscode.commands.executeCommand('setContext','rentgen.testsAvailable',nativeAvailable);
    return Object.freeze({ready: restorationError === null, ...(restorationError ? {error:restorationError} : {}),
      projectId: config.project_id, ...views, navigationAvailable:navigation.supported,
      metadataRoots:metadata.roots, metadataChildren:metadata.children, metadataSearch:metadata.search,
      repairRuns:repair.runs,platformRuns:platform.runs,editSessions:edit.sessions,bslRuns:bsl.runs,testRuns:tests.runs});
  } catch (error) {
    for (const subscription of context.subscriptions.splice(initialSubscriptions).reverse()) subscription.dispose();
    await vscode.commands.executeCommand('setContext','rentgen.profileLoaded',false);
    void vscode.window.showErrorMessage('Рентген: не удалось открыть профиль. ' + error.message);
    return Object.freeze({ready: false, error: error.message});
  }
};
