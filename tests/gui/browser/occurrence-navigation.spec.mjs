import {test,expect,importZip,ready,noHorizontalOverflow} from './fixtures.mjs';

async function importOccurrences(page,app){
  await importZip(page,app.archives.occurrences.path);
  await expect(page.locator('#progress-dialog')).not.toBeVisible();
  await expect(page.locator('#metric-modules')).toHaveText('2');
  await page.locator('[data-view="modules"]').click();
  await page.locator('#item-list button').filter({hasText:'AOccurrences.bsl'}).click();
  await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
  await expect(page.getByLabel('Исходный код',{exact:true})).toHaveText(app.occurrences.text);
  await expect(page.locator('#occurrence-query')).toBeVisible();
}

function occurrenceReply(page,app,query,offset=0){
  return page.waitForResponse(async response=>{
    if(!response.url().startsWith(`${app.origin}/api/occurrences?`))return false;
    const reply=await response.json();
    return reply.status==='ready'&&reply.query===query&&reply.offset===offset;
  }).then(response=>response.json());
}

async function findOccurrences(page,app,query){
  const received=occurrenceReply(page,app,query);
  await page.locator('#occurrence-query').fill(query);
  await page.locator('#occurrence-find').click();
  return received;
}

async function frames(page){
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
}

function positions(result){
  return result.occurrences.map(({line,column,offset})=>({line,column,offset}));
}

async function deliverHeld(route,response,gate){
  try{await route.fulfill({response});}
  catch(error){
    // The controller deliberately aborts obsolete polls. Only their expected
    // browser interception cancellation is allowed; keep real routing failures.
    const failure=route.request().failure()?.errorText||String(error);
    if(!/abort|cancel|Invalid InterceptionId/i.test(failure))throw error;
  }finally{gate?.delivered();}
}

test('selected module pages all 401 overlapping literal occurrences with exact byte provenance and source navigation',async({page,app},testInfo)=>{
  await importOccurrences(page,app);
  await page.getByRole('tab',{name:'Происхождение',exact:true}).click();
  await expect(page.locator('#detail-content')).toContainText(app.occurrences.path);
  await expect(page.locator('#detail-content')).toContainText(app.occurrences.raw_sha256);
  await expect(page.locator('#detail-content')).toContainText(app.archives.occurrences.sha256);
  await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
  await expect(page.locator('#occurrence-query')).toBeVisible();
  const start=page.waitForRequest(request=>request.url()===`${app.origin}/api/occurrences-start`);
  const first=await findOccurrences(page,app,app.occurrences.overlap_query);
  const request=(await start).postDataJSON();
  expect(request).toEqual({job:first.job,input_sha256:app.archives.occurrences.sha256,
    path:app.occurrences.path,raw_sha256:app.occurrences.raw_sha256,
    query:app.occurrences.overlap_query,offset:0});
  expect(first).toMatchObject({...request,status:'ready',error:null});
  expect(first.occurrence).toMatch(/^[a-f0-9]{32}$/);
  expect(first.result).toMatchObject({analysis:'literal_occurrences',query:app.occurrences.overlap_query,
    input_ref:{relative_path:app.occurrences.path,raw_sha256:app.occurrences.raw_sha256,input_sha256:app.archives.occurrences.sha256},
    size_bytes:app.occurrences.size_bytes,coverage:{complete:true,characters_scanned:app.occurrences.characters},
    page:{offset:0,limit:200,total:401,returned:200,has_previous:false,has_next:true}});
  expect(first.result.conventions).toEqual({line_base:1,column_base:1,column_unit:'unicode_codepoint',
    newlines:'CRLF_CR_LF',bom:'excluded',overlap:true,case_sensitive:true,normalization:'none'});
  expect(positions(first.result)).toEqual(Array.from({length:200},(_,index)=>({line:1,column:index+3,offset:index+2})));
  expect(first.result.occurrences[0].truncated_after).toBe(true);
  await expect(page.locator('#occurrence-list button')).toHaveCount(200);
  await expect(page.locator('#occurrence-range')).toContainText('1–200 из 401');
  await expect(page.locator('#occurrence-previous')).toBeDisabled();
  await page.locator('#occurrence-list button').first().click();
  await expect(page.locator('#source-selection')).toContainText(/строка 1.*столбец 3/i);
  await expect(page.locator('#occurrence-highlight')).toHaveText(app.occurrences.overlap_query);
  await expect(page.locator('#occurrence-highlight')).toBeFocused();
  const secondReply=occurrenceReply(page,app,app.occurrences.overlap_query,200);
  await page.locator('#occurrence-next').click();
  const second=await secondReply;
  expect(second.result.page).toEqual({offset:200,limit:200,total:401,returned:200,has_previous:true,has_next:true});
  expect(positions(second.result)).toEqual(Array.from({length:200},(_,index)=>({line:1,column:index+203,offset:index+202})));
  await expect(page.locator('#occurrence-range')).toContainText('201–400 из 401');
  const lastReply=occurrenceReply(page,app,app.occurrences.overlap_query,400);
  await page.locator('#occurrence-next').click();
  const last=await lastReply;
  expect(last.result.page).toEqual({offset:400,limit:200,total:401,returned:1,has_previous:true,has_next:false});
  expect(positions(last.result)).toEqual([{line:1,column:403,offset:402}]);
  expect(last.result.input_ref).toEqual(first.result.input_ref);
  await expect(page.locator('#occurrence-list button')).toHaveCount(1);
  await expect(page.locator('#occurrence-range')).toContainText('401–401 из 401');
  await expect(page.locator('#occurrence-next')).toBeDisabled();
  await page.locator('#occurrence-list button').click();
  await expect(page.locator('#source-selection')).toContainText(/строка 1.*столбец 403/i);
  await expect(page.locator('#occurrence-highlight')).toHaveText(app.occurrences.overlap_query);
  await expect(page.locator('#occurrence-highlight')).toBeFocused();
  await page.screenshot({path:testInfo.outputPath('module-occurrence-last-page-provenance.png'),fullPage:true});
  const backReply=occurrenceReply(page,app,app.occurrences.overlap_query,200);
  await page.locator('#occurrence-previous').click();
  expect(positions((await backReply).result)).toEqual(positions(second.result));
  await expect(page.locator('#occurrence-list button')).toHaveCount(200);
  const firstAgain=occurrenceReply(page,app,app.occurrences.overlap_query,0);
  await page.locator('#occurrence-previous').click();
  expect(positions((await firstAgain).result)).toEqual(positions(first.result));
  await expect(page.locator('#occurrence-range')).toContainText('1–200 из 401');
  await expect(page.getByLabel('Исходный код',{exact:true})).toHaveText(app.occurrences.text);
  await expect(page.locator('#toast')).not.toBeVisible();
});

