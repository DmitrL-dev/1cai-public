'use strict';
const vscode=require('vscode'),fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {createHash}=require('node:crypto');
exports.run=async()=>{
 const root=process.env.RENTGEN_EDITOR_PROFILE;if(!root)throw new Error('Explicit synthetic profile required');
 const prior=JSON.parse(await fs.readFile(path.join(root,'manual-acceptance.json'),'utf8'));assert.equal(prior.accepted,true);
 const extension=vscode.extensions.getExtension('rentgen.project-companion');assert.equal(extension?.packageJSON.version,'0.1.6');
 const api=await extension.activate();assert.equal(api.ready,true);
 async function files(folder){const result={};for(const entry of await fs.readdir(folder,{withFileTypes:true})){
  const file=path.join(folder,entry.name);if(entry.isDirectory())Object.assign(result,await files(file));
  else result[path.relative(root,file)]=createHash('sha256').update(await fs.readFile(file)).digest('hex');
 }return result;}
 const before=await files(path.join(root,'edit-sessions'));
 const session=(await api.editSessions()).find(s=>s.id===prior.sessions.first);assert.ok(session);
 await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(vscode.Uri.file(session.file)),{preview:false});
 assert.equal((await vscode.commands.executeCommand('rentgen.saveDraftEdit')).status,'unchanged');
 assert.deepEqual((await vscode.commands.executeCommand('rentgen.editResult',prior.sessions.first)).receipt,prior.saved.receipt);
 assert.equal((await vscode.commands.executeCommand('rentgen.editResult',prior.sessions.stale)).status,'unresolved');
 assert.deepEqual(await files(path.join(root,'edit-sessions')),before);
 assert.deepEqual((await vscode.commands.executeCommand('rentgen.platformResult',prior.platform.run_id)).report,prior.platform.report);
 const name=process.env.RENTGEN_MANUAL_RECOVERY_REPORT || 'manual-recovery.json';
 assert.ok(/^[a-z0-9-]+\.json$/.test(name));
 await fs.writeFile(path.join(root,name),JSON.stringify({accepted:true,new_saves:0,new_model_calls:0,companion:'0.1.6',unchanged_save_verified:true},null,2),{flag:'wx'});
};
