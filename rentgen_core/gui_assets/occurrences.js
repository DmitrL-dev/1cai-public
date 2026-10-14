import {boundedSourceQuery} from './model.js';

const ID=/^[0-9a-f]{32}$/,SHA=/^[0-9a-f]{64}$/;
export const occurrenceConventions=Object.freeze({line_base:1,column_base:1,column_unit:'unicode_codepoint',newlines:'CRLF_CR_LF',bom:'excluded',overlap:true,case_sensitive:true,normalization:'none'});

// Keep DOM/UTF-16 coordinates separate from the backend's Unicode-codepoint ones.
export function indexSource(text){
  const characters=[...text],positions=[];let utf16=0,line=1,column=1;
  for(let offset=0;offset<characters.length;offset++){
    const character=characters[offset];positions.push({utf16,line,column});utf16+=character.length;
    if(character==='\r'){line++;column=1;}
    else if(character==='\n'){if(characters[offset-1]!=='\r')line++;column=1;}
    else column++;
  }
  positions.push({utf16,line,column});return {text,characters,positions};
}

export function occurrenceResultMatches(binding,query,offset,result,index){
  const ref=result?.input_ref,p=result?.page,coverage=result?.coverage,hits=result?.occurrences;
  if(!boundedSourceQuery(query).valid)return false;
  if(!ref||ref.relative_path!==binding.path||ref.raw_sha256!==binding.raw_sha256||ref.input_sha256!==binding.input_sha256||result.size_bytes!==binding.size_bytes||result.query!==query||result.analysis!=='literal_occurrences')return false;
  if(!result.conventions||Object.entries(occurrenceConventions).some(([key,value])=>result.conventions[key]!==value))return false;
  if(!coverage||coverage.complete!==true||coverage.characters_scanned!==index.characters.length||!Array.isArray(hits)||hits.length>200)return false;
  const length=[...query].length,maximum=Math.max(0,index.characters.length-length+1);
  if(!p||!Number.isSafeInteger(offset)||offset<0||offset%200||p.offset!==offset||p.limit!==200||!Number.isSafeInteger(p.total)||p.total<0||p.total>maximum||(offset>0&&offset>=p.total)||p.returned!==hits.length||hits.length!==Math.min(200,Math.max(0,p.total-offset))||p.has_previous!==(offset>0)||p.has_next!==(offset+hits.length<p.total))return false;
  let previous=-1;
  return hits.every(hit=>{
    if(!hit||!Number.isSafeInteger(hit.offset)||hit.offset<=previous||hit.offset<0||hit.offset+length>index.characters.length)return false;
    previous=hit.offset;const position=index.positions[hit.offset],end=index.positions[hit.offset+length];
    const lineStart=hit.offset-position.column+1,snippetStart=Math.max(lineStart,hit.offset-128);
    let snippetEnd=Math.min(index.characters.length,snippetStart+512);
    for(let at=snippetStart;at<snippetEnd;at++)if(index.characters[at]==='\r'||index.characters[at]==='\n'){snippetEnd=at;break;}
    const excerpt=index.characters.slice(snippetStart,snippetEnd).join('');
    return hit.line===position.line&&hit.column===position.column&&index.text.slice(position.utf16,end.utf16)===query&&hit.excerpt===excerpt&&hit.truncated_before===(snippetStart>lineStart)&&hit.truncated_after===(snippetEnd<index.characters.length&&!['\r','\n'].includes(index.characters[snippetEnd]));
  });
}

export function occurrenceReplyMatches(binding,query,offset,reply,id=null){
  return !!reply&&ID.test(reply.occurrence)&&(id===null||reply.occurrence===id)&&reply.job===binding.job&&reply.input_sha256===binding.input_sha256&&reply.path===binding.path&&reply.raw_sha256===binding.raw_sha256&&reply.query===query&&reply.offset===offset;
}

