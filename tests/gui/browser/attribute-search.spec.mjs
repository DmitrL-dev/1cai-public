import {test,expect,importZip,ready,noHorizontalOverflow} from './fixtures.mjs';

async function importAttributes(page,app){
  await importZip(page,app.archives.attributes.path);
  await expect(page.locator('#progress-dialog')).not.toBeVisible();
  await expect(page.locator('#metric-objects')).toHaveText('3');
  await expect(page.locator('#metric-modules')).toHaveText('0');
  await expect(page.locator('#attribute-search-help')).toBeVisible();
}

async function search(page,app,query,owners){
  const received=page.waitForResponse(async response=>{
    if(!response.url().startsWith(`${app.origin}/api/search?`))return false;
    const reply=await response.json();
    return reply.kind==='metadata'&&reply.status==='ready'&&reply.query===query;
  });
  await page.locator('#search').fill(query);
  const reply=await (await received).json();
  expect(reply.result.matching_objects).toBe(owners);
  await expect(page.locator('#search-status-text')).toContainText(`Найдено ${owners} по всему ZIP`);
  await expect(page.locator('#search-status-text')).toContainText('объекты-владельцы');
  await expect(page.locator('#item-list button')).toHaveCount(owners);
  return reply.result;
}

async function deliveredFrames(page){
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
}

test('attribute names and synonyms find unique owners with tabular context and exact XML provenance',async({page,app},testInfo)=>{
  await importAttributes(page,app);
  const result=await search(page,app,'КОНТРАГЕНТ',2);
  const owner=result.objects.find(row=>row.name==='Поставщики');
  expect(owner.child_matching_total).toBe(2);
  expect(owner.child_matches_truncated).toBe(false);
  expect(owner.child_matches).toHaveLength(2);
  expect(owner.child_matches.map(row=>row.name)).toEqual([app.attributes.name,app.attributes.name]);
  expect(owner.child_matches[0]).toMatchObject({type:'Attribute',observed_uuid:app.attributes.uuid,uuid_status:'unverified',child_index:1,parent_index:null,parent_name:null,parent_type:null});
  expect(owner.child_matches[1]).toMatchObject({type:'Attribute',parent_type:'TabularSection',parent_name:app.attributes.section_name,observed_uuid:'invalid-owned-uuid',uuid_status:'unverified',child_index:1,parent_index:2});
  expect(owner.input_ref).toMatchObject({relative_path:app.attributes.path,raw_sha256:app.attributes.xml_sha256,input_sha256:app.archives.attributes.sha256});
  expect(result.objects.find(row=>row.name==='Остатки').child_matches.map(row=>row.type)).toEqual(['Dimension','Resource']);
  await page.locator('#item-list button').filter({hasText:'Остатки'}).click();
  await expect(page.locator('.attribute-match')).toHaveCount(2);
  await expect(page.locator('.attribute-matches')).toContainText('Измерение (Dimension)');
  await expect(page.locator('.attribute-matches')).toContainText('Ресурс (Resource)');
  await page.locator('#item-list button').filter({hasText:'Поставщики'}).click();
  await expect(page.locator('.attribute-match')).toHaveCount(2);
  await expect(page.locator('.attribute-matches')).toContainText(app.attributes.section_name);
  await expect(page.locator('.attribute-matches')).toContainText(app.attributes.uuid);
  await expect(page.locator('.attribute-provenance')).toContainText(app.attributes.path);
  await expect(page.locator('.attribute-provenance')).toContainText(app.attributes.xml_sha256);
  await expect(page.locator('.attribute-provenance')).toContainText(app.archives.attributes.sha256);
  await expect(page.locator('#attribute-coverage')).toBeVisible();
  await expect(page.locator('#attribute-coverage')).toContainText('Полей проверено: 30; табличных частей: 1');
  await expect(page.locator('#attribute-coverage')).toContainText('не полный состав метаданных');
  await page.screenshot({path:testInfo.outputPath('attribute-owner-context-provenance.png'),fullPage:true});
  await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
  await expect(page.getByLabel('Исходный код',{exact:true})).toHaveText(app.attributes.xml);
  await page.getByRole('tab',{name:'Происхождение',exact:true}).click();
  await expect(page.locator('#detail-content')).toContainText(app.attributes.path);
  await expect(page.locator('#detail-content')).toContainText(app.attributes.xml_sha256);
  await expect(page.locator('#detail-content')).toContainText(app.archives.attributes.sha256);
  await search(page,app,app.attributes.synonym.toUpperCase(),1);
  await expect(page.locator('.attribute-match')).toHaveCount(1);
  await expect(page.locator('.attribute-match')).toContainText(app.attributes.synonym);
  const localized=await search(page,app,app.attributes.english_synonym.toLowerCase(),1);
  expect(localized.objects[0].name).toBe('Поставщики');
  expect(localized.objects[0].child_matching_total).toBe(1);
  expect(localized.objects[0].child_matches).toHaveLength(1);
  expect(localized.objects[0].child_matches[0]).toMatchObject({name:app.attributes.name,synonym:'SupplierSKU',synonym_locale:'en',child_index:1,parent_index:null});
  expect(localized.objects[0].input_ref).toMatchObject({relative_path:app.attributes.path,raw_sha256:app.attributes.xml_sha256,input_sha256:app.archives.attributes.sha256});
  await expect(page.locator('.attribute-match')).toHaveCount(1);
  await expect(page.locator('.attribute-match')).toContainText('Синоним (en): SupplierSKU');
  await expect(page.locator('.attribute-provenance')).toContainText(app.attributes.path);
  await search(page,app,app.attributes.nested_synonym.toUpperCase(),1);
  await expect(page.locator('.attribute-match')).toHaveCount(1);
  await expect(page.locator('.attribute-match')).toContainText(app.attributes.section_name);
  // Unrelated descendant containers and Properties are outside the documented scope.
  await search(page,app,'ВНЕОБЛАСТИПРОВЕРКИ',0);
  await expect(page.locator('#no-results')).toBeVisible();
  await expect(page.locator('#attribute-coverage')).toBeVisible();
  await expect(page.locator('#attribute-coverage')).toContainText('Полей проверено: 30; табличных частей: 1');
  await expect(page.locator('.attribute-matches')).toHaveCount(0);
  await expect(page.locator('#toast')).not.toBeVisible();
});

