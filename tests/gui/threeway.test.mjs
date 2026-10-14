import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {threewayAction,threewayCountsMatch,threewayStatusMatches,threewayUploadMatches,threewayPageMatches,createThreeway} from '../../rentgen_core/gui_assets/threeway.js';
const binding={job:'a'.repeat(32),input_sha256:'b'.repeat(64),filename:'current.zip'};
const plan='c'.repeat(32), uploadBase='d'.repeat(32), uploadUpstream='e'.repeat(32);
const roles={base:{filename:'base.zip',sha256:'1'.repeat(64),status:'ready',upload:uploadBase},current:{filename:binding.filename,sha256:binding.input_sha256,status:'ready',upload:null},upstream:{filename:'upstream.zip',sha256:'3'.repeat(64),status:'ready',upload:uploadUpstream}};
const counts={total:1,files:1,changes:1,unchanged:0,same_change:0,keep_current:0,take_upstream:0,conflict:1};
const coverage={scope:'exact_path_inventory',comparison:'raw_sha256_and_size',complete:true,entry_records:3,decoded_bytes:15,union_paths:1,side_entries:{base:1,current:1,upstream:1},side_decoded_bytes:{base:5,current:5,upstream:5}};
const ready={plan,job:binding.job,current_sha256:binding.input_sha256,status:'ready',roles,counts,coverage};
const missing={filename:null,sha256:null,status:'missing',upload:null};
const started={plan,job:binding.job,current_sha256:binding.input_sha256,status:'awaiting_inputs',roles:{base:missing,current:roles.current,upstream:missing}};
const row={path:'CommonModules/Тест.bsl',action:'conflict',base:{raw_sha256:'4'.repeat(64),size_bytes:5},current:{raw_sha256:'5'.repeat(64),size_bytes:5},upstream:{raw_sha256:'6'.repeat(64),size_bytes:5}};
const page={id:'f'.repeat(32),offset:0,limit:200,total:1,returned:1,has_previous:false,has_next:false};
const pageReply={plan,job:binding.job,base_sha256:roles.base.sha256,current_sha256:binding.input_sha256,upstream_sha256:roles.upstream.sha256,action:'changes',counts,coverage,page,rows:[row]};
const copy=value=>structuredClone(value);

