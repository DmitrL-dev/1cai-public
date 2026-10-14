import {writeFile} from 'node:fs/promises';
import {test, expect, importZip, ready, keyboardReach, noHorizontalOverflow} from './fixtures.mjs';
import {
  labels, importCurrent, confirmCurrent, openThreeway, nextPageResponse,
  verifyPage, selectAction, deliveredFrames, holdReply,
} from './threeway-helpers.mjs';

test('three explicitly assigned ZIP roles expose all five observed-byte categories and every bounded page', async ({page, app}, testInfo) => {
  let starts = 0;
  page.on('request', request => {if (request.url() === `${app.origin}/api/threeway-start`) starts++;});
  await importCurrent(page, app);
  expect(starts).toBe(0);
  await confirmCurrent(page, app);
  expect(starts).toBe(1);
  await page.locator('#threeway-base-file').setInputFiles(app.threeway.archives.base.path);
  await expect(page.locator('#threeway-base')).toContainText(app.threeway.archives.base.sha256);
  await expect(page.locator('#threeway-upstream-file')).toBeEnabled();
  const first = nextPageResponse(page, app, 'changes');
  await page.locator('#threeway-upstream-file').setInputFiles(app.threeway.archives.upstream.path);
  const firstReply = await verifyPage(page, app, await first, 'changes');
  const paths = firstReply.rows.map(row => row.path);
  for (const offset of [200, 400]) {
    const received = nextPageResponse(page, app, 'changes', offset);
    await page.locator('#threeway-next').click();
    const reply = await verifyPage(page, app, await received, 'changes', offset);
    paths.push(...reply.rows.map(row => row.path));
  }
  expect(paths).toEqual(app.threeway.rows.filter(row => row.action !== 'unchanged').map(row => row.path));
  expect(new Set(paths).size).toBe(415);
  await expect(page.locator('#threeway-next')).toBeDisabled();
  const previous = nextPageResponse(page, app, 'changes', 200);
  await keyboardReach(page, page.locator('#threeway-previous'));
  await page.keyboard.press('Enter');
  await verifyPage(page, app, await previous, 'changes', 200);
  await expect(page.locator('#threeway-previous')).toBeFocused();
  for (const action of ['unchanged', 'same_change', 'keep_current', 'take_upstream', 'conflict', 'all']) {
    await selectAction(page, app, action);
    await expect(page.locator('#threeway-filter')).toBeFocused();
    await expect(page.locator('#threeway-counts')).toContainText('Всего путей: 417');
    for (const [category, label] of Object.entries(labels)) {
      await expect(page.locator('#threeway-counts')).toContainText(`${label}: ${app.threeway.counts[category]}`);
    }
  }
  await selectAction(page, app, 'conflict');
  await expect(page.locator('#threeway-list')).toContainText(app.threeway.untrusted_path);
  await expect(page.locator('#threeway-list')).not.toContainText('<img');
  await expect(page.locator('#threeway-view')).not.toContainText('безопасное слияние');
  await expect(page.locator('#threeway-view button').filter({hasText: /Применить|Слить/})).toHaveCount(0);
  await noHorizontalOverflow(page);
  await page.screenshot({path: testInfo.outputPath('threeway-five-categories-provenance.png'), fullPage: true});
});

test('three-ZIP replacement clears previous rows before upload and a rejected ZIP never restores them', async ({page, app}) => {
  await openThreeway(page, app);
  let release, observed;
  const hold = new Promise(resolve => {release = resolve;});
  const seen = new Promise(resolve => {observed = resolve;});
  const pattern = `${app.origin}/api/threeway-upload?*`;
  await page.route(pattern, async route => {observed(); await hold; await route.continue();});
  try {
    await page.locator('#threeway-upstream-file').setInputFiles(app.corrupt);
    await seen;
    await expect(page.locator('#threeway-list li')).toHaveCount(0);
    await expect(page.locator('#threeway-counts')).toBeEmpty();
    await expect(page.locator('#threeway-result')).not.toBeVisible();
    await expect(page.locator('#threeway-upstream')).not.toContainText(app.threeway.archives.upstream.sha256);
    release();
    await expect(page.locator('#threeway-message')).toContainText('Этот формат ZIP не поддерживается');
    await expect(page.locator('#threeway-list li')).toHaveCount(0);
    await expect(page.locator('#threeway-result')).not.toBeVisible();
    const cancelled = page.waitForResponse(response => response.url() === `${app.origin}/api/threeway-cancel`);
    await page.locator('#threeway-cancel').click();
    expect((await (await cancelled).json()).cancel_requested).toBe(true);
    await expect(page.locator('#threeway-confirm')).toBeEnabled();
    await expect(page.locator('#threeway-base-file')).toBeDisabled();
    await expect(page.locator('#threeway-base')).not.toContainText(app.threeway.archives.base.sha256);
  } finally {
    release();
    await page.unroute(pattern);
  }
});

