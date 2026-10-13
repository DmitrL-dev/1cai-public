import test from 'node:test';
import assert from 'node:assert/strict';
import {comparisonStatusMatches,comparisonMatches,comparisonPageMatches,comparisonSourceMatches} from '../../rentgen_core/gui_assets/comparison.js';
const binding={job:'a'.repeat(32),input_sha256:'b'.repeat(64)};
const pair={job:binding.job,pair:'c'.repeat(32),before_sha256:binding.input_sha256,after_sha256:'d'.repeat(64),before_filename:'before.zip',after_filename:'after.zip',scope:'submitted_zip_bytes',comparison:'raw_sha256_and_size',counts:{total:1,files:1,changes:1,added:0,removed:0,modified:1,unchanged:0}};
const row={path:'CommonModules/Модуль.bsl',status:'modified',before:{raw_sha256:'e'.repeat(64),size_bytes:4},after:{raw_sha256:'f'.repeat(64),size_bytes:5}};
const page={id:'1'.repeat(32),offset:0,limit:200,total:1,returned:1,has_previous:false,has_next:false};
test('comparison binds before job and both archive identities with complete counts',()=>{
 assert.ok(comparisonMatches(binding,pair));
 for(const change of [{job:'other'},{before_sha256:'0'.repeat(64)},{after_sha256:'bad'},{pair:'bad'},{scope:'snapshot'},{comparison:'semantic'},{counts:{...pair.counts,total:8193}},{counts:{...pair.counts,unchanged:1}}])assert.equal(comparisonMatches(binding,{...pair,...change}),false);
});
test('comparison pages reject cross-pair/filter/page bounds and forged side rows',()=>{
 const result={...pair,status:'changes',page,rows:[row]};assert.ok(comparisonPageMatches(pair,result,0,'changes'));
 for(const change of [{pair:'2'.repeat(32)},{after_sha256:'3'.repeat(64)},{status:'all'},{page:{...page,offset:200}},{page:{...page,limit:201}},{page:{...page,total:2}},{page:{...page,has_next:true}},{rows:[{...row,before:null}]},{rows:[{...row,after:{...row.after,raw_sha256:'forged'}}]},{rows:Array(201).fill(row)}])assert.equal(comparisonPageMatches(pair,{...result,...change},0,'changes'),false);
});
test('comparison source is side-specific, page-specific and raw-hash bound',()=>{
 const result={pair:pair.pair,before_sha256:pair.before_sha256,after_sha256:pair.after_sha256,page:page.id,side:'before',text:'test',encoding:'UTF-8',size_bytes:4,input_ref:{input_sha256:pair.before_sha256,relative_path:row.path,raw_sha256:row.before.raw_sha256}};
 assert.ok(comparisonSourceMatches(pair,page,row,'before',result));
 for(const change of [{side:'after'},{page:'2'.repeat(32)},{pair:'2'.repeat(32)},{input_ref:{...result.input_ref,raw_sha256:row.after.raw_sha256}},{input_ref:{...result.input_ref,relative_path:'elsewhere'}},{text:'x'.repeat(262145)},{size_bytes:5}])assert.equal(comparisonSourceMatches(pair,page,row,'before',{...result,...change}),false);
 assert.equal(comparisonSourceMatches(pair,page,{...row,before:null},'before',result),false);
});
test('comparison markup exposes native labeled controls and source uses text only',async()=>{
 const {readFile}=await import('node:fs/promises');
 const html=await readFile(new URL('../../rentgen_core/gui_assets/index.html',import.meta.url),'utf8');
 const js=await readFile(new URL('../../rentgen_core/gui_assets/comparison.js',import.meta.url),'utf8');
 assert.match(html,/<label for="compare-filter">Показать файлы<\/label><select id="compare-filter">/);
 assert.match(html,/aria-label="ZIP после изменения"/);assert.match(html,/data-view="comparison"/);
 assert.ok(!js.includes('innerHTML'));assert.match(js,/pre.textContent=result.text/);
 assert.match(js,/attempt<3/);assert.match(js,/\/api\/comparison-upload/);
});


test('ready comparison envelope must bind its exact known operation, not another pair',()=>{
 const reply={comparison:pair.pair,job:binding.job,input_sha256:binding.input_sha256,status:'ready',result:pair};
 assert.ok(comparisonStatusMatches(binding,reply,pair.pair));
 assert.equal(comparisonStatusMatches(binding,{...reply,result:{...pair,pair:'2'.repeat(32)}},pair.pair),false);
 assert.equal(comparisonStatusMatches(binding,reply,'2'.repeat(32)),false);
 assert.equal(comparisonStatusMatches(binding,{...reply,job:'old'},pair.pair),false);
 const result={...pair,status:'changes',page,rows:[{...row,status:'modified',after:row.before}]};
 assert.equal(comparisonPageMatches(pair,result,0,'changes'),false);
 const unchanged={...pair,counts:{total:1,files:1,changes:0,added:0,removed:0,modified:0,unchanged:1}};
 assert.equal(comparisonPageMatches(unchanged,{...unchanged,status:'all',page,rows:[{...row,status:'unchanged'}]},0,'all'),false);
});

