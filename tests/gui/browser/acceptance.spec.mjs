import {writeFile} from 'node:fs/promises';
import {test, expect, importZip, ready, noHorizontalOverflow, keyboardReach} from './fixtures.mjs';

test('real UI ZIP import, objects, modules, UTF-8 source and byte provenance', async ({page, app}, testInfo) => {
  const response = await page.request.get(app.origin);
  expect(response.headers()['content-security-policy']).toContain("frame-ancestors 'none'");
  expect(response.headers()['access-control-allow-origin']).toBeUndefined();
  expect((await page.request.get(`${app.origin}/api/session`)).status()).toBe(401);
  await importZip(page, app.archives.first.path);
  await ready(page, 'first.zip');
  await expect(page.locator('#detail-panel h2')).toHaveText('Products');
  await expect(page.locator('#detail-content')).toContainText('Catalogs/Products.xml');
  await page.locator('.module-link').click();
  await expect(page.getByLabel('Исходный код', {exact: true})).toHaveText(app.module);
  await page.getByRole('tab', {name: 'Происхождение', exact: true}).click();
  await expect(page.locator('#detail-content')).toContainText(app.module_sha256);
  await expect(page.locator('#detail-content')).toContainText(app.archives.first.sha256);
  await page.locator('[data-view="provenance"]').click();
  await expect(page.locator('#provenance-view')).toContainText(app.archives.first.sha256);
  await expect(page.locator('#provenance-view')).toContainText('Не выполнялась');
  await expect(page.locator('#toast')).not.toBeVisible();
  await page.screenshot({path: testInfo.outputPath('real-import-provenance.png'), fullPage: true});
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
});

test('cancel real reservation, failed import preserves result, repeated import replaces it', async ({page, app}) => {
  await importZip(page, app.archives.first.path);
  await ready(page, 'first.zip');
  let release;
  const held = new Promise(resolve => {release = resolve;});
  let observed;
  const observedUpload = new Promise(resolve => {observed = resolve;});
  // Hold only the outgoing upload, after the production server reserved a job.
  // All responses including cancellation come from the unmodified backend.
  await page.route(`${app.origin}/api/import?*`, async route => {
    observed();
    await held;
    await route.abort('aborted');
  });
  try {
    await importZip(page, app.archives.second.path);
    await observedUpload;
    const cancelled = page.waitForResponse(response => response.url() === `${app.origin}/api/cancel`);
    await page.locator('#cancel-analysis').click();
    const reply = await cancelled;
    expect(reply.status()).toBe(200);
    expect((await reply.json()).cancel_requested).toBe(true);
  } finally {
    release();
    await page.unrouteAll({behavior: 'wait'});
  }
  await expect(page.locator('#progress-dialog')).not.toBeVisible();
  await expect(page.locator('#toast')).toHaveText('Анализ отменён.');
  await ready(page, 'first.zip');
  await importZip(page, app.corrupt);
  await expect(page.locator('#upload-error')).toHaveText('Этот формат ZIP не поддерживается. Используйте обычный ZIP со сжатием Deflate или без сжатия, без пароля.');
  await page.getByRole('button', {name: 'Закрыть', exact: true}).click();
  await ready(page, 'first.zip');
  await page.locator('.module-link').click();
  await expect(page.getByLabel('Исходный код', {exact: true})).toHaveText(app.module);
  await importZip(page, app.archives.second.path);
  await ready(page, 'second.zip');
  await page.locator('[data-view="provenance"]').click();
  await expect(page.locator('#provenance-view')).toContainText(app.archives.second.sha256);
  await expect(page.locator('#provenance-view')).not.toContainText(app.archives.first.sha256);
});

test('keyboard open, dismiss, return focus, search and roving detail tabs', async ({page, app}) => {
  const open = page.locator('#import-button');
  await keyboardReach(page, open);
  await expect(open).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#import-dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#import-dialog')).not.toBeVisible();
  await expect(open).toBeFocused();
  await page.keyboard.press('Enter');
  await keyboardReach(page, page.locator('#file-input'));
  await page.locator('#file-input').setInputFiles(app.archives.first.path);
  await ready(page, 'first.zip');
  await page.keyboard.press('Control+k');
  await expect(page.locator('#search')).toBeFocused();
  await page.keyboard.type('missing-owned-name');
  await expect(page.locator('#no-results')).toBeVisible();
  await page.keyboard.press('Control+a');
  await page.keyboard.type('Products');
  await expect(page.locator('#item-list button')).toHaveCount(1);
  await keyboardReach(page, page.getByRole('tab', {name: 'Сведения', exact: true}));
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', {name: 'Исходный файл', exact: true})).toBeFocused();
  await expect(page.getByLabel('Исходный код', {exact: true})).toContainText('<Name>Products</Name>');
  await page.keyboard.press('End');
  await expect(page.getByRole('tab', {name: 'Происхождение', exact: true})).toBeFocused();
  await page.keyboard.press('Home');
  await expect(page.getByRole('tab', {name: 'Сведения', exact: true})).toBeFocused();
});

