import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {test,expect,importZip,ready,keyboardReach} from './fixtures.mjs';
import {openComparison} from './comparison-helpers.mjs';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
async function download(page,format,testInfo,keyboard=false){
  const event=page.waitForEvent('download');
  const response=page.waitForResponse(reply=>reply.url().endsWith('/api/comparison-report')&&reply.request().postDataJSON().format===format);
  if(keyboard)await page.keyboard.press('Enter');else await page.locator(`#compare-report-${format}`).click();
  const item=await event,reply=await response;
  expect(reply.status()).toBe(200);expect(await item.failure()).toBeNull();
  const path=testInfo.outputPath(item.suggestedFilename());await item.saveAs(path);
  const bytes=await readFile(path);expect(sha(bytes)).toBe(reply.headers()['x-rentgen-report-sha256']);
  expect(Number(reply.headers()['content-length'])).toBe(bytes.length);
  await expect(page.locator('#compare-report-status')).toContainText(sha(bytes));
  await expect(page.locator(`#compare-report-${format}`)).toBeFocused();
  return {bytes,digest:sha(bytes)};
}

test('complete current-pair JSON and inert standalone HTML downloads include every change beyond the visible filter',async({page,context,app},testInfo)=>{
  await openComparison(page,app);
  const dangerous="После & ' <img src=x onerror=alert(1)>.zip";
  await page.locator('#compare-file').setInputFiles({name:dangerous,mimeType:'application/zip',buffer:await readFile(app.archives.compare_after.path)});
  await expect(page.locator('#compare-after')).toContainText(dangerous);await expect(page.locator('#compare-list button')).toHaveCount(200);
  await page.getByLabel('Показать файлы',{exact:true}).selectOption('added');await expect(page.locator('#compare-list button')).toHaveCount(1);
  await keyboardReach(page,page.locator('#compare-report-json'));await expect(page.locator('#compare-report-json')).toBeFocused();
  const json=await download(page,'json',testInfo,true),report=JSON.parse(json.bytes.toString('utf8'));
  expect(report.schema_version).toBe(1);expect(report.scope).toBe('submitted_zip_bytes');expect(report.comparison).toBe('raw_sha256_and_size');
  expect(report.before_sha256).toBe(app.archives.compare_before.sha256);expect(report.after_sha256).toBe(app.archives.compare_after.sha256);
  expect(report.after_filename).toBe(dangerous);expect(report.counts.total).toBe(406);expect(report.counts.unchanged).toBe(1);expect(report.rows).toHaveLength(405);
  const late=report.rows.find(row=>row.path==='CommonModules/Compare400.bsl');expect(late.before.raw_sha256).toBe(app.compare_hashes.before);expect(late.after.raw_sha256).toBe(app.compare_hashes.after);
  expect(report.rows.filter(row=>row.status==='added')).toHaveLength(1);expect(report.rows.filter(row=>row.status==='removed')).toHaveLength(1);expect(report.rows.filter(row=>row.status==='modified')).toHaveLength(403);
  expect(json.bytes.includes(Buffer.from(app.token))).toBe(false);expect(json.bytes.includes(Buffer.from(app.archives.compare_before.path))).toBe(false);expect(json.bytes.includes(Buffer.from(app.compare_code.before))).toBe(false);
  const html=await download(page,'html',testInfo),text=html.bytes.toString('utf8');
  expect(text).toContain('&lt;img');expect(text).not.toContain('<img');expect(text).not.toContain('<script');expect(text).not.toContain(app.token);
  // Owned downloaded HTML, inspected offline in a disposable blank tab: no hosting or external resources.
  const offline=await context.newPage();const requests=[];offline.on('request',request=>requests.push(request.url()));
  try{
    await offline.setContent(text);await expect(offline.locator('tbody tr')).toHaveCount(405);
    await expect(offline.locator('body')).toContainText(dangerous);await expect(offline.locator('body')).toContainText(app.compare_hashes.after);
    await expect(offline.locator('script,img,iframe,object,embed,link')).toHaveCount(0);
    expect(await offline.locator('body').evaluate(node=>getComputedStyle(node).backgroundColor)).toBe('rgb(255, 255, 255)');
    await offline.emulateMedia({media:'print'});await expect(offline.locator('h1')).toBeVisible();
    await offline.screenshot({path:testInfo.outputPath('offline-report-print-header.png'),fullPage:false});expect(requests).toEqual([]);
  }finally{await offline.close();}
  await writeFile(testInfo.outputPath('report-receipt.json'),JSON.stringify({json_sha256:json.digest,html_sha256:html.digest,changed_rows:405,scope:report.scope},null,2)+'\n');
});

test('cancelled and late report responses never download after view or archive replacement',async({page,app})=>{
  await openComparison(page,app);
  const downloads=[];page.on('download',download=>downloads.push(download));
  for(const action of ['cancel','replace']){
    let release,observed,delivered;
    const held=new Promise(resolve=>release=resolve),seen=new Promise(resolve=>observed=resolve),sent=new Promise(resolve=>delivered=resolve);
    const pattern=`${app.origin}/api/comparison-report`;
    await page.route(pattern,async route=>{const response=await route.fetch();expect(response.status()).toBe(200);observed();await held;try{await route.fulfill({response});}catch{/* The browser may already have cancelled this exact request. */}finally{delivered();}});
    try{
      await page.locator('#compare-report-json').click();await seen;
      if(action==='cancel')await page.locator('#compare-report-cancel').click();
      else{await page.locator('[data-view="objects"]').click();await importZip(page,app.archives.first.path);await ready(page,'first.zip');}
      release();await sent;await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      expect(downloads).toHaveLength(0);
      if(action==='cancel'){await expect(page.locator('#compare-report-status')).toHaveText('Скачивание отменено.');await expect(page.locator('#compare-list button')).toHaveCount(200);}
      else{await page.locator('[data-view="comparison"]').click();await expect(page.locator('#compare-result')).not.toBeVisible();}
    }finally{release();await page.unroute(pattern);}
  }
});
