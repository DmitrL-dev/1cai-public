import {test,expect,importZip} from './fixtures.mjs';
import {openComparison,comparisonBeforeReady,lastComparisonSource} from './comparison-helpers.mjs';
const query='Кириллица 😀';
async function literalMode(page){
  await page.locator('[data-view="modules"]').click();
  await expect(page.locator('#module-search-mode')).toHaveAccessibleName('Режим поиска модулей');
  await page.getByLabel('Режим поиска модулей',{exact:true}).selectOption('source');
  await expect(page.getByRole('searchbox',{name:'Поиск точного фрагмента кода',exact:true})).toBeVisible();
  await expect(page.locator('#item-list button')).toHaveCount(0);
}
async function literalReady(page){
  await expect(page.locator('#search-status-text')).toContainText('Найдено 401 файлов');
  await expect(page.locator('#source-coverage')).toContainText('Частичное покрытие: проверено 402 из 403');
  await expect(page.locator('#item-list button')).toHaveCount(200);
}
async function deliveredFrames(page){await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));}

test('late literal-search result cannot overwrite comparison and both feature sources retain their own archive bindings',async({page,app})=>{
  await importZip(page,app.archives.compare_before.path);await comparisonBeforeReady(page);await literalMode(page);
  let release,observed,delivered;
  const held=new Promise(resolve=>release=resolve),seen=new Promise(resolve=>observed=resolve),sent=new Promise(resolve=>delivered=resolve);
  let taken=false;
  const pattern=`${app.origin}/api/search?*`;
  await page.route(pattern,async route=>{
    const response=await route.fetch();const reply=await response.json();
    if(!taken&&reply.kind==='source'&&reply.query===query&&reply.status==='ready'){
      taken=true;expect(reply.result.matching_modules).toBe(401);observed();await held;await route.fulfill({response});delivered();
    }else await route.fulfill({response});
  });
  try{
    await page.locator('#search').fill(query);await seen;
    await page.locator('[data-view="comparison"]').click();await expect(page.locator('#compare-file')).toBeEnabled();
    await page.locator('#compare-file').setInputFiles(app.archives.compare_after.path);
    await expect(page.locator('#compare-list button')).toHaveCount(200);
    release();await sent;await deliveredFrames(page);
    await expect(page.locator('#comparison-view')).toBeVisible();await expect(page.locator('#inventory-view')).not.toBeVisible();
    await expect(page.locator('#compare-counts')).toContainText('Изменены байты: 403');
    await lastComparisonSource(page,app);
  }finally{release();await page.unroute(pattern);}
  await literalMode(page);await page.locator('#search').fill(query);await literalReady(page);
  await page.locator('#next-page').click();await expect(page.locator('#page-range')).toHaveText('Строки 201–400 из 401');
  await page.locator('#next-page').click();await expect(page.locator('#page-range')).toHaveText('Строки 401–401 из 401');
  await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
  await expect(page.getByLabel('Исходный код',{exact:true})).toHaveText(app.compare_code.before);
  await page.getByRole('tab',{name:'Происхождение',exact:true}).click();
  await expect(page.locator('#detail-content')).toContainText(app.archives.compare_before.sha256);
  await expect(page.locator('#detail-content')).not.toContainText(app.archives.compare_after.sha256);
});

test('leaving a pending comparison cancels only its reservation and late comparison pages cannot replace literal search',async({page,app})=>{
  await openComparison(page,app);
  let releaseUpload,observedUpload;
  const heldUpload=new Promise(resolve=>releaseUpload=resolve),seenUpload=new Promise(resolve=>observedUpload=resolve);
  const uploadPattern=`${app.origin}/api/comparison-upload?*`;
  await page.route(uploadPattern,async route=>{observedUpload();await heldUpload;await route.abort('aborted');});
  try{
    await page.locator('#compare-file').setInputFiles(app.archives.compare_before.path);await seenUpload;
    const cancelled=page.waitForResponse(response=>response.url().endsWith('/api/comparison-cancel'));
    await literalMode(page);expect((await (await cancelled).json()).cancel_requested).toBe(true);
    releaseUpload();await page.locator('#search').fill(query);await literalReady(page);
  }finally{releaseUpload();await page.unroute(uploadPattern);}
  await page.locator('[data-view="comparison"]').click();await expect(page.locator('#compare-list button')).toHaveCount(200);
  await expect(page.locator('#compare-after')).toContainText(app.archives.compare_after.sha256);
  let releasePage,observedPage,delivered;
  const heldPage=new Promise(resolve=>releasePage=resolve),seenPage=new Promise(resolve=>observedPage=resolve),sent=new Promise(resolve=>delivered=resolve);
  const pattern=`${app.origin}/api/comparison-page`;
  await page.route(pattern,async route=>{const response=await route.fetch();expect((await response.json()).page.offset).toBe(200);observedPage();await heldPage;await route.fulfill({response});delivered();});
  try{
    await page.locator('#compare-next').click();await seenPage;await literalMode(page);
    await page.locator('#search').fill(query);await literalReady(page);
    releasePage();await sent;await deliveredFrames(page);
    await expect(page.locator('#inventory-view')).toBeVisible();await expect(page.locator('#comparison-view')).not.toBeVisible();
    await expect(page.locator('#compare-list')).toBeEmpty();await expect(page.locator('#compare-source')).toBeEmpty();
    await expect(page.locator('#search-status-text')).toContainText('Найдено 401 файлов');
  }finally{releasePage();await page.unroute(pattern);}
});
