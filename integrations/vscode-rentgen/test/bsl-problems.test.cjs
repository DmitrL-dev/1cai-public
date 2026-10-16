'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createHash}=require('node:crypto');
const path=require('node:path'),{readFileSync,readdirSync}=require('node:fs');
const {createBslProblems}=require('../lib/bsl-problems.cjs');
const {PROFILE}=require('../lib/bsl-result.cjs');
const sha=text=>createHash('sha256').update(Buffer.from(text,'utf8')).digest('hex');
const clone=value=>structuredClone(value);
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};

// Models the documented TextDocument UTF-16 offsets without clamping. Production
// uses the actual editor's positionAt/offsetAt and validates the round trip.
function textDocument(uri,text){
 const offsets=[0];for(let i=0;i<text.length;i++)if(text[i]==='\n')offsets.push(i+1);
 return {uri,getText:()=>text,
  positionAt(offset){assert.ok(Number.isInteger(offset)&&offset>=0&&offset<=text.length);let line=0;
   while(line+1<offsets.length&&offsets[line+1]<=offset)line++;return {line,character:offset-offsets[line]};},
  offsetAt(position){return offsets[position.line]+position.character;}};
}

// Explicit API unit doubles. Native editor-host acceptance is a separate gate.
function fixture(text='Процедура Тест()\r\nКонецПроцедуры\n'){
 const project='00000000-0000-4000-8000-000000000001';
 const receipt={project_id:project,draft_id:'00000000-0000-4000-8000-000000000002',revision:3,
  title:'Проверенная версия',proposal_content_id:'b'.repeat(64),
  source_ref:{snapshot:{project_id:project,snapshot_id:'a'.repeat(64),manifest_hash:'a'.repeat(64)},
   layer_id:'base',relative_path:'CommonModules/Test/Module.bsl',raw_sha256:'d'.repeat(64)}};
 const analysis={candidate_sha256:sha(text),candidate_size_bytes:Buffer.byteLength(text,'utf8'),profile_id:PROFILE,
  config_sha256:'e56b86d4187a301a6e17e7e46906d4e7fcf6e84166d648684b6d5f1bd540af72',
  runtime_manifest_sha256:'2835e1a268e67be020e99ecd8d2a64c7b390e3752ed99c89d71a5340eb792ca5',
  status:'completed',reason:null,scope:'single_module_isolated',runtime_verified:true,coverage:'exact_one',
  diagnostics:[],diagnostics_complete:true,total_diagnostics:0,exit_code:0,
  report_sha256:'e'.repeat(64),stdout_sha256:'f'.repeat(64),stderr_sha256:sha('')};
 const result={run_id:'00000000-0000-4000-8000-000000000003',status:'completed',evidence:'local_unattested',receipt,
  report:{diagnostic:{source_ref:clone(receipt.source_ref),proposal_content_id:receipt.proposal_content_id,
   diagnostics_status:'clean',tests_status:'not_run',apply_status:'unavailable',evidence:'ephemeral_unattested',analysis},
  tests:{status:'not_run'},apply:{status:'unavailable'}}};
 const uri={scheme:'rentgen-view',authority:'minted-version-3',path:'/v3 Module.bsl',query:'',fragment:''};
 const draft={uri,text,receipt:clone(receipt),rawSha256:sha(text),sizeBytes:Buffer.byteLength(text,'utf8')};
 const events=[],published=new Map();let disposed=0,reads=0;
 const collection={set:(key,rows)=>{events.push({type:'set',uri:key,rows});published.set(key,rows);},
  clear:()=>{events.push({type:'clear'});published.clear();},dispose:()=>{events.push({type:'dispose'});disposed++;}};
 const vscode={workspace:{isTrusted:true,openTextDocument:async selected=>{
  assert.equal(selected,uri);return textDocument(uri,text.startsWith('\ufeff')?text.slice(1):text);
 }},DiagnosticSeverity:{Error:0,Warning:1,Information:2,Hint:3},
  languages:{createDiagnosticCollection:name=>{events.push({type:'create',name});return collection;},
   registerCodeActionsProvider:()=>{events.push({type:'code-actions'});return {dispose(){}};}},
  Range:class {constructor(startLine,startCharacter,endLine,endCharacter){this.start={line:startLine,character:startCharacter};this.end={line:endLine,character:endCharacter};}},
  Diagnostic:class {constructor(range,message,severity){this.range=range;this.message=message;this.severity=severity;}}};
 const options={readDraft:async saved=>{reads++;assert.deepEqual(saved,receipt);return draft;}};
 const problems=createBslProblems(vscode,options);
 const add=(row={})=>{
  analysis.diagnostics.push({code:'UnusedVariable',severity:'Warning',message:'Не используется',
   start:{line:0,character:0},end:{line:0,character:9},...row});
  analysis.total_diagnostics=analysis.diagnostics.length;result.report.diagnostic.diagnostics_status='diagnostics_present';
 };
 return {text,receipt,analysis,result,draft,uri,events,published,vscode,problems,options,add,
  reads:()=>reads,disposed:()=>disposed};
}

