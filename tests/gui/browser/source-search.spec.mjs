import {test,expect,importZip,ready} from './fixtures.mjs';

async function sourceMode(page){
  await page.locator('[data-view="modules"]').click();
  await expect(page.locator('#module-search-mode')).toHaveAccessibleName('Режим поиска модулей');
  await page.getByLabel('Режим поиска модулей',{exact:true}).selectOption('source');
  await expect(page.locator('#module-search-mode')).toHaveAccessibleName('Режим поиска модулей');
  await expect(page.locator('#source-search-help')).toBeVisible();
  await expect(page.getByRole('searchbox',{name:'Поиск точного фрагмента кода',exact:true})).toBeVisible();
  await expect(page.locator('#item-list button')).toHaveCount(0);
}

test('literal source search pages first hits and opens rehashed line with explicit partial coverage',async({page,app},testInfo)=>{
  await importZip(page,app.archives.source.path);
  await expect(page.locator('#metric-modules')).toHaveText('204');
  await sourceMode(page);
  await page.locator('#search').fill(app.source_query);
  await expect(page.locator('#search-status-text')).toContainText('Найдено 201 файлов с фрагментом');
  await expect(page.locator('#source-coverage')).toContainText('Частичное покрытие: проверено 201 из 204');
  await expect(page.locator('#source-coverage')).toContainText('больше 256 КиБ — 1, не UTF-8 — 1, управляющие символы — 1');
  await expect(page.locator('#item-list button')).toHaveCount(200);
  await page.locator('#next-page').click();
  await expect(page.locator('#page-range')).toHaveText('Строки 201–201 из 201');
  await expect(page.locator('#item-list button')).toHaveCount(1);
  await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
  await expect(page.getByLabel('Исходный код',{exact:true})).toHaveText(app.source_module);
  await expect(page.locator('.source-hit')).toContainText('строка 2');
  await expect(page.getByLabel('Первое совпадение',{exact:true})).toContainText(app.source_query+' 200');
  await page.getByRole('tab',{name:'Происхождение',exact:true}).click();
  await expect(page.locator('#detail-content')).toContainText(app.source_module_sha256);
  await expect(page.locator('#detail-content')).toContainText(app.archives.source.sha256);
  await expect(page.locator('#toast')).not.toBeVisible();
  await page.screenshot({path:testInfo.outputPath('literal-source-partial-provenance.png'),fullPage:true});
  await page.locator('#search').fill(app.source_html);
  await expect(page.locator('#search-status-text')).toContainText('201 файлов с фрагментом');
  await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
  await expect(page.getByLabel('Первое совпадение',{exact:true})).toContainText(app.source_html);
  await expect(page.locator('.source-hit img')).toHaveCount(0);
  expect(await page.evaluate(()=>globalThis.ownedSourceInjected)).toBeUndefined();
  await page.locator('#search').fill('absent-owned-fragment');
  await expect(page.locator('#no-results')).toContainText('Совпадений в проверенных файлах нет');
  await expect(page.locator('#source-coverage')).toContainText('не исключает их в пропущенных файлах');
  await page.locator('#search').fill(app.source_query.toLowerCase());
  await expect(page.locator('#no-results')).toBeVisible();
  await page.locator('[data-view="objects"]').click();
  await expect(page.locator('#detail-panel h2')).toHaveText('SourceOwner');
  await page.locator('#discover-related-modules').click();
  await expect(page.locator('#search-status-text')).toContainText('Catalogs/SourceOwner.xml');
  await expect(page.locator('#module-search-mode')).toHaveAccessibleName('Режим поиска модулей');
  await page.getByLabel('Режим поиска модулей',{exact:true}).selectOption('source');
  await expect(page.locator('#module-search-mode')).toHaveAccessibleName('Режим поиска модулей');
  await page.locator('#search').fill(app.source_query);
  await expect(page.locator('#search-status-text')).toContainText('201 файлов с фрагментом');
  await expect(page.locator('#search-status-text')).toContainText('Catalogs/SourceOwner.xml');
});

test('late real source search cannot overwrite new query, mode, cancellation or import',async({page,app})=>{
  await importZip(page,app.archives.source.path);await expect(page.locator('#metric-modules')).toHaveText('204');
  await sourceMode(page);
  let nextGate;const gates=[];
  function holdNext(){let release,reached;const hold=new Promise(r=>{release=r;});const ready=new Promise(r=>{reached=r;});nextGate={release,reached,hold,ready};gates.push(nextGate);return nextGate;}
  await page.route(`${app.origin}/api/search?*`,async route=>{
    const response=await route.fetch(),data=await response.json();
    if(nextGate&&data.kind==='source'&&data.query===app.source_query&&data.status==='ready'){const gate=nextGate;nextGate=null;gate.reached();await gate.hold;}
    await route.fulfill({response});
  });
  try{
    const query=holdNext();await page.locator('#search').fill(app.source_query);await query.ready;
    await page.locator('#search').fill('absent-owned-fragment');query.release();await expect(page.locator('#no-results')).toBeVisible();
    await page.locator('#search').fill(app.source_query);
    await expect(page.locator('#search-status-text')).toContainText('201 файлов с фрагментом');
    let releasePreview,reachedPreview,deliveredPreview;
    const previewHold=new Promise(r=>{releasePreview=r;}),previewReady=new Promise(r=>{reachedPreview=r;}),previewDelivered=new Promise(r=>{deliveredPreview=r;});
    gates.push({release:releasePreview});
    await page.route(`${app.origin}/api/source?*`,async route=>{const response=await route.fetch();reachedPreview();await previewHold;await route.fulfill({response});deliveredPreview();});
    await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();await previewReady;
    await page.getByLabel('Режим поиска модулей',{exact:true}).selectOption('modules');
    releasePreview();await previewDelivered;await page.unroute(`${app.origin}/api/source?*`);
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    await expect(page.locator('.source-hit')).not.toBeVisible();
    await expect(page.locator('#module-search-mode')).toHaveAccessibleName('Режим поиска модулей');
    await page.getByLabel('Режим поиска модулей',{exact:true}).selectOption('source');
    await expect(page.locator('#module-search-mode')).toHaveAccessibleName('Режим поиска модулей');
    await page.locator('#search').fill('');
    const mode=holdNext();await page.locator('#search').fill(app.source_query);await mode.ready;
    await page.getByLabel('Режим поиска модулей',{exact:true}).selectOption('modules');mode.release();
    await page.locator('#search').fill('Code200');await expect(page.locator('#item-list button')).toHaveCount(1);
    await expect(page.locator('#source-coverage')).not.toBeVisible();
    await expect(page.locator('#module-search-mode')).toHaveAccessibleName('Режим поиска модулей');
    await page.getByLabel('Режим поиска модулей',{exact:true}).selectOption('source');
    await expect(page.locator('#module-search-mode')).toHaveAccessibleName('Режим поиска модулей');
    const cancelled=holdNext();await page.locator('#search').fill(app.source_query);await cancelled.ready;
    await page.locator('#cancel-search').click();cancelled.release();
    await expect(page.locator('#item-list button')).toHaveCount(0);await expect(page.locator('#source-coverage')).not.toBeVisible();
    const replaced=holdNext();await page.locator('#search').fill(app.source_query);await replaced.ready;
    await importZip(page,app.archives.first.path);await ready(page,'first.zip');replaced.release();
    await page.unrouteAll({behavior:'wait'});await expect(page.locator('#detail-panel h2')).toHaveText('Products');
    await expect(page.locator('#source-search-help')).not.toBeVisible();
  }finally{for(const gate of gates)gate.release();await page.unrouteAll({behavior:'wait'});}
});
