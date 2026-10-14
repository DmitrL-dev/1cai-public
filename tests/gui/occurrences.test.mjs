import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {indexSource,occurrenceConventions,occurrenceReplyMatches,occurrenceResultMatches,createOccurrenceController} from '../../rentgen_core/gui_assets/occurrences.js';

const query='аа',text='Я😀ааа\r\nБ\rВ\nГ';
const bindingFor=source=>({job:'a'.repeat(32),input_sha256:'b'.repeat(64),path:'CommonModules/Код.bsl',raw_sha256:'c'.repeat(64),size_bytes:new TextEncoder().encode(source).length});
const binding=bindingFor(text),id='d'.repeat(32);
const echo=(b,q,offset=0,occurrence=id)=>({job:b.job,input_sha256:b.input_sha256,path:b.path,raw_sha256:b.raw_sha256,query:q,offset,occurrence});
function resultFor(source,q,offset=0,b=bindingFor(source)){
  const index=indexSource(source),length=[...q].length,all=[];
  for(let at=0;at+length<=index.characters.length;at++)if(index.characters.slice(at,at+length).join('')===q){
    const position=index.positions[at],lineStart=at-position.column+1,start=Math.max(lineStart,at-128);
    const window=index.characters.slice(start,start+512),newline=window.findIndex(char=>char==='\r'||char==='\n');
    const end=start+(newline<0?window.length:newline);
    all.push({offset:at,line:position.line,column:position.column,excerpt:index.characters.slice(start,end).join(''),truncated_before:start>lineStart,truncated_after:end<index.characters.length&&!['\r','\n'].includes(index.characters[end])});
  }
  const occurrences=all.slice(offset,offset+200);
  return {input_ref:{relative_path:b.path,raw_sha256:b.raw_sha256,input_sha256:b.input_sha256},size_bytes:b.size_bytes,query:q,analysis:'literal_occurrences',conventions:{...occurrenceConventions},occurrences,coverage:{complete:true,characters_scanned:index.characters.length},page:{offset,limit:200,total:all.length,returned:occurrences.length,has_previous:offset>0,has_next:offset+occurrences.length<all.length}};
}
const result=resultFor(text,query);
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};

test('occurrence coordinates keep Unicode columns and CRLF, CR, LF distinct from UTF-16 DOM offsets',()=>{
  const index=indexSource(text);
  assert.deepEqual(index.positions[2],{utf16:3,line:1,column:3});
  assert.deepEqual(index.positions[3],{utf16:4,line:1,column:4});
  assert.deepEqual(index.positions[7],{utf16:8,line:2,column:1});
  assert.deepEqual(index.positions[9],{utf16:10,line:3,column:1});
  assert.deepEqual(index.positions[11],{utf16:12,line:4,column:1});
  assert.deepEqual(result.occurrences.map(({offset,line,column})=>({offset,line,column})),[{offset:2,line:1,column:3},{offset:3,line:1,column:4}]);
  assert.equal(result.occurrences[0].excerpt,'Я😀ааа');assert.equal(result.occurrences[0].truncated_before,false);assert.equal(result.occurrences[0].truncated_after,false);
  assert.ok(occurrenceResultMatches(binding,query,0,result,index));
});

test('occurrence start and status echoes bind job, archive, exact module bytes, literal query and page',()=>{
  assert.ok(occurrenceReplyMatches(binding,query,0,echo(binding,query)));
  for(const change of [{job:'x'},{input_sha256:'0'.repeat(64)},{path:'Other.bsl'},{raw_sha256:'0'.repeat(64)},{query:'АА'},{offset:200},{occurrence:'bad'}])assert.equal(occurrenceReplyMatches(binding,query,0,{...echo(binding,query),...change}),false);
  assert.equal(occurrenceReplyMatches(binding,query,0,echo(binding,query),'e'.repeat(32)),false);
});

test('occurrence pages reject altered source references, semantics, partial coverage and counts',()=>{
  const index=indexSource(text);
  for(const change of [{input_ref:{...result.input_ref,relative_path:'other'}},{input_ref:{...result.input_ref,raw_sha256:'0'.repeat(64)}},{input_ref:{...result.input_ref,input_sha256:'0'.repeat(64)}},{query:'АА'},{analysis:'semantic'},{size_bytes:1},{coverage:{complete:false,characters_scanned:index.characters.length}},{coverage:{complete:true,characters_scanned:1}},{occurrences:[]},{page:{...result.page,total:3}},{page:{...result.page,limit:201}},{page:{...result.page,offset:200}},{page:{...result.page,has_next:true}}])assert.equal(occurrenceResultMatches(binding,query,0,{...result,...change},index),false,JSON.stringify(change));
  for(const key of Object.keys(occurrenceConventions))assert.equal(occurrenceResultMatches(binding,query,0,{...result,conventions:{...occurrenceConventions,[key]:'wrong'}},index),false,key);
});

