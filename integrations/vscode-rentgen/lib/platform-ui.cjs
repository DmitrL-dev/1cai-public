'use strict';
const {isDeepStrictEqual} = require('node:util');
function createPlatformUI(vscode, service, views, context, enabled) {
  let busy = false;
  const subscribe = item => {context.subscriptions.push(item); return item;};
  const check = () => {
    if (!vscode.workspace.isTrusted) throw new Error('TRUST_REQUIRED');
    if (!enabled) throw new Error('PLATFORM_REQUIRES_DEV8');
  };
  async function show(result, current = () => true) {
    check(); if (!current()) return result;
    const analysis = result.report?.analysis;
    const message = result.status === 'completed' ?
      (analysis?.baseline?.status === 'passed' && analysis?.candidate?.status === 'passed'
        ? 'Компиляция исходника и черновика прошла. Функциональные тесты не запускались.'
        : 'Компиляция обнаружила замечания. Подробности — в отчёте; функциональные тесты не запускались.') :
      result.status === 'failed' ? 'Проверка завершилась технической ошибкой. Подробности — в отчёте.' :
      'Завершение проверки не подтверждено. Состояние процесса неизвестно; автоматического повторения нет.';
    const document = await vscode.workspace.openTextDocument({language:'json',content:JSON.stringify(result,null,2)});
    check(); if (!current()) return result;
    await vscode.window.showTextDocument(document,{preview:false});
    check(); if (!current()) return result;
    void vscode.window.showInformationMessage('Рентген: '+message);
    return result;
  }
  async function start(selection, suppliedPlatform) {
    check(); if (busy || service.running) throw new Error('PLATFORM_RUNNING');
    const token = typeof selection === 'string' ? selection : selection?.token;
    const receipt = views.selectedDraft(token);
    busy = true;
    // Refresh/new-save invalidation suppresses only automatic presentation;
    // the exact historical result remains available through explicit recovery.
    const current = () => {
      try { return isDeepStrictEqual(views.selectedDraft(token), receipt); }
      catch (error) { if (error?.message === 'UNKNOWN_VIEW_HANDLE') return false; throw error; }
    };
    try {
      let platform = suppliedPlatform;
      if (platform === undefined) {
        const files = await vscode.window.showOpenDialog({title:'Полный клиент 1С — 1cv8.exe',canSelectFiles:true,canSelectFolders:false,canSelectMany:false,filters:{'Платформа 1С':['exe']}});
        if (!files?.length) return null;
        platform = files[0].fsPath;
      }
      if (typeof platform !== 'string' || !platform) throw new Error('FULL_PLATFORM_REQUIRED');
      check(); await vscode.commands.executeCommand('setContext','rentgen.platformRunning',true);
      const result = await vscode.window.withProgress({location:vscode.ProgressLocation.Notification,title:`Рентген: проверка версии ${receipt.revision} в 1С`,cancellable:true},async(_,token)=>{
        if (token.isCancellationRequested) throw new Error('PLATFORM_CANCELLED');
        const subscription=token.onCancellationRequested(()=>service.cancel());
        try {return await service.start(receipt,platform);} finally {subscription.dispose();}
      });
      return await show(result, current);
    } finally {busy=false; await vscode.commands.executeCommand('setContext','rentgen.platformRunning',false);}
  }
  async function inspect(id) {
    check(); if (busy || service.running) throw new Error('PLATFORM_RUNNING');
    if (!id) {
      const rows = await service.list();
      const selected = await vscode.window.showQuickPick([
        {label:'Ввести номер запуска…',manual:true},
        ...rows.map(row=>({label:`v${row.receipt.revision} · ${row.receipt.source_ref.relative_path}`,description:row.created_at,detail:row.id,id:row.id})),
      ],{title:'Результат проверки 1С'});
      if (!selected) return null;
      id = selected.manual ? await vscode.window.showInputBox({title:'Номер запуска проверки 1С',prompt:'UUID из сообщения или сохранённого отчёта.'}) : selected.id;
      if (!id) return null;
    }
    check(); return show(await service.inspect(id));
  }
  for (const [name, fn] of [['rentgen.platformCheck',start],['rentgen.platformResult',inspect]]) {
    subscribe(vscode.commands.registerCommand(name,async(...args)=>{
      try {return await fn(...args);} catch(error) {void vscode.window.showErrorMessage('Рентген: '+error.message);throw error;}
    }));
  }
  subscribe(service);
  return Object.freeze({runs:()=>service.list()});
}
module.exports={createPlatformUI};
