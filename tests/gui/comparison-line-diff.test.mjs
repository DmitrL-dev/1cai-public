import test from 'node:test';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {comparisonLineDiffMatches,createComparison} from '../../rentgen_core/gui_assets/comparison.js';
const binding={job:'a'.repeat(32),input_sha256:'b'.repeat(64)};
const pair={job:binding.job,pair:'c'.repeat(32),before_sha256:binding.input_sha256,after_sha256:'d'.repeat(64),before_filename:'before.zip',after_filename:'after.zip',scope:'submitted_zip_bytes',comparison:'raw_sha256_and_size',counts:{total:1,files:1,changes:1,added:0,removed:0,modified:1,unchanged:0}};
const row={path:'CommonModules/Модуль.bsl',status:'modified',before:{raw_sha256:'e'.repeat(64),size_bytes:4},after:{raw_sha256:'f'.repeat(64),size_bytes:5}};
const page={id:'1'.repeat(32),offset:0,limit:200,total:1,returned:1,has_previous:false,has_next:false};
const ref=side=>({input_sha256:pair[side+'_sha256'],relative_path:row.path,...row[side]});
const evidence=size=>({present:true,size_bytes:size,bom:false,line_count:1,newlines:{LF:0,CRLF:0,CR:0},final_newline:false});
const result=()=>({pair:pair.pair,before_sha256:pair.before_sha256,after_sha256:pair.after_sha256,page:page.id,path:row.path,input_refs:{before:ref('before'),after:ref('after')},status:'complete',reason:null,before:evidence(4),after:evidence(5),limits:{source_bytes:262144,lines_per_side:4096,output_rows:8192,dp_cells:1000000},coverage:{alignment:'complete',full_scan:true},pagination:{offset:0,limit:200,total:2,returned:2,has_previous:false,has_next:false},rows:[{kind:'delete',before_line:1,after_line:null,text:'test',eol:'none'},{kind:'insert',before_line:null,after_line:1,text:'tests',eol:'none'}]});
const valid=r=>comparisonLineDiffMatches(pair,page,row,0,r);
test('line diff validates exact pair, selected page/path, both file hashes and limits',()=>{
 assert.equal(valid(result()),true);
 const changes=[r=>r.pair='0'.repeat(32),r=>r.before_sha256='0'.repeat(64),r=>r.after_sha256='0'.repeat(64),r=>r.page='0'.repeat(32),r=>r.path='elsewhere',r=>r.input_refs.before.raw_sha256='0'.repeat(64),r=>r.input_refs.after.size_bytes=0,r=>r.input_refs.before.input_sha256=pair.after_sha256,r=>r.limits.dp_cells++,r=>r.coverage.full_scan=false,r=>r.status='partial',r=>r.reason='semantic'];
 for(const change of changes){const r=result();change(r);assert.equal(valid(r),false);}
});
test('line diff rejects malformed rows, text, line numbers, byte sizes and metadata',()=>{
 const changes=[r=>r.rows[0].kind='modified',r=>r.rows[0].text='too long',r=>r.rows[0].text='te\nst',r=>r.rows[0].text='te\u0000t',r=>r.rows[0].text='tes\ud800',r=>r.rows[0].before_line=2,r=>r.rows[0].after_line=1,r=>r.rows[0].eol='LF',r=>r.before.bom=true,r=>r.before.line_count=4097,r=>r.before.final_newline=true,r=>r.before.newlines.LF=1,r=>r.before.present=false,r=>r.before.size_bytes=0,r=>r.pagination.total=3,r=>r.pagination.has_next=true,r=>r.pagination.returned=0,r=>r.pagination.limit=201];
 for(const change of changes){const r=result();change(r);assert.equal(valid(r),false);}
 for(const offset of [-1,1,200.5,8200,'0',null])assert.equal(comparisonLineDiffMatches(pair,page,row,offset,result()),false);
});
test('absent, empty and BOM-only evidence stay distinct with exact zero-row coverage',()=>{
 const r=result(),selected={...row,before:null,after:{...row.after,size_bytes:3}};
 Object.assign(r,{input_refs:{before:null,after:{...ref('after'),size_bytes:3}},before:{present:false,size_bytes:null,bom:null,line_count:null,newlines:null,final_newline:null},after:{...evidence(3),bom:true,line_count:0},rows:[],pagination:{...r.pagination,total:0,returned:0}});
 assert.equal(comparisonLineDiffMatches(pair,page,selected,0,r),true);
 r.before.bom=false;assert.equal(comparisonLineDiffMatches(pair,page,selected,0,r),false);r.before.bom=null;
 r.after.size_bytes=0;assert.equal(comparisonLineDiffMatches(pair,page,selected,0,r),false);
});
test('unavailable results are row-free and never advertise full alignment',()=>{
 for(const reason of ['SOURCE_ENCODING_UNSUPPORTED','WORK_LIMIT','LINE_LIMIT','SOURCE_TOO_LARGE']){
 const r=result(),selected=structuredClone(row);Object.assign(r,{status:'unavailable',reason,coverage:{alignment:'unavailable',full_scan:false},rows:[],pagination:{...r.pagination,total:0,returned:0}});
 if(reason==='SOURCE_ENCODING_UNSUPPORTED')Object.assign(r.before,{line_count:null,newlines:null,final_newline:null});
 if(reason==='LINE_LIMIT'){selected.before.size_bytes=4097;r.input_refs.before.size_bytes=4097;Object.assign(r.before,{size_bytes:4097,line_count:4097,newlines:{LF:4097,CR:0,CRLF:0},final_newline:true});}
 if(reason==='SOURCE_TOO_LARGE'){selected.before.size_bytes=300000;r.input_refs.before.size_bytes=300000;Object.assign(r.before,{size_bytes:300000,bom:null,line_count:null,newlines:null,final_newline:null});}
 assert.equal(comparisonLineDiffMatches(pair,page,selected,0,r),true);r.rows=result().rows;assert.equal(comparisonLineDiffMatches(pair,page,selected,0,r),false);
 }
});
test('Unicode separators, inert HTML and bounded long lines remain literal text',()=>{
 for(const text of ['Привет 😃\u2028\u2029','<img src=x onerror=alert(1)>','x'.repeat(262144)]){
 const size=new TextEncoder().encode(text).length,selected={...row,before:null,after:{...row.after,size_bytes:size}},r=result();
 Object.assign(r,{input_refs:{before:null,after:{...ref('after'),size_bytes:size}},before:{present:false,size_bytes:null,bom:null,line_count:null,newlines:null,final_newline:null},after:evidence(size),rows:[{kind:'insert',before_line:null,after_line:1,text,eol:'none'}],pagination:{...r.pagination,total:1,returned:1}});
 assert.equal(comparisonLineDiffMatches(pair,page,selected,0,r),true);
 }
});
test('200-row pages preserve exact count and sequential line numbering',()=>{
 const r=result(),selected={...row,before:{...row.before,size_bytes:402},after:{...row.after,size_bytes:402}};
 const evidence={present:true,size_bytes:402,bom:false,line_count:201,newlines:{LF:201,CRLF:0,CR:0},final_newline:true};
 Object.assign(r,{before:evidence,after:evidence,input_refs:{before:{...ref('before'),size_bytes:402},after:{...ref('after'),size_bytes:402}},rows:Array.from({length:200},(_,i)=>({kind:'equal',before_line:i+1,after_line:i+1,text:'x',eol:'LF'})),pagination:{offset:0,limit:200,total:201,returned:200,has_previous:false,has_next:true}});
 assert.equal(comparisonLineDiffMatches(pair,page,selected,0,r),true);
 r.rows[4].after_line=7;assert.equal(comparisonLineDiffMatches(pair,page,selected,0,r),false);
 r.rows=[{kind:'equal',before_line:201,after_line:201,text:'x',eol:'LF'}];r.pagination={offset:200,limit:200,total:201,returned:1,has_previous:true,has_next:false};
 assert.equal(comparisonLineDiffMatches(pair,page,selected,200,r),true);
 r.rows[0].before_line=200;assert.equal(comparisonLineDiffMatches(pair,page,selected,200,r),false);
});
class Element{
 constructor(tag='div'){this.tag=tag;this.children=[];this.attrs={};this.listeners={};this.value='changes';this.files=[];this.hidden=false;this.disabled=false;this.textContent='';}
 append(...nodes){this.children.push(...nodes);for(const node of nodes)node.parent=this;}
 replaceChildren(...nodes){this.children=[];this.textContent='';this.append(...nodes);}
 replaceWith(node){const parent=this.parent;parent.children[parent.children.indexOf(this)]=node;node.parent=parent;}
 setAttribute(k,v){this.attrs[k]=v;}focus(){document.activeElement=this;}
 addEventListener(k,fn){this.listeners[k]=fn;}
 querySelectorAll(tag){return this.children.flatMap(node=>[...(node.tag===tag?[node]:[]),...node.querySelectorAll(tag)]);}
}
const until=async check=>{for(let i=0;i<100;i++){if(check())return;await new Promise(resolve=>setTimeout(resolve,2));}assert.ok(check(),'controller did not reach expected state');};
async function setup(diff){
 const nodes=new Map();globalThis.document={getElementById:id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},createElement:tag=>new Element(tag)};
 const requests=[];
 const api=async(path,options)=>{
  if(path.startsWith('/api/comparison-current'))return {...binding,current:{comparison:pair.pair,...binding,status:'ready',result:pair},pending:null};
  if(path==='/api/comparison-page')return {...pair,status:'changes',page,rows:[row]};
  if(path.startsWith('/api/comparison-source')){const side=new URLSearchParams(path.split('?')[1]).get('side');return {pair:pair.pair,before_sha256:pair.before_sha256,after_sha256:pair.after_sha256,page:page.id,side,text:side==='before'?'test':'tests',encoding:'UTF-8',size_bytes:row[side].size_bytes,input_ref:ref(side)};}
  if(path==='/api/comparison-line-diff'){requests.push(options);return diff(options);}
  throw Error(path);
 };
 const ui=createComparison({api,errorText:error=>error.code,getBinding:()=>({...binding,filename:'before.zip'})});ui.enter();await until(()=>nodes.get('compare-list')?.children.length===1);nodes.get('compare-list').children[0].listeners.click();await until(()=>requests.length===1);
 return {ui,nodes,requests};
}
const flatten=node=>[node,...node.children.flatMap(flatten)];
test('selected diff sends exact read-only request and renders originals plus numbered rows',async()=>{
 const {ui,nodes,requests}=await setup(async()=>result());await until(()=>flatten(nodes.get('compare-source')).some(n=>n.className==='comparison-diff-text'));
 assert.deepEqual(JSON.parse(requests[0].body),{pair:pair.pair,before_sha256:pair.before_sha256,after_sha256:pair.after_sha256,page:page.id,path:row.path,offset:0});
 assert.equal(requests[0].method,'POST');assert.equal(nodes.get('compare-source').querySelectorAll('pre').length,4);ui.leave();
});
test('cancel, new selection, filter and leave suppress a late diff even when API ignores abort',async()=>{
 for(const action of ['cancel','selection','filter','leave']){
  let release;const {ui,nodes,requests}=await setup(()=>new Promise(resolve=>release=resolve));
  const original=nodes.get('compare-source'),section=original.children.at(-1),all=flatten(section);
  if(action==='cancel')all.find(n=>n.textContent==='Отменить ожидание строк').listeners.click();
  if(action==='selection')nodes.get('compare-list').children[0].listeners.click();
  if(action==='filter')nodes.get('compare-filter').listeners.change();
  if(action==='leave')ui.leave();
  assert.equal(requests[0].signal.aborted,true);release(result());await new Promise(resolve=>setTimeout(resolve,10));
  assert.equal(flatten(section).filter(n=>n.className==='comparison-diff-text').length,0);
  if(action==='cancel'){assert.equal(original.querySelectorAll('pre').length,2);assert.ok(flatten(section).some(n=>n.textContent.includes('сервере может продолжаться')));}
  ui.leave();
 }
});
test('invalid response falls back without discarding original panels; retry is possible',async()=>{
 const bad=result();bad.input_refs.after.raw_sha256='0'.repeat(64);
 const {ui,nodes}=await setup(async()=>bad);await until(()=>flatten(nodes.get('compare-source')).some(n=>n.textContent.includes('PROTOCOL_ERROR')));
 assert.equal(nodes.get('compare-source').querySelectorAll('pre').length,2);
 const retry=flatten(nodes.get('compare-source')).find(n=>n.textContent==='Повторить сравнение строк');assert.equal(retry.disabled,false);ui.leave();
});

