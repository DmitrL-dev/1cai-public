import {writeFile} from 'node:fs/promises';
import {test,expect,importZip,ready,noHorizontalOverflow} from './fixtures.mjs';

const region=page=>page.getByRole('region',{name:'Построчное сравнение выбранного файла',exact:true});
const rows=page=>region(page).locator('.comparison-diff-row');
const next=page=>region(page).getByRole('button',{name:'Следующие строки',exact:true});
const retry=page=>region(page).getByRole('button',{name:'Повторить сравнение строк',exact:true});
async function openDiff(page,app){
  await importZip(page,app.line_diff.archives.before.path);
  await expect(page.locator('#progress-dialog')).not.toBeVisible();
  await expect(page.locator('#page-subtitle')).toContainText('line-diff-before.zip');
  await page.locator('[data-view="comparison"]').click();
  await page.locator('#compare-file').setInputFiles(app.line_diff.archives.after.path);
  await expect(page.locator('#compare-list button')).toHaveCount(13);
}
function reply(page,app,path,offset=0){
  return page.waitForResponse(response=>response.url()===`${app.origin}/api/comparison-line-diff`&&
    response.request().postDataJSON().path===path&&response.request().postDataJSON().offset===offset)
    .then(async response=>{expect(response.status()).toBe(200);return {request:response.request().postDataJSON(),result:await response.json()};});
}
async function select(page,app,path){
  const received=reply(page,app,path);
  await page.locator('#compare-list button').filter({hasText:path}).click();
  const data=await received;
  await expect(region(page).getByRole('status')).not.toContainText('Вычисляем');
  return data;
}
async function exactRows(page,expected){
  await expect(rows(page)).toHaveCount(expected.length);
  expect(await rows(page).evaluateAll(elements=>elements.map(element=>({
    kind:['equal','delete','insert'].find(kind=>element.classList.contains(`diff-${kind}`)),
    text:element.querySelector('.comparison-diff-text').textContent,
    location:element.querySelector('.comparison-diff-location').textContent,
  })))).toEqual(expected.map(row=>({kind:row.kind,text:row.text,location:
    `${{equal:'= Совпадает',delete:'− Удалено',insert:'+ Добавлено'}[row.kind]} · До ${row.before_line??'—'} · После ${row.after_line??'—'} · ${row.eol==='none'?'без окончания строки':row.eol}`})));
}

const unicodeRows=[
  {kind:'equal',before_line:1,after_line:1,text:'// Кириллица 😀 <img src=x onerror=globalThis.ownedLineDiffInjected=true>',eol:'CRLF'},
  {kind:'delete',before_line:2,after_line:null,text:'старое',eol:'CR'},
  {kind:'insert',before_line:null,after_line:2,text:'новое',eol:'LF'},
  {kind:'equal',before_line:3,after_line:3,text:'хвост',eol:'none'},
];

