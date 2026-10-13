// Bounded binary download: never render report HTML inside the application's DOM.
export const REPORT_LIMITS=Object.freeze({json:16*1024*1024,html:64*1024*1024});
export function reportFilename(pair,format){return `rentgen-change-review-${pair.before_sha256.slice(0,12)}-${pair.after_sha256.slice(0,12)}.${format}`;}
export async function fetchReport(pair,format,{token,signal,fetcher=fetch}={}){
  if(typeof format!=='string'||!Object.hasOwn(REPORT_LIMITS,format))throw {code:'INVALID_REQUEST'};
  const cap=REPORT_LIMITS[format];
  if(!cap)throw {code:'INVALID_REQUEST'};
  let response;
  try{response=await fetcher('/api/comparison-report',{method:'POST',cache:'no-store',credentials:'omit',signal,headers:{'Content-Type':'application/json','X-Rentgen-Session':token},body:JSON.stringify({pair:pair.pair,before_sha256:pair.before_sha256,after_sha256:pair.after_sha256,format})});}
  catch{throw {code:signal?.aborted?'CANCELLED':'CONNECTION_LOST'};}
  if(!response.ok){let data;try{data=await response.json();}catch{}throw {code:data?.error||'PROTOCOL_ERROR'};}
  const mime=format==='json'?'application/json; charset=utf-8':'text/html; charset=utf-8';
  const length=response.headers.get('Content-Length'),size=Number(length),digest=response.headers.get('X-Rentgen-Report-SHA256');
  const filename=reportFilename(pair,format);
  if(!/^[1-9][0-9]*$/.test(length||'')||!Number.isSafeInteger(size)||size>cap||response.headers.get('Content-Type')!==mime||response.headers.get('Content-Disposition')!==`attachment; filename="${filename}"`||response.headers.get('X-Rentgen-Pair')!==pair.pair||response.headers.get('X-Rentgen-Before-SHA256')!==pair.before_sha256||response.headers.get('X-Rentgen-After-SHA256')!==pair.after_sha256||!/^[0-9a-f]{64}$/.test(digest||'')){
    await response.body?.cancel().catch(()=>{});throw {code:'PROTOCOL_ERROR'};
  }
  if(!response.body)throw {code:'PROTOCOL_ERROR'};
  // One exact-size byte buffer bounds overhead even if the stream yields tiny chunks.
  const reader=response.body.getReader(),payload=new Uint8Array(size);let received=0;
  try{
    while(true){
      if(signal?.aborted)throw {code:'CANCELLED'};
      const {done,value}=await reader.read();if(done)break;
      if(!(value instanceof Uint8Array)||!value.length||received+value.length>size||received+value.length>cap)throw {code:'PROTOCOL_ERROR'};
      payload.set(value,received);received+=value.length;
    }
    if(signal?.aborted)throw {code:'CANCELLED'};
    if(received!==size)throw {code:'PROTOCOL_ERROR'};
    const blob=new Blob([payload],{type:mime});
    return {blob,filename,sha256:digest,size};
  }catch(error){await reader.cancel().catch(()=>{});throw {code:signal?.aborted?'CANCELLED':typeof error?.code==='string'?error.code:'CONNECTION_LOST'};}
  finally{reader.releaseLock();}
}
let reportURL=null,releaseTimer=null;
export function releaseReportURL(){
  if(reportURL!==null)URL.revokeObjectURL(reportURL);
  reportURL=null;if(releaseTimer!==null)clearTimeout(releaseTimer);releaseTimer=null;
}
export function deliverReport({blob,filename}){
  releaseReportURL();
  const url=URL.createObjectURL(blob),link=document.createElement('a');reportURL=url;
  link.href=url;link.download=filename;link.hidden=true;document.body.append(link);
  try{link.click();}finally{link.remove();releaseTimer=setTimeout(releaseReportURL,30000);}
}