export function createOccurrenceController({api,binding,text,isCurrent=()=>true,onChange=()=>{},pause=ms=>new Promise(resolve=>setTimeout(resolve,ms))}){
  if(!ID.test(binding.job)||!SHA.test(binding.input_sha256)||!SHA.test(binding.raw_sha256)||typeof binding.path!=='string'||!Number.isInteger(binding.size_bytes)||binding.size_bytes<0||binding.size_bytes>262144||typeof text!=='string')throw {code:'PROTOCOL_ERROR'};
  const bytes=new TextEncoder().encode(text).length;
  if(![0,3].includes(binding.size_bytes-bytes))throw {code:'PROTOCOL_ERROR'};
  const index=indexSource(text),state={query:'',busy:false,result:null,error:null,message:''};
  text=''; // The index owns the sole controller-side source string until disposal.
  let active=true,generation=0,queue=Promise.resolve(),operation=null;
  const current=g=>active&&generation===g&&isCurrent();
  const notify=()=>{if(active&&isCurrent())onChange(state);};
  const post=(path,body)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(5000)});
  const selector=op=>({job:binding.job,input_sha256:binding.input_sha256,occurrence:op.id});
  const url=op=>'/api/occurrences?'+new URLSearchParams(selector(op));

  function cancelOperation(op){
    if(!op||!op.started)return Promise.resolve();
    if(op.cancellation)return op.cancellation;
    op.cancellation=(async()=>{
      try{
        let reply=await post('/api/occurrences-cancel',selector(op));
        const deadline=Date.now()+12000;
        while(reply.status==='searching'&&Date.now()<deadline){
          await pause(250);
          // Lost start replies have no ID: cancellation recovery stays bounded to
          // this same import, before any newer operation can leave the queue.
          reply=op.id?await api(url(op),{signal:AbortSignal.timeout(3000)}):await post('/api/occurrences-cancel',selector(op));
        }
      }catch{/* The backend owns its deadline/reap; no result is disclosed here. */}
    })();
    return op.cancellation;
  }

  function invalidate(){
    generation++;operation?.pollController?.abort();
    // A start still in flight may allocate an ID. Its finally block cancels only
    // after that response or timeout, and serializes the next start behind it.
    if(operation?.id)void cancelOperation(operation);
  }

  async function execute(query,offset,g){
    if(!current(g))return;
    const op={id:null,started:false,terminal:false,cancellation:null,pollController:null};operation=op;
    try{
      op.started=true;
      const started=await post('/api/occurrences-start',{job:binding.job,input_sha256:binding.input_sha256,path:binding.path,raw_sha256:binding.raw_sha256,query,offset});
      if(occurrenceReplyMatches(binding,query,offset,started))op.id=started.occurrence;
      else throw {code:'PROTOCOL_ERROR'};
      if(!current(g))return;
      const deadline=Date.now()+65000;
      while(current(g)&&Date.now()<deadline){
        op.pollController=new AbortController();
        const reply=await api(url(op),{signal:AbortSignal.any([op.pollController.signal,AbortSignal.timeout(5000)])});
        op.pollController=null;
        if(!current(g))return;
        if(!occurrenceReplyMatches(binding,query,offset,reply,op.id)||!['searching','ready','error','cancelled'].includes(reply.status))throw {code:'PROTOCOL_ERROR'};
        if(reply.status==='ready'){
          if(!occurrenceResultMatches(binding,query,offset,reply.result,index))throw {code:'PROTOCOL_ERROR'};
          op.terminal=true;state.result=reply.result;state.busy=false;notify();return;
        }
        if(reply.status==='error'||reply.status==='cancelled'){op.terminal=true;throw {code:reply.error||'CANCELLED'};}
        await pause(250);
      }
      if(current(g))throw {code:'SEARCH_TIMEOUT'};
    }catch(error){if(current(g)){state.error=error?.code||'PROTOCOL_ERROR';state.busy=false;state.result=null;notify();}}
    finally{if(!op.terminal||!current(g))await cancelOperation(op);}
  }

  function search(query,offset=0){
    invalidate();state.query=query;state.result=null;state.error=null;state.message='';
    if(!boundedSourceQuery(query).valid||!Number.isSafeInteger(offset)||offset<0||offset%200){state.busy=false;state.error='INVALID_OCCURRENCE_QUERY';notify();return queue;}
    state.busy=true;const g=generation;notify();
    queue=queue.catch(()=>{}).then(()=>execute(query,offset,g));return queue;
  }
  function edit(query){invalidate();state.query=query;state.busy=false;state.result=null;state.error=null;state.message='';notify();}
  function cancel(){invalidate();state.busy=false;state.result=null;state.error=null;state.message='Поиск в модуле отменён.';notify();return queue;}
  function leave(){
    invalidate();active=false;
    // Pending transport/reap promises retain only the small operation binding.
    // Every reply checks ownership before consulting this discarded source index.
    index.text='';index.characters=[];index.positions=[];state.result=null;state.query='';
    onChange=()=>{};isCurrent=()=>false;
    return Promise.all([queue.catch(()=>{}),operation?.cancellation]);
  }
  return {state,index,search,edit,cancel,leave};
}