test('exact Unicode lines, inert markup, endings and BOM retain both byte-bound originals',async({page,app},testInfo)=>{
  await openDiff(page,app);const {request,result}=await select(page,app,'AUnicode.bsl');
  expect(Object.keys(request).sort()).toEqual(['after_sha256','before_sha256','offset','page','pair','path']);
  expect(request).toMatchObject({before_sha256:app.line_diff.archives.before.sha256,after_sha256:app.line_diff.archives.after.sha256,path:'AUnicode.bsl',offset:0});
  expect(result).toMatchObject({...request,status:'complete',reason:null,coverage:{alignment:'complete',full_scan:true},
    pagination:{offset:0,limit:200,total:4,returned:4,has_previous:false,has_next:false}});
  expect(result.rows).toEqual(unicodeRows);await exactRows(page,unicodeRows);
  for(const side of ['before','after']){
    const source=app.line_diff.files['AUnicode.bsl'][side];
    expect(result.input_refs[side]).toEqual({relative_path:'AUnicode.bsl',input_sha256:app.line_diff.archives[side].sha256,raw_sha256:source.sha256,size_bytes:source.size_bytes});
    await expect(region(page).locator('.comparison-diff-evidence')).toContainText(source.sha256);
    // DOM textContent preserves literal CR and BOM; toHaveText normalizes them.
    expect(await page.getByLabel(side==='before'?'Код до':'Код после',{exact:true}).textContent()).toBe(source.text.replace(/^\uFEFF/,''));
  }
  expect(result.before).toMatchObject({bom:true,line_count:3,newlines:{CRLF:1,CR:1,LF:0},final_newline:false});
  expect(result.after).toMatchObject({bom:false,line_count:3,newlines:{CRLF:1,CR:0,LF:1},final_newline:false});
  await expect(page.locator('#compare-source img')).toHaveCount(0);
  expect(await page.evaluate(()=>globalThis.ownedLineDiffInjected)).toBeUndefined();
  await expect(page.locator('#toast')).not.toBeVisible();
  await region(page).scrollIntoViewIfNeeded();await noHorizontalOverflow(page);
  await page.screenshot({path:testInfo.outputPath('line-diff-unicode.png'),fullPage:true});
  const newline=await select(page,app,'BNewline.os');
  expect(newline.result.rows).toEqual([{kind:'delete',before_line:1,after_line:null,text:'одинаково',eol:'CRLF'},
    {kind:'insert',before_line:null,after_line:1,text:'одинаково',eol:'LF'}]);await exactRows(page,newline.result.rows);
  const bom=await select(page,app,'CBom.bsp');
  expect(bom.result.before.bom).toBe(true);expect(bom.result.after.bom).toBe(false);
  expect(bom.result.rows).toEqual([{kind:'equal',before_line:1,after_line:1,text:'одинаково',eol:'LF'}]);
  await expect(region(page).locator('.comparison-diff-evidence')).toContainText('BOM: есть');
  await expect(region(page).locator('.comparison-diff-evidence')).toContainText('BOM: нет');
  // Exactly one leading BOM is encoding evidence. A second leading BOM and
  // a U+FEFF at the start of an interior line are literal source characters.
  for(const [path,line,hasBom] of [['LDoubleBom.bsl',1,true],['MInteriorBom.bsl',2,false]]){
    const {result:found}=await select(page,app,path);
    const expected=[...(line===2?[{kind:'equal',before_line:1,after_line:1,text:'начало',eol:'LF'}]:[]),
      {kind:'delete',before_line:line,after_line:null,text:'\uFEFFстарое',eol:'LF'},
      {kind:'insert',before_line:null,after_line:line,text:'\uFEFFновое',eol:'LF'}];
    expect(found.rows).toEqual(expected);expect(found.before.bom).toBe(hasBom);expect(found.after.bom).toBe(hasBom);
    await exactRows(page,expected);
    for(const side of ['before','after']){
      const text=app.line_diff.files[path][side].text.replace(/^\uFEFF/,'');
      expect(await page.getByLabel(side==='before'?'Код до':'Код после',{exact:true}).textContent()).toBe(text);
    }
  }
});

test('absent and empty sides are distinct while unavailable alignments leave originals readable',async({page,app})=>{
  await openDiff(page,app);
  for(const [path,absent] of [['DEmptyAdded.bsl','before'],['EEmptyDeleted.bsl','after']]){
    const {result}=await select(page,app,path);const present=absent==='before'?'after':'before';
    expect(result[absent]).toMatchObject({present:false,size_bytes:null,line_count:null});
    expect(result[present]).toMatchObject({present:true,size_bytes:0,line_count:0});
    expect(result.input_refs[absent]).toBeNull();expect(result.rows).toEqual([]);
    await expect(region(page)).toContainText('файл отсутствует (это не пустой файл)');
    await expect(region(page)).toContainText('пустой текст');await expect(rows(page)).toHaveCount(0);
  }
  for(const [path,kind] of [['FAdded.os','insert'],['GDeleted.os','delete']]){
    const {result}=await select(page,app,path);expect(result.rows).toHaveLength(1);expect(result.rows[0].kind).toBe(kind);await exactRows(page,result.rows);
  }
  const limited=await select(page,app,'IWorkLimit.bsl');
  expect(limited.result).toMatchObject({status:'unavailable',reason:'WORK_LIMIT',rows:[],coverage:{alignment:'unavailable',full_scan:false},pagination:{total:0,returned:0}});
  await expect(region(page)).toContainText('превышен предел работы');await expect(rows(page)).toHaveCount(0);
  for(const side of ['before','after'])await expect(page.getByLabel(side==='before'?'Код до':'Код после',{exact:true})).toHaveText(app.line_diff.files['IWorkLimit.bsl'][side].text);
  const invalid=await select(page,app,'JInvalid.bsl');expect(invalid.result.reason).toBe('SOURCE_ENCODING_UNSUPPORTED');
  await expect(rows(page)).toHaveCount(0);await expect(next(page)).toBeDisabled();
  await expect(page.getByRole('region',{name:'Исходник до',exact:true})).toContainText('не является UTF-8');
});

