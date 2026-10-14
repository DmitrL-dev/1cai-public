export function escapeHTML(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
const labels={Catalog:'Справочник',Document:'Документ',CommonModule:'Общий модуль',InformationRegister:'Регистр сведений',AccumulationRegister:'Регистр накопления',Report:'Отчёт',DataProcessor:'Обработка',Enum:'Перечисление',Constant:'Константа',Subsystem:'Подсистема',Attribute:'Реквизит',Dimension:'Измерение',Resource:'Ресурс',TabularSection:'Табличная часть'};
export function typeLabel(type){return labels[type]||type||'Модуль';}
export function typeClass(type,module=false){return module||type==='CommonModule'?'module':type==='Catalog'?'catalog':type==='Document'?'document':'register';}
export function displayName(row,module=false){if(!module)return row.name||row.input_ref.relative_path;const parts=row.input_ref.relative_path.split('/');const ext=parts.indexOf('Ext');return ext>0?parts[ext-1]:parts.at(-1);}
export function filterRows(rows,query,type,module=false){const term=query.trim().toLocaleLowerCase('ru');return rows.filter(row=>(module||!type||row.type===type)&&(!term||[row.name,row.synonym,row.type,typeLabel(row.type),row.input_ref.relative_path].some(value=>String(value||'').toLocaleLowerCase('ru').includes(term))));}
export function relatedModules(row,modules){const path=row.input_ref.relative_path;if(!path.toLowerCase().endsWith('.xml'))return [];const prefix=path.slice(0,-4)+'/';return modules.filter(item=>item.input_ref.relative_path.startsWith(prefix));}
export function formatBytes(bytes){if(bytes<1024)return `${bytes} Б`;if(bytes<1048576)return `${(bytes/1024).toLocaleString('ru-RU',{maximumFractionDigits:1})} КиБ`;return `${(bytes/1048576).toLocaleString('ru-RU',{maximumFractionDigits:1})} МиБ`;}
export function transientImportError(error){return ['CONNECTION_LOST','PROTOCOL_ERROR'].includes(error?.code);}
// Three read-only attempts per reconciliation, never an upload/analysis replay.
export function reconcileImport(read,isCurrent,pause=()=>new Promise(resolve=>setTimeout(resolve,250))){
  return (async()=>{
    for(let attempt=0;attempt<3;attempt++){
      if(!isCurrent())throw {code:'STALE_IMPORT'};
      try{
        const status=await read();
        if(!isCurrent())throw {code:'STALE_IMPORT'};
        if(['ready','error','cancelled'].includes(status.status))return status;
      }catch(error){
        if(!isCurrent())throw {code:'STALE_IMPORT'};
        if(!transientImportError(error))throw error;
      }
      if(attempt<2)await pause();
    }
    throw {code:'IMPORT_OUTCOME_UNCERTAIN'};
  })();
}
export function boundedMetadataQuery(value){const query=value.trim();return {query,valid:new TextEncoder().encode(query).length<=256};}
export function boundedSourceQuery(query){
  try{encodeURIComponent(query);}catch{return {query,valid:false};}
  return {query,valid:query.length>0&&new TextEncoder().encode(query).length<=256&&!/[\x00-\x08\x0a-\x1f]/.test(query)};
}
function sourceResultMatches(result,rows,query){
  const c=result.source_coverage;
  if(!c||!['in_scope','searched','skipped_oversized','skipped_invalid_utf8','skipped_controls'].every(k=>Number.isInteger(c[k])&&c[k]>=0&&c[k]<=4096))return false;
  if(c.in_scope!==c.searched+c.skipped_oversized+c.skipped_invalid_utf8+c.skipped_controls||c.complete!==(c.searched===c.in_scope)||result.matching_modules>c.searched)return false;
  return rows.every(row=>row.analysis==='literal_first_match'&&Number.isInteger(row.first_match?.line)&&row.first_match.line>=1&&row.first_match.line<=262145&&typeof row.first_match.excerpt==='string'&&[...row.first_match.excerpt].length<=512&&row.first_match.excerpt.includes(query)&&typeof row.first_match.truncated_before==='boolean'&&typeof row.first_match.truncated_after==='boolean');
}
const attributeScope='designer_direct_fields_and_tabular_attributes';
const fieldText=value=>value===null||(typeof value==='string'&&new TextEncoder().encode(value).length<=512);
const positiveIndex=value=>Number.isSafeInteger(value)&&value>0;
function validAttributeCoverage(coverage){
  return !!coverage&&coverage.scope===attributeScope&&Number.isInteger(coverage.unsupported_metadata_roots)&&coverage.unsupported_metadata_roots>=0&&coverage.unsupported_metadata_roots<=4096&&coverage.complete===(coverage.unsupported_metadata_roots===0)&&['fields_scanned','tabular_sections_scanned'].every(key=>Number.isInteger(coverage[key])&&coverage[key]>=0)&&coverage.fields_scanned+coverage.tabular_sections_scanned<=20000;
}
function attributeResultMatches(result,rows,query,inputHash){
  const childKeys=['child_matches','child_matching_total','child_matches_truncated'];
  const hasChildren=row=>childKeys.some(key=>Object.hasOwn(row,key));
  const coverage=result.attribute_search;
  // Old root-only inventories keep their contract; child hits require coverage.
  if(!Object.hasOwn(result,'attribute_search'))return rows.every(row=>row&&typeof row==='object'&&!hasChildren(row));
  if(!query||!validAttributeCoverage(coverage))return false;
  const ownerPaths=new Set();let childTotal=0;
  return rows.every(row=>{
    const ref=row?.input_ref;
    if(!ref||ref.input_sha256!==inputHash||typeof ref.relative_path!=='string'||!ref.relative_path.toLowerCase().endsWith('.xml')||!/^[a-f0-9]{64}$/.test(ref.raw_sha256)||ownerPaths.has(ref.relative_path))return false;
    ownerPaths.add(ref.relative_path);
    if(!hasChildren(row))return true;
    const matches=row.child_matches,total=row.child_matching_total;
    if(!Array.isArray(matches)||!Number.isInteger(total)||total<1||total>coverage.fields_scanned||matches.length!==Math.min(20,total)||row.child_matches_truncated!==(total>matches.length))return false;
    childTotal+=total;
    return childTotal<=coverage.fields_scanned&&matches.every(child=>child&&['Attribute','Dimension','Resource'].includes(child.type)&&['name','synonym','synonym_locale','parent_name','observed_uuid'].every(key=>fieldText(child[key]))&&child.uuid_status==='unverified'&&positiveIndex(child.child_index)&&(child.parent_type===null?child.parent_name===null&&child.parent_index===null:child.parent_type==='TabularSection'&&child.type==='Attribute'&&positiveIndex(child.parent_index)));
  });
}
export function attributeSearchCoverageText(coverage){
  if(!validAttributeCoverage(coverage))return '';
  return `${coverage.complete?'Проверена только указанная область':'Частичное покрытие указанной области'} Designer XML: прямые реквизиты (Attribute), измерения (Dimension), ресурсы (Resource) и реквизиты табличных частей (TabularSection). Полей проверено: ${coverage.fields_scanned}; табличных частей: ${coverage.tabular_sections_scanned}.${coverage.complete?'':` Неподдерживаемых корней не разобрано: ${coverage.unsupported_metadata_roots}. Отсутствие совпадений не исключает их в полях этих корней.`} Это не полный состав метаданных и не семантический индекс. EDT вне области поиска.`;
}
export function childMatchesHTML(row){
  if(!row.child_matches?.length)return '';
  const esc=escapeHTML,ref=row.input_ref;
  const property=(label,value)=>`<dt>${esc(label)}</dt><dd class="mono">${esc(value)}</dd>`;
  return `<section class="detail-section attribute-matches" aria-label="Совпадения в полях Designer XML"><h3 class="section-label">СОВПАДЕНИЯ В ПОЛЯХ DESIGNER XML</h3><p class="source-meta">Показано ${row.child_matches.length} из ${row.child_matching_total} совпавших полей этого объекта-владельца.</p>${row.child_matches_truncated?'<p class="notice caution">Список совпадений сокращён до 20 полей. Остальные совпадения не перечислены; исходный XML объекта доступен на вкладке «Исходный файл».</p>':''}<ol class="attribute-match-list">${row.child_matches.map(child=>`<li class="attribute-match"><strong>${esc(child.name||'Имя не указано')}</strong><p class="attribute-match-type">${esc(typeLabel(child.type))} (${esc(child.type)})</p>${child.synonym!==null?`<p>Синоним${child.synonym_locale===null?'':` (${esc(child.synonym_locale)})`}: ${esc(child.synonym)}</p>`:''}<p class="attribute-parent">${child.parent_type===null?'Прямое поле объекта':`Табличная часть: ${esc(child.parent_name||'Имя не указано')} (${esc(child.parent_type)}); позиция в ChildObjects объекта: ${child.parent_index}`}</p><p class="source-meta">Позиция поля в ChildObjects: ${child.child_index}</p><p class="mono">UUID: ${esc(child.observed_uuid||'Не указан')}</p><span class="tag warn">Идентичность не проверена</span></li>`).join('')}</ol><p class="section-label">ИСТОЧНИК ПОЛЕЙ</p><dl class="properties attribute-provenance">${property('XML объекта-владельца',ref.relative_path)}${property('SHA-256 файла',ref.raw_sha256)}${property('SHA-256 архива',ref.input_sha256)}</dl><p class="source-meta">Позиции отсчитываются с 1 среди элементов соответствующего ChildObjects. Совпадения сохранены в порядке XML; одинаковые имена не объединяются. UUID наблюдается в XML и не доказывает идентичность.</p></section>`;
}
export function searchReplyMatches(binding,search,query,reply){
  if(reply?.search!==search||reply.job!==binding.job||reply.input_sha256!==binding.input_sha256||reply.query!==query||reply.offset!==binding.offset||reply.kind!==binding.kind||reply.object_path!==binding.object_path||reply.prefix!==(binding.object_path?binding.object_path.slice(0,-4)+'/':null))return false;
  if(reply.status!=='ready')return true;
  const result=reply.result,rows=result?.[binding.kind==='metadata'?'objects':'modules'],page=result?.page;
  if(result?.input?.input_sha256!==binding.input_sha256||!Array.isArray(rows)||rows.length>200||!page)return false;
  if(binding.kind==='source'&&!sourceResultMatches(result,rows,query))return false;
  if(binding.kind==='metadata'&&!attributeResultMatches(result,rows,query,binding.input_sha256))return false;
  const total=binding.kind==='metadata'?result.matching_objects:result.matching_modules;
  return Number.isInteger(binding.offset)&&binding.offset>=0&&binding.offset<=4000&&binding.offset%200===0&&Number.isInteger(total)&&total>=0&&total<=4096&&(binding.offset===0||binding.offset<total)&&page.offset===binding.offset&&page.limit===200&&page.total===total&&page.returned===rows.length&&rows.length===Math.min(200,Math.max(0,total-binding.offset))&&page.has_previous===(binding.offset>0)&&page.has_next===(binding.offset+rows.length<total);
}
