import {exerciseComparison} from './comparison-helpers.mjs';
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
  await discoverLongRelatedFolder(page,app);
  await noHorizontalOverflow(page);
  await expect(page.locator('#toast')).not.toBeVisible();
  await page.screenshot({path:testInfo.outputPath('narrow-related-long-path.png'),fullPage:true});
  await exerciseBoundedPagination(page,app);
  await page.screenshot({path:testInfo.outputPath('narrow-pagination.png'),fullPage:true});
  await exerciseComparison(page,app);
  await page.screenshot({path:testInfo.outputPath('narrow-comparison.png'),fullPage:true});
  await exerciseLiteralSearch(page,app);
  await page.screenshot({path:testInfo.outputPath('narrow-literal-source.png'),fullPage:true});
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
  await discoverLongRelatedFolder(page,app);
  await noHorizontalOverflow(page);
  expect(await worker.evaluate(async()=>chrome.tabs.getZoom((await chrome.tabs.query({active:true,lastFocusedWindow:true}))[0].id))).toBe(2);
  await expect(page.locator('#toast')).not.toBeVisible();
  await page.locator('#search-status').scrollIntoViewIfNeeded();
  const relatedCapture=await captureNativeViewport(page,context,testInfo,'browser-zoom-200-related-long-path.png');
  await writeFile(testInfo.outputPath('related-zoom-measurement.json'),JSON.stringify({factor:2,relatedCapture},null,2)+'\n');
  await exerciseBoundedPagination(page,app);
  expect(await worker.evaluate(async()=>chrome.tabs.getZoom((await chrome.tabs.query({active:true,lastFocusedWindow:true}))[0].id))).toBe(2);
  await page.locator('#pagination').scrollIntoViewIfNeeded();
  const pageCapture=await captureNativeViewport(page,context,testInfo,'browser-zoom-200-pagination.png');
  await writeFile(testInfo.outputPath('pagination-zoom-measurement.json'),JSON.stringify({factor:2,pageCapture},null,2)+'\n');
  await exerciseComparison(page,app);
  expect(await worker.evaluate(async()=>chrome.tabs.getZoom((await chrome.tabs.query({active:true,lastFocusedWindow:true}))[0].id))).toBe(2);
  await page.locator('.comparison-report-controls').scrollIntoViewIfNeeded();
  await expect(page.locator('#compare-report-json')).toBeInViewport({ratio:1});
  const reportCapture=await captureNativeViewport(page,context,testInfo,'browser-zoom-200-report-controls.png');
  const comparisonCaptures={};
  for(const [side,label] of [['before','Код до'],['after','Код после']]){
    const code=page.getByLabel(label,{exact:true});await code.scrollIntoViewIfNeeded();
    await expect(code).toBeInViewport({ratio:1});
    const capture=await captureNativeViewport(page,context,testInfo,`browser-zoom-200-comparison-${side}.png`);
    const bounds=await code.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);expect(bounds.y).toBeGreaterThanOrEqual(0);
    expect(bounds.x+bounds.width).toBeLessThanOrEqual(capture.viewport.width+1);
    expect(bounds.y+bounds.height).toBeLessThanOrEqual(capture.viewport.height+1);
    comparisonCaptures[side]={...capture,bounds};
  }
  await writeFile(testInfo.outputPath('comparison-zoom-measurement.json'),JSON.stringify({factor:2,comparisonCaptures,reportCapture},null,2)+'\n');
  await exerciseLiteralSearch(page,app);
  expect(await worker.evaluate(async()=>chrome.tabs.getZoom((await chrome.tabs.query({active:true,lastFocusedWindow:true}))[0].id))).toBe(2);
  await page.locator('.source-hit').scrollIntoViewIfNeeded();
  const literalCapture=await captureNativeViewport(page,context,testInfo,'browser-zoom-200-literal-source.png');
  await writeFile(testInfo.outputPath('literal-source-zoom-measurement.json'),JSON.stringify({factor:2,literalCapture},null,2)+'\n');
});

function observeImportWrites(page, origin) {
  const writes = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.origin === origin && ['POST', 'PUT'].includes(request.method()) && ['/api/import-start', '/api/import'].includes(url.pathname)) writes.push([request.method(), url.pathname]);
  });
  return writes;
}