test('five actions distinguish absence, empty files, same deletion and byte differences',()=>{
 const a={raw_sha256:'0'.repeat(64),size_bytes:0},b={raw_sha256:'1'.repeat(64),size_bytes:0},c={raw_sha256:'2'.repeat(64),size_bytes:1};
 const cases=[
  [a,a,a,'unchanged'],[null,a,a,'same_change'],[a,null,null,'same_change'],[a,b,b,'same_change'],
  [a,b,a,'keep_current'],[a,null,a,'keep_current'],[null,a,null,'keep_current'],
  [a,a,b,'take_upstream'],[a,a,null,'take_upstream'],[null,null,a,'take_upstream'],
  [null,a,b,'conflict'],[a,null,b,'conflict'],[a,b,null,'conflict'],[a,b,c,'conflict'],
 ];
 for(const [base,current,upstream,action] of cases)assert.equal(threewayAction(base,current,upstream),action);
 assert.equal(threewayAction(a,{...a,size_bytes:1},a),'keep_current');
});
test('complete counts and exact coverage are bounded and consistent for all three archives',()=>{
 assert.ok(threewayCountsMatch(counts,coverage));
 for(const change of [{total:12289},{files:2},{changes:0},{unchanged:1},{conflict:-1},{conflict:0.5}])assert.equal(threewayCountsMatch({...counts,...change},coverage),false);
 for(const change of [{complete:false},{scope:'native'},{comparison:'semantic'},{union_paths:2},{entry_records:4},{decoded_bytes:16},{side_entries:{base:4097,current:1,upstream:1}},{side_decoded_bytes:{base:-1,current:5,upstream:5}}])assert.equal(threewayCountsMatch(counts,{...coverage,...change}),false);
});
test('status binds Current and plan, all role identities and ready-only complete coverage',()=>{
 assert.ok(threewayStatusMatches(binding,ready,plan));assert.ok(threewayStatusMatches(binding,started));
 for(const change of [{plan:'x'},{job:'bad'},{current_sha256:'0'.repeat(64)},{status:'safe_merge'},{coverage:null}])assert.equal(threewayStatusMatches(binding,{...ready,...change},plan),false);
 assert.equal(threewayStatusMatches(binding,ready,'9'.repeat(32)),false);
 for(const [role,change] of [['current',{sha256:'9'.repeat(64)}],['current',{upload:uploadBase}],['base',{upload:null}],['base',{sha256:'bad'}],['upstream',{status:'missing'}]]){
  const altered=copy(ready);Object.assign(altered.roles[role],change);assert.equal(threewayStatusMatches(binding,altered),false);
 }
 assert.equal(threewayStatusMatches(binding,{...started,counts,coverage}),false);
});
test('upload responses bind exact plan, role and reserved upload capability',()=>{
 const reply={plan,role:'base',upload:uploadBase,status:'awaiting_upload'};
 assert.ok(threewayUploadMatches(plan,'base',reply,uploadBase));
 for(const change of [{plan:'9'.repeat(32)},{role:'upstream'},{role:'current'},{upload:'x'},{upload:uploadUpstream}])assert.equal(threewayUploadMatches(plan,'base',{...reply,...change},uploadBase),false);
});
test('pages reject drifted plan, every archive identity, filter, coverage and pagination',()=>{
 assert.ok(threewayPageMatches(ready,pageReply,0,'changes'));
 for(const change of [{plan:'9'.repeat(32)},{job:'9'.repeat(32)},{base_sha256:'9'.repeat(64)},{current_sha256:'9'.repeat(64)},{upstream_sha256:'9'.repeat(64)},{action:'all'},{counts:{...counts,conflict:2}},{coverage:{...coverage,decoded_bytes:16}},{page:{...page,id:'bad'}},{page:{...page,offset:200}},{page:{...page,limit:201}},{page:{...page,returned:0}},{page:{...page,total:2}},{page:{...page,has_previous:true}},{page:{...page,has_next:true}}])assert.equal(threewayPageMatches(ready,{...pageReply,...change},0,'changes'),false);
 assert.equal(threewayPageMatches(ready,pageReply,1,'changes'),false);
 assert.equal(threewayPageMatches(ready,pageReply,0,'unknown'),false);
});
test('pages validate action from all sides, require explicit null absence and treat hostile paths as text',()=>{
 for(const changed of [{path:''},{path:'x'.repeat(4097)},{action:'take_upstream'},{base:undefined},{base:null,current:null,upstream:null},{current:{raw_sha256:'bad',size_bytes:1}},{current:{raw_sha256:'5'.repeat(64),size_bytes:4194305}},{current:{raw_sha256:'5'.repeat(64),size_bytes:-1}},{current:{raw_sha256:'5'.repeat(64),size_bytes:1.5}}])assert.equal(threewayPageMatches(ready,{...pageReply,rows:[{...row,...changed}]},0,'changes'),false);
 assert.ok(threewayPageMatches(ready,{...pageReply,rows:[{...row,path:'&lt;img src=x onerror=alert(1)&gt;'}]},0,'changes'));
 const two={...ready,counts:{...counts,total:2,files:2,changes:2,conflict:2},coverage:{...coverage,union_paths:2}};
 assert.equal(threewayPageMatches(two,{...pageReply,counts:two.counts,coverage:two.coverage,page:{...page,total:2,returned:2},rows:[row,row]},0,'changes'),false);
});
test('markup offers explicit Current confirmation and separate read-only three-version controls',async()=>{
 const html=await readFile(new URL('../../rentgen_core/gui_assets/index.html',import.meta.url),'utf8');
 const js=await readFile(new URL('../../rentgen_core/gui_assets/threeway.js',import.meta.url),'utf8');
 assert.match(html,/data-view="threeway"/);assert.match(html,/id="threeway-confirm"/);
 for(const role of ['base','upstream'])assert.match(html,new RegExp(`<label for="threeway-${role}-file">`));
 assert.match(html,/<label for="threeway-filter">/);assert.match(html,/id="threeway-list"[^>]*tabindex="0"/);
 assert.ok(!js.includes('innerHTML'));assert.ok(!js.includes('/api/threeway-source'));
 assert.ok(!js.includes('download'));assert.match(js,/side.textContent/);
});