test('publishes actual Diagnostic instances on the exact immutable draft URI with explicit severity mapping',async()=>{
 const f=fixture();for(const severity of ['Error','Warning','Information','Hint'])f.add({severity});
 const value=await f.problems.present(f.result);
 assert.equal(value.status,'published');assert.equal(value.count,4);assert.deepEqual(value.receipt,f.receipt);
 assert.equal(value.uri,f.uri);assert.equal(f.reads(),1);
 assert.deepEqual(f.events[0],{type:'create',name:'rentgen-bsl'});
 const rows=f.published.get(f.uri);assert.deepEqual(rows.map(row=>row.severity),[0,1,2,3]);
 for(const row of rows){
  assert.ok(row instanceof f.vscode.Diagnostic);assert.ok(row.range instanceof f.vscode.Range);
  assert.equal(row.code,'UnusedVariable');assert.equal(row.source,`Рентген BSL · ${PROFILE}`);assert.equal(row.message,'Не используется');
  assert.deepEqual(row.range.start,{line:0,character:0});assert.deepEqual(row.range.end,{line:0,character:9});
 }
});

test('every Problem names the pinned analyzer profile and offers no quick fix or automatic edit',async()=>{
 const f=fixture();f.add();f.add({code:'LineLength',severity:'Information',message:'Длинная строка'});
 const edits=[];f.vscode.workspace.applyEdit=async edit=>{edits.push(edit);return false;};
 assert.equal((await f.problems.present(f.result)).status,'published');
 const rows=f.published.get(f.uri);assert.equal(rows.length,2);
 assert.equal(PROFILE,'bsl-ls-1.0.5-temurin21.0.12.1-win64-bmp-default-v1');
 for(const row of rows){
  // The profile is the validated report field, not a label chosen by the presenter.
  assert.equal(row.source,`Рентген BSL · ${f.analysis.profile_id}`);
  assert.deepEqual(Object.keys(row).sort(),['code','message','range','severity','source']);
 }
 assert.deepEqual(rows.map(row=>row.code),['UnusedVariable','LineLength']);
 assert.deepEqual(edits,[]);assert.equal(f.events.filter(event=>event.type==='code-actions').length,0);
 // A false positive must stay a report: no Companion module registers code actions.
 const root=path.join(__dirname,'..');
 const sources=['extension.cjs',...readdirSync(path.join(root,'lib')).filter(name=>name.endsWith('.cjs')).map(name=>'lib/'+name)];
 for(const name of sources)assert.doesNotMatch(readFileSync(path.join(root,name),'utf8'),/registerCodeActionsProvider|CodeActionKind|\bapplyEdit\b/,name);
 assert.ok(!Object.hasOwn(JSON.parse(readFileSync(path.join(root,'package.json'),'utf8')).contributes||{},'codeActions'));
});

test('zero diagnostics is clean only for a complete verified report and sets the URI explicitly',async()=>{
 const f=fixture(),value=await f.problems.present(f.result);
 assert.equal(value.status,'clean');assert.equal(value.count,0);assert.deepEqual(f.published.get(f.uri),[]);
 assert.equal(f.events.filter(event=>event.type==='set').length,1);
});

for(const status of ['failed','unsupported','incomplete'])test(`${status} clears previous Problems without presenting a clean check`,async()=>{
 const f=fixture();f.add();await f.problems.present(f.result);assert.equal(f.published.size,1);
 if(status==='incomplete')f.result.status='incomplete';
 else{f.analysis.status=status;f.result.report.diagnostic.diagnostics_status=status;f.analysis.diagnostics=[];}
 const value=await f.problems.present(f.result);
 assert.equal(value.status,status);assert.equal(f.published.size,0);assert.equal(f.reads(),1);
 assert.equal(f.events.filter(event=>event.type==='set').length,1);
});

