export function escapeHTML(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
const labels={Catalog:'Справочник',Document:'Документ',CommonModule:'Общий модуль',InformationRegister:'Регистр сведений',AccumulationRegister:'Регистр накопления',Report:'Отчёт',DataProcessor:'Обработка',Enum:'Перечисление',Constant:'Константа',Subsystem:'Подсистема'};
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
export function searchReplyMatches(binding,search,query,reply){
  if(reply?.search!==search||reply.job!==binding.job||reply.input_sha256!==binding.input_sha256||reply.query!==query||reply.offset!==binding.offset||reply.kind!==binding.kind||reply.object_path!==binding.object_path||reply.prefix!==(binding.object_path?binding.object_path.slice(0,-4)+'/':null))return false;
  if(reply.status!=='ready')return true;
  const result=reply.result,rows=result?.[binding.kind==='modules'?'modules':'objects'],page=result?.page;
  if(result?.input?.input_sha256!==binding.input_sha256||!Array.isArray(rows)||rows.length>200||!page)return false;
  const total=binding.kind==='modules'?result.matching_modules:result.matching_objects;
  return Number.isInteger(binding.offset)&&binding.offset>=0&&binding.offset<=4000&&binding.offset%200===0&&Number.isInteger(total)&&total>=0&&total<=4096&&(binding.offset===0||binding.offset<total)&&page.offset===binding.offset&&page.limit===200&&page.total===total&&page.returned===rows.length&&rows.length===Math.min(200,Math.max(0,total-binding.offset))&&page.has_previous===(binding.offset>0)&&page.has_next===(binding.offset+rows.length<total);
}