test('late genuine three-ZIP readiness cannot resurrect a cancelled plan or replace a new Current import', async ({page, app}) => {
  await importCurrent(page, app);
  await confirmCurrent(page, app);
  await page.locator('#threeway-base-file').setInputFiles(app.threeway.archives.base.path);
  await expect(page.locator('#threeway-base')).toContainText(app.threeway.archives.base.sha256);
  await expect(page.locator('#threeway-upstream-file')).toBeEnabled();
  const gate = await holdReply(page, `${app.origin}/api/threeway?*`, reply => reply.status === 'ready');
  try {
    await page.locator('#threeway-upstream-file').setInputFiles(app.threeway.archives.upstream.path);
    const accepted = await gate.seen;
    expect(accepted.counts).toEqual(app.threeway.counts);
    await page.locator('#threeway-cancel').click();
    await expect(page.locator('#threeway-confirm')).toBeEnabled();
    gate.release();
    await gate.sent;
    await deliveredFrames(page);
    await expect(page.locator('#threeway-list li')).toHaveCount(0);
    await expect(page.locator('#threeway-result')).not.toBeVisible();
    await expect(page.locator('#threeway-base-file')).toBeDisabled();
    await importZip(page, app.archives.first.path);
    await ready(page, 'first.zip');
    await page.locator('[data-view="threeway"]').click();
    await expect(page.locator('#threeway-current')).toContainText(app.archives.first.sha256);
    await expect(page.locator('#threeway-current')).not.toContainText(app.threeway.archives.current.sha256);
    await expect(page.locator('#threeway-confirm')).toBeEnabled();
    await expect(page.locator('#threeway-list li')).toHaveCount(0);
    await expect(page.locator('#threeway-result')).not.toBeVisible();
  } finally {await gate.close();}
});

test('late genuine three-ZIP pages stay cleared after navigation and a newer import requires new role confirmation', async ({page, app}) => {
  await openThreeway(page, app);
  const gate = await holdReply(page, `${app.origin}/api/threeway-page?*`, reply => reply.page?.offset === 200);
  try {
    await page.locator('#threeway-next').click();
    expect((await gate.seen).rows).toHaveLength(200);
    const cancelled = page.waitForResponse(response => response.url() === `${app.origin}/api/threeway-cancel`);
    await page.locator('[data-view="modules"]').click();
    expect((await (await cancelled).json()).cancel_requested).toBe(true);
    await importZip(page, app.archives.second.path);
    await ready(page, 'second.zip');
    gate.release();
    await gate.sent;
    await deliveredFrames(page);
    await expect(page.locator('#threeway-view')).not.toBeVisible();
    await expect(page.locator('#threeway-list li')).toHaveCount(0);
    await expect(page.locator('#threeway-counts')).toBeEmpty();
    await page.locator('[data-view="threeway"]').click();
    await expect(page.locator('#threeway-current')).toContainText(app.archives.second.sha256);
    await expect(page.locator('#threeway-confirm')).toBeEnabled();
    await expect(page.locator('#threeway-base-file')).toBeDisabled();
    await expect(page.locator('#threeway-upstream-file')).toBeDisabled();
    await expect(page.locator('#threeway-result')).not.toBeVisible();
  } finally {await gate.close();}
});

