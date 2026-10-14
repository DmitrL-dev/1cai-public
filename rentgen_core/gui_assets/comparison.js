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
const diffReasons=['SOURCE_TOO_LARGE','SOURCE_ENCODING_UNSUPPORTED','LINE_LIMIT','WORK_LIMIT'];
const integer=(value,max)=>Number.isSafeInteger(value)&&value>=0&&value<=max;
// Validate the selected entry, exact archive/file identities, full alignment and page.
export function comparisonLineDiffMatches(pair,page,row,offset,result){
  if(!result||!integer(offset,8000)||offset%200||result.pair!==pair.pair||result.before_sha256!==pair.before_sha256||result.after_sha256!==pair.after_sha256||result.page!==page.id||result.path!==row.path)return false;
  const complete=result.status==='complete';
  if(!complete&&result.status!=='unavailable'||(complete?result.reason!==null:!diffReasons.includes(result.reason)))return false;
  const limits=result.limits;
  if(!limits||limits.source_bytes!==262144||limits.lines_per_side!==4096||limits.output_rows!==8192||limits.dp_cells!==1000000)return false;
  if(result.coverage?.alignment!==result.status||result.coverage?.full_scan!==complete)return false;
  for(const side of ['before','after']){
    const ref=row[side],input=result.input_refs?.[side],e=result[side];
    if(!e||e.present!==(ref!==null)||e.size_bytes!==(ref?.size_bytes??null))return false;
    if(!ref){if(input!==null||['bom','line_count','newlines','final_newline'].some(key=>e[key]!==null))return false;continue;}
    if(!input||input.input_sha256!==pair[side+'_sha256']||input.relative_path!==row.path||input.raw_sha256!==ref.raw_sha256||input.size_bytes!==ref.size_bytes)return false;
    if(e.bom!==null&&typeof e.bom!=='boolean'||e.final_newline!==null&&typeof e.final_newline!=='boolean'||e.line_count!==null&&!integer(e.line_count,262144))return false;
    if(e.newlines!==null&&(!e.newlines||!['LF','CRLF','CR'].every(key=>integer(e.newlines[key],262144))))return false;
    if(complete&&(ref.size_bytes>262144||typeof e.bom!=='boolean'||typeof e.final_newline!=='boolean'||!integer(e.line_count,4096)||!e.newlines))return false;
    if(e.line_count===null&&(e.newlines!==null||e.final_newline!==null))return false;
    if(e.line_count!==null){
      if(!e.newlines||typeof e.final_newline!=='boolean')return false;
      const count=e.newlines.LF+e.newlines.CRLF+e.newlines.CR;
      if(count!==e.line_count-(e.line_count&&!e.final_newline?1:0)||e.final_newline&&e.line_count===0)return false;
      if(e.line_count===0&&e.size_bytes!==(e.bom?3:0))return false;
      if(count+e.newlines.CRLF+(e.line_count&&!e.final_newline?1:0)+(e.bom?3:0)>e.size_bytes)return false;
    }
  }
  const p=result.pagination,rows=result.rows;
  if(!p||p.offset!==offset||p.limit!==200||!integer(p.total,8192)||!Array.isArray(rows)||rows.length>200||p.returned!==rows.length||rows.length!==Math.min(200,Math.max(0,p.total-offset))||p.has_previous!==(offset>0)||p.has_next!==(offset+rows.length<p.total))return false;
  if(!complete){
    const present=['before','after'].map(side=>result[side]).filter(e=>e.present);
    const reasonMatches={
      SOURCE_TOO_LARGE:present.some(e=>e.size_bytes>262144),
      SOURCE_ENCODING_UNSUPPORTED:present.some(e=>e.size_bytes<=262144&&typeof e.bom==='boolean'&&e.line_count===null),
      LINE_LIMIT:present.some(e=>e.line_count>4096),
      WORK_LIMIT:present.every(e=>integer(e.line_count,4096)&&typeof e.bom==='boolean')
    };
    return offset===0&&p.total===0&&rows.length===0&&reasonMatches[result.reason];
  }
  const before=result.before.line_count??0,after=result.after.line_count??0;
  if(p.total<Math.max(before,after)||p.total>before+after||offset>0&&offset>=p.total)return false;
  let left=null,right=null,bytes=0;
  const observed={before:{bytes:0,LF:0,CRLF:0,CR:0},after:{bytes:0,LF:0,CRLF:0,CR:0}};
  for(const item of rows){
    if(!item||!['equal','delete','insert'].includes(item.kind)||typeof item.text!=='string'||item.text.length>262144||/[\u0000-\u0008\u000b\u000c\u000e-\u001f\r\n]/.test(item.text)||!['LF','CRLF','CR','none'].includes(item.eol))return false;
    const encoded=new TextEncoder().encode(item.text);if(new TextDecoder('utf-8',{ignoreBOM:true}).decode(encoded)!==item.text)return false;
    bytes+=encoded.length;if(bytes>524288)return false;
    for(const [side,count] of [['before',before],['after',after]]){
      const number=item[side+'_line'],present=item.kind==='equal'||item.kind===(side==='before'?'delete':'insert');
      if(present?(!integer(number,count)||number<1):number!==null)return false;
      if(present){
        if((item.eol==='none')!==(number===count&&!result[side].final_newline))return false;
        observed[side].bytes+=encoded.length+({none:0,LF:1,CR:1,CRLF:2}[item.eol]);
        if(item.eol!=='none'&&++observed[side][item.eol]>result[side].newlines[item.eol])return false;
        if(observed[side].bytes>result[side].size_bytes-(result[side].bom?3:0))return false;
      }
    }
    if(item.before_line!==null){if(left!==null&&item.before_line!==left+1)return false;left=item.before_line;}
    if(item.after_line!==null){if(right!==null&&item.after_line!==right+1)return false;right=item.after_line;}
  }
  if(offset===0&&!p.has_next){for(const side of ['before','after'])if(result[side].present&&observed[side].bytes!==result[side].size_bytes-(result[side].bom?3:0))return false;}
  if(offset===0){for(const side of ['before','after']){const first=rows.find(item=>item[side+'_line']!==null);if(first&&first[side+'_line']!==1)return false;}}
  if(!p.has_next&&((left!==null&&left!==before)||(right!==null&&right!==after)))return false;
  return true;
}

