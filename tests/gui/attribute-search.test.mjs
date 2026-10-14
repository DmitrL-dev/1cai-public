import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {searchReplyMatches,attributeSearchCoverageText,childMatchesHTML,typeLabel,escapeHTML} from '../../rentgen_core/gui_assets/model.js';

const binding={job:'owned-job',input_sha256:'a'.repeat(64),kind:'metadata',object_path:null,offset:0};
const inputRef={input_sha256:binding.input_sha256,raw_sha256:'b'.repeat(64),relative_path:'Catalogs/Владелец.xml'};
const owner={type:'Catalog',name:'Владелец',synonym:'Корневой объект',observed_uuid:null,uuid_status:'unverified',input_ref:inputRef};
const coverage={scope:'designer_direct_fields_and_tabular_attributes',fields_scanned:8,tabular_sections_scanned:2,unsupported_metadata_roots:0,complete:true};
const field={type:'Attribute',name:'Контрагент',synonym:'Основной партнёр',synonym_locale:'ru',parent_name:null,parent_type:null,observed_uuid:'observed-only',uuid_status:'unverified',child_index:1,parent_index:null};
const row=(matches=[field],extra={})=>({...owner,child_matches:matches,child_matching_total:matches.length,child_matches_truncated:false,...extra});
function reply(rows=[row()],result={}){
  return {...binding,search:'owned-search',query:'контрагент',prefix:null,status:'ready',result:{input:{input_sha256:binding.input_sha256},objects:rows,matching_objects:rows.length,attribute_search:coverage,page:{offset:0,limit:200,total:rows.length,returned:rows.length,has_previous:false,has_next:false},...result}};
}
const accepted=value=>searchReplyMatches(binding,'owned-search',value.query,value);

test('attribute hits keep one owner row and bounded direct and tabular field types',()=>{
  const matches=[field,{...field,type:'Dimension',child_index:2},{...field,type:'Resource',child_index:3},{...field,parent_name:'Строки',parent_type:'TabularSection',parent_index:4,child_index:1}];
  const value=reply([row(matches)]);
  assert.ok(accepted(value));
  assert.equal(value.result.matching_objects,1);
  assert.equal(value.result.objects[0].child_matching_total,4);
  assert.deepEqual(value.result.objects[0].input_ref,inputRef);
  assert.equal(typeLabel('Attribute'),'Реквизит');
  assert.equal(typeLabel('Dimension'),'Измерение');
  assert.equal(typeLabel('Resource'),'Ресурс');
  assert.equal(typeLabel('TabularSection'),'Табличная часть');
});

test('root-only and empty-query inventory contracts remain unchanged',()=>{
  const value=reply([owner]);
  assert.ok(accepted(value),'a root match may have no matching fields');
  delete value.result.attribute_search;
  assert.ok(accepted(value),'legacy root-only query remains accepted');
  value.query='';
  assert.ok(accepted(value),'empty listing needs no field-search coverage');
  assert.equal(childMatchesHTML(owner),'');
  assert.equal(attributeSearchCoverageText(undefined),'');
  assert.equal(accepted({...value,result:{...value.result,attribute_search:coverage}}),false,'empty listing must not claim a field scan');
});

test('coverage stays explicit when no owner matches and never means all metadata',()=>{
  const value=reply([]);
  assert.ok(accepted(value));
  const text=attributeSearchCoverageText(value.result.attribute_search);
  for(const part of ['только указанная область Designer XML','Attribute','Dimension','Resource','TabularSection','Полей проверено: 8','табличных частей: 2','не полный состав метаданных','не семантический индекс'])assert.ok(text.includes(part));
  assert.ok(!text.includes('Полное покрытие'));
  assert.equal(attributeSearchCoverageText({...coverage,scope:'all_metadata'}),'');
  assert.equal(attributeSearchCoverageText({...coverage,complete:false}),'');
});

test('coverage rejects unknown scope, inconsistent completeness, malformed and over-budget counts',()=>{
  for(const update of [{scope:'all_metadata'},{complete:false},{complete:1},{unsupported_metadata_roots:1},{unsupported_metadata_roots:-1},{unsupported_metadata_roots:4097},{unsupported_metadata_roots:0.5},{unsupported_metadata_roots:'0'},{unsupported_metadata_roots:undefined},{fields_scanned:-1},{fields_scanned:1.5},{fields_scanned:'8'},{tabular_sections_scanned:null},{tabular_sections_scanned:-1},{fields_scanned:20000,tabular_sections_scanned:1}]){
    assert.equal(accepted(reply([],{attribute_search:{...coverage,...update}})),false,JSON.stringify(update));
  }
  assert.equal(accepted(reply([],{attribute_search:null})),false);
  assert.ok(accepted(reply([],{attribute_search:{...coverage,fields_scanned:19999,tabular_sections_scanned:1}})));
});

