'use strict';
const {createHash}=require('node:crypto');
const {isDeepStrictEqual}=require('node:util');
const {sourceRef}=require('./core.cjs');
const {validateBsl}=require('./bsl-result.cjs');

const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const hash=/^[0-9a-f]{64}$/;
const MAX_BYTES=1048576;
const mismatch=()=>{throw new Error('BSL_PROBLEMS_MISMATCH');};
const requireValue=value=>{if(!value)mismatch();};

function validateReceipt(receipt){
 requireValue(receipt&&uuid.test(receipt.project_id)&&uuid.test(receipt.draft_id)&&
  Number.isSafeInteger(receipt.revision)&&receipt.revision>0&&hash.test(receipt.proposal_content_id));
 try{sourceRef(receipt.source_ref,receipt.project_id);}catch{mismatch();}
}
function freeze(value){
 if(value&&typeof value==='object'){
  Object.values(value).forEach(freeze);Object.freeze(value);
 }
 return value;
}
function validatePosition(position,lines){
 requireValue(position&&Number.isSafeInteger(position.line)&&Number.isSafeInteger(position.character)&&
  position.line>=0&&position.line<lines.length&&position.character>=0&&position.character<=lines[position.line].length);
}
function candidateLines(text){
 // The fixed analyzer profile uses BMP columns after utf-8-sig decoding.
 // Never infer mixed non-BMP conventions or clamp a report into the document.
 const plain=text.startsWith('\ufeff')?text.slice(1):text;
 if(/[\uD800-\uDFFF]/.test(plain)||/\r(?!\n)/u.test(plain))return null;
 return {plain,lines:plain.split(/\r\n|\n/)};
}
function diagnostics(vscode,analysis,candidate,document,delta){
 const {plain,lines}=candidate,offsets=[0];
 for(let index=0;index<plain.length;index++)if(plain[index]==='\n')offsets.push(index+1);
 const position=point=>{
  const offset=offsets[point.line]+point.character+delta;
  const result=document.positionAt(offset);
  requireValue(result&&Number.isSafeInteger(result.line)&&result.line>=0&&
   Number.isSafeInteger(result.character)&&result.character>=0&&document.offsetAt(result)===offset);
  return result;
 };
 const severities={Error:vscode.DiagnosticSeverity.Error,Warning:vscode.DiagnosticSeverity.Warning,
  Information:vscode.DiagnosticSeverity.Information,Hint:vscode.DiagnosticSeverity.Hint};
 return analysis.diagnostics.map(row=>{
  requireValue(row&&typeof row.code==='string'&&/^[A-Za-z][A-Za-z0-9_]{0,127}$/.test(row.code)&&
   Object.hasOwn(severities,row.severity)&&typeof row.message==='string'&&
   !/[\uD800-\uDFFF]/u.test(row.message)&&Buffer.byteLength(row.message,'utf8')<=1024);
  validatePosition(row.start,lines);validatePosition(row.end,lines);
  requireValue(row.start.line<row.end.line||row.start.line===row.end.line&&row.start.character<=row.end.character);
  const start=position(row.start),end=position(row.end);
  const range=new vscode.Range(start.line,start.character,end.line,end.character);
  const diagnostic=new vscode.Diagnostic(range,row.message,severities[row.severity]);
  diagnostic.code=row.code;diagnostic.source='Рентген BSL';return diagnostic;
 });
}