test('402 complete rows page at 200 with exact final line and keyboard controls',async({page,app})=>{
  await openDiff(page,app);const first=await select(page,app,'HPaged.bsl');
  expect(first.result.pagination).toEqual({offset:0,limit:200,total:402,returned:200,has_previous:false,has_next:true});
  await expect(rows(page)).toHaveCount(200);
  await next(page).focus();let received=reply(page,app,'HPaged.bsl',200);await page.keyboard.press('Enter');
  const second=await received;expect(second.request).toEqual({...first.request,offset:200});
  await exactRows(page,second.result.rows);expect(second.result.rows[0].before_line).toBe(201);
  await expect(next(page)).toBeFocused();received=reply(page,app,'HPaged.bsl',400);await page.keyboard.press('Enter');
  const last=await received;expect(last.result.pagination).toEqual({offset:400,limit:200,total:402,returned:2,has_previous:true,has_next:false});
  expect(last.result.rows).toEqual([{kind:'equal',before_line:401,after_line:401,text:'строка 400',eol:'LF'},
    {kind:'insert',before_line:null,after_line:402,text:'конец',eol:'none'}]);await exactRows(page,last.result.rows);
  await expect(next(page)).toBeDisabled();await expect(retry(page)).toBeFocused();
  received=reply(page,app,'HPaged.bsl',200);await region(page).getByRole('button',{name:'Предыдущие строки',exact:true}).click();await received;await expect(rows(page)).toHaveCount(200);
});

async function frames(page){await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));}
async function holdDiff(page,app,path){
  let release,observed,delivered;const hold=new Promise(resolve=>release=resolve),seen=new Promise(resolve=>observed=resolve),sent=new Promise(resolve=>delivered=resolve);
  const pattern=`${app.origin}/api/comparison-line-diff`;
  const handler=async route=>{
    const response=await route.fetch();
    if(route.request().postDataJSON().path!==path){await route.fulfill({response});return;}
    observed();await hold;
    try{await route.fulfill({response});}catch(error){if(!/abort|cancel|Invalid InterceptionId/i.test(route.request().failure()?.errorText||String(error)))throw error;}finally{delivered();}
  };
  await page.route(pattern,handler);
  return {seen,release:async()=>{release();await sent;await page.unroute(pattern,handler);await frames(page);},cleanup:release};
}