test('a truncated completed diagnostic report is incomplete and never publishes partial rows',async()=>{
 const f=fixture();f.add();f.analysis.diagnostics_complete=false;f.analysis.total_diagnostics=200;
 assert.equal((await f.problems.present(f.result)).status,'incomplete');
 assert.equal(f.reads(),0);assert.equal(f.published.size,0);
});

const tamperCases={
 'candidate text':f=>{f.draft.text+='x';},
 'reader digest':f=>{f.draft.rawSha256='9'.repeat(64);},
 'reader byte size':f=>{f.draft.sizeBytes++;},
 'analysis digest':f=>{f.analysis.candidate_sha256='9'.repeat(64);},
 'analysis byte size':f=>{f.analysis.candidate_size_bytes++;},
 'receipt revision':f=>{f.draft.receipt.revision++;},
 'receipt content identity':f=>{f.draft.receipt.proposal_content_id='9'.repeat(64);},
 'receipt source snapshot':f=>{f.draft.receipt.source_ref.snapshot.snapshot_id='9'.repeat(64);},
 'receipt source path':f=>{f.draft.receipt.source_ref.relative_path='Other.bsl';},
 'receipt title':f=>{f.draft.receipt.title='Different receipt';},
 'report source binding':f=>{f.result.report.diagnostic.source_ref.raw_sha256='9'.repeat(64);},
 'report content binding':f=>{f.result.report.diagnostic.proposal_content_id='9'.repeat(64);},
 'profile identity':f=>{f.analysis.profile_id='other';},
 'config digest':f=>{f.analysis.config_sha256='9'.repeat(64);},
 'runtime digest':f=>{f.analysis.runtime_manifest_sha256='9'.repeat(64);},
 'runtime verification':f=>{f.analysis.runtime_verified=false;},
 'coverage':f=>{f.analysis.coverage='incomplete';},
 'unverified outer evidence':f=>{f.result.evidence='attested';},
 'unverified diagnostic evidence':f=>{f.result.report.diagnostic.evidence='local_unattested';},
 'missing report hash':f=>{delete f.analysis.report_sha256;},
 'missing stdout hash':f=>{delete f.analysis.stdout_sha256;},
 'invalid stderr hash':f=>{f.analysis.stderr_sha256='not-a-hash';},
 'failure reason in completed':f=>{f.analysis.reason='BSL_FAILED';},
 'nonzero exit':f=>{f.analysis.exit_code=1;},
 'incorrect total':f=>{f.analysis.total_diagnostics++;},
 'false clean status':f=>{f.result.report.diagnostic.diagnostics_status='clean';},
 'filesystem URI':f=>{f.draft.uri={...f.uri,scheme:'file'};},
 'unknown URI token':f=>{f.draft.uri={...f.uri,authority:''};},
 'URI query':f=>{f.draft.uri={...f.uri,query:'mutable=1'};},
 'URI fragment':f=>{f.draft.uri={...f.uri,fragment:'other'};},
 'invalid project identity':f=>{f.result.receipt.project_id='project';},
 'invalid run identity':f=>{f.result.run_id='run';},
 'fractional revision':f=>{f.result.receipt.revision=3.5;},
};
for(const [name,tamper]of Object.entries(tamperCases))test(`rejects ${name} and clears rather than retaining stale Problems`,async()=>{
 const f=fixture();f.add();await f.problems.present(f.result);tamper(f);
 await assert.rejects(f.problems.present(f.result),/BSL_PROBLEMS_MISMATCH/);
 assert.equal(f.published.size,0);assert.equal(f.events.filter(event=>event.type==='set').length,1);
});