test('every displayed occurrence is checked against verified source coordinates and bounded literal excerpt',()=>{
  const index=indexSource(text),first=result.occurrences[0];
  for(const change of [{offset:-1},{offset:3.5},{offset:1},{line:2},{column:4},{excerpt:'missing literal'},{excerpt:'FORGED '+query},{excerpt:'а'.repeat(513)},{truncated_before:0},{truncated_after:null},{truncated_before:true},{truncated_after:true}])assert.equal(occurrenceResultMatches(binding,query,0,{...result,occurrences:[{...first,...change},result.occurrences[1]]},index),false,JSON.stringify(change));
  assert.equal(occurrenceResultMatches(binding,query,0,{...result,occurrences:[first,first]},index),false);
  assert.equal(occurrenceResultMatches(binding,'',0,result,index),false);
});

test('overlapping occurrence pages retain the exact total beyond two hundred hits and accept complete zero results',()=>{
  const source='а'.repeat(402),b=bindingFor(source),index=indexSource(source);
  for(const offset of [0,200,400]){
    const page=resultFor(source,query,offset,b);assert.ok(occurrenceResultMatches(b,query,offset,page,index));assert.equal(page.page.total,401);
  }
  assert.equal(resultFor(source,query,400,b).occurrences[0].offset,400);
  assert.ok(occurrenceResultMatches(binding,'absent',0,resultFor(text,'absent'),indexSource(text)));
  assert.equal(occurrenceResultMatches(binding,'absent',200,resultFor(text,'absent',200),indexSource(text)),false);
});

test('controller sends only occurrence-specific bound requests and accepts verified completion',async()=>{
  const calls=[];
  const api=async(path,options)=>{calls.push([path,options?.body&&JSON.parse(options.body)]);return path.endsWith('-start')?echo(binding,query):{...echo(binding,query),status:'ready',result};};
  const controller=createOccurrenceController({api,binding,text});await controller.search(query);
  assert.deepEqual(calls[0],['/api/occurrences-start',{job:binding.job,input_sha256:binding.input_sha256,path:binding.path,raw_sha256:binding.raw_sha256,query,offset:0}]);
  assert.ok(calls[1][0].startsWith('/api/occurrences?'));assert.equal(calls.length,2);
  assert.equal(controller.state.result,result);assert.equal(controller.state.busy,false);
});

test('controller refuses invalid query and inconsistent decoded source size before network IO',async()=>{
  let requests=0;const api=async()=>{requests++;};
  const controller=createOccurrenceController({api,binding,text});
  for(const value of ['', '\n', 'я'.repeat(129), '\ud800']){await controller.search(value);assert.equal(controller.state.error,'INVALID_OCCURRENCE_QUERY');}
  assert.equal(requests,0);
  assert.throws(()=>createOccurrenceController({api,binding:{...binding,size_bytes:1},text}),error=>error.code==='PROTOCOL_ERROR');
  assert.doesNotThrow(()=>createOccurrenceController({api,binding:{...binding,size_bytes:binding.size_bytes+3},text}),'excluded UTF-8 BOM accounts for three raw bytes');
});

test('lost occurrence start reply uses nullable server cancellation recovery without replaying the start',async()=>{
  const calls=[];
  const api=async(path,options)=>{calls.push([path,JSON.parse(options.body)]);if(path.endsWith('-start'))throw {code:'CONNECTION_LOST'};return {status:'cancelled',cancel_requested:false};};
  const controller=createOccurrenceController({api,binding,text});await controller.search(query);
  assert.equal(controller.state.error,'CONNECTION_LOST');assert.equal(controller.state.result,null);
  assert.deepEqual(calls.map(([path])=>path),['/api/occurrences-start','/api/occurrences-cancel']);
  assert.deepEqual(calls[1][1],{job:binding.job,input_sha256:binding.input_sha256,occurrence:null});
});

test('malformed ready pages are never displayed and cancel the exact known occurrence',async()=>{
  const cancelled=[];
  const api=async(path,options)=>{if(path.endsWith('-start'))return echo(binding,query);if(path.endsWith('-cancel')){cancelled.push(JSON.parse(options.body));return {status:'ready'};}return {...echo(binding,query),status:'ready',result:{...result,coverage:{complete:false,characters_scanned:12}}};};
  const controller=createOccurrenceController({api,binding,text});await controller.search(query);
  assert.equal(controller.state.error,'PROTOCOL_ERROR');assert.equal(controller.state.result,null);assert.equal(cancelled[0].occurrence,id);
});

test('explicit cancel aborts an in-flight poll, requests real cancellation and suppresses late completion',async()=>{
  const reached=deferred(),cancelled=[];let aborted=false;
  const api=async(path,options)=>{
    if(path.endsWith('-start'))return echo(binding,query);
    if(path.endsWith('-cancel')){cancelled.push(JSON.parse(options.body));return {status:'cancelled',cancel_requested:true};}
    reached.resolve();return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>{aborted=true;reject({code:'CONNECTION_LOST'});},{once:true}));
  };
  const controller=createOccurrenceController({api,binding,text});const pending=controller.search(query);await reached.promise;await controller.cancel();await pending;
  assert.ok(aborted);assert.equal(cancelled.length,1);assert.equal(cancelled[0].occurrence,id);
  assert.equal(controller.state.result,null);assert.equal(controller.state.error,null);assert.equal(controller.state.busy,false);assert.equal(controller.state.message,'Поиск в модуле отменён.');
});