test('partial coverage retains honest results and warns that zero matches excludes no skipped fields',()=>{
  const partial={...coverage,unsupported_metadata_roots:2,complete:false};
  assert.ok(accepted(reply([row()],{attribute_search:partial})));
  assert.ok(accepted(reply([],{attribute_search:partial})));
  assert.ok(accepted(reply([],{attribute_search:{...partial,unsupported_metadata_roots:4096}})));
  const text=attributeSearchCoverageText(partial);
  for(const part of ['Частичное покрытие указанной области Designer XML','Неподдерживаемых корней не разобрано: 2','Отсутствие совпадений не исключает их в полях этих корней','не полный состав метаданных','EDT вне области поиска'])assert.ok(text.includes(part));
  assert.equal(attributeSearchCoverageText({...partial,complete:true}),'');
});

test('child hits cannot appear without their full honest count and scope envelope',()=>{
  const value=reply();delete value.result.attribute_search;
  assert.equal(accepted(value),false);
  for(const key of ['child_matches','child_matching_total','child_matches_truncated']){
    const object=row();delete object[key];assert.equal(accepted(reply([object])),false,key);
  }
  for(const update of [{child_matches:[]},{child_matching_total:0},{child_matching_total:1.5},{child_matching_total:9},{child_matches_truncated:true},{child_matches_truncated:0}])assert.equal(accepted(reply([row([field],update)])),false,JSON.stringify(update));
});

test('twenty displayed child hits retain the actual bounded total and exact truncation flag',()=>{
  const matches=Array.from({length:20},(_,i)=>({...field,child_index:i+1}));
  const object=row(matches,{child_matching_total:25,child_matches_truncated:true});
  const value=reply([object],{attribute_search:{...coverage,fields_scanned:25}});
  assert.ok(accepted(value));
  assert.equal(accepted(reply([row(matches,{child_matching_total:25})],{attribute_search:{...coverage,fields_scanned:25}})),false);
  assert.equal(accepted(reply([row([...matches,field],{child_matching_total:25,child_matches_truncated:true})],{attribute_search:{...coverage,fields_scanned:25}})),false);
  const html=childMatchesHTML(object);
  assert.equal((html.match(/class="attribute-match"/g)||[]).length,20);
  assert.ok(html.includes('Показано 20 из 25 совпавших полей'));
  assert.ok(html.includes('Список совпадений сокращён до 20 полей'));
  assert.ok(html.includes('исходный XML объекта'));
});

test('field contract accepts nullable values and rejects unsupported fields or nesting',()=>{
  assert.ok(accepted(reply([row([{...field,name:null,synonym:null,synonym_locale:null,observed_uuid:null}])])));
  assert.ok(accepted(reply([row([{...field,parent_type:'TabularSection',parent_name:null,parent_index:3}])])));
  for(const update of [{type:'Form'},{type:'TabularSection'},{uuid_status:'verified'},{child_index:0},{child_index:1.1},{child_index:'1'},{child_index:Number.MAX_SAFE_INTEGER+1},{parent_type:null,parent_name:'unexpected'},{parent_index:3},{parent_type:'Form',parent_index:3},{parent_type:'TabularSection',parent_index:null},{parent_type:'TabularSection',parent_index:0},{type:'Resource',parent_type:'TabularSection',parent_index:3},{name:undefined},{synonym:7},{synonym_locale:undefined},{synonym_locale:7},{observed_uuid:{}}])assert.equal(accepted(reply([row([{...field,...update}])])),false,JSON.stringify(update));
});

test('each child textual field uses the 512 UTF-8-byte bound',()=>{
  for(const key of ['name','synonym','synonym_locale','observed_uuid']){
    assert.ok(accepted(reply([row([{...field,[key]:'я'.repeat(256)}])])),key);
    assert.equal(accepted(reply([row([{...field,[key]:'я'.repeat(257)}])])),false,key);
  }
  const child={...field,parent_type:'TabularSection',parent_index:4,parent_name:'😀'.repeat(128)};
  assert.ok(accepted(reply([row([child])])));
  assert.equal(accepted(reply([row([{...child,parent_name:'😀'.repeat(129)}])])),false);
});

test('child hit provenance is the exact owner XML and duplicate owners are rejected',()=>{
  for(const update of [{input_sha256:'c'.repeat(64)},{raw_sha256:'b'.repeat(63)},{raw_sha256:'g'.repeat(64)},{relative_path:'Catalogs/Владелец/Ext/Module.bsl'},{relative_path:null}])assert.equal(accepted(reply([row([field],{input_ref:{...inputRef,...update}})])),false,JSON.stringify(update));
  assert.equal(accepted(reply([row([field],{input_ref:null})])),false);
  assert.equal(accepted(reply([row(),row()])),false,'one owner per row, not one row per matching child');
  const another=row([field],{input_ref:{...inputRef,relative_path:'Catalogs/Другой.xml'}});
  assert.ok(accepted(reply([row(),another])));
  assert.equal(accepted(reply([row(),another],{attribute_search:{...coverage,fields_scanned:1}})),false,'summed child totals cannot exceed scanned fields');
});

