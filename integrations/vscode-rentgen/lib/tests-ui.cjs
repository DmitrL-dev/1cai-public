'use strict';
function createTestsUI(vscode,service,views,context,enabled){
 let busy=false;
 const check=()=>{if(!vscode.workspace.isTrusted)throw new Error('TRUST_REQUIRED');if(!enabled)throw new Error('TEST_REQUIRES_DEV8');};
 const status={passed:'пройдены',failed:'есть ошибки',incomplete:'выполнены не все',not_run:'не запущены из-за ошибок компиляции'};
 async function show(result){
  check();let message;
  if(result.status==='completed')message=`Тесты исходного кода: ${status[result.report.tests.baseline.status]}. Тесты предложенной версии: ${status[result.report.tests.candidate.status]}.`;
  else if(result.status==='failed')message=`Технический сбой проверки: ${result.failure.code}.`;
  else message='Завершённый результат пока не сохранён. Повторного запуска не было.';
  const document=await vscode.workspace.openTextDocument({language:'json',content:JSON.stringify(result,null,2)});check();await vscode.window.showTextDocument(document,{preview:false});
  void vscode.window.showInformationMessage('Рентген: '+message);return result;
 }
 async function start(selection,profileId){
  check();if(busy||service.running)throw new Error('TEST_RUNNING');const receipt=views.selectedDraft(typeof selection==='string'?selection:selection?.token);busy=true;
  try{
   const profiles=await service.profiles();check();
   if(!profiles.length){void vscode.window.showInformationMessage('Рентген: нет включённых тестовых профилей. Администратор проекта может зарегистрировать профиль командой test-profile-register.');return null;}
   const choices=profiles.map(p=>({label:p.name,description:`${p.modules.reduce((n,m)=>n+m.tests.length,0)} тестов`,detail:p.profile_id,profile_id:p.profile_id}));
   const selected=profileId?choices.find(p=>p.profile_id===profileId):await vscode.window.showQuickPick(choices,{title:`Тесты версии ${receipt.revision}: выберите профиль`});
   if(profileId&&!selected)throw new Error('TEST_PROFILE_UNAVAILABLE');if(!selected)return null;
   check();await vscode.commands.executeCommand('setContext','rentgen.testsRunning',true);
   const result=await vscode.window.withProgress({location:vscode.ProgressLocation.Notification,title:`Рентген: тесты версии ${receipt.revision}`,cancellable:true},async(_,token)=>{
    if(token.isCancellationRequested)throw new Error('TEST_CANCELLED');const subscription=token.onCancellationRequested(()=>service.cancel());
    try{return await service.start(receipt,selected.profile_id);}finally{subscription.dispose();}
   });return await show(result);
  }finally{busy=false;await vscode.commands.executeCommand('setContext','rentgen.testsRunning',false);}
 }
 async function inspect(id){
  check();if(busy||service.running)throw new Error('TEST_RUNNING');
  if(!id){const rows=await service.list();const selected=await vscode.window.showQuickPick(rows.map(r=>({label:`v${r.receipt.revision} · ${r.receipt.source_ref.relative_path}`,description:r.profile.name,detail:r.id,id:r.id})),{title:'Сохранённые запуски тестов'});if(!selected)return null;id=selected.id;}
  return show(await service.inspect(id));
 }
 for(const [name,fn]of [['rentgen.testDraft',start],['rentgen.testResult',inspect]])context.subscriptions.push(vscode.commands.registerCommand(name,async(...args)=>{
  try{return await fn(...args);}catch(error){void vscode.window.showErrorMessage('Рентген: '+error.message);throw error;}
 }));context.subscriptions.push(service);return Object.freeze({runs:()=>service.list()});
}
module.exports={createTestsUI};