test('query editing and newer search serialize behind exact cancellation and ignore stale ready rows',async()=>{
  const held=deferred(),reached=deferred(),records=new Map(),events=[],visible=[];let count=0;
  const source='aaa bbb aaa',b=bindingFor(source);
  const api=async(path,options)=>{
    if(path.endsWith('-start')){const body=JSON.parse(options.body),record=echo(b,body.query,body.offset,String(++count).repeat(32));records.set(record.occurrence,record);events.push('start:'+body.query);return record;}
    if(path.endsWith('-cancel')){events.push('cancel:'+JSON.parse(options.body).occurrence);return {status:'ready'};}
    const record=records.get(new URLSearchParams(path.split('?')[1]).get('occurrence'));
    if(record.query==='aaa'){reached.resolve();await held.promise;}
    return {...record,status:'ready',result:resultFor(source,record.query,record.offset,b)};
  };
  const controller=createOccurrenceController({api,binding:b,text:source,onChange:state=>{if(state.result)visible.push(state.result.query);}});
  const first=controller.search('aaa');await reached.promise;controller.edit('bbb');const second=controller.search('bbb');held.resolve();await Promise.all([first,second]);
  assert.deepEqual(visible,['bbb']);assert.deepEqual(events,['start:aaa','cancel:'+'1'.repeat(32),'start:bbb']);
});

test('leaving during a pending start waits for its identity then cancels without presenting any reply',async()=>{
  const held=deferred(),reached=deferred(),cancelled=[],visible=[];
  const api=async(path,options)=>{if(path.endsWith('-start')){reached.resolve();await held.promise;return echo(binding,query);}if(path.endsWith('-cancel')){cancelled.push(JSON.parse(options.body));return {status:'cancelled'};}throw Error('Detached controller must not poll');};
  const controller=createOccurrenceController({api,binding,text,onChange:state=>visible.push(state.result)});
  const pending=controller.search(query);await reached.promise;const before=visible.length,leaving=controller.leave();held.resolve();await Promise.all([pending,leaving]);
  assert.equal(visible.length,before);assert.equal(cancelled.length,1);assert.equal(cancelled[0].occurrence,id);
});

test('new source generation suppresses ready replies even before explicit view teardown',async()=>{
  let current=true;const cancelled=[];
  const api=async(path,options)=>{if(path.endsWith('-start'))return echo(binding,query);if(path.endsWith('-cancel')){cancelled.push(JSON.parse(options.body));return {status:'ready'};}current=false;return {...echo(binding,query),status:'ready',result};};
  const controller=createOccurrenceController({api,binding,text,isCurrent:()=>current});await controller.search(query);
  assert.equal(controller.state.result,null);assert.equal(cancelled[0].occurrence,id);
});

test('leaving drops the bounded source index and rendered rows before a held late poll or reap finishes',async()=>{
  const held=deferred(),reached=deferred(),cancelled=[];
  const api=async(path,options)=>{if(path.endsWith('-start'))return echo(binding,query);if(path.endsWith('-cancel')){cancelled.push(JSON.parse(options.body));return {status:'ready'};}reached.resolve();await held.promise;return {...echo(binding,query),status:'ready',result};};
  const controller=createOccurrenceController({api,binding,text});
  const pending=controller.search(query);await reached.promise;
  assert.ok(controller.index.positions.length>0);
  const leaving=controller.leave();
  assert.equal(controller.index.text,'');assert.deepEqual(controller.index.characters,[]);assert.deepEqual(controller.index.positions,[]);assert.equal(controller.state.result,null);
  held.resolve();await Promise.all([pending,leaving]);
  assert.equal(controller.state.result,null);assert.equal(cancelled[0].occurrence,id);
});

test('app mounts occurrences only after verified source and invalidates on source/search/import generation changes',async()=>{
  const app=await readFile(new URL('../../rentgen_core/gui_assets/app.js',import.meta.url),'utf8');
  assert.match(app,/import \{mountOccurrences\} from '\.\/occurrences.js'/);
  assert.match(app,/function renderDetails\(row\)\{leaveOccurrences\(\);state.sourceGeneration\+\+/);
  assert.match(app,/function invalidateMetadataSearch\(\)\{\s*leaveOccurrences\(\)/);
  assert.match(app,/await occurrenceBarrier/);
  assert.match(app,/initialQuery:sourceMode\(\)\?state.metadataQuery:''/);
  assert.match(app,/generation===state.sourceGeneration&&state.view==='modules'&&state.tab==='source'/);
});