// readDraft is an authority owned by views/client: it mints an immutable URI for
// exactly this receipt and supplies the verified, BOM-preserving UTF-8 text.
// Local JSON remains untrusted evidence; this presenter does not authenticate it.
function createBslProblems(vscode,{trusted=()=>vscode.workspace.isTrusted,readDraft}={}){
 if(typeof trusted!=='function'||typeof readDraft!=='function')throw new TypeError('BSL_PROBLEMS_OPTIONS_REQUIRED');
 const collection=vscode.languages.createDiagnosticCollection('rentgen-bsl');
 let generation=0,disposed=false;
 const status=(value,extra={})=>Object.freeze({status:value,...extra});
 function clear(value='cleared'){
  generation++;if(!disposed)collection.clear();return status(value);
 }
 function active(token,isCurrent){
  if(disposed)return 'disposed';
  if(token!==generation)return 'stale';
  if(!trusted())return 'untrusted';
  if(!isCurrent())return 'stale';
  return null;
 }
 async function present(value,{isCurrent=()=>true}={}){
  if(typeof isCurrent!=='function')throw new TypeError('BSL_PROBLEMS_CURRENT_REQUIRED');
  const token=++generation;
  if(disposed)return status('disposed');
  collection.clear();
  let stopped=active(token,isCurrent);
  if(stopped)return status(stopped);
  try{
   // A caller must not be able to change a pending report's receipt or rows.
   let result;
   try{result=structuredClone(value);}catch{mismatch();}
   requireValue(result&&typeof result==='object');
   if(result.status==='incomplete')return status('incomplete');
   requireValue(result.status==='completed'&&uuid.test(result.run_id)&&result.evidence==='local_unattested');
   validateReceipt(result.receipt);
   const report=result.report,analysis=report?.diagnostic?.analysis;
   requireValue(analysis&&hash.test(analysis.candidate_sha256)&&Number.isSafeInteger(analysis.candidate_size_bytes)&&
    analysis.candidate_size_bytes>=0&&analysis.candidate_size_bytes<=MAX_BYTES);
   const proposal={content_id:result.receipt.proposal_content_id,
    replacement:{raw_sha256:analysis.candidate_sha256,size_bytes:analysis.candidate_size_bytes}};
   try{validateBsl(report,result.receipt,proposal);}catch{mismatch();}
   if(analysis.status!=='completed')return status(analysis.status);
   if(!analysis.diagnostics_complete)return status('incomplete');
   requireValue(analysis.reason===null&&analysis.exit_code===0&&hash.test(analysis.report_sha256)&&
    hash.test(analysis.stdout_sha256)&&hash.test(analysis.stderr_sha256));
   const receipt=freeze(result.receipt);
   const draft=await readDraft(receipt);
   stopped=active(token,isCurrent);
   if(stopped){if(token===generation&&!disposed)collection.clear();return status(stopped);}
   requireValue(draft&&isDeepStrictEqual(draft.receipt,receipt)&&typeof draft.text==='string'&&draft.text.length<=MAX_BYTES&&
    hash.test(draft.rawSha256)&&Number.isSafeInteger(draft.sizeBytes)&&draft.sizeBytes>=0&&draft.sizeBytes<=MAX_BYTES);
   // Snapshot reader values before the editor await as well: a mutable reader
   // response may not substitute text after its bytes have been checked.
   const text=draft.text,bytes=Buffer.from(text,'utf8');
   requireValue(bytes.length===draft.sizeBytes&&draft.sizeBytes===analysis.candidate_size_bytes&&
    createHash('sha256').update(bytes).digest('hex')===draft.rawSha256&&draft.rawSha256===analysis.candidate_sha256);
   // Only a views-owned read-only virtual document is eligible. A filesystem
   // working copy can drift independently of the checked revision.
   const uri=draft.uri;
   requireValue(uri?.scheme==='rentgen-view'&&typeof uri.authority==='string'&&uri.authority.length>0&&
    typeof uri.path==='string'&&uri.path.startsWith('/')&&!uri.query&&!uri.fragment);
   const uriFields=Object.fromEntries(['scheme','authority','path','query','fragment'].map(key=>[key,uri[key]]));
   const candidate=candidateLines(text);
   if(candidate===null)return status('unsupported_coordinates');
   const document=await vscode.workspace.openTextDocument(uri);
   stopped=active(token,isCurrent);
   if(stopped){if(token===generation&&!disposed)collection.clear();return status(stopped);}
   requireValue(document&&typeof document.getText==='function'&&typeof document.positionAt==='function'&&
    typeof document.offsetAt==='function'&&Object.entries(uriFields).every(([key,value])=>document.uri?.[key]===value&&uri[key]===value));
   const documentText=document.getText();
   // Content providers and editor buffers may keep or strip one leading BOM.
   // Inspect the actual immutable document rather than guessing its columns.
   requireValue(documentText===text||documentText===candidate.plain);
   const delta=documentText.length-candidate.plain.length;
   const rows=diagnostics(vscode,analysis,candidate,document,delta);
   stopped=active(token,isCurrent);
   if(stopped){if(token===generation&&!disposed)collection.clear();return status(stopped);}
   collection.set(uri,rows);
   return status(rows.length?'published':'clean',{receipt,count:rows.length,uri});
  }catch(error){
   // A late failed read must not erase a newer successfully published report.
   if(token===generation&&!disposed)collection.clear();
   stopped=active(token,isCurrent);
   if(stopped)return status(stopped);
   throw error;
  }
 }
 function dispose(){
  if(disposed)return;
  generation++;collection.clear();disposed=true;collection.dispose();
 }
 return Object.freeze({present,clear,dispose});
}
module.exports={createBslProblems};
