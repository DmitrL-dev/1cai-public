import {deliverReport,releaseReportURL} from './report-download.js';
// Read-only submitted-export comparison. No browser path or hash grants authority.
const ID=/^[0-9a-f]{32}$/, SHA=/^[0-9a-f]{64}$/;
const statuses=['added','removed','modified','unchanged'];
const labels={added:'Добавлен',removed:'Удалён',modified:'Изменены байты',unchanged:'Без изменений'};
const terminal=status=>['ready','error','cancelled'].includes(status);
const protocol=()=>{throw {code:'PROTOCOL_ERROR'};};
export function comparisonMatches(binding,result){
  if(!binding||!result||result.job!==binding.job||result.before_sha256!==binding.input_sha256||!ID.test(result.pair)||!SHA.test(result.after_sha256))return false;
  if(result.scope!=='submitted_zip_bytes'||result.comparison!=='raw_sha256_and_size'||typeof result.before_filename!=='string'||typeof result.after_filename!=='string')return false;
  const c=result.counts;
  return !!c&&['total','files','changes',...statuses].every(k=>Number.isInteger(c[k])&&c[k]>=0&&c[k]<=8192)&&c.total===c.files&&c.total===statuses.reduce((sum,k)=>sum+c[k],0)&&c.changes===c.added+c.removed+c.modified;
}
export function comparisonStatusMatches(binding,reply,id=null){
  if(!reply||!ID.test(reply.comparison)||(id&&reply.comparison!==id)||reply.job!==binding?.job||reply.input_sha256!==binding?.input_sha256||!['awaiting_upload','uploading','analyzing','ready','error','cancelled'].includes(reply.status))return false;
  return reply.status!=='ready'||(comparisonMatches(binding,reply.result)&&reply.result.pair===reply.comparison);
}
export function comparisonPageMatches(pair,result,offset,status){
  if(!comparisonMatches({job:pair.job,input_sha256:pair.before_sha256},result)||result.pair!==pair.pair||result.after_sha256!==pair.after_sha256||result.status!==status)return false;
  if(['total','files','changes',...statuses].some(k=>result.counts[k]!==pair.counts[k]))return false;
  const p=result.page,rows=result.rows,total=status==='all'?pair.counts.total:pair.counts[status];
  if(!p||!ID.test(p.id)||p.offset!==offset||p.limit!==200||p.total!==total||!Array.isArray(rows)||rows.length>200||p.returned!==rows.length||p.returned!==Math.min(200,Math.max(0,total-offset))||p.has_previous!==(offset>0)||p.has_next!==(offset+rows.length<total))return false;
  const paths=new Set();
  return rows.every(row=>{
    if(typeof row.path!=='string'||!row.path||row.path.length>4096||paths.has(row.path)||!statuses.includes(row.status)||(status!=='all'&&status!=='changes'&&row.status!==status)||(status==='changes'&&row.status==='unchanged'))return false;
    paths.add(row.path);
    for(const side of ['before','after'])if(row[side]!==null&&(!row[side]||!SHA.test(row[side].raw_sha256)||!Number.isInteger(row[side].size_bytes)||row[side].size_bytes<0||row[side].size_bytes>4*1024*1024))return false;
    if(row.status==='added')return row.before===null&&row.after!==null;
    if(row.status==='removed')return row.before!==null&&row.after===null;
    if(!row.before||!row.after)return false;
    const equal=row.before.raw_sha256===row.after.raw_sha256&&row.before.size_bytes===row.after.size_bytes;
    return row.status==='unchanged'?equal:!equal;
  });
}
export function comparisonSourceMatches(pair,page,row,side,result){
  const ref=row[side];
  return !!ref&&result?.pair===pair.pair&&result.page===page.id&&result.side===side&&result.before_sha256===pair.before_sha256&&result.after_sha256===pair.after_sha256&&result.input_ref?.input_sha256===pair[side+'_sha256']&&result.input_ref?.relative_path===row.path&&result.input_ref?.raw_sha256===ref.raw_sha256&&result.size_bytes===ref.size_bytes&&result.encoding==='UTF-8'&&typeof result.text==='string'&&new TextEncoder().encode(result.text).length<=256*1024;
}
export function createComparison({api,errorText,getBinding,fetchReport}){
  const $=id=>document.getElementById(id);
  const state={active:false,generation:0,sourceGeneration:0,busy:false,binding:null,pair:null,page:null,offset:0,status:'changes',pending:null,upload:null,notice:'',reportGeneration:0,reportBusy:false,reportController:null};
  const owns=g=>state.active&&state.generation===g&&getBinding()?.job===state.binding?.job&&getBinding()?.input_sha256===state.binding?.input_sha256;
  const pairBody=()=>({pair:state.pair.pair,before_sha256:state.pair.before_sha256,after_sha256:state.pair.after_sha256});
  function controls(){ $('compare-report-html').disabled=$('compare-report-json').disabled=state.busy||state.reportBusy||!!state.pending||!state.pair;$('compare-report-cancel').hidden=!state.reportBusy; $('compare-file').disabled=state.busy||!!state.pending;$('compare-check').disabled=state.busy;$('compare-cancel').hidden=!state.pending;$('compare-filter').disabled=state.busy||!state.pair;$('compare-previous').disabled=state.busy||!state.page?.has_previous;$('compare-next').disabled=state.busy||!state.page?.has_next; }
  function message(text){$('compare-message').textContent=text;}
  function clearPage(){cancelReport();$('compare-report-status').textContent='';state.sourceGeneration++;state.page=null;$('compare-list').replaceChildren();$('compare-source').replaceChildren();$('compare-range').textContent='';controls();}
  function clearResult(){clearPage();state.pair=null;$('compare-result').hidden=true;controls();}
  const post=(path,body,timeout=5000)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(timeout)});
  async function known(id){return api('/api/comparison?'+new URLSearchParams({comparison:id}),{signal:AbortSignal.timeout(3000)});}
  function checkStatus(reply,id=null){if(!comparisonStatusMatches(state.binding,reply,id))protocol();return reply;}
  async function loadPage(offset=0,focus=null){
    if(!state.pair||!state.active)return;
    const g=++state.generation,pair=state.pair,status=$('compare-filter').value;
    state.status=status;state.busy=true;clearPage();message('Читаем страницу сравнения…');
    try{
      const result=await post('/api/comparison-page',{...pairBody(),offset,status});
      if(!owns(g))return;if(!comparisonPageMatches(pair,result,offset,status))protocol();
      state.page=result.page;state.offset=offset;
      $('compare-range').textContent=result.page.total?`Файлы ${offset+1}–${offset+result.rows.length} из ${result.page.total}`:'Нет файлов в выбранной категории';
      for(const [index,row] of result.rows.entries()){
        const button=document.createElement('button');button.type='button';button.tabIndex=index===0?0:-1;button.setAttribute('aria-pressed','false');button.textContent=`${labels[row.status]} · ${row.path}`;
        button.addEventListener('click',()=>openSources(row,button));
        button.addEventListener('keydown',event=>{
          const buttons=[...$('compare-list').querySelectorAll('button')];let next;
          if(event.key==='ArrowDown')next=Math.min(index+1,buttons.length-1);if(event.key==='ArrowUp')next=Math.max(0,index-1);
          if(event.key==='Home')next=0;if(event.key==='End')next=buttons.length-1;
          if(next!==undefined){event.preventDefault();buttons.forEach((b,i)=>b.tabIndex=i===next?0:-1);buttons[next].focus();}
        });$('compare-list').append(button);
      }
      message(state.notice||'Сравнение только байтов и путей. Выберите файл для просмотра обеих сторон.');
    }catch(error){if(owns(g)){clearPage();message('Страница недоступна. '+errorText(error)+' Нажмите «Проверить результат».');}}
    finally{if(owns(g)){state.busy=false;controls();if(focus){const target=$(focus);const fallback=$(focus==='compare-next'?'compare-previous':'compare-next');(target.disabled?fallback:target).focus();}}}
  }
  function cancelReport(){state.reportGeneration++;state.reportController?.abort();state.reportController=null;state.reportBusy=false;controls();}
  async function downloadReport(format){
    if(state.busy||state.reportBusy||state.pending||!state.pair)return;
    releaseReportURL();
    const pair=state.pair,g=state.generation,report=++state.reportGeneration;
    const controller=new AbortController();state.reportController=controller;state.reportBusy=true;controls();
    const current=()=>owns(g)&&state.reportGeneration===report&&state.pair?.pair===pair.pair;
    $('compare-report-status').textContent='Готовим полный отчёт без исходных текстов…';
    try{
      const result=await fetchReport(pair,format,AbortSignal.any([controller.signal,AbortSignal.timeout(65000)]));
      if(!current())return;
      deliverReport(result);
      $('compare-report-status').textContent=`Отчёт передан браузеру: ${result.filename} · ${result.size} байт · SHA-256 отчёта от сервера: ${result.sha256}. Скачанные байты не отзываются при последующей смене прав или пары.`;
    }catch(error){if(current())$('compare-report-status').textContent=error.code==='CANCELLED'?'Скачивание отменено.':errorText(error);}
    finally{if(current()){state.reportBusy=false;state.reportController=null;controls();const button=$('compare-report-'+format);if(document.activeElement===document.body||document.activeElement===button)button.focus();}}
  }
  async function openSources(row,button){
    if(state.busy||!state.page)return;
    const g=state.generation,source=++state.sourceGeneration,pair=state.pair,page=state.page;
    const current=()=>owns(g)&&state.sourceGeneration===source&&state.page?.id===page.id;
    $('compare-list').querySelectorAll('button').forEach(b=>{b.setAttribute('aria-pressed',String(b===button));b.tabIndex=b===button?0:-1;});
    const heading=document.createElement('h3');heading.textContent=row.path;
    const columns=document.createElement('div');columns.className='comparison-sides';$('compare-source').replaceChildren(heading,columns);
    // Sequential reads share one owned Rust reader; never launch both sides concurrently.
    for(const side of ['before','after']){
      if(!current())return;
      const section=document.createElement('section');section.className='comparison-side';section.setAttribute('aria-label',side==='before'?'Исходник до':'Исходник после');
      const title=document.createElement('h4');title.textContent=side==='before'?'До':'После';section.append(title);columns.append(section);
      if(!row[side]){const absent=document.createElement('p');absent.textContent='Файл отсутствует на этой стороне.';section.append(absent);continue;}
      const provenance=document.createElement('p');provenance.className='comparison-source-ref';provenance.textContent=`SHA-256 ZIP: ${pair[side+'_sha256']} · SHA-256 файла: ${row[side].raw_sha256} · ${row[side].size_bytes} байт`;section.append(provenance);
      const content=document.createElement('p');content.textContent='Читаем проверенные байты…';section.append(content);
      try{
        const result=await api('/api/comparison-source?'+new URLSearchParams({...pairBody(),page:page.id,side,path:row.path}),{signal:AbortSignal.timeout(15000)});
        if(!current())return;if(!comparisonSourceMatches(pair,page,row,side,result))protocol();
        const pre=document.createElement('pre');pre.setAttribute('aria-label',side==='before'?'Код до':'Код после');pre.textContent=result.text;content.replaceWith(pre);
      }catch(error){if(current())content.textContent=errorText(error);}
    }
  }
  async function accept(result,g){
    if(!owns(g))return;if(!comparisonMatches(state.binding,result))protocol();
    state.pair=result;state.pending=null;state.busy=false;
    $('compare-after').textContent=`После: ${result.after_filename} · SHA-256 ZIP: ${result.after_sha256}`;
    const c=result.counts;$('compare-counts').textContent=`Всего путей: ${c.total} · Добавлено: ${c.added} · Удалено: ${c.removed} · Изменены байты: ${c.modified} · Без изменений: ${c.unchanged}`;
    $('compare-result').hidden=false;controls();await loadPage(0);
  }
  async function refresh(){
    const binding=getBinding();if(!binding||!state.active||state.busy)return;
    state.binding=binding;const g=++state.generation;state.busy=true;clearResult();message('Проверяем принятую пару…');
    try{
      const result=await api('/api/comparison-current?'+new URLSearchParams({job:binding.job,input_sha256:binding.input_sha256}),{signal:AbortSignal.timeout(5000)});
      if(!owns(g))return;if(result.job!==binding.job||result.input_sha256!==binding.input_sha256)protocol();
      const pending=result.pending&&checkStatus(result.pending);
      if(pending&&!terminal(pending.status)){state.pending=pending.comparison;message('Вторая выгрузка ещё не принята. Исход операции пока неизвестен: проверьте результат или отмените.');return;}
      state.pending=null;
      if(result.current){checkStatus(result.current);if(result.current.status!=='ready')protocol();await accept(result.current.result,g);}
      else message(state.notice||'Принятой пары пока нет. Выберите ZIP «После».');
    }catch(error){if(owns(g))message('Не удалось подтвердить принятую пару. Исход операции неизвестен. '+errorText(error));}
    finally{if(owns(g)){state.busy=false;controls();}}
  }
  async function outcome(reply,g){
    if(!owns(g))return;checkStatus(reply,state.pending);
    if(reply.status==='ready'){await accept(reply.result,g);return;}
    if(terminal(reply.status)){state.pending=null;state.busy=false;state.notice=reply.status==='cancelled'?'Сравнение отменено. Показана последняя подтверждённая пара, если она есть.':errorText({code:reply.error});await refresh();return;}
    message('Исход операции пока неизвестен. Проверьте результат или отмените сравнение.');
  }
  async function submit(file){
    if(state.busy||state.pending||!getBinding())return;
    if(!/\.zip$/i.test(file.name)||!file.size||file.size>16*1024*1024){message(errorText({code:'INVALID_UPLOAD'}));return;}
    state.notice='';state.binding=getBinding();const g=++state.generation;state.busy=true;clearResult();message('Передаём и проверяем ZIP «После»…');let id;
    state.upload=new AbortController();
    try{
      const started=checkStatus(await post('/api/comparison-start',{job:state.binding.job,input_sha256:state.binding.input_sha256,filename:file.name.slice(0,240)}));
      if(!owns(g)){await post('/api/comparison-cancel',{comparison:started.comparison});return;}
      id=started.comparison;state.pending=id;controls();
      await api('/api/comparison-upload?'+new URLSearchParams({comparison:id}),{method:'PUT',headers:{'Content-Type':'application/zip'},body:file,signal:AbortSignal.any([state.upload.signal,AbortSignal.timeout(35000)])});
      const deadline=Date.now()+75000;
      while(owns(g)&&Date.now()<deadline){const reply=checkStatus(await known(id),id);if(terminal(reply.status)){await outcome(reply,g);return;}await new Promise(resolve=>setTimeout(resolve,350));}
      if(owns(g))message('Проверка ещё не подтверждена. Исход операции неизвестен. Нажмите «Проверить результат».');
    }catch(error){
      if(!owns(g))return;
      if(id&&['CONNECTION_LOST','PROTOCOL_ERROR'].includes(error.code)){
        // Only three read-backs of this exact known operation; never replay an upload.
        for(let attempt=0;attempt<3&&owns(g);attempt++){
          try{const reply=checkStatus(await known(id),id);if(terminal(reply.status)){await outcome(reply,g);return;}}catch{}
          if(attempt<2)await new Promise(resolve=>setTimeout(resolve,250));
        }
        message('Исход операции неизвестен. Нажмите «Проверить результат»; повторная загрузка не выполняется.');
      }else{state.busy=false;state.notice=errorText(error)+' Проверьте подтверждённую пару перед продолжением.';await refresh();}
    }finally{if(owns(g)){state.busy=false;state.upload=null;controls();}}
  }
  async function cancel(){
    const id=state.pending,g=state.generation;if(!id)return;
    try{const reply=await post('/api/comparison-cancel',{comparison:id});if(!owns(g))return;if(reply.cancel_requested)state.upload?.abort();state.busy=false;await refresh();}
    catch(error){if(owns(g)){state.busy=false;controls();message('Отмена не подтверждена. '+errorText(error));}}
  }
  function leave(){
    state.active=false;state.generation++;state.sourceGeneration++;state.upload?.abort();state.upload=null;
    const id=state.pending;if(id)void post('/api/comparison-cancel',{comparison:id}).catch(()=>{});
    state.pending=null;state.busy=false;clearResult();
  }
  function enter(){
    const binding=getBinding();if(!binding)return;
    $('compare-before').textContent=`До: ${binding.filename} · SHA-256 ZIP: ${binding.input_sha256}`;
    if(state.active&&state.binding?.job===binding.job&&state.binding?.input_sha256===binding.input_sha256)return;
    state.active=true;state.binding=binding;state.notice='';$('compare-filter').value='changes';void refresh();
  }
  $('compare-report-html').addEventListener('click',()=>void downloadReport('html'));
  $('compare-report-json').addEventListener('click',()=>void downloadReport('json'));
  $('compare-report-cancel').addEventListener('click',()=>{cancelReport();$('compare-report-status').textContent='Скачивание отменено.';$('compare-report-json').focus();});
  $('compare-file').addEventListener('change',()=>{const file=$('compare-file').files[0];$('compare-file').value='';if(file)void submit(file);});
  $('compare-check').addEventListener('click',()=>void refresh());$('compare-cancel').addEventListener('click',()=>void cancel());
  $('compare-filter').addEventListener('change',()=>void loadPage(0,'compare-filter'));
  $('compare-previous').addEventListener('click',()=>void loadPage(state.offset-200,'compare-previous'));$('compare-next').addEventListener('click',()=>void loadPage(state.offset+200,'compare-next'));
  return {enter,leave,get busy(){return state.busy||!!state.pending;}};
}