test('lost real ready response reconciles the same second job without upload replay', async ({page, app}) => {
  await importZip(page, app.archives.first.path);
  await ready(page, 'first.zip');
  const writes = observeImportWrites(page, app.origin);
  let dropped = false;
  await page.route(`${app.origin}/api/job?*`, async route => {
    const response = await route.fetch();
    const status = await response.json();
    if (!dropped && status.status === 'ready') {dropped = true; await route.abort('failed');}
    else await route.fulfill({response});
  });
  await importZip(page, app.archives.second.path);
  await ready(page, 'second.zip');
  expect(dropped).toBe(true);
  expect(writes).toEqual([['POST', '/api/import-start'], ['PUT', '/api/import']]);
  await expect(page.locator('#import-uncertain')).not.toBeVisible();
  await page.locator('.module-link').click();
  await expect(page.getByLabel('Исходный код', {exact: true})).toHaveText(app.module);
  await page.getByRole('tab', {name: 'Происхождение', exact: true}).click();
  await expect(page.locator('#detail-content')).toContainText(app.archives.second.sha256);
  await expect(page.locator('#detail-content')).not.toContainText(app.archives.first.sha256);
});

test('continued reply loss is explicitly uncertain and manual check only reads the known job', async ({page, app}) => {
  await importZip(page, app.archives.first.path);
  await ready(page, 'first.zip');
  const writes = observeImportWrites(page, app.origin);
  let committed = false, outage = true, lostReads = 0;
  await page.route(`${app.origin}/api/job?*`, async route => {
    if (committed && outage) {lostReads++; await route.abort('failed'); return;}
    const response = await route.fetch();
    if (!committed && (await response.json()).status === 'ready') {
      committed = true; await route.abort('failed');
    } else await route.fulfill({response});
  });
  await importZip(page, app.archives.second.path);
  await expect(page.locator('#import-uncertain')).toBeVisible();
  await expect(page.locator('#import-uncertain')).toContainText('Результат импорта неизвестен');
  await expect(page.locator('#analysis-state')).not.toBeVisible();
  await expect(page.locator('#page-subtitle')).not.toContainText('first.zip');
  expect(lostReads).toBe(3);
  await page.locator('#check-import-result').click();
  await expect(page.locator('#check-import-result')).toBeEnabled();
  expect(lostReads).toBe(6);
  await expect(page.locator('#import-uncertain')).toBeVisible();
  outage = false;
  await page.locator('#check-import-result').click();
  await ready(page, 'second.zip');
  await expect(page.locator('#import-uncertain')).not.toBeVisible();
  expect(writes).toEqual([['POST', '/api/import-start'], ['PUT', '/api/import']]);
  await page.locator('.module-link').click();
  await expect(page.getByLabel('Исходный код', {exact: true})).toHaveText(app.module);
});

test('late cancellation acknowledgement cannot alter a newer import after uncertain outcome', async ({page, app}) => {
  await importZip(page, app.archives.first.path);
  await ready(page, 'first.zip');
  let oldJob, signalReady, releaseCancel;
  const serverReady = new Promise(resolve => {signalReady = resolve;});
  const heldCancel = new Promise(resolve => {releaseCancel = resolve;});
  await page.route(`${app.origin}/api/job?*`, async route => {
    const job = new URL(route.request().url()).searchParams.get('job');
    if (oldJob === job) {await route.abort('failed'); return;}
    const response = await route.fetch();
    if (!oldJob && (await response.json()).status === 'ready') {
      oldJob = job; signalReady();
      // Leave a deterministic opportunity for a real cancel request after commit.
      await actualCancel;
      await route.abort('failed');
    } else await route.fulfill({response});
  });
  let cancelFetched;
  const actualCancel = new Promise(resolve => {cancelFetched = resolve;});
  await page.route(`${app.origin}/api/cancel`, async route => {
    const response = await route.fetch();
    expect((await response.json()).status).toBe('ready');
    cancelFetched();
    await heldCancel;
    await route.fulfill({response});
  });
  try {
    await importZip(page, app.archives.second.path);
    await serverReady;
    await page.locator('#cancel-analysis').click();
    await actualCancel;
    // The backend acknowledgement is real but intentionally withheld from the UI.
    await expect(page.locator('#import-uncertain')).toBeVisible();
    await importZip(page, app.archives.first.path);
    await ready(page, 'first.zip');
    releaseCancel();
    await page.unrouteAll({behavior: 'wait'});
    await expect(page.locator('#import-uncertain')).not.toBeVisible();
    await expect(page.locator('#progress-dialog')).not.toBeVisible();
    await page.locator('[data-view="provenance"]').click();
    await expect(page.locator('#provenance-view')).toContainText(app.archives.first.sha256);
    await expect(page.locator('#provenance-view')).not.toContainText(app.archives.second.sha256);
  } finally {releaseCancel();}
});