// Fixtures below are actual bounded_line_diff(None, raw) output, preserving U+FEFF
// after UTF-8-sig consumes at most the first leading BOM.
test('actual engine payloads retain interior-line BOM and a second leading BOM',()=>{
 const cases=[{"raw":"first\n\ufeffinside\n","diff":{"status":"complete","reason":null,"before":{"present":false,"size_bytes":null,"bom":null,"line_count":null,"newlines":null,"final_newline":null},"after":{"present":true,"size_bytes":16,"bom":false,"line_count":2,"newlines":{"LF":2,"CRLF":0,"CR":0},"final_newline":true},"rows":[{"kind":"insert","before_line":null,"after_line":1,"text":"first","eol":"LF"},{"kind":"insert","before_line":null,"after_line":2,"text":"\ufeffinside","eol":"LF"}],"limits":{"source_bytes":262144,"lines_per_side":4096,"output_rows":8192,"dp_cells":1000000}}},{"raw":"\ufeff\ufeffsecond\n","diff":{"status":"complete","reason":null,"before":{"present":false,"size_bytes":null,"bom":null,"line_count":null,"newlines":null,"final_newline":null},"after":{"present":true,"size_bytes":13,"bom":true,"line_count":1,"newlines":{"LF":1,"CRLF":0,"CR":0},"final_newline":true},"rows":[{"kind":"insert","before_line":null,"after_line":1,"text":"\ufeffsecond","eol":"LF"}],"limits":{"source_bytes":262144,"lines_per_side":4096,"output_rows":8192,"dp_cells":1000000}}}];
 for(const {raw,diff} of cases){
  const bytes=Buffer.from(raw,'utf8'),sha=createHash('sha256').update(bytes).digest('hex');
  const selected={...row,before:null,after:{raw_sha256:sha,size_bytes:bytes.length}};
  const r={...result(),...diff,input_refs:{before:null,after:{input_sha256:pair.after_sha256,relative_path:row.path,...selected.after}},pagination:{offset:0,limit:200,total:diff.rows.length,returned:diff.rows.length,has_previous:false,has_next:false}};
  assert.ok(diff.rows.some(item=>item.text.startsWith('\ufeff')));
  assert.equal(comparisonLineDiffMatches(pair,page,selected,0,r),true);
  const changed=structuredClone(r);changed.rows.at(-1).text=changed.rows.at(-1).text.replace('\ufeff','');
  assert.equal(comparisonLineDiffMatches(pair,page,selected,0,changed),false,'dropping preserved BOM changes verified bytes');
 }
});

test('comparison banner describes bounded line comparison without semantic claims',()=>{
 const html=readFileSync(new URL('../../rentgen_core/gui_assets/index.html',import.meta.url),'utf8');
 assert.ok(html.includes('Для выбранного файла доступно ограниченное построчное сравнение текста.'));
 assert.ok(html.includes('Семантический анализ и применение изменений не выполняются.'));
 assert.ok(!html.includes('Построчное выравнивание, семантический анализ'));
});
