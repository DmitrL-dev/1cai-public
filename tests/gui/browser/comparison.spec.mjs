import {test,expect,importZip,ready,keyboardReach} from './fixtures.mjs';
import {openComparison,lastComparisonSource,comparisonBeforeReady} from './comparison-helpers.mjs';

test('two explicit ZIPs yield complete paged byte counts and verified before/after sources',async({page,app},testInfo)=>{
  await openComparison(page,app);await lastComparisonSource(page,app);
  await page.screenshot({path:testInfo.outputPath('comparison-two-sources.png'),fullPage:true});
  await keyboardReach(page,page.locator('#compare-previous'));await page.keyboard.press('Enter');
  await expect(page.locator('#compare-range')).toHaveText('Файлы 201–400 из 405');
  await expect(page.locator('#compare-previous')).toBeFocused();await page.keyboard.press('Enter');
  await expect(page.locator('#compare-range')).toHaveText('Файлы 1–200 из 405');
  await expect(page.locator('#compare-next')).toBeFocused();
  await page.keyboard.press('Enter');await expect(page.locator('#compare-range')).toHaveText('Файлы 201–400 из 405');
  await expect(page.locator('#compare-next')).toBeFocused();await page.keyboard.press('Enter');
  await expect(page.locator('#compare-range')).toHaveText('Файлы 401–405 из 405');await expect(page.locator('#compare-previous')).toBeFocused();
  await page.getByLabel('Показать файлы',{exact:true}).selectOption('added');
  await expect(page.locator('#compare-list button')).toHaveCount(1);await page.locator('#compare-list button').click();
  await expect(page.getByRole('region',{name:'Исходник до',exact:true})).toContainText('Файл отсутствует');
  await expect(page.getByLabel('Код после',{exact:true})).toHaveText('after');
  await page.getByLabel('Показать файлы',{exact:true}).selectOption('modified');
  await page.getByRole('button',{name:'Изменены байты · Binary.bin',exact:true}).click();
  await expect(page.getByRole('region',{name:'Исходник после',exact:true})).toContainText('не является UTF-8');
  await page.getByLabel('ZIP после изменения',{exact:true}).setInputFiles(app.corrupt);
  await expect(page.locator('#compare-message')).toContainText('Этот формат ZIP не поддерживается');
  await expect(page.locator('#compare-after')).toContainText(app.archives.compare_after.sha256);
  await expect(page.locator('#compare-list button')).toHaveCount(200);
  await page.getByLabel('ZIP после изменения',{exact:true}).setInputFiles(app.archives.compare_before.path);
  await expect(page.locator('#compare-counts')).toHaveText('Всего путей: 405 · Добавлено: 0 · Удалено: 0 · Изменены байты: 0 · Без изменений: 405');
  await page.getByLabel('Показать файлы',{exact:true}).selectOption('changes');
  await expect(page.locator('#compare-range')).toHaveText('Нет файлов в выбранной категории');
  await expect(page.locator('#compare-list button')).toHaveCount(0);
});

test('lost genuine comparison readiness is read back without upload replay and continued outage stays unknown',async({page,app})=>{
  await importZip(page,app.archives.compare_before.path);await comparisonBeforeReady(page);
  await page.locator('[data-view="comparison"]').click();await expect(page.locator('#compare-file')).toBeEnabled();
  let uploads=0,starts=0,dropped=false,outage=false;
  page.on('request',request=>{if(request.url().includes('/api/comparison-upload?'))uploads++;if(request.url().endsWith('/api/comparison-start'))starts++;});
  await page.route(`${app.origin}/api/comparison?*`,async route=>{
    const response=await route.fetch();const data=await response.json();
    if(data.status==='ready'&&(!dropped||outage)){dropped=true;await route.abort('failed');}else await route.fulfill({response});
  });
  await page.locator('#compare-file').setInputFiles(app.archives.compare_after.path);
  await expect(page.locator('#compare-list button')).toHaveCount(200);expect(dropped).toBe(true);expect(uploads).toBe(1);expect(starts).toBe(1);
  outage=true;
  await page.locator('#compare-file').setInputFiles(app.archives.compare_before.path);
  await expect(page.locator('#compare-message')).toContainText('Исход операции неизвестен');
  await expect(page.locator('#compare-result')).not.toBeVisible();expect(uploads).toBe(2);expect(starts).toBe(2);
  outage=false;await page.locator('#compare-check').click();
  await expect(page.locator('#compare-counts')).toContainText('Без изменений: 405');
  expect(uploads).toBe(2);expect(starts).toBe(2);
});

test('cancelled replacement, late page/source replies and new import cannot resurrect an old comparison',async({page,app})=>{
  await openComparison(page,app);
  let release,observed;const held=new Promise(resolve=>release=resolve),seen=new Promise(resolve=>observed=resolve);
  await page.route(`${app.origin}/api/comparison-upload?*`,async route=>{observed();await held;await route.abort('aborted');});
  try{
    await page.locator('#compare-file').setInputFiles(app.archives.compare_before.path);await seen;
    const cancelled=page.waitForResponse(response=>response.url().endsWith('/api/comparison-cancel'));
    await page.locator('#compare-cancel').click();expect((await (await cancelled).json()).cancel_requested).toBe(true);
  }finally{release();await page.unrouteAll({behavior:'wait'});}
  await expect(page.locator('#compare-after')).toContainText(app.archives.compare_after.sha256);
  await expect(page.locator('#compare-list button')).toHaveCount(200);
  let releasePage,seenPage;const heldPage=new Promise(resolve=>releasePage=resolve),observedPage=new Promise(resolve=>seenPage=resolve);
  await page.route(`${app.origin}/api/comparison-page`,async route=>{const response=await route.fetch();seenPage();await heldPage;await route.fulfill({response});});
  try{await page.locator('#compare-next').click();await observedPage;await page.locator('[data-view="modules"]').click();}
  finally{releasePage();await page.unrouteAll({behavior:'wait'});}
  await expect(page.locator('#comparison-view')).not.toBeVisible();
  await page.locator('[data-view="comparison"]').click();await expect(page.locator('#compare-list button')).toHaveCount(200);
  let releaseSource,seenSource;const heldSource=new Promise(resolve=>releaseSource=resolve),observedSource=new Promise(resolve=>seenSource=resolve);
  await page.route(`${app.origin}/api/comparison-source?*`,async route=>{const response=await route.fetch();seenSource();await heldSource;await route.fulfill({response});});
  try{await page.getByRole('button',{name:'Изменены байты · CommonModules/Compare000.bsl',exact:true}).click();await observedSource;await page.locator('[data-view="objects"]').click();}
  finally{releaseSource();await page.unrouteAll({behavior:'wait'});}
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  await expect(page.locator('#compare-source')).toBeEmpty();
  await importZip(page,app.archives.first.path);await ready(page,'first.zip');
  await page.locator('[data-view="comparison"]').click();
  await expect(page.locator('#compare-before')).toContainText(app.archives.first.sha256);
  await expect(page.locator('#compare-result')).not.toBeVisible();await expect(page.locator('#compare-message')).toContainText('Принятой пары пока нет');
});