test('archive literal query prefills module navigation with BOM-free Unicode columns, mixed newlines and inert snippets',async({page,app},testInfo)=>{
  await importOccurrences(page,app);
  await page.getByLabel('Режим поиска модулей',{exact:true}).selectOption('source');
  await page.locator('#search').fill(app.occurrences.query);
  await expect(page.locator('#search-status-text')).toContainText('Найдено 1 файлов с фрагментом');
  await expect(page.locator('#item-list button')).toHaveCount(1);
  await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
  await expect(page.locator('#occurrence-query')).toHaveValue(app.occurrences.query);
  const result=(await findOccurrences(page,app,app.occurrences.query)).result;
  expect(result.page).toEqual({offset:0,limit:200,total:3,returned:3,has_previous:false,has_next:false});
  expect(positions(result)).toEqual(app.occurrences.positions);
  expect(result.input_ref).toEqual({relative_path:app.occurrences.path,
    raw_sha256:app.occurrences.raw_sha256,input_sha256:app.archives.occurrences.sha256});
  await expect(page.locator('#occurrence-list button')).toHaveCount(3);
  for(let index=0;index<3;index++){
    await expect(page.locator('.occurrence-location').nth(index)).toContainText(new RegExp(`строка ${index+2}.*столбец 3`,'i'));
    await page.locator('#occurrence-list button').nth(index).click();
    await expect(page.locator('#source-selection')).toContainText(new RegExp(`строка ${index+2}.*столбец 3`,'i'));
    await expect(page.locator('#occurrence-highlight')).toHaveText(app.occurrences.query);
    await expect(page.locator('#occurrence-highlight')).toBeFocused();
    expect(await page.getByLabel('Исходный код',{exact:true}).textContent()).toBe(app.occurrences.text);
  }
  const html=(await findOccurrences(page,app,app.occurrences.html)).result;
  expect(html.page.total).toBe(1);
  expect(html.occurrences[0].excerpt).toContain(app.occurrences.html);
  await expect(page.locator('#occurrence-list')).toContainText(app.occurrences.html);
  await expect(page.locator('#occurrence-list img,#occurrence-list [onerror],#occurrence-list [onload]')).toHaveCount(0);
  expect(await page.evaluate(()=>globalThis.ownedOccurrenceInjected)).toBeUndefined();
  await page.setViewportSize({width:390,height:844});
  await noHorizontalOverflow(page);
  await page.screenshot({path:testInfo.outputPath('module-occurrence-unicode-inert-narrow.png'),fullPage:true});
  await page.locator('#occurrence-query').fill('');
  await expect(page.locator('#occurrence-list button')).toHaveCount(0);
  await expect(page.locator('#occurrence-range')).toBeEmpty();
  await expect(page.locator('#occurrence-highlight')).toHaveCount(0);
  const absent=(await findOccurrences(page,app,app.occurrences.query.toLowerCase())).result;
  expect(absent.page.total).toBe(0);
  expect(absent.coverage).toEqual({complete:true,characters_scanned:app.occurrences.characters});
  await expect(page.locator('#occurrence-list button')).toHaveCount(0);
  await expect(page.locator('#occurrence-status')).toContainText('Найдено 0 вхождений');
  await page.locator('#occurrence-query').fill('');
  await expect(page.locator('#occurrence-previous')).toBeDisabled();
  await expect(page.locator('#occurrence-next')).toBeDisabled();
  await expect(page.locator('#occurrence-highlight')).toHaveCount(0);
  await expect(page.locator('#occurrence-list button')).toHaveCount(0);
  await expect(page.locator('#toast')).not.toBeVisible();
});