export function createComparison({api,errorText,getBinding,fetchReport}){
  const $=id=>document.getElementById(id);
  const state={active:false,generation:0,sourceGeneration:0,busy:false,binding:null,pair:null,page:null,offset:0,status:'changes',pending:null,upload:null,notice:'',reportGeneration:0,reportBusy:false,reportController:null,diffGeneration:0,diffController:null};
  const owns=g=>state.active&&state.generation===g&&getBinding()?.job===state.binding?.job&&getBinding()?.input_sha256===state.binding?.input_sha256;
  const pairBody=()=>({pair:state.pair.pair,before_sha256:state.pair.before_sha256,after_sha256:state.pair.after_sha256});
  function controls(){ $('compare-report-html').disabled=$('compare-report-json').disabled=state.busy||state.reportBusy||!!state.pending||!state.pair;$('compare-report-cancel').hidden=!state.reportBusy; $('compare-file').disabled=state.busy||!!state.pending;$('compare-check').disabled=state.busy;$('compare-cancel').hidden=!state.pending;$('compare-filter').disabled=state.busy||!state.pair;$('compare-previous').disabled=state.busy||!state.page?.has_previous;$('compare-next').disabled=state.busy||!state.page?.has_next; }
  function message(text){$('compare-message').textContent=text;}
  function clearPage(){cancelLineDiff();cancelReport();$('compare-report-status').textContent='';state.sourceGeneration++;state.page=null;$('compare-list').replaceChildren();$('compare-source').replaceChildren();$('compare-range').textContent='';controls();}
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
    cancelLineDiff();
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
    if(current())mountLineDiff(pair,page,row,current);
  }
  function cancelLineDiff(){state.diffGeneration++;state.diffController?.abort();state.diffController=null;}
  function mountLineDiff(pair,page,row,current){
    const make=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
    const section=make('section',undefined,'comparison-line-diff');section.setAttribute('aria-label','Построчное сравнение выбранного файла');
    const heading=make('h4','Построчное сравнение текста');
    const scope=make('p','Точное сравнение строк и их окончаний; не анализ поведения кода. Исходные тексты обеих сторон сохранены выше. Каждая страница вычисляется заново.');
    const status=make('p');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    const evidence=make('div',undefined,'comparison-diff-evidence'),list=make('ol',undefined,'comparison-diff-rows');list.setAttribute('aria-label','Строки сравнения');
    const navigation=make('div',undefined,'pagination');
    const previous=make('button','Предыдущие строки','button'),next=make('button','Следующие строки','button'),retry=make('button','Повторить сравнение строк','button'),cancel=make('button','Отменить ожидание строк','button');
    for(const button of [previous,next,retry,cancel])button.type='button';
    navigation.append(previous,next,retry,cancel);section.append(heading,scope,status,evidence,navigation,list);$('compare-source').append(section);
    let offset=0,busy=false,pagination=null;
    const controls=()=>{previous.disabled=busy||!pagination?.has_previous;next.disabled=busy||!pagination?.has_next;retry.disabled=busy;cancel.hidden=!busy;};
    async function load(start,focus=null){
      if(!current()||busy)return;
      cancelLineDiff();const generation=state.diffGeneration,controller=new AbortController();state.diffController=controller;
      const owned=()=>current()&&generation===state.diffGeneration;
      offset=start;busy=true;pagination=null;list.replaceChildren();evidence.replaceChildren();controls();status.textContent='Вычисляем полное выравнивание строк…';
      try{
        const result=await api('/api/comparison-line-diff',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pair:pair.pair,before_sha256:pair.before_sha256,after_sha256:pair.after_sha256,page:page.id,path:row.path,offset:start}),signal:AbortSignal.any([controller.signal,AbortSignal.timeout(65000)])});
        if(!owned())return;if(!comparisonLineDiffMatches(pair,page,row,start,result))protocol();
        pagination=result.pagination;
        for(const side of ['before','after']){
          const e=result[side],ref=row[side],title=side==='before'?'До':'После';
          let text=`${title}: SHA-256 ZIP ${pair[side+'_sha256']} · `;
          text+=ref?`SHA-256 файла ${ref.raw_sha256} · ${ref.size_bytes} байт`:'файл отсутствует (это не пустой файл)';
          if(ref){text+=` · BOM: ${e.bom===null?'не определён':e.bom?'есть':'нет'} · строк: ${e.line_count??'не определено'}`;if(e.newlines)text+=` · LF ${e.newlines.LF}, CRLF ${e.newlines.CRLF}, CR ${e.newlines.CR}`;text+=` · последнее окончание строки: ${e.final_newline===null?'не определено':e.final_newline?'есть':'нет'}`;if(e.line_count===0)text+=' · пустой текст';}
          evidence.append(make('p',text));
        }
        if(result.status==='unavailable'){
          const reasons={SOURCE_TOO_LARGE:'превышен предел 256 КиБ на сторону',SOURCE_ENCODING_UNSUPPORTED:'неподдерживаемое текстовое кодирование',LINE_LIMIT:'более 4096 строк на стороне',WORK_LIMIT:'превышен предел работы выравнивания'};
          status.textContent=`Построчное сравнение недоступно: ${reasons[result.reason]}. Неполные строки сравнения не показаны. Используйте исходные панели выше.`;return;
        }
        status.textContent=pagination.total?`Полное выравнивание: ${pagination.total} строк. Показаны ${start+1}–${start+result.rows.length} из ${pagination.total}.`:'Полное выравнивание: 0 строк. Сверьте наличие файла и BOM.';
        for(const item of result.rows){
          const line=make('li',undefined,'comparison-diff-row diff-'+item.kind);
          const label={equal:'= Совпадает',delete:'− Удалено',insert:'+ Добавлено'}[item.kind];
          const location=make('span',`${label} · До ${item.before_line??'—'} · После ${item.after_line??'—'} · ${item.eol==='none'?'без окончания строки':item.eol}`,'comparison-diff-location');
          const code=make('pre',item.text,'comparison-diff-text');line.append(location,code);list.append(line);
        }
      }catch(error){if(owned())status.textContent='Построчное сравнение недоступно. '+errorText(error)+' Используйте исходные панели выше.';}
      finally{if(owned()){busy=false;state.diffController=null;controls();if(focus)(focus.disabled?retry:focus).focus();}}
    }
    previous.addEventListener('click',()=>void load(offset-200,previous));next.addEventListener('click',()=>void load(offset+200,next));retry.addEventListener('click',()=>void load(0,retry));
    cancel.addEventListener('click',()=>{cancelLineDiff();busy=false;pagination=null;controls();status.textContent='Ожидание строк отменено. Ответ больше не будет показан; вычисление на сервере может продолжаться. Исходные панели выше доступны.';retry.focus();});
    void load(0);
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
