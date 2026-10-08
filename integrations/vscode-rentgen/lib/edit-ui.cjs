'use strict';
function createEditUI(vscode,service,views,context,enabled){
 let busy=false;
 function check(){if(!vscode.workspace.isTrusted)throw new Error('TRUST_REQUIRED');if(!enabled)throw new Error('EDIT_REQUIRES_DEV7_OR_DEV8');}
 async function openFile(session){check();await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(vscode.Uri.file(session.file)),{preview:false});return session;}
 async function show(result,current=()=>true,notificationCurrent=current){
  check();
  if(result.status==='saved'){
   views.refreshDrafts();if(!current())return result;
   const opened=await views.openDraft(result.receipt,current);check();
   if(opened!==null&&notificationCurrent(opened))void vscode.window.showInformationMessage(`Рентген: сохранена версия ${result.receipt.revision} черновика. Запустите проверки этой версии; конфигурация не изменялась.`);
  }else if(!current())return result;
  else if(result.status==='unchanged')void vscode.window.showInformationMessage('Рентген: сохранённые байты не изменились; новая версия не создана.');
  else if(result.status==='unresolved')void vscode.window.showInformationMessage('Рентген: результат сохранения не подтверждён. '+(result.error||'')+' Рабочая копия сохранена. Повторной отправки нет; получите результат операции или откройте новую сессию из актуальной версии.');
  else await openFile(result);
  return result;
 }
 async function open(selection){check();const receipt=views.selectedDraft(typeof selection==='string'?selection:selection?.token);return openFile(await service.open(receipt));}
 async function save(){
  check();if(busy||service.running)throw new Error('EDIT_RUNNING');busy=true;
  try{
   const document=vscode.window.activeTextEditor?.document;
   if(document?.uri.scheme!=='file')throw new Error('UNKNOWN_EDIT_DOCUMENT');
   const file=document.uri.fsPath,initialVersion=document.version;
   const sameDocument=()=>!document.isClosed&&document.uri.scheme==='file'&&document.uri.fsPath===file;
   const selected=await service.forFile(file);check();
   if(!sameDocument()||document.version!==initialVersion)throw new Error('EDIT_BUFFER_CHANGED');
   if(document.isDirty&&!await document.save())throw new Error('EDIT_BUFFER_NOT_SAVED');
   check();if(!sameDocument()||document.isDirty)throw new Error('EDIT_BUFFER_NOT_SAVED');
   // Format-on-save may produce a new clean version. Later edits, including an
   // autosave back to clean, must not present this completion as the current buffer.
   const version=document.version;
   const bufferCurrent=()=>sameDocument()&&document.version===version&&!document.isDirty;
   const current=()=>vscode.workspace.isTrusted&&bufferCurrent()&&vscode.window.activeTextEditor?.document===document;
   const notificationCurrent=opened=>{
    const active=vscode.window.activeTextEditor?.document;
    return bufferCurrent()&&(active===document||(Array.isArray(opened)&&opened.some(uri=>uri.toString()===active?.uri?.toString())));
   };
   return await show(await service.save(selected.id),current,notificationCurrent);
  }finally{busy=false;}
 }
 async function inspect(id){
  check();if(busy||service.running)throw new Error('EDIT_RUNNING');
  if(!id){const selected=await vscode.window.showQuickPick((await service.list()).map(s=>({label:`v${s.receipt.revision} · ${s.receipt.source_ref.relative_path}`,description:s.created_at,detail:s.id,id:s.id})),{title:'Редактирование: продолжить или получить результат'});if(!selected)return null;id=selected.id;}
  const result=await show(await service.inspect(id));
  if(result.status!=='editing')await openFile(result);
  return result;
 }
 for(const [name,fn]of [['rentgen.editDraft',open],['rentgen.saveDraftEdit',save],['rentgen.editResult',inspect]])context.subscriptions.push(vscode.commands.registerCommand(name,async(...args)=>{
  try{return await fn(...args);}catch(error){void vscode.window.showErrorMessage('Рентген: '+error.message);throw error;}
 }));
 context.subscriptions.push(service);return Object.freeze({sessions:()=>service.list()});
}
module.exports={createEditUI};