test('failed replacement reservation retains the uncertain known job through transport loss and real BUSY', async ({page, app}) => {
  await importZip(page, app.archives.first.path);
  await ready(page, 'first.zip');
  const writes = observeImportWrites(page, app.origin);
  let committed = false;
  await page.route(`${app.origin}/api/job?*`, async route => {
    if (committed) {await route.abort('failed'); return;}
    const response = await route.fetch();
    if ((await response.json()).status === 'ready') {committed = true; await route.abort('failed');}
    else await route.fulfill({response});
  });
  await importZip(page, app.archives.second.path);
  await expect(page.locator('#import-uncertain')).toBeVisible();
  await page.unrouteAll({behavior: 'wait'});
  // Reserve a real replacement, then lose its ID reply before any bytes are sent.
  await page.route(`${app.origin}/api/import-start`, async route => {
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    await route.abort('failed');
  });
  await importZip(page, app.archives.first.path);
  await expect(page.locator('#upload-error')).toBeVisible();
  await page.getByRole('button', {name: 'Закрыть', exact: true}).click();
  await expect(page.locator('#import-uncertain')).toBeVisible();
  await page.unrouteAll({behavior: 'wait'});
  // The unuploaded real reservation is still live, so the backend itself returns BUSY.
  await importZip(page, app.archives.first.path);
  await expect(page.locator('#upload-error')).toHaveText('Другой анализ ещё выполняется. Дождитесь завершения или отмените его.');
  await page.getByRole('button', {name: 'Закрыть', exact: true}).click();
  await expect(page.locator('#import-uncertain')).toBeVisible();
  await page.locator('#check-import-result').click();
  await ready(page, 'second.zip');
  await expect(page.locator('#import-uncertain')).not.toBeVisible();
  expect(writes).toEqual([['POST', '/api/import-start'], ['PUT', '/api/import'], ['POST', '/api/import-start'], ['POST', '/api/import-start']]);
  await page.locator('[data-view="provenance"]').click();
  await expect(page.locator('#provenance-view')).toContainText(app.archives.second.sha256);
});