test('late genuine module occurrences cannot overwrite query, clear, cancellation, tab, module, source mode or imported archive',async({page,app})=>{
  await importOccurrences(page,app);
  const gates=[];let nextGate;
  function holdNext(){
    let release,reached,delivered;
    const hold=new Promise(resolve=>release=resolve),seen=new Promise(resolve=>reached=resolve),sent=new Promise(resolve=>delivered=resolve);
    nextGate={release,reached,delivered,hold,seen,sent};gates.push(nextGate);return nextGate;
  }
  const pattern=`${app.origin}/api/occurrences?*`;
  await page.route(pattern,async route=>{
    const response=await route.fetch(),reply=await response.json();let gate;
    if(nextGate&&reply.status==='ready'&&reply.query===app.occurrences.overlap_query){
      expect(reply.result.page.total).toBe(401);gate=nextGate;nextGate=null;gate.reached();await gate.hold;
    }
    await deliverHeld(route,response,gate);
  });
  async function pending(){
    const gate=holdNext();await page.locator('#occurrence-query').fill(app.occurrences.overlap_query);
    await page.locator('#occurrence-find').click();await gate.seen;return gate;
  }
  async function release(gate){gate.release();await gate.sent;await frames(page);}
  try{
    // Lose only the response to a real allocation. Recovery must cancel the
    // same import with a nullable ID, without replaying the start or disclosing
    // the worker result whose operation identity never reached the browser.
    let lostStart,allocated=0;
    const startPattern=`${app.origin}/api/occurrences-start`;
    await page.route(startPattern,async route=>{
      lostStart=route.request().postDataJSON();
      const response=await route.fetch();expect(response.status()).toBe(201);allocated++;
      await route.abort('failed');
    });
    const recovery=page.waitForRequest(request=>request.url()===`${app.origin}/api/occurrences-cancel`&&request.postDataJSON().occurrence===null);
    await page.locator('#occurrence-query').fill(app.occurrences.overlap_query);
    await page.locator('#occurrence-find').click();
    expect((await recovery).postDataJSON()).toEqual({job:lostStart.job,input_sha256:app.archives.occurrences.sha256,occurrence:null});
    await expect(page.locator('#occurrence-status')).toContainText('Поиск в модуле не завершён');
    await expect(page.locator('#occurrence-list button')).toHaveCount(0);
    expect(allocated).toBe(1);
    await page.unroute(startPattern);
    await findOccurrences(page,app,app.occurrences.query);
    await expect(page.locator('#occurrence-list button')).toHaveCount(3);
    const query=await pending();
    await page.locator('#occurrence-query').fill(app.occurrences.query);await release(query);
    await expect(page.locator('#occurrence-list button')).toHaveCount(0);
    await findOccurrences(page,app,app.occurrences.query);
    await expect(page.locator('#occurrence-list button')).toHaveCount(3);
    const clear=await pending();await page.locator('#occurrence-query').fill('');await release(clear);
    await expect(page.locator('#occurrence-list button')).toHaveCount(0);
    await expect(page.locator('#occurrence-previous')).toBeDisabled();
    await expect(page.locator('#occurrence-next')).toBeDisabled();
    const cancelled=await pending();await page.locator('#occurrence-cancel').click();await release(cancelled);
    await expect(page.locator('#occurrence-list button')).toHaveCount(0);
    await expect(page.locator('#occurrence-status')).toContainText(/отмен/i);
    const tab=await pending();await page.getByRole('tab',{name:'Происхождение',exact:true}).click();await release(tab);
    await expect(page.locator('#detail-content')).toContainText(app.occurrences.raw_sha256);
    await expect(page.locator('#occurrence-query')).toHaveCount(0);
    await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
    await expect(page.locator('#occurrence-query')).toBeVisible();
    await expect(page.locator('#occurrence-list button')).toHaveCount(0);
    const module=await pending();await page.locator('#item-list button').filter({hasText:'ZOther.os'}).click();
    await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();await release(module);
    await expect(page.getByLabel('Исходный код',{exact:true})).toHaveText(app.occurrences.other_text);
    await expect(page.locator('#occurrence-list button')).toHaveCount(0);
    // Also hold a genuine verified source reply: a former module's source must
    // never create occurrence controls bound to a newly selected module.
    let releaseSource,reachedSource,deliveredSource;
    const sourceHold=new Promise(resolve=>releaseSource=resolve),sourceSeen=new Promise(resolve=>reachedSource=resolve),sourceSent=new Promise(resolve=>deliveredSource=resolve);
    gates.push({release:releaseSource});
    const sourcePattern=`${app.origin}/api/source?*`;
    await page.route(sourcePattern,async route=>{
      const response=await route.fetch();
      if(new URL(route.request().url()).searchParams.get('path')===app.occurrences.path){
        reachedSource();await sourceHold;await deliverHeld(route,response,{delivered:deliveredSource});
      }else await route.fulfill({response});
    });
    await page.locator('#item-list button').filter({hasText:'AOccurrences.bsl'}).click();
    await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();await sourceSeen;
    await page.locator('#item-list button').filter({hasText:'ZOther.os'}).click();
    await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
    releaseSource();await sourceSent;await frames(page);
    await expect(page.getByLabel('Исходный код',{exact:true})).toHaveText(app.occurrences.other_text);
    await expect(page.locator('#occurrence-list button')).toHaveCount(0);
    const other=(await findOccurrences(page,app,'other-only')).result;
    expect(other.page.total).toBe(1);
    expect(other.input_ref).toEqual({relative_path:app.occurrences.other_path,
      raw_sha256:app.occurrences.other_sha256,input_sha256:app.archives.occurrences.sha256});
    await expect(page.locator('#occurrence-list button')).toHaveCount(1);
    await page.unroute(sourcePattern);
    await page.locator('#item-list button').filter({hasText:'AOccurrences.bsl'}).click();
    await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
    await expect(page.locator('#occurrence-query')).toBeVisible();
    const mode=await pending();await page.getByLabel('Режим поиска модулей',{exact:true}).selectOption('source');await release(mode);
    await expect(page.locator('#occurrence-list button')).toHaveCount(0);
    await page.locator('#search').fill(app.occurrences.query);
    await expect(page.locator('#search-status-text')).toContainText('Найдено 1 файлов с фрагментом');
    await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
    await expect(page.locator('#occurrence-query')).toHaveValue(app.occurrences.query);
    const replaced=await pending();await importZip(page,app.archives.first.path);await ready(page,'first.zip');await release(replaced);
    await expect(page.locator('#detail-panel h2')).toHaveText('Products');
    await expect(page.locator('#occurrence-query')).toHaveCount(0);
    await expect(page.locator('#detail-content')).not.toContainText(app.occurrences.raw_sha256);
    await expect(page.locator('#toast')).not.toBeVisible();
  }finally{for(const gate of gates)gate.release();await page.unrouteAll({behavior:'wait'});}
});