test('narrow viewport reflow preserves import, source and provenance controls', async ({page, app}, testInfo) => {
  await page.setViewportSize({width: 390, height: 844});
  await noHorizontalOverflow(page);
  await importZip(page, app.archives.first.path);
  await ready(page, 'first.zip');
  await noHorizontalOverflow(page);
  await page.locator('.module-link').click();
  await expect(page.getByLabel('Исходный код', {exact: true})).toHaveText(app.module);
  await noHorizontalOverflow(page);
  await page.locator('[data-view="provenance"]').click();
  await noHorizontalOverflow(page);
  await expect(page.locator('#toast')).not.toBeVisible();
  await page.screenshot({path: testInfo.outputPath('narrow-provenance.png'), fullPage: true});
});

// Avoid Playwright fullPage viewport/clip overrides at native browser zoom.
// CDP captures the current compositor surface without changing zoom or viewport.
async function captureNativeViewport(page, context, testInfo, filename) {
  const viewport = await page.evaluate(() => ({width: innerWidth, height: innerHeight, dpr: devicePixelRatio}));
  const cdp = await context.newCDPSession(page);
  let png;
  try {
    const reply = await cdp.send('Page.captureScreenshot', {format: 'png', fromSurface: true, captureBeyondViewport: false});
    png = Buffer.from(reply.data, 'base64');
  } finally {await cdp.detach();}
  expect(png.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a');
  const pixels = {width: png.readUInt32BE(16), height: png.readUInt32BE(20)};
  expect(Math.abs(pixels.width - viewport.width * viewport.dpr)).toBeLessThanOrEqual(2);
  expect(Math.abs(pixels.height - viewport.height * viewport.dpr)).toBeLessThanOrEqual(2);
  await writeFile(testInfo.outputPath(filename), png);
  return {viewport, pixels};
}

test('genuine Chromium 200 percent zoom reflows and keeps controls operable', async ({page, context, app}, testInfo) => {
  const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
  const before = await page.evaluate(() => ({width: innerWidth, dpr: devicePixelRatio}));
  const factor = await worker.evaluate(async () => {
    const tabs = await chrome.tabs.query({active: true, lastFocusedWindow: true});
    if (tabs.length !== 1) throw new Error('Expected one owned active test tab');
    await chrome.tabs.setZoomSettings(tabs[0].id, {mode: 'automatic', scope: 'per-tab'});
    await chrome.tabs.setZoom(tabs[0].id, 2);
    return chrome.tabs.getZoom(tabs[0].id);
  });
  expect(factor).toBe(2);
  await expect.poll(() => page.evaluate(() => devicePixelRatio)).toBe(before.dpr * 2);
  const after = await page.evaluate(() => ({width: innerWidth, dpr: devicePixelRatio}));
  expect(Math.abs(after.width - before.width / 2)).toBeLessThanOrEqual(1);
  await noHorizontalOverflow(page);
  await importZip(page, app.archives.first.path);
  await ready(page, 'first.zip');
  await noHorizontalOverflow(page);
  await page.locator('.module-link').click();
  await expect(page.getByLabel('Исходный код', {exact: true})).toHaveText(app.module);
  await noHorizontalOverflow(page);
  await expect(page.locator('#toast')).not.toBeVisible();
  await page.evaluate(() => scrollTo(0, 0));
  const workspaceCapture = await captureNativeViewport(page, context, testInfo, 'browser-zoom-200-workspace.png');
  const source = page.getByLabel('Исходный код', {exact: true});
  await source.scrollIntoViewIfNeeded();
  await expect(source).toBeInViewport({ratio: 1});
  const sourceCapture = await captureNativeViewport(page, context, testInfo, 'browser-zoom-200-source.png');
  const sourceBounds = await source.boundingBox();
  expect(sourceBounds.x).toBeGreaterThanOrEqual(0);
  expect(sourceBounds.x + sourceBounds.width).toBeLessThanOrEqual(sourceCapture.viewport.width + 1);
  expect(sourceBounds.y).toBeGreaterThanOrEqual(0);
  expect(sourceBounds.y + sourceBounds.height).toBeLessThanOrEqual(sourceCapture.viewport.height + 1);
  const measurement = testInfo.outputPath('browser-zoom-measurement.json');
  await writeFile(measurement, JSON.stringify({factor, before, after, workspaceCapture, sourceCapture, sourceBounds}, null, 2) + '\n');
  await testInfo.attach('browser-zoom-measurement', {path: measurement, contentType: 'application/json'});
});