const malformedRows={
 'negative line':{start:{line:-1,character:0}},
 'line beyond EOF':{end:{line:3,character:0}},
 'fractional line':{start:{line:0.5,character:0}},
 'boolean line':{start:{line:false,character:0}},
 'negative column':{start:{line:0,character:-1}},
 'fractional column':{start:{line:0,character:0.5}},
 'column beyond line':{end:{line:0,character:100}},
 'reversed range':{start:{line:1,character:0},end:{line:0,character:2}},
 'unknown severity':{severity:'error'},
 'prototype severity':{severity:'toString'},
 'non-string severity':{severity:null},
 'invalid code':{code:'../warning'},
 'oversize UTF-8 message':{message:'я'.repeat(513)},
 'invalid UTF-16 message':{message:'bad\uD800'},
};
for(const [name,row]of Object.entries(malformedRows))test(`refuses ${name} without clamping or publishing other valid rows`,async()=>{
 const f=fixture();f.add();f.add(row);
 await assert.rejects(f.problems.present(f.result),/BSL_PROBLEMS_MISMATCH/);assert.equal(f.published.size,0);
 assert.equal(f.events.some(event=>event.type==='set'),false);
});

test('UTF-8 BOM participates in byte identity while BMP columns, CRLF and final empty line match backend coordinates',async()=>{
 const f=fixture('\ufeffЯ\r\nЁж\n');
 f.add({start:{line:0,character:0},end:{line:0,character:1}});
 f.add({start:{line:1,character:1},end:{line:2,character:0}});
 assert.equal((await f.problems.present(f.result)).status,'published');
 const rows=f.published.get(f.uri);assert.deepEqual(rows[0].range.end,{line:0,character:1});
 assert.deepEqual(rows[1].range.end,{line:2,character:0});
 f.draft.rawSha256=sha(f.text.slice(1));
 await assert.rejects(f.problems.present(f.result),/BSL_PROBLEMS_MISMATCH/);assert.equal(f.published.size,0);
});

for(const text of ['','\ufeff','x\n','x\r\n'])test(`empty last line remains a valid zero-width location for ${JSON.stringify(text)}`,async()=>{
 const f=fixture(text),line=text.includes('\n')?1:0;
 f.add({start:{line,character:0},end:{line,character:0}});
 assert.equal((await f.problems.present(f.result)).status,'published');
});

for(const text of ['a😀b','a\uD800b','a\rb','a\r','a\r\r\nb'])test(`unsupported coordinate text ${JSON.stringify(text)} never becomes clean or publishes guessed ranges`,async()=>{
 const f=fixture(text);
 assert.equal((await f.problems.present(f.result)).status,'unsupported_coordinates');
 assert.equal(f.published.size,0);assert.equal(f.events.some(event=>event.type==='set'),false);
});

test('BOM retained by the actual virtual document shifts ranges by its inspected offset',async()=>{
 const f=fixture('\ufeffЯ\r\nЁж\n');f.add({start:{line:0,character:0},end:{line:0,character:1}});
 f.vscode.workspace.openTextDocument=async uri=>textDocument(uri,f.text);
 assert.equal((await f.problems.present(f.result)).status,'published');
 const [row]=f.published.get(f.uri);assert.deepEqual(row.range.start,{line:0,character:1});
 assert.deepEqual(row.range.end,{line:0,character:2});
});

test('actual virtual document text must match the independently verified bytes, except for one leading BOM',async()=>{
 const f=fixture();f.vscode.workspace.openTextDocument=async uri=>textDocument(uri,f.text.replace(/\r\n/g,'\n'));
 await assert.rejects(f.problems.present(f.result),/BSL_PROBLEMS_MISMATCH/);assert.equal(f.published.size,0);
});

test('reader text and URI cannot be substituted while the editor is opening',async()=>{
 for(const change of ['text','uri']){
  const f=fixture(),opening=deferred(),opened=deferred();
  f.vscode.workspace.openTextDocument=async()=>{opening.resolve();return opened.promise;};
  const pending=f.problems.present(f.result);await opening.promise;
  if(change==='text')f.draft.text=f.text.replace('Тест','Пуск');
  else f.uri.authority='substituted';
  opened.resolve(textDocument(f.uri,f.draft.text));
  await assert.rejects(pending,/BSL_PROBLEMS_MISMATCH/);assert.equal(f.published.size,0);
 }
});

test('actual document must retain the minted URI and preserve exact position offset round trips',async()=>{
 for(const tamper of [document=>{document.uri={...document.uri,authority:'different'};},
  document=>{document.offsetAt=()=>0;}]){
  const f=fixture();f.add();f.vscode.workspace.openTextDocument=async uri=>{
   const document=textDocument(uri,f.text);tamper(document);return document;
  };
  await assert.rejects(f.problems.present(f.result),/BSL_PROBLEMS_MISMATCH/);assert.equal(f.published.size,0);
 }
});