// A minimal owned DOM tests controller ownership only; this is not browser execution.
class Element {
 constructor(tag='div'){this.tag=tag;this.children=[];this.listeners={};this.value='changes';this.files=[];this.hidden=false;this.disabled=false;this.textContent='';}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this.children=[];this.textContent='';this.append(...nodes);}
 addEventListener(event,fn){this.listeners[event]=fn;}
 focus(){document.activeElement=this;}
}
async function until(check){for(let i=0;i<150;i++){if(check())return;await new Promise(resolve=>setTimeout(resolve,5));}assert.ok(check(),'controller did not settle');}
const tick=()=>new Promise(resolve=>setTimeout(resolve,10));
function controller(api){
 const nodes=new Map();let current={...binding};
 globalThis.document={getElementById:id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},createElement:tag=>new Element(tag)};
 const ui=createThreeway({api,errorText:error=>error.code,getBinding:()=>current});
 const click=id=>nodes.get(id).listeners.click();
 const upload=role=>{const input=nodes.get(`threeway-${role}-file`);input.files=[{name:role+'.zip',size:100}];input.listeners.change();};
 return {ui,nodes,click,upload,replaceBinding:value=>{current=value;}};
}
function backend(overrides={}){
 let status=copy(started),currentUpload=null;const calls=[];
 const api=async(path,options={})=>{
  calls.push({path,options});
  const url=new URL(path,'http://127.0.0.1'),body=options.body&&typeof options.body==='string'?JSON.parse(options.body):null;
  if(overrides[url.pathname])return overrides[url.pathname]({path,options,body,status,calls,setStatus:value=>{status=value;}});
  if(url.pathname==='/api/threeway-start')return copy(status);
  if(url.pathname==='/api/threeway-current')return copy(status);
  if(url.pathname==='/api/threeway-upload-start'){
   currentUpload=body.role;const upload=body.role==='base'?uploadBase:uploadUpstream;
   status.roles[body.role]={...roles[body.role],sha256:null,status:'awaiting_upload'};
   return {plan,role:body.role,upload,status:'awaiting_upload'};
  }
  if(url.pathname==='/api/threeway-upload'){
   status.roles[currentUpload]=copy(roles[currentUpload]);
   if(['base','upstream'].every(role=>status.roles[role].status==='ready'))status=copy(ready);
   return {plan,role:currentUpload,upload:currentUpload==='base'?uploadBase:uploadUpstream};
  }
  if(url.pathname==='/api/threeway')return copy(status);
  if(url.pathname==='/api/threeway-page')return {...copy(pageReply),action:url.searchParams.get('action')};
  if(url.pathname==='/api/threeway-cancel'){status={...copy(started),status:'cancelled'};return {plan,status:'cancelled'};}
  throw new Error(path);
 };
 return {api,calls,setStatus:value=>{status=value;}};
}
async function openReady(mock=backend()){
 const view=controller(mock.api);view.ui.enter();view.click('threeway-confirm');await until(()=>!view.ui.busy);
 view.upload('base');await until(()=>!view.ui.busy);
 view.upload('upstream');await until(()=>view.nodes.get('threeway-list').children.length===1&&!view.ui.busy);
 return {...view,mock};
}
test('enter never assigns Current implicitly; explicit confirmation enables role uploads',async()=>{
 const mock=backend(),view=controller(mock.api);view.ui.enter();
 assert.equal(mock.calls.length,0);assert.equal(view.nodes.get('threeway-base-file').disabled,true);
 view.click('threeway-confirm');await until(()=>!view.ui.busy);
 assert.equal(view.nodes.get('threeway-base-file').disabled,false);assert.equal(mock.calls.filter(c=>c.path==='/api/threeway-start').length,1);
 assert.equal(view.nodes.get('threeway-result').hidden,true);view.ui.leave();await tick();
});
test('full controller shows all identities/counts and plain-text side inventory, with no source requests',async()=>{
 const view=await openReady();
 for(const role of ['base','current','upstream'])assert.ok(view.nodes.get('threeway-'+role).textContent.includes(roles[role].sha256));
 assert.ok(view.nodes.get('threeway-counts').textContent.includes('Разные отличия Current и Upstream: 1'));
 assert.equal(view.nodes.get('threeway-range').textContent,'Пути 1–1 из 1');
 assert.equal(view.nodes.get('threeway-list').children[0].children.length,4);
 assert.ok(!view.mock.calls.some(c=>c.path.includes('source')));view.ui.leave();await tick();
});
test('replacement immediately clears all old rows/counts and rejects status for the former upload',async()=>{
 const view=await openReady();let release;
 view.mock.setStatus(copy(ready));
 // Replace the API is impossible by design; use a second controller with a held start.
 view.ui.leave();await tick();
 const mock=backend({'/api/threeway-upload-start':({body,status})=>{
  if(status.status==='ready')return new Promise(resolve=>{release=()=>resolve({plan,role:body.role,upload:'9'.repeat(32),status:'awaiting_upload'});});
  status.roles[body.role]={...roles[body.role],sha256:null,status:'awaiting_upload'};return {plan,role:body.role,upload:body.role==='base'?uploadBase:uploadUpstream,status:'awaiting_upload'};
 },'/api/threeway-upload':({status})=>{
  const role=status.roles.base.status!=='ready'?'base':'upstream';status.roles[role]=copy(roles[role]);
  if(status.roles.base.status==='ready'&&status.roles.upstream.status==='ready')Object.assign(status,copy(ready));
  return {plan,role,upload:role==='base'?uploadBase:uploadUpstream};
 }});
 const held=await openReady(mock);held.upload('base');await until(()=>!!release);
 assert.equal(held.nodes.get('threeway-list').children.length,0);assert.equal(held.nodes.get('threeway-counts').textContent,'');assert.equal(held.nodes.get('threeway-result').hidden,true);
 release();await until(()=>held.nodes.get('threeway-message').textContent.includes('не подтверждён'));
 assert.equal(held.nodes.get('threeway-list').children.length,0);held.ui.leave();await tick();
});
test('only one role may upload while another reservation or bytes are in flight',async()=>{
 let release;const mock=backend({'/api/threeway-upload-start':({body})=>new Promise(resolve=>{release=()=>resolve({plan,role:body.role,upload:uploadBase,status:'awaiting_upload'});} )});
 const view=controller(mock.api);view.ui.enter();view.click('threeway-confirm');await until(()=>!view.ui.busy);view.upload('base');await until(()=>!!release);
 assert.equal(view.nodes.get('threeway-upstream-file').disabled,true);view.upload('upstream');
 assert.equal(mock.calls.filter(c=>c.path==='/api/threeway-upload-start').length,1);view.ui.leave();release();await tick();
 assert.equal(mock.calls.filter(c=>c.options.method==='PUT').length,0);
});
test('navigation and a changed primary binding discard late pages',async()=>{
 for(const changedBinding of [false,true]){
  let release;const mock=backend({'/api/threeway-page':()=>new Promise(resolve=>{release=()=>resolve(copy(pageReply));})});
  const view=controller(mock.api);view.ui.enter();view.click('threeway-confirm');await until(()=>!view.ui.busy);view.upload('base');await until(()=>!view.ui.busy);view.upload('upstream');await until(()=>!!release);
  if(changedBinding)view.replaceBinding({...binding,job:'9'.repeat(32)});
  view.ui.leave();release();await tick();assert.equal(view.nodes.get('threeway-list').children.length,0);assert.equal(view.nodes.get('threeway-result').hidden,true);
 }
});
test('cancel clears a ready result and permits a fresh explicit Current confirmation',async()=>{
 const view=await openReady();view.click('threeway-cancel');assert.equal(view.nodes.get('threeway-list').children.length,0);
 await until(()=>!view.ui.busy);assert.equal(view.nodes.get('threeway-confirm').disabled,false);assert.equal(view.nodes.get('threeway-base-file').disabled,true);assert.equal(view.nodes.get('threeway-result').hidden,true);
 assert.equal(view.mock.calls.filter(c=>c.path==='/api/threeway-cancel').length,1);view.ui.leave();await tick();
});
test('a late upload after cancellation cannot restore the cancelled rows',async()=>{
 let release;const mock=backend({'/api/threeway-upload':()=>new Promise(resolve=>{release=()=>resolve({plan,role:'base',upload:uploadBase});})});
 const view=controller(mock.api);view.ui.enter();view.click('threeway-confirm');await until(()=>!view.ui.busy);view.upload('base');await until(()=>!!release);
 view.click('threeway-cancel');await until(()=>!view.ui.busy);release();await tick();assert.equal(view.nodes.get('threeway-list').children.length,0);assert.equal(view.nodes.get('threeway-confirm').disabled,false);view.ui.leave();
});
test('lost Current-start response uses exact read-only recovery without replaying start',async()=>{
 const mock=backend({'/api/threeway-start':()=>{throw {code:'CONNECTION_LOST'};}}),view=controller(mock.api);
 view.ui.enter();view.click('threeway-confirm');await until(()=>!view.ui.busy);
 assert.equal(mock.calls.filter(c=>c.path==='/api/threeway-start').length,1);
 assert.ok(mock.calls.some(c=>c.path==='/api/threeway-current?'+new URLSearchParams({job:binding.job,input_sha256:binding.input_sha256})));
 assert.equal(view.nodes.get('threeway-base-file').disabled,false);view.ui.leave();await tick();
});
test('late Current start is cancelled and serialized before the next explicit start',async()=>{
 let releaseStart,releaseCancel,starts=0;
 const mock=backend({'/api/threeway-start':()=>{starts++;return starts===1?new Promise(resolve=>{releaseStart=()=>resolve(copy(started));}):copy(started);},'/api/threeway-cancel':()=>new Promise(resolve=>{releaseCancel=()=>resolve({plan,status:'cancelled'});})});
 const view=controller(mock.api);view.ui.enter();view.click('threeway-confirm');await until(()=>!!releaseStart);view.ui.leave();view.ui.enter();view.click('threeway-confirm');
 releaseStart();await until(()=>!!releaseCancel);assert.equal(starts,1);releaseCancel();await until(()=>starts===2&&!view.ui.busy);assert.equal(view.nodes.get('threeway-base-file').disabled,false);
 view.ui.leave();await tick();releaseCancel();await tick();
});
test('lost PUT response is read back once accepted and never retransmitted',async()=>{
 let puts=0;const mock=backend({'/api/threeway-upload':({status})=>{puts++;status.roles.base=copy(roles.base);throw {code:'CONNECTION_LOST'};}});
 const view=controller(mock.api);view.ui.enter();view.click('threeway-confirm');await until(()=>!view.ui.busy);view.upload('base');await until(()=>!view.ui.busy);
 assert.equal(puts,1);assert.ok(view.nodes.get('threeway-base').textContent.includes(roles.base.sha256));assert.equal(view.nodes.get('threeway-upstream-file').disabled,false);view.ui.leave();await tick();
});
test('uncertain upload-start keeps old inventory hidden and prevents automatic byte replay',async()=>{
 const mock=backend({'/api/threeway-upload-start':({body,status})=>{status.roles[body.role]={...roles[body.role],sha256:null,status:'awaiting_upload'};throw {code:'CONNECTION_LOST'};}});
 const view=controller(mock.api);view.ui.enter();view.click('threeway-confirm');await until(()=>!view.ui.busy);view.upload('base');
 await until(()=>view.nodes.get('threeway-message').textContent.includes('не подтверждён'));
 assert.equal(mock.calls.filter(c=>c.options.method==='PUT').length,0);assert.equal(view.nodes.get('threeway-upstream-file').disabled,true);assert.equal(view.nodes.get('threeway-list').children.length,0);
 view.click('threeway-check');await until(()=>view.nodes.get('threeway-message').textContent.includes('не завершено'));assert.equal(view.nodes.get('threeway-upstream-file').disabled,true);view.ui.leave();await tick();
});
test('forged status with another accepted role digest cannot restore a result',async()=>{
 const view=await openReady();const altered=copy(ready);altered.roles.base.sha256='9'.repeat(64);view.mock.setStatus(altered);view.click('threeway-check');
 await until(()=>view.nodes.get('threeway-message').textContent.includes('PROTOCOL_ERROR'));assert.equal(view.nodes.get('threeway-list').children.length,0);view.ui.leave();await tick();
});

test('lost cancellation acknowledgement is read back without repeating the cancellation write',async()=>{
 const mock=backend({'/api/threeway-cancel':({setStatus})=>{setStatus({...copy(started),status:'cancelled'});throw {code:'CONNECTION_LOST'};}});
 const view=await openReady(mock);view.click('threeway-cancel');view.click('threeway-cancel');await until(()=>!view.ui.busy);
 assert.equal(mock.calls.filter(c=>c.path==='/api/threeway-cancel').length,1);assert.equal(view.nodes.get('threeway-confirm').disabled,false);assert.equal(view.nodes.get('threeway-list').children.length,0);view.ui.leave();await tick();
});
