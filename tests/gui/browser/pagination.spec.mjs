import {test, expect, importZip, ready, keyboardReach} from './fixtures.mjs';

async function pageRange(page,start,end,total=401){
  await expect(page.locator('#page-range')).toHaveText(`Строки ${start}–${end} из ${total}`);
  await expect(page.locator('#item-list button')).toHaveCount(end-start+1);
}
async function go(page,direction,start,end){
  await page.locator(direction>0?'#next-page':'#previous-page').click();
  await pageRange(page,start,end);
}

test('browse all 401 objects and modules with bounded pages, back, queries and related source',async({page,app},testInfo)=>{
  await importZip(page,app.archives.paged.path);
  await expect(page.locator('#metric-objects')).toHaveText('401');
  await expect(page.locator('#metric-modules')).toHaveText('401');
  await pageRange(page,1,200);
  await expect(page.locator('#previous-page')).toBeDisabled();
  const names=await page.locator('#item-list strong').allTextContents();
  await keyboardReach(page,page.locator('#next-page'));
  await page.keyboard.press('Enter');
  await pageRange(page,201,400);
  await expect(page.locator('#next-page')).toBeFocused();
  names.push(...await page.locator('#item-list strong').allTextContents());
  await page.keyboard.press('Enter');
  await pageRange(page,401,401);
  await expect(page.locator('#previous-page')).toBeFocused();
  await expect(page.locator('#next-page')).toBeDisabled();
  names.push(...await page.locator('#item-list strong').allTextContents());
  expect(names).toEqual(Array.from({length:401},(_,i)=>`ОбъектСтраницы${String(i).padStart(3,'0')}`));
  await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
  await expect(page.getByLabel('Исходный код',{exact:true})).toHaveText(app.page_xml);
  await page.getByRole('tab',{name:'Происхождение',exact:true}).click();
  await expect(page.locator('#detail-content')).toContainText(app.page_xml_sha256);
  await expect(page.locator('#detail-content')).toContainText(app.archives.paged.sha256);
  await go(page,-1,201,400);await go(page,-1,1,200);
  await page.locator('#search').fill('ОБЪЕКТСТРАНИЦЫ');
  await expect(page.locator('#search-status-text')).toContainText('Найдено 401 по всему ZIP');
  await go(page,1,201,400);await go(page,1,401,401);
  await page.locator('#discover-related-modules').click();
  await expect(page.locator('#search-status-text')).toContainText('Catalogs/Page400.xml');
  await pageRange(page,1,200);
  await page.locator('#search').fill('МОДУЛЬ');
  await expect(page.locator('#search-status-text')).toContainText('Найдено 401 по всему ZIP');
  await go(page,1,201,400);await go(page,1,401,401);
  await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
  await expect(page.getByLabel('Исходный код',{exact:true})).toHaveText(app.page_module);
  await page.getByRole('tab',{name:'Происхождение',exact:true}).click();
  await expect(page.locator('#detail-content')).toContainText(app.page_module_sha256);
  await expect(page.locator('#detail-content')).toContainText(app.archives.paged.sha256);
  await expect(page.locator('#toast')).not.toBeVisible();
  await page.screenshot({path:testInfo.outputPath('pagination-final-module-provenance.png'),fullPage:true});
  await go(page,-1,201,400);await go(page,-1,1,200);
  await page.locator('[data-view="modules"]').click();
  await pageRange(page,1,200);
  const paths=await page.locator('#item-list small').allTextContents();
  await go(page,1,201,400);paths.push(...await page.locator('#item-list small').allTextContents());
  await go(page,1,401,401);paths.push(...await page.locator('#item-list small').allTextContents());
  expect(paths).toEqual(Array.from({length:401},(_,i)=>`Catalogs/Page400/Ext/Модуль${String(i).padStart(3,'0')}.bsl`));
  await page.locator('#search').fill('МОДУЛЬ');
  await pageRange(page,1,200);
  await go(page,1,201,400);await go(page,1,401,401);
  await page.locator('#search').fill('missing-owned-path');
  await expect(page.locator('#no-results')).toBeVisible();
  await expect(page.locator('#next-page')).toBeDisabled();
});

test('late page responses cannot overwrite new query, view, cancelled page or import',async({page,app})=>{
  await importZip(page,app.archives.paged.path);
  await pageRange(page,1,200);
  let nextGate;const gates=[];
  function holdNextPage(){
    let release,reached;const hold=new Promise(r=>{release=r;});const ready=new Promise(r=>{reached=r;});
    nextGate={release,reached,hold,ready};gates.push(nextGate);return nextGate;
  }
  await page.route(`${app.origin}/api/search?*`,async route=>{
    const response=await route.fetch();const data=await response.json();
    if(nextGate&&data.status==='ready'&&data.offset===200){const gate=nextGate;nextGate=null;gate.reached();await gate.hold;}
    await route.fulfill({response});
  });
  try{
    const query=holdNextPage();await page.locator('#next-page').click();await query.ready;
    await page.locator('#search').fill('missing-owned-object');query.release();
    await expect(page.locator('#no-results')).toBeVisible();
    await page.locator('#search').fill('');await pageRange(page,1,200);
    const view=holdNextPage();await page.locator('#next-page').click();await view.ready;
    await page.locator('[data-view="modules"]').click();view.release();
    await pageRange(page,1,200);await expect(page.locator('#page-title')).toHaveText('Модули конфигурации');
    const cancelled=holdNextPage();await page.locator('#next-page').click();await cancelled.ready;
    await page.locator('#cancel-search').click();cancelled.release();await pageRange(page,1,200);
    await expect(page.locator('#search-status')).not.toBeVisible();
    const imported=holdNextPage();await page.locator('#next-page').click();await imported.ready;
    await importZip(page,app.archives.first.path);await ready(page,'first.zip');
    imported.release();await page.unrouteAll({behavior:'wait'});
    await expect(page.locator('#detail-panel h2')).toHaveText('Products');
    await expect(page.locator('#pagination')).not.toBeVisible();
    await expect(page.locator('#search-status')).not.toBeVisible();
  }finally{for(const gate of gates)gate.release();await page.unrouteAll({behavior:'wait'});}
});