export function mountOccurrences({container,source,binding,text,initialQuery='',api,errorText,isCurrent}){
  const section=document.createElement('section');section.className='module-occurrences';section.setAttribute('aria-label','Совпадения в выбранном модуле');
  section.innerHTML='<h3>Найти все вхождения в модуле</h3><p class="source-meta">Точный однострочный текст с учётом регистра, без regex и анализа смысла кода. Перекрывающиеся совпадения учитываются. Строки и столбцы с 1; столбцы в Unicode-кодовых точках. CRLF, CR и LF — перевод строки; UTF-8 BOM не учитывается.</p><form class="occurrence-form"><label for="occurrence-query">Фрагмент в выбранном модуле</label><input id="occurrence-query" type="search" maxlength="256" autocomplete="off" spellcheck="false"><button id="occurrence-find" class="button secondary" type="submit">Найти в модуле</button><button id="occurrence-cancel" class="button subtle" type="button" hidden>Отменить поиск в модуле</button></form><p id="occurrence-status" role="status"></p><nav class="pagination" aria-label="Страницы вхождений"><button id="occurrence-previous" class="button subtle" type="button" disabled>Предыдущие вхождения</button><p id="occurrence-range"></p><button id="occurrence-next" class="button subtle" type="button" disabled>Следующие вхождения</button></nav><div id="occurrence-list" aria-label="Вхождения в выбранном модуле"></div>';
  const selection=document.createElement('p');selection.id='source-selection';selection.className='source-meta';selection.setAttribute('role','status');source.after(selection);container.append(section);
  const $=id=>section.querySelector('#'+id);
  let controller;
  function render(state){
    source.textContent=text;selection.textContent='';
    $('occurrence-find').disabled=state.busy;$('occurrence-cancel').hidden=!state.busy;
    $('occurrence-previous').disabled=state.busy||!state.result?.page.has_previous;
    $('occurrence-next').disabled=state.busy||!state.result?.page.has_next;
    $('occurrence-status').textContent=state.busy?'Ищем все вхождения в проверенном модуле…':state.error?(state.error==='INVALID_OCCURRENCE_QUERY'?'Введите однострочный фрагмент до 256 байт UTF-8, без управляющих символов.':'Поиск в модуле не завершён. '+errorText({code:state.error})):state.result?`Найдено ${state.result.page.total} вхождений. Полное покрытие выбранного модуля: ${state.result.coverage.characters_scanned} символов.`:state.message||'Введите фрагмент и нажмите «Найти в модуле».';
    const result=state.result,p=result?.page;
    $('occurrence-range').textContent=p?`Вхождения ${p.returned?p.offset+1:0}–${p.offset+p.returned} из ${p.total}`:'';
    $('occurrence-list').replaceChildren();
    for(const hit of result?.occurrences||[]){
      const button=document.createElement('button');button.type='button';button.setAttribute('aria-pressed','false');
      const label=document.createElement('span');label.className='occurrence-location';label.textContent=`Строка ${hit.line}, столбец ${hit.column}`;
      const excerpt=document.createElement('span');excerpt.className='occurrence-excerpt';excerpt.textContent=(hit.truncated_before?'…':'')+hit.excerpt+(hit.truncated_after?'…':'');button.append(label,excerpt);
      button.addEventListener('click',()=>{
        if(!isCurrent()||controller.state.result!==result)return;
        const start=controller.index.positions[hit.offset].utf16,end=controller.index.positions[hit.offset+[...result.query].length].utf16;
        const mark=document.createElement('mark');mark.id='occurrence-highlight';mark.tabIndex=-1;mark.textContent=text.slice(start,end);
        source.replaceChildren(document.createTextNode(text.slice(0,start)),mark,document.createTextNode(text.slice(end)));
        selection.textContent=`Строка ${hit.line}, столбец ${hit.column}. Выбрано буквальное вхождение.`;
        $('occurrence-list').querySelectorAll('button').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));
        mark.focus({preventScroll:true});mark.scrollIntoView({block:'center',inline:'nearest'});
      });$('occurrence-list').append(button);
    }
  }
  controller=createOccurrenceController({api,binding,text,isCurrent,onChange:render});
  $('occurrence-query').value=initialQuery;controller.edit(initialQuery);
  section.querySelector('form').addEventListener('submit',event=>{event.preventDefault();void controller.search($('occurrence-query').value);});
  $('occurrence-query').addEventListener('input',()=>controller.edit($('occurrence-query').value));
  $('occurrence-cancel').addEventListener('click',()=>{void controller.cancel();$('occurrence-query').focus();});
  for(const [id,direction] of [['occurrence-previous',-1],['occurrence-next',1]])$(id).addEventListener('click',async()=>{
    const p=controller.state.result?.page;if(!p||$(id).disabled)return;
    await controller.search(controller.state.query,p.offset+direction*200);
    if(isCurrent()){$(id).disabled?$(direction>0?'occurrence-previous':'occurrence-next').focus():$(id).focus();}
  });
  return controller;
}