test('archive-wide metadata search finds the 201st owned object and opens verified source', async ({page, app}, testInfo) => {
  await importZip(page, app.archives.many.path);
  await expect(page.locator('#progress-dialog')).not.toBeVisible();
  await expect(page.locator('#page-subtitle')).toContainText('many.zip');
  await expect(page.locator('#metric-objects')).toHaveText('201');
  await expect(page.locator('#item-list button')).toHaveCount(200);
  await expect(page.locator('#truncation-warning')).toContainText('201');
  for (const query of [app.many_name, app.many_synonym, app.many_path]) {
    await page.locator('#search').fill(query);
    await expect(page.locator('#search-status-text')).toContainText('Найдено 1 по всему ZIP');
    await expect(page.locator('#item-list button')).toHaveCount(1);
    await expect(page.locator('#detail-panel h2')).toHaveText(app.many_name);
  }
  await page.getByRole('tab', {name: 'Исходный файл', exact: true}).click();
  await expect(page.getByLabel('Исходный код', {exact: true})).toHaveText(app.many_xml);
  await page.getByRole('tab', {name: 'Происхождение', exact: true}).click();
  await expect(page.locator('#detail-content')).toContainText(app.many_xml_sha256);
  await expect(page.locator('#detail-content')).toContainText(app.archives.many.sha256);
  await expect(page.locator('#toast')).not.toBeVisible();
  await page.screenshot({path: testInfo.outputPath('archive-search-201st-provenance.png'), fullPage: true});
  // A failed replacement invalidates the search allowlist but preserves the ZIP.
  await importZip(page, app.corrupt);
  await expect(page.locator('#upload-error')).toBeVisible();
  await page.getByRole('button', {name: 'Закрыть', exact: true}).click();
  await expect(page.locator('#page-subtitle')).toContainText('many.zip');
  await expect(page.locator('#search')).toHaveValue('');
  await expect(page.locator('#item-list button')).toHaveCount(200);
  await expect(page.locator('#detail-panel h2')).toHaveText('Object000');
  await page.locator('#search').fill(app.many_name);
  await expect(page.locator('#detail-panel h2')).toHaveText(app.many_name);
  // Cancel another real reservation while its upload is held in the browser.
  let releaseUpload, observedUpload;
  const holdUpload = new Promise(resolve => {releaseUpload = resolve;});
  const uploadStarted = new Promise(resolve => {observedUpload = resolve;});
  await page.route(`${app.origin}/api/import?*`, async route => {
    observedUpload(); await holdUpload; await route.abort('aborted');
  });
  try {
    await importZip(page, app.archives.first.path);
    await uploadStarted;
    const cancelled = page.waitForResponse(response => response.url() === `${app.origin}/api/cancel`);
    await page.locator('#cancel-analysis').click();
    expect((await (await cancelled).json()).cancel_requested).toBe(true);
  } finally {releaseUpload(); await page.unrouteAll({behavior: 'wait'});}
  await expect(page.locator('#progress-dialog')).not.toBeVisible();
  await expect(page.locator('#page-subtitle')).toContainText('many.zip');
  await expect(page.locator('#search')).toHaveValue('');
  await expect(page.locator('#item-list button')).toHaveCount(200);
  await expect(page.locator('#detail-panel h2')).toHaveText('Object000');
  await page.locator('#search').fill(app.many_name);
  await expect(page.locator('#detail-panel h2')).toHaveText(app.many_name);
  await page.getByRole('tab', {name: 'Исходный файл', exact: true}).click();
  await expect(page.getByLabel('Исходный код', {exact: true})).toHaveText(app.many_xml);
  await page.locator('#search').fill('Catalog');
  await expect(page.locator('#search-status-text')).toContainText('Найдено 201 по всему ZIP');
  await expect(page.locator('#item-list button')).toHaveCount(200);
  await expect(page.locator('#truncation-warning')).toBeVisible();
  await page.locator('#search').fill('я'.repeat(129));
  await expect(page.locator('#search-status-text')).toContainText('256 байт UTF-8');
  await page.locator('#search').fill('absent-owned-object');
  await expect(page.locator('#no-results')).toBeVisible();
  await page.locator('#search').fill('');
  await expect(page.locator('#item-list button')).toHaveCount(200);
  await page.locator('[data-view="modules"]').click();
  await expect(page.locator('#search')).toHaveAttribute('placeholder', 'Имя или путь модуля по всему ZIP…');
  await expect(page.locator('#metric-objects')).toHaveText('201');
});

test('late metadata search responses cannot overwrite a new query, view or imported archive', async ({page, app}) => {
  await importZip(page, app.archives.many.path);
  await expect(page.locator('#metric-objects')).toHaveText('201');
  let nextGate;
  const gates = [];
  function holdNextReady() {
    let release, reached;
    const hold = new Promise(resolve => {release = resolve;});
    const ready = new Promise(resolve => {reached = resolve;});
    nextGate = {release, reached, hold, ready};
    gates.push(nextGate);
    return nextGate;
  }
  await page.route(`${app.origin}/api/search?*`, async route => {
    const response = await route.fetch();
    if (nextGate && (await response.json()).status === 'ready') {
      const gate = nextGate; nextGate = null; gate.reached(); await gate.hold;
    }
    await route.fulfill({response});
  });
  try {
    const oldQuery = holdNextReady();
    await page.locator('#search').fill(app.many_name);
    await oldQuery.ready;
    await page.locator('#search').fill('absent-owned-object');
    oldQuery.release();
    await expect(page.locator('#no-results')).toBeVisible();
    await expect(page.locator('#item-list button')).toHaveCount(0);
    const oldView = holdNextReady();
    await page.locator('#search').fill(app.many_name);
    await oldView.ready;
    await page.locator('[data-view="modules"]').click();
    oldView.release();
    await expect(page.locator('#page-title')).toHaveText('Модули конфигурации');
    await expect(page.locator('#search-status')).not.toBeVisible();
    await page.locator('[data-view="objects"]').click();
    const oldArchive = holdNextReady();
    await page.locator('#search').fill(app.many_name);
    await oldArchive.ready;
    await importZip(page, app.archives.first.path);
    await ready(page, 'first.zip');
    oldArchive.release();
    await page.unrouteAll({behavior: 'wait'});
    await expect(page.locator('#item-list button')).toHaveCount(1);
    await expect(page.locator('#detail-panel h2')).toHaveText('Products');
    await expect(page.locator('#search-status')).not.toBeVisible();
  } finally {for (const gate of gates) gate.release(); await page.unrouteAll({behavior: 'wait'});}
});

