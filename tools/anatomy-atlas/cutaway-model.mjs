/** Source-backed containment. Names/roles/paths are evidence; grouping is editorial, never execution. */
export function cutawayModels(D){
 const file=n=>n.id.startsWith('file:');
 const labels={production_source:'Код продукта',test:'Тесты',documentation:'Документы',build_and_delivery:'Поставка',verification_harness:'Проверки',fixture:'Фикстуры',supporting_file:'Служебные файлы',license:'Лицензии'};
 const named={
 native:[['Проверки и preview',['edt_command.py','edt_fixture_executor.py','metadata_apply_gate.py','metadata_native_apply.py','metadata_preview.py','platform_check.py','test_execution.py','yaxunit_runner.py']],['Live writer / sealed recovery',['_live_recovery_stage.py','metadata_live_apply.py','proposal_live_apply.py']],['Workspace и runtime',['edt_runtime.py','metadata_workspace.py','native_platform.py','native_process.py','native_resources.py','native_scratch.py']],['Профили и evidence',['edt_execution.py','edt_profiles.py','metadata_apply.py','metadata_runs.py','platform_runs.py','test_profiles.py','yaxunit_report.py']]],
 snapshots:[['Захват и настройка источника',['capture.py','_windows_source_tree.py','source_catalog.py','source_configuration.py']],['Манифест и публикация',['manifests.py','publication.py']],['Снимки и чтение',['snapshots.py','snapshot_diff.py','sources.py']]],
 identity:[['Контекст и идентичность',['context.py','local_identity.py','resolver.py']],['Доступ и полномочия',['access.py','authorization.py','capabilities.py']],['Ошибки',['errors.py']]],
 state:[['Состояние и реестр',['state.py','registry.py','_sqlite.py']],['Схемы и миграции',['_schema_upgrade.py','_workflow_schema.py','access_migration.py','state_migration.py','workflow_migration.py']]],
 drafts:[['Предложение и история',['proposals.py','drafts.py']],['Редактирование и сравнение',['draft_editing.py','bsl_three_way.py']],['MCP-вход',['mcp_drafts.py']]],
 metadata:[['Чтение метаданных',['metadata.py','metadata_xml.py','edt_inventory.py']],['Планы',['metadata_plans.py']],['Трёхстороннее сравнение',['metadata_three_way.py','edt_attribute_three_way.py','edt_identity_three_way.py','three_way.py']]],
 observer:[['Git-захват и политика',['_git_capture.py','_git_policy.py','git_watcher.py','git_observer.py']],['Анализ и свидетельства',['_git_analysis_failure.py','git_snapshot_evidence.py']],['Службы наблюдения',['observer.py','observer_cli.py']]],
 evidence:[['Отчёты владельца',['owner_report.py','owner_report_store.py']],['Уведомления',['notification_delivery.py','notification_receiver.py','notification_receiver_asgi.py']],['Runtime-свидетельства',['runtime_metrics.py','runtime_producer.py','runtime_source.py']]]
 };
 const result={};
 for(const s of D.sections){
  const files=D.nodes.filter(n=>file(n)&&n.systemId===s.id),assigned=new Set();let groups=[];
  if(named[s.id])for(const [label,names]of named[s.id]){
   // Curated names are relative to this exact source directory, never basename matches.
   const paths=names.map(name=>'rentgen_core/'+name);
   const fs=paths.map(path=>{const matches=files.filter(n=>n.path===path);if(matches.length!==1)throw new Error('Curated source path must identify exactly one file: '+path);const n=matches[0];if(assigned.has(n.id))throw new Error('Duplicate curated source path: '+path);assigned.add(n.id);return n;});
   groups.push({label,basis:'editorial',files:fs});
  }
  const remaining=files.filter(n=>!assigned.has(n.id));
  if(groups.length){if(remaining.length)groups.push({label:'Другие файлы системы',basis:'source-membership',files:remaining});}
  else{
   const buckets=new Map();for(const n of files){const dir=n.path.includes('/')?n.path.slice(0,n.path.lastIndexOf('/')):'./',key=n.role==='production_source'?dir:(labels[n.role]||n.role);if(!buckets.has(key))buckets.set(key,[]);buckets.get(key).push(n);}
   const sorted=[...buckets].sort((a,b)=>b[1].length-a[1].length||a[0].localeCompare(b[0]));
   groups=sorted.slice(0,sorted.length>4?3:4).map(([label,fs])=>({label,basis:fs.every(n=>n.role==='production_source')?'directory':'role',files:fs}));
   if(sorted.length>4)groups.push({label:'Остальные каталоги и роли',basis:'source-membership',files:sorted.slice(3).flatMap(x=>x[1])});
  }
  result[s.id]={systemId:s.id,label:s.label,sourceCommit:D.meta.sourceCommit,fileCount:files.length,grouping:'Редакторская группировка по точным путям и ролям; не архитектура выполнения.',caveat:s.id==='drafts'?'Черновик предлагает изменения; создание черновика не применяет их.':s.id==='native'?'Проверки не дают разрешение на запись. Live writer ограничен проверенной операцией; recovery восстанавливает только sealed recovery files. Workspace — принадлежащая копия, не произвольная live infobase.':'Форма показывает принадлежность исходников, а не оборудование или поток выполнения.',compartments:groups.map((g,i)=>({id:s.id+':compartment:'+i,label:g.label,basis:g.basis,fileIds:g.files.map(n=>n.id),representativeIds:[...g.files].sort((a,b)=>(s.primaryNodeIds?.includes(a.id)?0:1)-(s.primaryNodeIds?.includes(b.id)?0:1)||a.path.localeCompare(b.path)).slice(0,2).map(n=>n.id),directories:[...new Set(g.files.map(n=>n.path.includes('/')?n.path.slice(0,n.path.lastIndexOf('/')):'./'))].sort(),roles:[...new Set(g.files.map(n=>n.role))],refs:g.files.slice(0,3).flatMap(n=>(n.refs||[]).slice(0,1))}))};
 }
 return result;
}
