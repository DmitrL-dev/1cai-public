import test from 'node:test';
import assert from 'node:assert/strict';
import {fetchReport,reportFilename,REPORT_LIMITS,deliverReport,releaseReportURL} from '../../rentgen_core/gui_assets/report-download.js';
const pair={pair:'a'.repeat(32),before_sha256:'b'.repeat(64),after_sha256:'c'.repeat(64)};
const raw=new TextEncoder().encode('{"safe":"данные"}');
function reply({format='json',headers={},body=raw,status=200}={}){
 return new Response(body,{status,headers:{'Content-Type':format==='json'?'application/json; charset=utf-8':'text/html; charset=utf-8','Content-Length':String(raw.length),'Content-Disposition':`attachment; filename="${reportFilename(pair,format)}"`,'X-Rentgen-Pair':pair.pair,'X-Rentgen-Before-SHA256':pair.before_sha256,'X-Rentgen-After-SHA256':pair.after_sha256,'X-Rentgen-Report-SHA256':'d'.repeat(64),...headers}});
}
test('download uses exact current pair and session header, returns complete bounded bytes and adjacent receipt',async()=>{
 let calls=0;
 const result=await fetchReport(pair,'json',{token:'owned-test-session',fetcher:async(path,options)=>{
  calls++;assert.equal(path,'/api/comparison-report');assert.equal(options.credentials,'omit');assert.equal(options.headers['X-Rentgen-Session'],'owned-test-session');
  assert.deepEqual(JSON.parse(options.body),{...pair,format:'json'});return reply();
 }});
 assert.equal(calls,1);assert.equal(await result.blob.text(),new TextDecoder().decode(raw));assert.equal(result.size,raw.length);assert.equal(result.sha256,'d'.repeat(64));assert.equal(result.filename,reportFilename(pair,'json'));
});
test('download rejects stale pair, missing hash, wrong MIME, unsafe filename and over-limit length',async()=>{
 for(const headers of [{'X-Rentgen-Pair':'e'.repeat(32)},{'X-Rentgen-Before-SHA256':'e'.repeat(64)},{'X-Rentgen-After-SHA256':'e'.repeat(64)},{'X-Rentgen-Report-SHA256':'missing'},{'Content-Type':'text/html'},{'Content-Disposition':'attachment; filename="../../unsafe"'},{'Content-Length':String(REPORT_LIMITS.json+1)},{'Content-Length':'0'},{'Content-Length':'12junk'}]){
  await assert.rejects(fetchReport(pair,'json',{fetcher:async()=>reply({headers})}),error=>error.code==='PROTOCOL_ERROR');
 }
});
test('download never returns a truncated or oversized stream as a successful report',async()=>{
 for(const body of [raw.slice(1),new Uint8Array(raw.length+1)])await assert.rejects(fetchReport(pair,'json',{fetcher:async()=>reply({body})}),error=>error.code==='PROTOCOL_ERROR');
});
test('tiny stream chunks use bounded exact-size storage and preserve complete content',async()=>{
 let i=0;const body=new ReadableStream({pull(controller){if(i===raw.length)controller.close();else controller.enqueue(raw.slice(i,i+=1));}});
 const result=await fetchReport(pair,'json',{fetcher:async()=>reply({body})});assert.equal(await result.blob.text(),new TextDecoder().decode(raw));
});
test('forbidden and aborted downloads are not automatically retried',async()=>{
 let calls=0;
 await assert.rejects(fetchReport(pair,'json',{fetcher:async()=>{calls++;return new Response('{"error":"FORBIDDEN"}',{status:403});}}),error=>error.code==='FORBIDDEN');assert.equal(calls,1);
 const controller=new AbortController();controller.abort();
 await assert.rejects(fetchReport(pair,'json',{signal:controller.signal,fetcher:async()=>{calls++;throw Error('aborted');}}),error=>error.code==='CANCELLED');assert.equal(calls,2);
});
test('unknown report formats fail before any request',async()=>{
 for(const format of ['xml','toString','__proto__',null,{},[]])await assert.rejects(fetchReport(pair,format,{fetcher:async()=>assert.fail('no request expected')}),error=>error.code==='INVALID_REQUEST');
});


test('completed download retains only one temporary Blob URL and uses a download-only anchor',()=>{
 const previousDocument=globalThis.document,create=URL.createObjectURL,revoke=URL.revokeObjectURL;
 const created=[],revoked=[],clicked=[];
 URL.createObjectURL=blob=>{assert.ok(blob instanceof Blob);const url=`blob:owned-${created.length}`;created.push(url);return url;};
 URL.revokeObjectURL=url=>revoked.push(url);
 globalThis.document={body:{append(){}},createElement:tag=>{assert.equal(tag,'a');return {click(){clicked.push({href:this.href,download:this.download,hidden:this.hidden});},remove(){}};}};
 try{
  deliverReport({blob:new Blob(['one']),filename:'one.json'});deliverReport({blob:new Blob(['two']),filename:'two.html'});
  assert.deepEqual(revoked,['blob:owned-0']);assert.deepEqual(clicked,[{href:'blob:owned-0',download:'one.json',hidden:true},{href:'blob:owned-1',download:'two.html',hidden:true}]);
  releaseReportURL();assert.deepEqual(revoked,created);
 }finally{releaseReportURL();globalThis.document=previousDocument;URL.createObjectURL=create;URL.revokeObjectURL=revoke;}
});


test('stream DOM errors expose a stable connection error rather than numeric browser codes',async()=>{
 const body=new ReadableStream({pull(){throw new DOMException('network failed','NetworkError');}});
 await assert.rejects(fetchReport(pair,'json',{fetcher:async()=>reply({body})}),error=>error.code==='CONNECTION_LOST');
});