test('archive-wide module paths and related folder reveal later verified sources', async ({page, app}, testInfo) => {
  await importZip(page, app.archives.many.path);
  await expect(page.locator('#metric-modules')).toHaveText('204');
  await page.locator('#search').fill(app.many_name);
  await expect(page.locator('#detail-panel h2')).toHaveText(app.many_name);
  await expect(page.locator('[data-module]')).toHaveCount(0);
  await page.locator('#discover-related-modules').click();
  await expect(page.locator('#page-title')).toHaveText('Модули конфигурации');
  await expect(page.locator('#search-status-text')).toContainText('Найдено 3 по всему ZIP');
  await expect(page.locator('#search-status-text')).toContainText(app.many_path);
  await expect(page.locator('#item-list button')).toHaveCount(3);
  await expect(page.locator('#item-list')).not.toContainText('Neighbor');
  for (const query of ['ПОЗДНИЙМОДУЛЬ.OS', 'другоймодуль.bsp', 'ObjectModule.bsl']) {
    await page.locator('#search').fill(query);
    await expect(page.locator('#search-status-text')).toContainText('Найдено 1 по всему ZIP');
    await expect(page.locator('#item-list button')).toHaveCount(1);
    await page.getByRole('tab', {name:'Исходный файл', exact:true}).click();
    await expect(page.getByLabel('Исходный код', {exact:true})).toHaveText(app.module);
    await page.getByRole('tab', {name:'Происхождение', exact:true}).click();
    await expect(page.locator('#detail-content')).toContainText(app.module_sha256);
    await expect(page.locator('#detail-content')).toContainText(app.archives.many.sha256);
    await expect(page.locator('#detail-content')).toContainText(app.many_path.slice(0,-4)+'/Ext/');
  }
  await expect(page.locator('#toast')).not.toBeVisible();
  await page.screenshot({path:testInfo.outputPath('late-module-verified-provenance.png'),fullPage:true});
  await page.locator('#search').fill('');
  await expect(page.locator('#item-list button')).toHaveCount(3);
  await page.locator('#cancel-search').click();
  await expect(page.locator('#item-list button')).toHaveCount(200);
  await expect(page.locator('#result-count')).toHaveText('Показано 200 из 204');
  await expect(page.locator('#truncation-warning')).toContainText('не содержимое кода');
  await page.locator('#search').fill('ObjectModule.bsl');
  await expect(page.locator('#search-status-text')).toContainText('Найдено 201 по всему ZIP');
  await expect(page.locator('#item-list button')).toHaveCount(200);
  await page.locator('#search').fill('Synthetic only');
  await expect(page.locator('#no-results')).toBeVisible();
  await page.locator('#search').fill('поздниймодуль.os');
  await expect(page.locator('#item-list button')).toHaveCount(1);
  await page.getByRole('tab', {name:'Исходный файл', exact:true}).click();
  await expect(page.getByLabel('Исходный код', {exact:true})).toHaveText(app.module);
});