test('attribute details disclose the per-owner bound and render HTML-like names as inert text',async({page,app},testInfo)=>{
  await importAttributes(page,app);
  const result=await search(page,app,'МАССОВЫЙРЕКВИЗИТ',1);
  expect(result.objects[0].child_matching_total).toBe(25);
  expect(result.objects[0].child_matches_truncated).toBe(true);
  expect(result.objects[0].child_matches).toHaveLength(20);
  await expect(page.locator('#detail-panel h2')).toHaveText('Лимит');
  await expect(page.locator('.attribute-match')).toHaveCount(20);
  await expect(page.locator('.attribute-matches')).toContainText('Показано 20 из 25 совпавших полей');
  await expect(page.locator('.attribute-matches')).toContainText('Список совпадений сокращён до 20 полей');
  await expect(page.locator('.attribute-matches')).not.toContainText('МассовыйРеквизит24');
  await page.setViewportSize({width:390,height:844});
  await noHorizontalOverflow(page);
  await page.screenshot({path:testInfo.outputPath('attribute-bounded-narrow.png'),fullPage:true});
  await search(page,app,'ownedAttributeInjected',1);
  await expect(page.locator('.attribute-match')).toHaveCount(1);
  await expect(page.locator('.attribute-match')).toContainText(app.attributes.html_name);
  await expect(page.locator('.attribute-match')).toContainText(app.attributes.html_synonym);
  await expect(page.locator('.attribute-match img,.attribute-match [onerror],.attribute-match [onload]')).toHaveCount(0);
  expect(await page.evaluate(()=>globalThis.ownedAttributeInjected)).toBeUndefined();
  await noHorizontalOverflow(page);
  await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
  await expect(page.getByLabel('Исходный код',{exact:true})).toHaveText(app.attributes.xml);
  await noHorizontalOverflow(page);
  await page.locator('#search').fill('');
  await expect(page.locator('#item-list button')).toHaveCount(3);
  await expect(page.locator('#attribute-coverage')).not.toBeVisible();
  await expect(page.locator('.attribute-matches')).toHaveCount(0);
  await expect(page.locator('#search-status')).not.toBeVisible();
});