test('cancel, newer selection, inventory filter and navigation suppress delayed genuine diff replies',async({page,app})=>{
  await openDiff(page,app);const gates=[];
  async function pending(){const gate=await holdDiff(page,app,'KLongLine.os');gates.push(gate);await page.locator('#compare-list button').filter({hasText:'KLongLine.os'}).click();await gate.seen;return gate;}
  try{
    const cancelled=await pending();await region(page).getByRole('button',{name:'Отменить ожидание строк',exact:true}).click();await cancelled.release();
    await expect(region(page)).toContainText('Ожидание строк отменено');await expect(rows(page)).toHaveCount(0);await expect(retry(page)).toBeFocused();
    await expect(page.getByLabel('Код после',{exact:true})).toHaveText(app.line_diff.files['KLongLine.os'].after.text);
    const selection=await pending();await select(page,app,'AUnicode.bsl');await selection.release();await exactRows(page,unicodeRows);
    const filter=await pending();await page.getByLabel('Показать файлы',{exact:true}).selectOption('added');await filter.release();await expect(region(page)).toHaveCount(0);
    await page.getByLabel('Показать файлы',{exact:true}).selectOption('changes');await expect(page.locator('#compare-list button')).toHaveCount(13);
    const navigation=await pending();await page.locator('[data-view="objects"]').click();await navigation.release();await expect(page.locator('#compare-source')).toBeEmpty();
    await page.locator('[data-view="comparison"]').click();await expect(page.locator('#compare-list button')).toHaveCount(13);
    const replacement=await pending();await importZip(page,app.archives.first.path);await ready(page,'first.zip');await replacement.release();
    await page.locator('[data-view="comparison"]').click();await expect(page.locator('#compare-result')).not.toBeVisible();await expect(region(page)).toHaveCount(0);
  }finally{for(const gate of gates)gate.cleanup();await page.unrouteAll({behavior:'wait'});}
});

test('390px inline diff wraps long exact text without page overflow or transient toast',async({page,app},testInfo)=>{
  await page.setViewportSize({width:390,height:844});await openDiff(page,app);await select(page,app,'AUnicode.bsl');
  await exactRows(page,unicodeRows);await noHorizontalOverflow(page);await expect(page.locator('#toast')).not.toBeVisible();
  await region(page).scrollIntoViewIfNeeded();await page.screenshot({path:testInfo.outputPath('line-diff-390px.png'),fullPage:true});
  await select(page,app,'KLongLine.os');await expect(rows(page)).toHaveCount(2);await noHorizontalOverflow(page);
  expect(await rows(page).first().locator('pre').textContent()).toBe('x'.repeat(18000));
});

test('real Chromium 200 percent zoom keeps inline line navigation operable',async({page,context,app},testInfo)=>{
  const worker=context.serviceWorkers()[0]||await context.waitForEvent('serviceworker');
  const before=await page.evaluate(()=>({width:innerWidth,dpr:devicePixelRatio}));
  expect(await worker.evaluate(async()=>{const tabs=await chrome.tabs.query({active:true,lastFocusedWindow:true});if(tabs.length!==1)throw new Error('Expected one owned active test tab');await chrome.tabs.setZoomSettings(tabs[0].id,{mode:'automatic',scope:'per-tab'});await chrome.tabs.setZoom(tabs[0].id,2);return chrome.tabs.getZoom(tabs[0].id);})).toBe(2);
  await expect.poll(()=>page.evaluate(()=>devicePixelRatio)).toBe(before.dpr*2);
  expect(Math.abs(await page.evaluate(()=>innerWidth)-before.width/2)).toBeLessThanOrEqual(1);
  await openDiff(page,app);await select(page,app,'HPaged.bsl');const received=reply(page,app,'HPaged.bsl',200);await next(page).click();await received;await expect(rows(page)).toHaveCount(200);await noHorizontalOverflow(page);
  await select(page,app,'AUnicode.bsl');await expect(page.locator('#toast')).not.toBeVisible();await region(page).scrollIntoViewIfNeeded();
  const viewport=await page.evaluate(()=>({width:innerWidth,height:innerHeight,dpr:devicePixelRatio}));const cdp=await context.newCDPSession(page);let png;
  try{const capture=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});png=Buffer.from(capture.data,'base64');}finally{await cdp.detach();}
  expect(png.subarray(0,8).toString('hex')).toBe('89504e470d0a1a0a');expect(Math.abs(png.readUInt32BE(16)-viewport.width*viewport.dpr)).toBeLessThanOrEqual(2);expect(Math.abs(png.readUInt32BE(20)-viewport.height*viewport.dpr)).toBeLessThanOrEqual(2);
  await writeFile(testInfo.outputPath('line-diff-200-percent.png'),png);
});
