import {mountOccurrences} from './occurrences.js';
import {fetchReport} from './report-download.js';
import {createComparison} from './comparison.js';
import {escapeHTML as esc, typeLabel, typeClass, displayName, filterRows, relatedModules, formatBytes,transientImportError,reconcileImport,boundedMetadataQuery,boundedSourceQuery,searchReplyMatches,attributeSearchCoverageText,childMatchesHTML} from './model.js';
const icons={boxes:'<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9M8 5.2l8 4.5"/>',code:'<path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16"/>',shield:'<path d="M12 3 4.5 6v6c0 4.2 3 7.2 7.5 9 4.5-1.8 7.5-4.8 7.5-9V6L12 3Z"/><path d="m8 12 2.5 2.5L16 9"/>',network:'<rect x="9" y="3" width="6" height="5" rx="1"/><rect x="3" y="16" width="6" height="5" rx="1"/><rect x="15" y="16" width="6" height="5" rx="1"/><path d="M12 8v4M6 16v-4h12v4"/>',pulse:'<path d="M3 12h4l3-7 4 14 3-7h4"/>',compare:'<path d="M8 3v15m0 0-4-4m4 4 4-4M16 21V6m0 0-4 4m4-4 4 4"/>',lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',folder:'<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>',plus:'<path d="M12 5v14M5 12h14"/>',upload:'<path d="M12 16V3m0 0L7 8m5-5 5 5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',fingerprint:'<path d="M7 7a7 7 0 0 1 12 5c0 3-1 6-2 8M4 10c0-5 3-8 8-8m0 6a4 4 0 0 1 4 4c0 3-.5 5-2 9M8 19c2-3 2-5 2-7a2 2 0 0 1 4 0m-8 4 1-4m-3 0c0 3-1 5-1 5"/>',info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.5"/>',check:'<path d="m5 12 4 4L19 6"/>',close:'<path d="m6 6 12 12M6 18 18 6"/>',file:'<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Zm0 0v6h6M8 13h8m-8 4h5"/>',database:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>'};
const svg=name=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]||icons.file}</svg>`;
function paintIcons(root=document){root.querySelectorAll('[data-icon]').forEach(node=>node.innerHTML=svg(node.dataset.icon));}
paintIcons();
const $=id=>document.getElementById(id), state={view:'objects',moduleSearchMode:'modules',result:null,selected:null,tab:'info',job:null,busy:false,connected:false,token:location.hash.slice(1),filename:'',sourceGeneration:0,importGeneration:0,uncertainImport:null,searchGeneration:0,metadataQuery:'',relatedObject:null,pageOffset:0,pageRequested:false,pageFocus:null,metadataSearchResult:null,searchBusy:false,searchError:'',searchQueue:Promise.resolve()};
if(state.token) history.replaceState(null,'',location.pathname);
const comparison=createComparison({api,errorText,fetchReport:(pair,format,signal)=>fetchReport(pair,format,{token:state.token,signal}),getBinding:()=>state.result&&!state.busy?{job:state.job,input_sha256:state.result.input.input_sha256,filename:state.filename}:null});
let occurrenceView=null,occurrenceBarrier=Promise.resolve();
function leaveOccurrences(){if(!occurrenceView)return;const previous=occurrenceView;occurrenceView=null;occurrenceBarrier=Promise.all([occurrenceBarrier,previous.leave()]).then(()=>{},()=>{});}
const errors={INVALID_OCCURRENCE_QUERY:'Нужен однострочный фрагмент до 256 байт UTF-8.',OCCURRENCE_SEARCH_BUDGET_EXCEEDED:'Поиск в модуле превысил ограничение времени. Полный результат не получен.',PROTOCOL_ERROR:'Ответ локального сервиса не прошёл проверку привязки к исходному файлу.',METADATA_SEARCH_BUDGET_EXCEEDED:'Поиск полей не завершён: достигнут предел времени. Полного результата нет; частичные совпадения не показаны.',METADATA_SEARCH_LIMIT_EXCEEDED:'Поиск полей не завершён: превышен предел числа полей и табличных частей или длины их свойств. Частичный результат не показан.',METADATA_SEARCH_UNSUPPORTED:'Поиск полей не завершён: структура поля, табличной части или синонима не поддерживается либо содержит неоднозначные блоки. Проверьте XML выгрузки; частичный результат не показан.',REPORT_TOO_LARGE:'Полный отчёт превышает ограничение размера. Частичный отчёт не создаётся.',SOURCE_SEARCH_BUDGET_EXCEEDED:'Поиск не завершён: достигнут предел времени или объёма. Полного результата нет. Уточните область поиска.',COMPARISON_NOT_AVAILABLE:'Пара сравнения или страница больше не актуальна. Проверьте результат сравнения.',IMPORT_INVALID_ARCHIVE:'Файл не является поддерживаемым ZIP. Проверьте архив и попробуйте ещё раз.',IMPORT_UNSUPPORTED_ARCHIVE:'Этот формат ZIP не поддерживается. Используйте обычный ZIP со сжатием Deflate или без сжатия, без пароля.',IMPORT_INVALID_PATH:'В архиве обнаружены небезопасные или конфликтующие пути. Выгрузите исходники заново.',IMPORT_LIMIT_EXCEEDED:'Архив превышает ограничения: 16 МиБ ZIP, 32 МиБ после распаковки, 4096 записей, 4 МиБ на файл.',IMPORTED_EXPORT_UNSUPPORTED:'Не найдены объекты Designer XML в корне архива. Уберите внешнюю папку-обёртку. EDT-выгрузка пока не поддерживается.',CANCELLED:'Анализ отменён.',BUSY:'Другой анализ ещё выполняется. Дождитесь завершения или отмените его.',UNAUTHORIZED:'Сеанс недоступен. Откройте адрес запуска, показанный Рентгеном в терминале.',FORBIDDEN:'Доступ к проекту больше не разрешён.',SOURCE_TOO_LARGE:'Этот файл слишком велик для просмотра. Лимит просмотра: 256 КиБ.',SOURCE_ENCODING_UNSUPPORTED:'Файл не является UTF-8. Просмотр в этой кодировке пока не поддерживается.',INVALID_QUERY_OPTIONS:'Запрос должен быть не длиннее 256 байт UTF-8.',SEARCH_TIMEOUT:'Истекло время поиска. Можно повторить запрос.',SOURCE_NOT_AVAILABLE:'Файл недоступен в текущем результате. Повторите импорт.',UPLOAD_TIMEOUT:'Передача не завершилась вовремя. Выберите архив ещё раз.',INVALID_UPLOAD:'Нужен ZIP-файл размером не более 16 МиБ.',INTERNAL_ERROR:'Не удалось завершить операцию. Повторите импорт; исходные файлы не изменены.'};
function errorText(error){return errors[error.code]||'Не удалось прочитать выгрузку. '+(error.code ? `Код: ${error.code}.`:'Проверьте, что локальный Рентген запущен.');}
async function api(path,options={}){let response;try{response=await fetch(path,{...options,cache:'no-store',credentials:'omit',headers:{'X-Rentgen-Session':state.token,...options.headers}});}catch{throw {code:'CONNECTION_LOST'};}let data;try{data=await response.json();}catch{throw {code:'PROTOCOL_ERROR'};}if(!response.ok)throw {code:data.error||'INTERNAL_ERROR'};return data;}
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,4500);}
function setConnection(connected){state.connected=connected;$('runtime-status').textContent=connected?'Локальный сервис подключён':'Нет соединения с ядром';$('import-button').disabled=!connected;$('empty-import').disabled=!connected;}
function openImport(){if(comparison.busy){toast('Дождитесь результата сравнения или отмените его.');return;}if(!state.connected||state.busy)return;$('upload-error').hidden=true;$('file-input').value='';$('import-dialog').showModal();}
document.querySelector('.brand').addEventListener('click',event=>{event.preventDefault();setView('objects');});
$('import-button').addEventListener('click',openImport);$('empty-import').addEventListener('click',openImport);
$('show-limits').addEventListener('click',()=>setView('provenance'));
$('primary-nav').addEventListener('click',event=>{const button=event.target.closest('[data-view]');if(button)setView(button.dataset.view);});
$('module-search-mode').addEventListener('change',()=>{state.moduleSearchMode=$('module-search-mode').value;queueMetadataSearch(state.relatedObject);});
$('search').addEventListener('input',()=>queueMetadataSearch(state.relatedObject));$('type-filter').addEventListener('change',renderInventory);
$('reset-search').addEventListener('click',()=>{$('search').value='';$('type-filter').value='';queueMetadataSearch();$('search').focus();});
document.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'&&state.result&&['objects','modules'].includes(state.view)&&!state.busy){event.preventDefault();$('search').focus();$('search').select();}});
function setView(view){if(!['objects','modules','provenance','comparison'].includes(view))return;comparison.leave();invalidateMetadataSearch();state.view=view;state.moduleSearchMode='modules';$('module-search-mode').value='modules';state.selected=null;state.tab='info';$('search').value='';$('type-filter').value='';render();}
function render(){const names={objects:['Объекты','Объекты конфигурации'],modules:['Модули','Модули конфигурации'],provenance:['Источник и границы','Источник и границы анализа'],comparison:['Сравнение ZIP','Сравнение двух выгрузок']};$('breadcrumb-current').textContent=names[state.view][0];$('page-title').textContent=names[state.view][1];$('primary-nav').querySelectorAll('[data-view]').forEach(button=>{const active=button.dataset.view===state.view;button.classList.toggle('active',active);if(active)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});$('empty-state').hidden=!!state.result;$('analysis-state').hidden=!state.result;if(!state.result)return;const r=state.result;$('runtime-status').textContent='Rust input core · локально';$('page-subtitle').textContent=`${state.filename} · ZIP-выгрузка Конфигуратора`;$('object-count').textContent=r.counts.metadata_objects;$('module-count').textContent=r.counts.modules;$('metric-objects').textContent=r.counts.metadata_objects;$('metric-modules').textContent=r.counts.modules;$('metric-types').textContent=Object.keys(r.by_type).length;$('metric-files').textContent=r.counts.files;$('analysis-time').textContent=new Date(state.completedAt).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'});$('inventory-view').hidden=!['objects','modules'].includes(state.view);$('comparison-view').hidden=state.view!=='comparison';$('provenance-view').hidden=state.view!=='provenance';if(state.view==='comparison')comparison.enter();else if(state.view==='provenance')renderProvenance();else renderInventory();}
function sourceMode(){return state.view==='modules'&&state.moduleSearchMode==='source';}
function rows(){const field=state.view==='modules'?'modules':'objects';return sourceMode()||state.metadataQuery||state.relatedObject||state.pageRequested?(state.metadataSearchResult?.[field]||[]):state.result[field];}
function key(row){return row.input_ref.relative_path;}
function renderInventory(){if(!state.result||!['objects','modules'].includes(state.view))return;const all=rows(), isModules=state.view==='modules';$('type-filter').parentElement.hidden=isModules;$('module-mode-control').hidden=!isModules;$('source-search-help').hidden=!sourceMode();$('attribute-search-help').hidden=isModules;$('list-title').textContent=isModules?'МОДУЛЬ':'ОБЪЕКТ';if(!isModules){const value=$('type-filter').value;$('type-filter').innerHTML='<option value="">Все типы</option>'+Object.keys(state.result.by_type).map(type=>`<option value="${esc(type)}">${esc(typeLabel(type))} (${state.result.by_type[type]})</option>`).join('');$('type-filter').value=value;}const shown=filterRows(all,'',$('type-filter').value,isModules);
const searchResult=state.metadataSearchResult||(!sourceMode()&&!state.metadataQuery&&!state.relatedObject&&!state.pageRequested?state.result:null);
const matching=isModules?(searchResult?.matching_modules??searchResult?.counts.modules??0):(searchResult?.matching_objects??0);
$('result-count').textContent=`Показано ${shown.length} из ${matching}`;
const truncated=isModules?!!searchResult?.modules_truncated:!!searchResult?.objects_truncated;
$('truncation-warning').hidden=!truncated;
$('truncation-warning').textContent=sourceMode()?`На странице ${all.length} из ${matching} файлов. Только первое совпадение в каждом файле; остальные вхождения не перечисляются.`:isModules?`На странице ${all.length} из ${matching} модулей. Поиск проверяет пути по всему ZIP, не содержимое кода.`:`На странице ${all.length} из ${matching} объектов-владельцев. Поиск проверяет корневые свойства и указанную область полей Designer XML по всему ZIP; фильтр типа применяется только к текущей странице.`;
renderPagination(searchResult,matching,all.length);renderSourceCoverage(searchResult);renderAttributeCoverage(searchResult);
$('search-status').hidden=!state.metadataQuery&&!state.relatedObject&&!state.pageRequested&&!state.searchError&&!state.searchBusy;
$('search-status-text').textContent=state.searchError||(state.searchBusy?'Ищем по всему ZIP…':`Найдено ${matching} ${sourceMode()?'файлов с фрагментом':isModules?'по всему ZIP':searchResult?.attribute_search?.complete===false?'в проверенных корнях (объекты-владельцы)':'по всему ZIP (объекты-владельцы)'} · показано ${shown.length}${state.relatedObject?' · папка '+state.relatedObject:''}${!isModules&&$('type-filter').value?' · тип отфильтрован в показанной части':''}`);
$('retry-search').hidden=!state.searchError;$('cancel-search').hidden=!state.searchBusy&&!state.relatedObject;
$('search').setAttribute('aria-label',sourceMode()?'Поиск точного фрагмента кода':isModules?'Поиск по имени или пути':'Поиск объектов и полей Designer XML');$('search').placeholder=sourceMode()?'Фрагмент кода: точно, с учётом регистра…':isModules?'Имя или путь модуля по всему ZIP…':'Объект или поле: имя, синоним, тип; путь XML…';if(!shown.some(row=>key(row)===state.selected)){state.selected=shown.length?key(shown[0]):null;state.tab='info';}const counts=shown.length;$('item-list').innerHTML=shown.map((row,index)=>`<button class="item-row ${key(row)===state.selected?'selected':''}" data-index="${index}" aria-pressed="${key(row)===state.selected}"><span class="object-icon ${typeClass(row.type,isModules)}">${svg(isModules?'code':row.type==='InformationRegister'?'database':row.type==='Document'?'file':'boxes')}</span><span class="item-main"><strong>${esc(displayName(row,isModules))}</strong><small>${esc(isModules?row.input_ref.relative_path:(row.synonym||row.type))}</small></span><span class="item-type">${esc(isModules?formatBytes(row.size_bytes):typeLabel(row.type))}</span></button>`).join('');$('item-list').querySelectorAll('button').forEach(button=>button.addEventListener('click',()=>{state.selected=key(shown[Number(button.dataset.index)]);state.tab='info';renderInventory();$('item-list').querySelector(`[data-index="${button.dataset.index}"]`)?.focus();}));$('no-results').hidden=counts>0||state.searchBusy||!!state.searchError||(sourceMode()&&!state.metadataQuery);$('no-results').querySelector('strong').textContent=sourceMode()?'Совпадений в проверенных файлах нет':searchResult?.attribute_search?.complete===false?'В проверенных корнях совпадений нет':'Ничего не найдено';renderDetails(all.find(row=>key(row)===state.selected));}
function renderAttributeCoverage(result){
  const text=state.view==='objects'&&state.metadataQuery?attributeSearchCoverageText(result?.attribute_search):'';
  $('attribute-coverage').hidden=!text;
  $('attribute-coverage').classList.toggle('caution',!!text&&result.attribute_search.complete===false);
  $('attribute-coverage').textContent=text;
}
function renderSourceCoverage(result){
  const c=result?.source_coverage;
  $('source-coverage').hidden=!sourceMode()||!c;
  if(!c)return;
  $('source-coverage').textContent=`${c.complete?'Полное покрытие выбранной области':'Частичное покрытие'}: проверено ${c.searched} из ${c.in_scope} модулей. Пропущено: больше 256 КиБ — ${c.skipped_oversized}, не UTF-8 — ${c.skipped_invalid_utf8}, управляющие символы — ${c.skipped_controls}. ${c.complete?'':'Отсутствие совпадений не исключает их в пропущенных файлах.'}`;
}
function renderPagination(result,total,count){
  const offset=state.pageOffset;
  const page=result?.page||{offset:0,limit:200,total,returned:count,has_previous:false,has_next:total>count};
  $('pagination').hidden=total<=200&&offset===0&&!state.pageRequested;
  $('page-range').textContent=state.searchBusy?'Загружаем страницу…':state.searchError?'Страница не загружена':`Строки ${count?offset+1:0}–${offset+count} из ${total}`;
  const blocked=state.searchBusy||!!state.searchError||!result;
  $('previous-page').disabled=blocked||!page.has_previous;
  $('next-page').disabled=blocked||!page.has_next;
}
function changePage(direction){
  const button=$(direction<0?'previous-page':'next-page');
  if(button.disabled||state.busy)return;
  queueMetadataSearch(state.relatedObject,state.pageOffset+direction*200,true,button.id);
}
function restorePageFocus(){
  if(!state.pageFocus)return;
  const requested=$(state.pageFocus);state.pageFocus=null;
  const fallback=$('previous-page').disabled?$('next-page'):$('previous-page');
  (requested.disabled?fallback:requested).focus();
}
$('previous-page').addEventListener('click',()=>changePage(-1));
$('next-page').addEventListener('click',()=>changePage(1));
function pair(label,value,cls=''){return `<dt>${esc(label)}</dt><dd class="${cls}">${esc(value??'Не указан')}</dd>`;}
function renderDetails(row){leaveOccurrences();state.sourceGeneration++;if(!row){$('detail-panel').innerHTML=`<div class="detail-empty">${svg('boxes')}<p>Выберите объект из списка</p></div>`;return;}const module=state.view==='modules',ref=row.input_ref;$('detail-panel').innerHTML=`<div class="detail-heading"><span class="object-icon ${typeClass(row.type,module)}">${svg(module?'code':row.type==='InformationRegister'?'database':row.type==='Document'?'file':'boxes')}</span><div><h2>${esc(displayName(row,module))}</h2><p>${esc(module?'BSL · модуль исходного кода':typeLabel(row.type))}</p></div></div><div class="detail-tabs" role="tablist" aria-label="Сведения"><button role="tab" data-tab="info" aria-selected="${state.tab==='info'}">Сведения</button><button role="tab" data-tab="source" aria-selected="${state.tab==='source'}">Исходный файл</button><button role="tab" data-tab="provenance" aria-selected="${state.tab==='provenance'}">Происхождение</button></div><div id="detail-content" role="tabpanel"></div>`;$('detail-panel').querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{state.tab=button.dataset.tab;renderDetails(row);$('detail-panel').querySelector(`[data-tab="${state.tab}"]`).focus();}));const tabs=[...$('detail-panel').querySelectorAll('[data-tab]')];tabs.forEach((button,index)=>{button.id='detail-tab-'+button.dataset.tab;button.tabIndex=button.getAttribute('aria-selected')==='true'?0:-1;button.setAttribute('aria-controls','detail-content');button.addEventListener('keydown',event=>{let next;if(event.key==='ArrowRight')next=(index+1)%tabs.length;if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;if(event.key==='Home')next=0;if(event.key==='End')next=tabs.length-1;if(next!==undefined){event.preventDefault();tabs[next].click();}});});$('detail-content').setAttribute('aria-labelledby','detail-tab-'+state.tab);if(state.tab==='source'){renderSource(row);return;}if(state.tab==='provenance'){$('detail-content').innerHTML=`<p class="section-label">ПРОВЕРЯЕМЫЕ БАЙТЫ</p><dl class="properties">${pair('Файл',ref.relative_path,'mono')}${pair('SHA-256 файла',ref.raw_sha256,'mono')}${pair('SHA-256 архива',ref.input_sha256,'mono')}${pair('Источник','Выбранный ZIP-архив')}${pair('Живая база','Связь не подтверждена')}</dl><div class="detail-section detail-footnote">${svg('shield')}<span>Хеш подтверждает совпадение байтов. Он не подтверждает автора, полноту выгрузки или актуальность относительно базы 1С.</span></div>`;return;}let content=`<p class="section-label">${module?'О МОДУЛЕ':'ОСНОВНЫЕ СВОЙСТВА'}</p><dl class="properties">${pair(module?'Имя файла':'Имя',module?ref.relative_path.split('/').at(-1):row.name)}${module?pair('Размер',formatBytes(row.size_bytes)):pair('Синоним',row.synonym)}${pair('Тип',module?'Исходный модуль':typeLabel(row.type))}${pair('Файл',ref.relative_path,'mono')}${!module?`<dt>UUID</dt><dd class="mono">${esc(row.observed_uuid||'Не указан')}<br><span class="tag warn">Идентичность не проверена</span></dd>`:`<dt>Анализ</dt><dd><span class="tag">Только инвентаризация</span></dd>`}</dl>`;if(!module){content+=childMatchesHTML(row);const related=relatedModules(row,state.result.modules);content+=`<div class="detail-section"><p class="section-label">МОДУЛИ В ПАПКЕ ОБЪЕКТА <span class="tag">${related.length}</span></p>${related.length?related.map((item,index)=>`<button class="module-link" data-module="${index}"><span>${svg('code')}</span><span><strong>${esc(item.input_ref.relative_path.split('/').at(-1))}</strong><small>${esc(formatBytes(item.size_bytes))} · найден по пути файла</small></span><span class="arrow">↗</span></button>`).join(''):'<p class="source-meta">Модулей в первоначальной части инвентаря не найдено.</p>'}<button id="discover-related-modules" class="button subtle">Найти модули в папке по всему ZIP</button><p class="source-meta">Связь определяется только точным путём папки, не семантикой кода.</p></div>`;}
content+=`<div class="detail-section detail-footnote">${svg('info')}<span>${module?'Код доступен для чтения. Диагностика, поиск вызовов и выполнение 1С не запускались.':state.metadataSearchResult?.attribute_search?'Показаны корневые свойства и совпадения только в прямых реквизитах, измерениях, ресурсах и реквизитах табличных частей Designer XML. Полный состав метаданных, семантика и связи объекта не проверены.':'Показаны корневые свойства XML. Состав реквизитов, полнота и связи объекта пока не анализируются.'}</span></div>`;$('detail-content').innerHTML=content;if(!module){$('discover-related-modules').addEventListener('click',()=>{const path=row.input_ref.relative_path;setView('modules');queueMetadataSearch(path);});const related=relatedModules(row,state.result.modules);$('detail-content').querySelectorAll('[data-module]').forEach(button=>button.addEventListener('click',()=>{invalidateMetadataSearch();state.view='modules';state.moduleSearchMode='modules';$('module-search-mode').value='modules';state.selected=key(related[Number(button.dataset.module)]);state.tab='source';$('search').value='';$('type-filter').value='';render();}));}}
async function renderSource(row){
  const generation=state.sourceGeneration,job=state.job,ref=row.input_ref;
  $('detail-content').innerHTML='<p class="source-meta" role="status">Читаем проверенные байты из архива…</p>';
  try{
    await occurrenceBarrier;
    if(generation!==state.sourceGeneration)return;
    const data=await api(`/api/source?job=${encodeURIComponent(job)}&path=${encodeURIComponent(ref.relative_path)}`);
    if(generation!==state.sourceGeneration)return;
    if(data.input_ref?.relative_path!==ref.relative_path||data.input_ref?.raw_sha256!==ref.raw_sha256||data.input_ref?.input_sha256!==ref.input_sha256||data.encoding!=='UTF-8'||typeof data.text!=='string'||!Number.isInteger(data.size_bytes)||data.size_bytes<0||data.size_bytes>262144||(state.view==='modules'&&data.size_bytes!==row.size_bytes))throw {code:'PROTOCOL_ERROR'};
    $('detail-content').innerHTML=`<p class="source-meta">${esc(data.encoding)} · ${esc(formatBytes(data.size_bytes))} · только чтение</p><pre class="source-code" tabindex="0" aria-label="Исходный код"></pre><div class="detail-footnote">${svg('shield')}<span>Байты сверены с SHA-256 файла из результата анализа.</span></div>`;
    const source=$('detail-content').querySelector('pre');source.textContent=data.text;
    if(row.first_match){
      const hit=document.createElement('div');hit.className='source-hit';const label=document.createElement('p');
      label.textContent=`Первое совпадение в файле: строка ${row.first_match.line}. В списке файлов показано первое совпадение; все вхождения можно найти ниже.`;
      const excerpt=document.createElement('pre');excerpt.className='source-code';excerpt.setAttribute('aria-label','Первое совпадение');
      excerpt.textContent=(row.first_match.truncated_before?'…':'')+row.first_match.excerpt+(row.first_match.truncated_after?'…':'');hit.append(label,excerpt);$('detail-content').prepend(hit);
    }
    if(state.view==='modules')occurrenceView=mountOccurrences({container:$('detail-content'),source,api,errorText,text:data.text,initialQuery:sourceMode()?state.metadataQuery:'',binding:{job,input_sha256:ref.input_sha256,path:ref.relative_path,raw_sha256:ref.raw_sha256,size_bytes:data.size_bytes},isCurrent:()=>generation===state.sourceGeneration&&state.view==='modules'&&state.tab==='source'&&!state.busy&&state.job===job&&state.result?.input.input_sha256===ref.input_sha256});
  }catch(error){if(generation!==state.sourceGeneration)return;$('detail-content').innerHTML=`<div class="notice danger" role="alert">${esc(errorText(error))}</div>`;}
}
function renderProvenance(){const r=state.result;$('provenance-view').innerHTML=`<div class="provenance-card"><h2>Откуда получены данные</h2><dl class="properties">${pair('Архив',state.filename)}${pair('SHA-256 архива',r.input.input_sha256,'mono')}${pair('Принятые файлы',`${r.input.files_count} · ${formatBytes(r.input.total_bytes)} после распаковки`)}${pair('Парсер','Designer XML · корневые свойства')}${pair('Распознавание',r.format_status==='partial'?'Частичное. Некоторые корни не поддерживаются.':'Обнаружены поддерживаемые корни Designer XML')}${pair('Неизвестные корни',r.counts.unsupported_metadata_roots)}${pair('Публикация снимка','Не выполнялась')}</dl></div><div class="provenance-card"><h2>Границы этого результата</h2><div class="scope-grid"><div><h3>Доступно сейчас</h3><ul><li>Проверка ZIP и SHA-256</li><li>Имена и типы объектов из XML</li><li>Инвентарь модулей и просмотр UTF-8</li><li>Поиск корневых свойств объектов, прямых реквизитов, измерений, ресурсов и реквизитов табличных частей Designer XML; одна строка на объект-владелец</li><li>Поиск путей модулей; точный фрагмент кода в UTF-8 файлах до 256 КиБ с явным покрытием</li></ul></div><div class="unavailable"><h3>Пока не проверяется</h3><ul><li>Актуальность и полнота относительно базы 1С</li><li>Диагностика и качество кода</li><li>Полный состав метаданных, семантический индекс, граф вызовов и зависимости</li><li>Выполнение, изменение базы и командная работа</li></ul></div></div></div><div class="provenance-card"><h2>Локальная обработка</h2><p>Архив обрабатывается на этом компьютере. Нет отправки кода в облако, телеметрии или обращения к LLM. Временная копия нужна только до следующего импорта или завершения приложения. Исходный ZIP и файлы базы 1С не изменяются.</p><p>Ограничения: ZIP до 16 МиБ, 4096 записей, 32 МиБ после распаковки, 4 МиБ на файл. Каждая страница инвентаря показывает до 200 объектов или модулей. Просмотр текста: до 256 КиБ, UTF-8.</p><p>Этот backend пока экспериментальный, для GNU/Linux x86_64. Приёмка Windows и macOS для этого GUI ещё не выполнена.</p></div>`;}
$('file-input').addEventListener('change',()=>{if($('file-input').files[0])startImport($('file-input').files[0]);});
let dragDepth=0;document.addEventListener('dragenter',event=>{if([...event.dataTransfer.types].includes('Files')){event.preventDefault();dragDepth++;if(!state.busy&&!comparison.busy&&state.connected)$('drag-overlay').hidden=false;}});document.addEventListener('dragover',event=>{if([...event.dataTransfer.types].includes('Files'))event.preventDefault();});document.addEventListener('dragleave',()=>{if(--dragDepth<=0){dragDepth=0;$('drag-overlay').hidden=true;}});document.addEventListener('drop',event=>{event.preventDefault();dragDepth=0;$('drag-overlay').hidden=true;if(!state.busy&&!comparison.busy&&state.connected&&event.dataTransfer.files.length){if(event.dataTransfer.files.length!==1){toast('Выберите один ZIP-архив.');return;}startImport(event.dataTransfer.files[0]);}});
function invalidateMetadataSearch(){
  leaveOccurrences();
  clearTimeout(state.searchTimer);state.searchGeneration++;state.sourceGeneration++;state.metadataQuery='';state.relatedObject=null;state.pageOffset=0;state.pageRequested=false;state.pageFocus=null;state.metadataSearchResult=null;state.searchBusy=false;state.searchError='';
}
function searchOwns(generation,binding){return state.searchGeneration===generation&&state.view===(binding.kind==='metadata'?'objects':'modules')&&(binding.kind==='metadata'||state.moduleSearchMode===binding.kind)&&!state.busy&&state.job===binding.job&&state.result?.input.input_sha256===binding.input_sha256;}
function searchURL(binding,id){return '/api/search?'+new URLSearchParams({job:binding.job,input_sha256:binding.input_sha256,search:id});}
async function cancelMetadataSearch(binding,id){
  try{
    const reply=await api('/api/search-cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job:binding.job,input_sha256:binding.input_sha256,search:id}),signal:AbortSignal.timeout(3000)});
    // Serialize the next start behind bounded cancellation/reap observation.
    if(id&&reply.status==='searching'){
      const deadline=Date.now()+12000;
      while(Date.now()<deadline){
        await new Promise(resolve=>setTimeout(resolve,500));
        const status=await api(searchURL(binding,id),{signal:AbortSignal.timeout(3000)});
        if(status.status!=='searching')break;
      }
    }
  }catch{/* The backend independently bounds/reaps owned work; next start fails BUSY until then. */}
}
function queueMetadataSearch(objectPath=null,offset=0,forcePage=false,focus=null){
  if(!state.result||!['objects','modules'].includes(state.view))return;
  const literal=sourceMode(),{query,valid}=literal?boundedSourceQuery($('search').value):boundedMetadataQuery($('search').value);
  invalidateMetadataSearch();state.metadataQuery=query;state.relatedObject=objectPath;state.pageOffset=offset;state.pageRequested=forcePage;state.pageFocus=focus;state.selected=null;state.tab='info';
  if(literal&&!query){renderInventory();return;}
  if(!valid){state.searchError=literal?'Нужен однострочный фрагмент до 256 байт UTF-8, без управляющих символов.':'Запрос превышает 256 байт UTF-8. Сократите его.';renderInventory();return;}
  if(!query&&!objectPath&&!forcePage){renderInventory();return;}
  const generation=state.searchGeneration,binding={job:state.job,input_sha256:state.result.input.input_sha256,kind:state.view==='modules'?state.moduleSearchMode:'metadata',object_path:objectPath,offset};
  state.searchBusy=true;renderInventory();
  state.searchTimer=setTimeout(()=>{
    state.searchQueue=state.searchQueue.catch(()=>{}).then(()=>runMetadataSearch(query,binding,generation));
  },350);
}
async function runMetadataSearch(query,binding,generation){
  if(!searchOwns(generation,binding))return;
  let id=null,terminal=false;
  try{
    const started=await api('/api/search-start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...binding,query}),signal:AbortSignal.timeout(5000)});
    id=started.search;
    if(started.query!==query||started.job!==binding.job||started.input_sha256!==binding.input_sha256||started.offset!==binding.offset||started.kind!==binding.kind||started.object_path!==binding.object_path||started.prefix!==(binding.object_path?binding.object_path.slice(0,-4)+'/':null))throw {code:'SOURCE_NOT_AVAILABLE'};
    const deadline=Date.now()+65000;
    while(searchOwns(generation,binding)&&Date.now()<deadline){
      const reply=await api(searchURL(binding,id),{signal:AbortSignal.timeout(5000)});
      if(!searchOwns(generation,binding))return;
      if(!searchReplyMatches(binding,id,query,reply))throw {code:'SOURCE_NOT_AVAILABLE'};
      if(reply.status==='ready'){
        terminal=true;state.metadataSearchResult=reply.result;state.searchBusy=false;state.searchError='';renderInventory();restorePageFocus();return;
      }
      if(reply.status==='error'||reply.status==='cancelled'){terminal=true;throw {code:reply.error||'CANCELLED'};}
      await new Promise(resolve=>setTimeout(resolve,350));
    }
    if(searchOwns(generation,binding))throw {code:'SEARCH_TIMEOUT'};
  }catch(error){
    if(searchOwns(generation,binding)){state.searchBusy=false;state.searchError='Поиск не завершён. '+errorText(error);renderInventory();}
  }finally{
    if(!terminal||!searchOwns(generation,binding))await cancelMetadataSearch(binding,id);
  }
}
$('retry-search').addEventListener('click',()=>queueMetadataSearch(state.relatedObject,state.pageOffset,state.pageRequested));
$('cancel-search').addEventListener('click',()=>{$('search').value='';queueMetadataSearch();});
function ownsImport(generation,job){return state.busy&&state.importGeneration===generation&&(job===undefined||state.pendingJob===job);}
function clearUncertainImport(){state.uncertainImport=null;$('import-uncertain').hidden=true;}
function showImportError(error){
  $('file-input').value='';$('upload-error').textContent=errorText(error);$('upload-error').hidden=false;
  $('progress-dialog').close();if(!$('import-dialog').open)$('import-dialog').showModal();
}
function showUncertainImport(job,filename){
  invalidateMetadataSearch();
  state.uncertainImport={job,filename};state.result=null;state.job=null;state.selected=null;state.filename='';state.sourceGeneration++;
  $('detail-panel').replaceChildren();$('item-list').replaceChildren();$('provenance-view').replaceChildren();
  $('object-count').textContent='0';$('module-count').textContent='0';render();
  $('page-subtitle').textContent=`${filename} · результат импорта пока неизвестен`;
  $('runtime-status').textContent='Результат импорта не подтверждён';
  $('import-uncertain').hidden=false;$('import-dialog').close();
}
function presentImportOutcome(status,job,generation){
  if(!ownsImport(generation,job))return;
  if(status.status==='ready'){
    clearUncertainImport();invalidateMetadataSearch();
    state.result=status.result;state.job=job;state.filename=status.filename;state.completedAt=status.completed_at;
    state.selected=null;state.tab='info';state.view='objects';state.sourceGeneration++;
    $('step-analyze').className='complete';$('step-ready').className='complete';
    $('search').value='';$('type-filter').value='';render();toast('Выгрузка прочитана. Исходные файлы не изменены.');
  }else{
    // A rejected replacement does not discard an older job still awaiting read-back.
    if(state.uncertainImport?.job===job)clearUncertainImport();
    if(!state.result&&!state.uncertainImport){$('page-subtitle').textContent='Начните с ZIP-выгрузки из Конфигуратора 1С';$('runtime-status').textContent='Локальный сервис подключён';}
    if(status.status==='cancelled')toast('Анализ отменён.');
    else showImportError({code:status.error||'INTERNAL_ERROR'});
  }
}
async function reconcileKnownImport(job,filename,generation){
  $('progress-title').textContent='Проверяем результат импорта';
  let status;
  try{
    status=await reconcileImport(
      ()=>api(`/api/job?job=${encodeURIComponent(job)}`,{signal:AbortSignal.timeout(3000)}),
      ()=>ownsImport(generation,job));
  }catch{
    if(ownsImport(generation,job))showUncertainImport(job,filename);
    return;
  }
  presentImportOutcome(status,job,generation);
}
async function startImport(file){
  if(state.busy||comparison.busy)return;
  if(!/\.zip$/i.test(file.name)||file.size===0||file.size>16*1024*1024){$('upload-error').textContent=errors.INVALID_UPLOAD;$('upload-error').hidden=false;if(!$('import-dialog').open)$('import-dialog').showModal();return;}
  invalidateMetadataSearch();state.moduleSearchMode='modules';$('module-search-mode').value='modules';$('search').value='';state.selected=null;state.tab='info';if(state.result)render();
  comparison.leave();state.busy=true;const generation=++state.importGeneration;state.pendingJob=null;
  $('import-dialog').close();$('progress-file').textContent=file.name;$('progress-title').textContent='Читаем выгрузку';
  $('step-upload').className='current';$('step-analyze').className='';$('step-ready').className='';
  $('cancel-analysis').disabled=false;$('cancel-analysis').textContent='Отменить';$('progress-dialog').showModal();
  state.uploadController=new AbortController();state.cancelRequested=false;let job;
  try{
    const prepared=await api('/api/import-start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:file.name.slice(0,240)})});
    if(!ownsImport(generation))return;
    job=prepared.job;state.pendingJob=job;
    if(state.cancelRequested)await api('/api/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job})});
    else await api(`/api/import?job=${encodeURIComponent(job)}`,{method:'PUT',headers:{'Content-Type':'application/zip'},body:file,signal:state.uploadController.signal});
    if(!ownsImport(generation,job))return;
    $('step-upload').className='complete';$('step-analyze').className='current';
    while(ownsImport(generation,job)){
      const status=await api(`/api/job?job=${encodeURIComponent(job)}`);
      if(['ready','error','cancelled'].includes(status.status)){presentImportOutcome(status,job,generation);break;}
      await new Promise(resolve=>setTimeout(resolve,250));
    }
  }catch(error){
    if(!ownsImport(generation))return;
    if(job&&transientImportError(error))await reconcileKnownImport(job,file.name,generation);
    else showImportError(error);
  }finally{
    if(state.importGeneration===generation){state.busy=false;state.pendingJob=null;state.uploadController=null;$('progress-dialog').close();if(state.view==='comparison')comparison.enter();}
  }
}
async function checkUncertainImport(){
  if(state.busy||!state.uncertainImport)return;
  const {job,filename}=state.uncertainImport,generation=++state.importGeneration;
  state.busy=true;state.pendingJob=job;state.cancelRequested=false;state.uploadController=null;
  $('check-import-result').disabled=true;$('check-import-result').textContent='Проверяем…';
  try{await reconcileKnownImport(job,filename,generation);}
  finally{if(state.importGeneration===generation){state.busy=false;state.pendingJob=null;$('check-import-result').disabled=false;$('check-import-result').textContent='Проверить результат';if(state.view==='comparison')comparison.enter();}}
}
async function cancel(){
  if(!state.busy||state.cancelRequested)return;
  state.cancelRequested=true;const job=state.pendingJob,controller=state.uploadController,generation=state.importGeneration;
  $('cancel-analysis').disabled=true;$('cancel-analysis').textContent='Отменяем…';$('progress-title').textContent='Отменяем анализ';
  if(job){try{
    const reply=await api('/api/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job})});
    if(!ownsImport(generation,job))return;
    if(reply.cancel_requested&&controller)controller.abort();
    else if(reply.status==='ready'){state.cancelRequested=false;$('progress-title').textContent='Выгрузка уже прочитана';}
  }catch(error){if(ownsImport(generation,job)){state.cancelRequested=false;$('cancel-analysis').disabled=false;toast(errorText(error));}}}
}
$('check-import-result').addEventListener('click',checkUncertainImport);
$('cancel-analysis').addEventListener('click',cancel);$('progress-dialog').addEventListener('cancel',event=>{event.preventDefault();cancel();});
try{const session=await api('/api/session');$('project-label').textContent=session.project_name;setConnection(true);}catch(error){setConnection(false);$('connection-warning').textContent=errorText(error);$('connection-warning').hidden=false;}
