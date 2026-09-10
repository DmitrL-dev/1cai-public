'use strict';
function createBslUI(vscode,service,views,context,enabled){
 let busy=false;
 const check=()=>{if(!vscode.workspace.isTrusted)throw new Error('TRUST_REQUIRED');if(!enabled)throw new Error('BSL_REQUIRES_DEV8');};
 async function show(result){
  check();const status=result.report?.diagnostic?.diagnostics_status;
  const message=result.status!=='completed'?'Результат не сохранён. Завершение проверки не подтверждено; автоматического повторения нет.':
   status==='clean'?'BSL: замечаний в выбранной версии не найдено.':
   status==='diagnostics_present'?'BSL: в выбранной версии есть замечания.':
   status==='unsupported'?'BSL: этот модуль не поддерживается профилем проверки.':'BSL: анализ завершился технической ошибкой.';
  const document=await vscode.workspace.openTextDocument({language:'json',content:JSON.stringify(result,null,2)});
  check();await vscode.window.showTextDocument(document,{preview:false});
  void vscode.window.showInformationMessage(`Рентген: ${message} Функциональные тесты не запускались.`);return result;
 }
 async function start(selection){
  check();if(busy||service.running)throw new Error('BSL_RUNNING');
  const receipt=views.selectedDraft(typeof selection==='string'?selection:selection?.token);busy=true;
  try{
   await vscode.commands.executeCommand('setContext','rentgen.bslRunning',true);
   const result=await vscode.window.withProgress({location:vscode.ProgressLocation.Notification,title:`Рентген: BSL-проверка версии ${receipt.revision}`,cancellable:true},async(_,token)=>{
    if(token.isCancellationRequested)throw new Error('BSL_CANCELLED');
    const subscription=token.onCancellationRequested(()=>service.cancel());
    try{return await service.start(receipt);}finally{subscription.dispose();}
   });return await show(result);
  }finally{busy=false;await vscode.commands.executeCommand('setContext','rentgen.bslRunning',false);}
 }
 async function inspect(id){
  check();if(busy||service.running)throw new Error('BSL_RUNNING');
  if(!id){
   const rows=await service.list();
   const selected=await vscode.window.showQuickPick(rows.map(row=>({label:`v${row.receipt.revision} · ${row.receipt.source_ref.relative_path}`,description:row.created_at,detail:row.id,id:row.id})),{title:'Сохранённые BSL-проверки'});
   if(!selected)return null;id=selected.id;
  }return show(await service.inspect(id));
 }
 for(const [name,fn]of [['rentgen.bslCheck',start],['rentgen.bslResult',inspect]])context.subscriptions.push(vscode.commands.registerCommand(name,async(...args)=>{
  try{return await fn(...args);}catch(error){void vscode.window.showErrorMessage('Рентген: '+error.message);throw error;}
 }));
 context.subscriptions.push(service);return Object.freeze({runs:()=>service.list()});
}
module.exports={createBslUI};