// Minimal owned DOM surface exercises async controller ownership without a browser substitute.
class Element {
 constructor(tag='div'){this.tag=tag;this.children=[];this.attrs={};this.listeners={};this.value='changes';this.files=[];this.hidden=false;this.disabled=false;this.textContent='';}
 append(...nodes){this.children.push(...nodes);for(const node of nodes)node.parent=this;}
 replaceChildren(...nodes){this.children=[];this.textContent='';this.append(...nodes);}
 replaceWith(node){const parent=this.parent;parent.children[parent.children.indexOf(this)]=node;node.parent=parent;}
 setAttribute(k,v){this.attrs[k]=v;}
 focus(){document.activeElement=this;}
 addEventListener(k,fn){this.listeners[k]=fn;}
 querySelectorAll(tag){return this.children.flatMap(node=>[...(node.tag===tag?[node]:[]),...node.querySelectorAll(tag)]);}
}
async function controller(api,fetchReport){
 const {createComparison}=await import('../../rentgen_core/gui_assets/comparison.js');
 const nodes=new Map();globalThis.document={getElementById:id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},createElement:tag=>new Element(tag)};
 const ui=createComparison({api,fetchReport,errorText:error=>error.code,getBinding:()=>({...binding,filename:'before.zip'})});
 return {ui,nodes};
}
async function until(check){for(let i=0;i<100;i++){if(check())return;await new Promise(resolve=>setTimeout(resolve,5));}assert.ok(check(),'controller did not reach expected state');}
const readyStatus={comparison:pair.pair,job:binding.job,input_sha256:binding.input_sha256,status:'ready',result:pair};
const pageReply={...pair,status:'changes',page,rows:[row]};
test('leaving comparison ignores a late real-shaped page and source response',async()=>{
 let releasePage,releaseSource,holdPage=true;
 const api=async path=>{
  if(path.startsWith('/api/comparison-current'))return {...binding,current:readyStatus,pending:null};
  if(path==='/api/comparison-page'){if(holdPage)return new Promise(resolve=>releasePage=()=>resolve(pageReply));return pageReply;}
  if(path.startsWith('/api/comparison-source'))return new Promise(resolve=>releaseSource=()=>resolve({pair:pair.pair,before_sha256:pair.before_sha256,after_sha256:pair.after_sha256,page:page.id,side:'before',text:'test',encoding:'UTF-8',size_bytes:4,input_ref:{input_sha256:pair.before_sha256,relative_path:row.path,raw_sha256:row.before.raw_sha256}}));
  throw Error(path);
 };
 const {ui,nodes}=await controller(api);ui.enter();await until(()=>!!releasePage);ui.leave();releasePage();await new Promise(resolve=>setTimeout(resolve,10));
 assert.equal(nodes.get('compare-list').children.length,0);assert.equal(nodes.get('compare-result').hidden,true);
 holdPage=false;ui.enter();await until(()=>nodes.get('compare-list').children.length===1);nodes.get('compare-list').children[0].listeners.click();await until(()=>!!releaseSource);
 ui.leave();releaseSource();await new Promise(resolve=>setTimeout(resolve,10));assert.equal(nodes.get('compare-source').children.length,0);
});
test('failed replacement restores accepted pair and retains explicit error without replay',async()=>{
 let puts=0,starts=0;
 const id='9'.repeat(32);
 const api=async path=>{
  if(path.startsWith('/api/comparison-current'))return {...binding,current:readyStatus,pending:null};
  if(path==='/api/comparison-page')return pageReply;
  if(path==='/api/comparison-start'){starts++;return {comparison:id,...binding,status:'awaiting_upload'};}
  if(path.startsWith('/api/comparison-upload')){puts++;throw {code:'IMPORT_UNSUPPORTED_ARCHIVE'};}
  throw Error(path);
 };
 const {ui,nodes}=await controller(api);ui.enter();await until(()=>nodes.get('compare-list').children.length===1);
 nodes.get('compare-file').files=[{name:'corrupt.zip',size:30}];nodes.get('compare-file').listeners.change();
 await until(()=>nodes.get('compare-message').textContent.includes('IMPORT_UNSUPPORTED_ARCHIVE')&&nodes.get('compare-list').children.length===1);
 assert.equal(puts,1);assert.equal(starts,1);assert.equal(nodes.get('compare-result').hidden,false);assert.equal(ui.busy,false);ui.leave();
});


test('late report is discarded after view change or explicit cancellation without creating a download',async()=>{
 const api=async path=>path.startsWith('/api/comparison-current')?{...binding,current:readyStatus,pending:null}:pageReply;
 for(const action of ['leave','cancel']){
  let release,signal;const pending=new Promise(resolve=>release=resolve);
  const {ui,nodes}=await controller(api,async(pair,format,ownedSignal)=>{signal=ownedSignal;return pending;});
  ui.enter();await until(()=>nodes.get('compare-list').children.length===1);
  nodes.get('compare-report-json').listeners.click();await until(()=>!!signal);
  if(action==='leave')ui.leave();else nodes.get('compare-report-cancel').listeners.click();
  assert.equal(signal.aborted,true);
  // An invalid blob would fail visibly if the late result reached deliverReport.
  release({blob:null,filename:'must-not-download.json',sha256:'0'.repeat(64),size:1});
  await new Promise(resolve=>setTimeout(resolve,10));
  assert.ok(!nodes.get('compare-report-status').textContent.includes('передан браузеру'));
  if(action==='cancel')assert.equal(nodes.get('compare-result').hidden,false);
  ui.leave();
 }
});
