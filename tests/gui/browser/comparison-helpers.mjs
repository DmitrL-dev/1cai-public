import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {expect,importZip,noHorizontalOverflow} from './fixtures.mjs';
export async function comparisonBeforeReady(page){
  await expect(page.locator('#progress-dialog')).not.toBeVisible();
  await expect(page.locator('#page-subtitle')).toContainText('compare-before.zip');
  await expect(page.locator('#metric-objects')).toHaveText('1');
  await expect(page.locator('#metric-modules')).toHaveText('403');
}
export async function openComparison(page,app){
  await importZip(page,app.archives.compare_before.path);await comparisonBeforeReady(page);
  await page.getByRole('button',{name:'Сравнение ZIP',exact:true}).click();
  await expect(page.locator('#compare-before')).toContainText(app.archives.compare_before.sha256);
  await expect(page.getByLabel('ZIP после изменения',{exact:true})).toBeEnabled();
  await page.getByLabel('ZIP после изменения',{exact:true}).setInputFiles(app.archives.compare_after.path);
  await expect(page.locator('#compare-counts')).toHaveText('Всего путей: 406 · Добавлено: 1 · Удалено: 1 · Изменены байты: 403 · Без изменений: 1');
  await expect(page.locator('#compare-list button')).toHaveCount(200);
  await expect(page.locator('#compare-next')).toBeEnabled();
}
export async function lastComparisonSource(page,app){
  await page.locator('#compare-next').click();await expect(page.locator('#compare-range')).toHaveText('Файлы 201–400 из 405');
  await page.locator('#compare-next').click();await expect(page.locator('#compare-range')).toHaveText('Файлы 401–405 из 405');
  await page.getByRole('button',{name:'Изменены байты · CommonModules/Compare400.bsl',exact:true}).click();
  await expect(page.getByLabel('Код до',{exact:true})).toHaveText(app.compare_code.before);
  await expect(page.getByLabel('Код после',{exact:true})).toHaveText(app.compare_code.after);
  for(const side of ['before','after']){
    const panel=page.getByRole('region',{name:side==='before'?'Исходник до':'Исходник после',exact:true});
    await expect(panel).toContainText(app.archives[`compare_${side}`].sha256);
    await expect(panel).toContainText(app.compare_hashes[side]);
  }
  await expect(page.locator('#compare-source img')).toHaveCount(0);
  await noHorizontalOverflow(page);
}
export async function exerciseComparison(page,app){
  await openComparison(page,app);await lastComparisonSource(page,app);await expect(page.locator('#toast')).not.toBeVisible();
  const event=page.waitForEvent('download');await page.getByRole('button',{name:'Скачать JSON-отчёт',exact:true}).click();
  const download=await event;expect(await download.failure()).toBeNull();
  const bytes=await readFile(await download.path()),digest=createHash('sha256').update(bytes).digest('hex');
  expect(JSON.parse(bytes.toString('utf8')).rows).toHaveLength(405);
  await expect(page.locator('#compare-report-status')).toContainText(digest);
  await noHorizontalOverflow(page);
}