test('isCurrent revocation during the second await prevents publication after the actual document opens',async()=>{
 const f=fixture(),opening=deferred(),opened=deferred();let current=true;
 f.vscode.workspace.openTextDocument=async()=>{opening.resolve();return opened.promise;};
 const pending=f.problems.present(f.result,{isCurrent:()=>current});await opening.promise;current=false;
 opened.resolve(textDocument(f.uri,f.text));assert.equal((await pending).status,'stale');assert.equal(f.published.size,0);
});

test('isCurrent is checked before reading and after a pending read',async()=>{
 const f=fixture();let current=false;
 assert.equal((await f.problems.present(f.result,{isCurrent:()=>current})).status,'stale');assert.equal(f.reads(),0);
 current=true;const waiting=deferred();f.options.readDraft=()=>waiting.promise;
 const problems=createBslProblems(f.vscode,f.options),pending=problems.present(f.result,{isCurrent:()=>current});
 current=false;waiting.resolve(f.draft);assert.equal((await pending).status,'stale');assert.equal(f.published.size,0);
});

test('a newer presentation wins over an older pending read and late rejection',async()=>{
 const f=fixture();f.add();const waiting=deferred();let calls=0;
 const problems=createBslProblems(f.vscode,{readDraft:()=>++calls===1?waiting.promise:Promise.resolve(f.draft)});
 const older=problems.present(f.result);assert.equal((await problems.present(f.result)).status,'published');
 waiting.reject(new Error('OLD_READ_FAILED'));assert.equal((await older).status,'stale');
 assert.equal(f.published.get(f.uri).length,1);
});

test('clear cancels a pending publication and returns the explicit reason',async()=>{
 const f=fixture(),waiting=deferred();
 const problems=createBslProblems(f.vscode,{readDraft:()=>waiting.promise});
 const pending=problems.present(f.result);assert.deepEqual(problems.clear('cancelled'),{status:'cancelled'});
 waiting.resolve(f.draft);assert.equal((await pending).status,'stale');assert.equal(f.published.size,0);
});

test('trust revocation during read clears and cannot publish even a genuine clean report',async()=>{
 const f=fixture(),waiting=deferred();
 const problems=createBslProblems(f.vscode,{readDraft:()=>waiting.promise});
 const pending=problems.present(f.result);f.vscode.workspace.isTrusted=false;waiting.resolve(f.draft);
 assert.equal((await pending).status,'untrusted');assert.equal(f.published.size,0);
 assert.equal((await problems.present(f.result)).status,'untrusted');
});

test('dispose cancels pending work, clears once, and never touches the disposed collection again',async()=>{
 const f=fixture(),waiting=deferred();const problems=createBslProblems(f.vscode,{readDraft:()=>waiting.promise});
 const pending=problems.present(f.result);problems.dispose();const count=f.events.length;
 problems.dispose();problems.clear('cancelled');waiting.resolve(f.draft);
 assert.equal((await pending).status,'disposed');assert.equal((await problems.present(f.result)).status,'disposed');
 assert.equal(f.events.length,count);assert.equal(f.disposed(),1);assert.equal(f.published.size,0);
});

test('pending report input is copied and its receipt is immutable at the reader boundary',async()=>{
 const f=fixture(),waiting=deferred();let saved;
 const problems=createBslProblems(f.vscode,{readDraft:receipt=>{saved=receipt;return waiting.promise;}});
 const pending=problems.present(f.result);assert.ok(Object.isFrozen(saved));assert.ok(Object.isFrozen(saved.source_ref.snapshot));
 f.result.receipt.revision=99;f.analysis.candidate_sha256='9'.repeat(64);waiting.resolve(f.draft);
 const value=await pending;assert.equal(value.status,'clean');assert.equal(value.receipt.revision,3);
});

test('read failure removes previous Problems and stays a failure rather than a zero-diagnostic success',async()=>{
 const f=fixture();f.add();let fail=false;
 const problems=createBslProblems(f.vscode,{readDraft:async()=>{if(fail)throw new Error('ACCESS_DENIED');return f.draft;}});
 await problems.present(f.result);fail=true;
 await assert.rejects(problems.present(f.result),/ACCESS_DENIED/);assert.equal(f.published.size,0);
});
