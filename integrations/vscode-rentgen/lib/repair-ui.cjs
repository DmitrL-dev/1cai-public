'use strict';
function createRepairUI(vscode, service, views, context, enabled) {
  let busy = false;
  const subscribe = item => {context.subscriptions.push(item);return item;};
  const check = () => {if (!vscode.workspace.isTrusted) throw new Error('TRUST_REQUIRED'); if (!enabled) throw new Error('REPAIR_REQUIRES_DEV7_OR_DEV8');};
  async function show(result) {
    views.refreshDrafts();
    if (result.receipt) await views.openDraft(result.receipt);
    const message = result.status === 'analysis_clean' ? 'Черновик сохранён. Диагностика BSL чиста; проверьте смысл изменения. Тесты 1С не запускались, исходник не изменён.' :
      result.status === 'diagnostics_present' ? 'Черновик сохранён, диагностика BSL обнаружила замечания. Тесты 1С не запускались, исходник не изменён.' :
      result.status === 'saved_unverified' ? 'Найдена сохранённая ревизия. Завершённая проверка BSL не подтверждена; исходник не изменён.' :
      'Результат последней операции не установлен. Автоматического повторения нет. Проверьте результат позднее.';
    void vscode.window.showInformationMessage('Рентген: ' + message);
    return result;
  }
  async function start(selection, supplied) {
    check(); if (busy || service.running) throw new Error('REPAIR_RUNNING');
    const token = typeof selection === 'string' ? selection : selection?.token;
    const ref = views.selectedSource(token); busy = true;
    try {
      let options = supplied;
      if (!options) {
        const model = await vscode.window.showInputBox({title:'Локальная модель Ollama',value:'qwen3.5:9b',prompt:'Модель должна быть установлена. Один запрос, без автоматических повторов.',
          validateInput:v=>/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$/.test(v)?undefined:'Укажите имя установленной модели'});
        if (model === undefined) return null;
        const instruction = await vscode.window.showInputBox({title:'Задача для ' + ref.relative_path,prompt:'Будет создан новый черновик. Исходная конфигурация не изменяется.',
          validateInput:v=>v.trim() && Buffer.byteLength(v,'utf8')<=4096?undefined:'Введите задачу длиной до 4 КиБ'});
        if (instruction === undefined) return null;
        options = {model,instruction};
      }
      check(); await vscode.commands.executeCommand('setContext','rentgen.repairRunning',true);
      const result = await vscode.window.withProgress({location:vscode.ProgressLocation.Notification,title:'Рентген: подготовка и проверка правки',cancellable:true}, async (_, cancellation) => {
        if (cancellation.isCancellationRequested) throw new Error('REPAIR_CANCELLED');
        const subscription = cancellation.onCancellationRequested(()=>service.cancel());
        try { return await service.start(ref, options); } finally {subscription.dispose();}
      });
      check(); return await show(result);
    } finally {busy=false;await vscode.commands.executeCommand('setContext','rentgen.repairRunning',false);}
  }
  async function inspect(id) {
    check(); if (busy || service.running) throw new Error('REPAIR_RUNNING');
    if (!id) {
      const rows = await service.list();
      const selected = await vscode.window.showQuickPick(rows.map(row=>({label:row.source_ref.relative_path,description:row.created_at,detail:row.model,id:row.id})),{title:'Проверить результат правки'});
      if (!selected) return null; id=selected.id;
    }
    return show(await service.reconcile(id));
  }
  function register(name, fn) {
    subscribe(vscode.commands.registerCommand(name,async (...args)=>{try{return await fn(...args);}catch(error){void vscode.window.showErrorMessage('Рентген: '+error.message);throw error;}}));
  }
  register('rentgen.repairSource',start);
  register('rentgen.repairResult',inspect);
  register('rentgen.cancelRepair',()=>service.cancel());
  subscribe(service);
  return Object.freeze({runs:()=>service.list()});
}
module.exports={createRepairUI};