test('lost three-ZIP start and readiness recover by exact read-back without replaying reservations or uploads', async ({page, app}) => {
  await importCurrent(page, app);
  let starts = 0, currentReads = 0, reservations = 0, uploads = 0, dropped = 0, outage = true;
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (path === '/api/threeway-start') starts++;
    if (path === '/api/threeway-current') currentReads++;
    if (path === '/api/threeway-upload-start') reservations++;
    if (path === '/api/threeway-upload') uploads++;
  });
  const startPattern = `${app.origin}/api/threeway-start`;
  await page.route(startPattern, async route => {
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    expect((await response.json()).current_sha256).toBe(app.threeway.archives.current.sha256);
    await route.abort('failed');
  });
  try {
    await page.locator('#threeway-confirm').click();
    await expect(page.locator('#threeway-base-file')).toBeEnabled();
    await expect(page.locator('#threeway-current')).toContainText(app.threeway.archives.current.sha256);
    expect(starts).toBe(1);
    expect(currentReads).toBeGreaterThan(0);
  } finally {await page.unroute(startPattern);}
  await page.locator('#threeway-base-file').setInputFiles(app.threeway.archives.base.path);
  await expect(page.locator('#threeway-base')).toContainText(app.threeway.archives.base.sha256);
  await expect(page.locator('#threeway-upstream-file')).toBeEnabled();
  const pattern = `${app.origin}/api/threeway?*`;
  await page.route(pattern, async route => {
    const response = await route.fetch();
    if ((await response.json()).status === 'ready' && outage) {dropped++; await route.abort('failed');}
    else await route.fulfill({response});
  });
  try {
    await page.locator('#threeway-upstream-file').setInputFiles(app.threeway.archives.upstream.path);
    await expect(page.locator('#threeway-message')).toContainText('Результат загрузки не подтверждён');
    expect(dropped).toBeGreaterThan(0);
    await expect(page.locator('#threeway-result')).not.toBeVisible();
    await expect(page.locator('#threeway-list li')).toHaveCount(0);
    await expect(page.locator('#threeway-base-file')).toBeDisabled();
    expect({starts, reservations, uploads}).toEqual({starts: 1, reservations: 2, uploads: 2});
    outage = false;
    const recovered = nextPageResponse(page, app, 'changes');
    await page.locator('#threeway-check').click();
    await verifyPage(page, app, await recovered, 'changes');
    expect({starts, reservations, uploads}).toEqual({starts: 1, reservations: 2, uploads: 2});
  } finally {await page.unroute(pattern);}
});

test('three-ZIP role evidence and absent sides reflow at a narrow viewport with keyboard paging', async ({page, app}, testInfo) => {
  await page.setViewportSize({width: 390, height: 844});
  await openThreeway(page, app);
  await noHorizontalOverflow(page);
  const received = nextPageResponse(page, app, 'changes', 200);
  await keyboardReach(page, page.locator('#threeway-next'));
  await page.keyboard.press('Enter');
  await verifyPage(page, app, await received, 'changes', 200);
  await expect(page.locator('#threeway-next')).toBeFocused();
  await selectAction(page, app, 'conflict');
  await expect(page.locator('#threeway-list')).toContainText(app.threeway.untrusted_path);
  await noHorizontalOverflow(page);
  await page.screenshot({path: testInfo.outputPath('threeway-narrow-literal-paths.png'), fullPage: true});
  await keyboardReach(page, page.locator('#threeway-cancel'));
  await page.keyboard.press('Enter');
  await expect(page.locator('#threeway-confirm')).toBeEnabled();
  await expect(page.locator('#threeway-result')).not.toBeVisible();
});

test('three-ZIP inventory remains operable at genuine Chromium 200 percent zoom', async ({page, context, app}, testInfo) => {
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
  await openThreeway(page, app);
  await selectAction(page, app, 'conflict');
  await noHorizontalOverflow(page);
  await page.locator('#threeway-list').scrollIntoViewIfNeeded();
  const cdp = await context.newCDPSession(page);
  try {
    const shot = await cdp.send('Page.captureScreenshot', {format: 'png', fromSurface: true, captureBeyondViewport: false});
    const png = Buffer.from(shot.data, 'base64');
    expect(png.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a');
    const viewport = await page.evaluate(() => ({width: innerWidth, height: innerHeight, dpr: devicePixelRatio}));
    const pixels = {width: png.readUInt32BE(16), height: png.readUInt32BE(20)};
    expect(Math.abs(pixels.width - viewport.width * viewport.dpr)).toBeLessThanOrEqual(2);
    expect(Math.abs(pixels.height - viewport.height * viewport.dpr)).toBeLessThanOrEqual(2);
    await writeFile(testInfo.outputPath('threeway-browser-zoom-200.png'), png);
    await writeFile(testInfo.outputPath('threeway-browser-zoom-measurement.json'), JSON.stringify({factor, before, after, viewport, pixels}, null, 2) + '\n');
  } finally {await cdp.detach();}
  await selectAction(page, app, 'same_change');
  await expect(page.locator('#threeway-list')).toContainText('Current: файл отсутствует');
  await expect(page.locator('#threeway-list')).toContainText('Upstream: файл отсутствует');
  await noHorizontalOverflow(page);
  expect(await worker.evaluate(async () => chrome.tabs.getZoom((await chrome.tabs.query({active: true, lastFocusedWindow: true}))[0].id))).toBe(2);
});