test('detail markup preserves duplicate names, XML order, parent context and observed UUID warning',()=>{
  const matches=[{...field,child_index:7},{...field,parent_name:'Строки',parent_type:'TabularSection',parent_index:9,child_index:2},{...field,child_index:10}];
  const object=row(matches);
  assert.ok(accepted(reply([object])));
  const html=childMatchesHTML(object);
  assert.equal((html.match(/<strong>Контрагент<\/strong>/g)||[]).length,3);
  assert.equal((html.match(/Идентичность не проверена/g)||[]).length,3);
  assert.ok(html.includes('Реквизит (Attribute)'));
  assert.ok(html.includes('Табличная часть: Строки (TabularSection); позиция в ChildObjects объекта: 9'));
  assert.ok(html.indexOf('ChildObjects: 7')<html.indexOf('ChildObjects: 2'));
  assert.ok(html.indexOf('ChildObjects: 2')<html.indexOf('ChildObjects: 10'));
  assert.ok(html.includes('XML объекта-владельца'));
  assert.ok(html.includes(inputRef.relative_path));
  assert.ok(html.includes(inputRef.raw_sha256));
  assert.ok(html.includes(inputRef.input_sha256));
  assert.ok(html.includes('UUID наблюдается в XML и не доказывает идентичность'));
  assert.ok(!html.includes('Список совпадений сокращён'));
  assert.ok(!/<button|<a\b/.test(html),'fields have no independent source capability or navigation');
});

test('displayed matched synonym keeps its own locale without changing owner synonyms',()=>{
  const object=row([{...field,synonym:'Business partner',synonym_locale:'en'}]);
  assert.ok(accepted(reply([object])));
  assert.ok(childMatchesHTML(object).includes('Синоним (en): Business partner'));
  assert.ok(childMatchesHTML(row()).includes('Синоним (ru): Основной партнёр'));
  assert.ok(childMatchesHTML(row([{...field,synonym_locale:null}])).includes('Синоним: Основной партнёр'));
  assert.equal(object.synonym,'Корневой объект');
  const child={...field};delete child.synonym_locale;
  assert.equal(accepted(reply([row([child])])),false,'a child record must explicitly identify a nullable locale');
});

test('all archive text in child details is escaped rather than executable markup',()=>{
  const payload='<img src=x onerror="globalThis.injected=1">';
  const child={...field,name:payload,synonym:payload,synonym_locale:payload,parent_name:payload,parent_type:'TabularSection',parent_index:2,observed_uuid:payload};
  const object=row([child],{input_ref:{...inputRef,relative_path:`Catalogs/${payload}.xml`}});
  assert.ok(accepted(reply([object])));
  const html=childMatchesHTML(object);
  assert.ok(!html.includes('<img'));
  assert.equal((html.match(/&lt;img/g)||[]).length,6);
  assert.ok(html.includes(escapeHTML(payload)));
  assert.ok(html.includes('Позиция поля в ChildObjects: 1'));
});

test('attribute reply retains job, archive, query, search and pagination ownership guards',()=>{
  const value=reply();
  for(const update of [{job:'stale'},{input_sha256:'c'.repeat(64)},{search:'stale'},{kind:'modules'},{query:'other'},{offset:200},{object_path:'Catalogs/Other.xml'}])assert.equal(searchReplyMatches(binding,'owned-search','контрагент',{...value,...update}),false,JSON.stringify(update));
  const page={...value.result.page,total:2};
  assert.equal(accepted({...value,result:{...value.result,page}}),false);
});

test('app wires field details, owner counts, scope help and explicit failure states without a new capability',async()=>{
  const app=await readFile(new URL('../../rentgen_core/gui_assets/app.js',import.meta.url),'utf8');
  const html=await readFile(new URL('../../rentgen_core/gui_assets/index.html',import.meta.url),'utf8');
  assert.ok(app.includes('content+=childMatchesHTML(row)'));
  assert.ok(app.includes('renderAttributeCoverage(searchResult)'));
  assert.ok(app.includes("state.view==='objects'&&state.metadataQuery?attributeSearchCoverageText(result?.attribute_search):''"));
  assert.ok(app.includes("$('attribute-coverage').textContent=text"));
  assert.ok(app.includes('по всему ZIP (объекты-владельцы)'));
  assert.ok(app.includes('в проверенных корнях (объекты-владельцы)'));
  assert.ok(app.includes('В проверенных корнях совпадений нет'));
  assert.ok(app.includes("$('attribute-coverage').classList.toggle('caution',!!text&&result.attribute_search.complete===false)"));
  assert.ok(html.includes('id="attribute-coverage" class="notice" role="status" hidden'));
  assert.ok(html.includes('id="attribute-search-help"'));
  assert.ok(html.includes('aria-label="Поиск объектов и полей Designer XML"'));
  assert.ok(app.includes("sourceMode()?'Поиск точного фрагмента кода':isModules?'Поиск по имени или пути':'Поиск объектов и полей Designer XML'"));
  assert.ok(html.includes('Одна строка на объект-владелец'));
  for(const code of ['METADATA_SEARCH_BUDGET_EXCEEDED','METADATA_SEARCH_LIMIT_EXCEEDED','METADATA_SEARCH_UNSUPPORTED'])assert.ok(app.includes(code));
  assert.ok(!app.includes('/api/attribute'));
});