test('late module discovery cannot overwrite newer query, cancelled search, view or import', async ({page, app}) => {
  await importZip(page, app.archives.many.path);
  await expect(page.locator('#metric-modules')).toHaveText('204');
  await page.locator('[data-view="modules"]').click();
  let nextGate;
  const gates=[];
  function holdNextReady() {
    let release,reached;
    const hold=new Promise(resolve=>{release=resolve;});
    const ready=new Promise(resolve=>{reached=resolve;});
    nextGate={release,reached,hold,ready};gates.push(nextGate);return nextGate;
  }
  await page.route(`${app.origin}/api/search?*`,async route=>{
    const response=await route.fetch();
    const data=await response.json();
    if(nextGate&&data.status==='ready'&&data.kind==='modules'){
      const gate=nextGate;nextGate=null;gate.reached();await gate.hold;
    }
    await route.fulfill({response});
  });
  try {
    const oldQuery=holdNextReady();
    await page.locator('#search').fill('поздниймодуль.os');await oldQuery.ready;
    await page.locator('#search').fill('absent-owned-module');oldQuery.release();
    await expect(page.locator('#no-results')).toBeVisible();
    const cancelled=holdNextReady();
    await page.locator('#search').fill('поздниймодуль.os');await cancelled.ready;
    await page.locator('#cancel-search').click();cancelled.release();
    await expect(page.locator('#item-list button')).toHaveCount(200);
    await expect(page.locator('#search')).toHaveValue('');
    const oldView=holdNextReady();
    await page.locator('#search').fill('поздниймодуль.os');await oldView.ready;
    await page.locator('[data-view="objects"]').click();oldView.release();
    await page.locator('#search').fill(app.many_name);
    await expect(page.locator('#detail-panel h2')).toHaveText(app.many_name);
    await expect(page.locator('#item-list button')).toHaveCount(1);
    await page.locator('[data-view="modules"]').click();
    const oldArchive=holdNextReady();
    await page.locator('#search').fill('поздниймодуль.os');await oldArchive.ready;
    await importZip(page,app.archives.first.path);await ready(page,'first.zip');
    oldArchive.release();await page.unrouteAll({behavior:'wait'});
    await expect(page.locator('#detail-panel h2')).toHaveText('Products');
    await expect(page.locator('#metric-modules')).toHaveText('1');
    await expect(page.locator('#search-status')).not.toBeVisible();
  } finally {for(const gate of gates)gate.release();await page.unrouteAll({behavior:'wait'});}
});

async function discoverLongRelatedFolder(page,app){
  await importZip(page,app.archives.many.path);
  await expect(page.locator('#metric-objects')).toHaveText('201');
  await page.locator('#search').fill(app.many_name);
  await expect(page.locator('#detail-panel h2')).toHaveText(app.many_name);
  await noHorizontalOverflow(page);
  await page.locator('#discover-related-modules').click();
  await expect(page.locator('#search-status-text')).toContainText('Найдено 3 по всему ZIP');
  await expect(page.locator('#search-status-text')).toContainText(app.many_path);
  await expect(page.locator('#cancel-search')).toBeVisible();
}

async function exerciseBoundedPagination(page,app){
  await importZip(page,app.archives.paged.path);
  await expect(page.locator('#page-range')).toHaveText('Строки 1–200 из 401');
  await noHorizontalOverflow(page);
  await page.locator('#next-page').click();
  await expect(page.locator('#page-range')).toHaveText('Строки 201–400 из 401');
  await noHorizontalOverflow(page);
  await page.locator('#previous-page').click();
  await expect(page.locator('#page-range')).toHaveText('Строки 1–200 из 401');
  await expect(page.locator('#next-page')).toBeEnabled();
  await expect(page.locator('#toast')).not.toBeVisible();
  await noHorizontalOverflow(page);
}

async function exerciseLiteralSearch(page,app){
  await importZip(page,app.archives.source.path);
  await expect(page.locator('#metric-modules')).toHaveText('204');
  await page.locator('[data-view="modules"]').click();
  await expect(page.locator('#module-search-mode')).toHaveAccessibleName('Режим поиска модулей');
  await page.getByLabel('Режим поиска модулей',{exact:true}).selectOption('source');
  await expect(page.locator('#module-search-mode')).toHaveAccessibleName('Режим поиска модулей');
  await page.getByRole('searchbox',{name:'Поиск точного фрагмента кода',exact:true}).fill(app.source_query);
  await expect(page.locator('#source-coverage')).toContainText('Частичное покрытие');
  await noHorizontalOverflow(page);
  await page.locator('#next-page').click();
  await expect(page.locator('#page-range')).toHaveText('Строки 201–201 из 201');
  await page.getByRole('tab',{name:'Исходный файл',exact:true}).click();
  await expect(page.getByLabel('Первое совпадение',{exact:true})).toContainText(app.source_query);
  await expect(page.getByLabel('Исходный код',{exact:true})).toHaveText(app.source_module);
  await expect(page.locator('#toast')).not.toBeVisible();
  await noHorizontalOverflow(page);
}