test('late real attribute searches and owner XML cannot overwrite a newer query, clear, view, cancellation or import',async({page,app})=>{
  await importAttributes(page,app);
  let nextGate;const gates=[];
  function holdNext(){
    let release,reached,delivered;
    const hold=new Promise(resolve=>release=resolve),seen=new Promise(resolve=>reached=resolve),sent=new Promise(resolve=>delivered=resolve);
    nextGate={release,reached,delivered,hold,seen,sent};gates.push(nextGate);return nextGate;
  }
  const pattern=`${app.origin}/api/search?*`;
  await page.route(pattern,async route=>{
    const response=await route.fetch(),reply=await response.json();
    let gate;
    if(nextGate&&reply.kind==='metadata'&&reply.query==='КОНТРАГЕНТ'&&reply.status==='ready'){
      expect(reply.result.objects.some(row=>row.child_matches?.length===2)).toBe(true);
      gate=nextGate;nextGate=null;gate.reached();await gate.hold;
    }
    await route.fulfill({response});gate?.delivered();
  });
  try{
    const query=holdNext();await page.locator('#search').fill('КОНТРАГЕНТ');await query.seen;
    await page.locator('#search').fill(app.attributes.nested_synonym.toUpperCase());query.release();await query.sent;
    await expect(page.locator('.attribute-match')).toHaveCount(1);
    await expect(page.locator('.attribute-match')).toContainText(app.attributes.nested_synonym);
    const clear=holdNext();await page.locator('#search').fill('КОНТРАГЕНТ');await clear.seen;
    await page.locator('#search').fill('');clear.release();await clear.sent;await deliveredFrames(page);
    await expect(page.locator('#item-list button')).toHaveCount(3);
    await expect(page.locator('.attribute-matches')).toHaveCount(0);
    await expect(page.locator('#attribute-coverage')).not.toBeVisible();
    const view=holdNext();await page.locator('#search').fill('КОНТРАГЕНТ');await view.seen;
    await page.locator('[data-view="modules"]').click();view.release();await view.sent;await deliveredFrames(page);
    await expect(page.locator('#page-title')).toHaveText('Модули конфигурации');
    await expect(page.locator('#attribute-search-help')).not.toBeVisible();
    await expect(page.locator('.attribute-matches')).toHaveCount(0);
    await page.locator('[data-view="objects"]').click();
    const cancelled=holdNext();await page.locator('#search').fill('КОНТРАГЕНТ');await cancelled.seen;
    await page.locator('#cancel-search').click();cancelled.release();await cancelled.sent;await deliveredFrames(page);
    await expect(page.locator('#item-list button')).toHaveCount(3);
    await expect(page.locator('.attribute-matches')).toHaveCount(0);
    await search(page,app,'КОНТРАГЕНТ',2);
    await page.locator('#item-list button').filter({hasText:'Поставщики'}).click();
    let releasePreview,reachedPreview,deliveredPreview;
    const previewHold=new Promise(resolve=>releasePreview=resolve),previewSeen=new Promise(resolve=>reachedPreview=resolve),previewSent=new Promise(resolve=>deliveredPreview=resolve);
    gates.push({release:releasePreview});
    const sourcePattern=`${app.origin}/api/source?*`;
    await page.route(sourcePattern,async route=>{const response=await route.fetch();expect((await response.json()).input_ref.raw_sha256).toBe(app.attributes.xml_sha256);reachedPreview();await previewHold;await route.fulfill({response});deliveredPreview();});
    await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();await previewSeen;
    await search(page,app,'МАССОВЫЙРЕКВИЗИТ',1);releasePreview();
    await previewSent;await page.unroute(sourcePattern);await deliveredFrames(page);
    await expect(page.locator('#detail-panel h2')).toHaveText('Лимит');
    await expect(page.locator('.attribute-match')).toHaveCount(20);
    await expect(page.getByLabel('Исходный код',{exact:true})).toHaveCount(0);
    const imported=holdNext();await page.locator('#search').fill('КОНТРАГЕНТ');await imported.seen;
    await importZip(page,app.archives.first.path);await ready(page,'first.zip');
    imported.release();await imported.sent;await deliveredFrames(page);
    await expect(page.locator('#detail-panel h2')).toHaveText('Products');
    await expect(page.locator('.attribute-matches')).toHaveCount(0);
    await expect(page.locator('#attribute-coverage')).not.toBeVisible();
    await expect(page.locator('#search-status')).not.toBeVisible();
  }finally{for(const gate of gates)gate.release();await page.unrouteAll({behavior:'wait'});}
});
