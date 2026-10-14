import {expect, importZip} from './fixtures.mjs';

export const labels = {
  unchanged: 'Без изменений относительно Base',
  same_change: 'Одинаковое отличие от Base',
  keep_current: 'Отличается только Current',
  take_upstream: 'Отличается только Upstream',
  conflict: 'Разные отличия Current и Upstream',
};

export function expectedRows(app, action = 'changes') {
  return app.threeway.rows.filter(row => action === 'all' || row.action === action
    || (action === 'changes' && row.action !== 'unchanged'));
}

export function nextPageResponse(page, app, action, offset = 0) {
  return page.waitForResponse(response => {
    const url = new URL(response.url());
    return url.origin === app.origin && url.pathname === '/api/threeway-page'
      && url.searchParams.get('action') === action
      && Number(url.searchParams.get('offset')) === offset;
  });
}

export async function verifyPage(page, app, response, action, offset = 0) {
  expect(response.status()).toBe(200);
  const reply = await response.json();
  const expected = expectedRows(app, action);
  for (const role of ['base', 'current', 'upstream']) {
    expect(reply[`${role}_sha256`]).toBe(app.threeway.archives[role].sha256);
    expect(new URL(response.url()).searchParams.get(`${role}_sha256`))
      .toBe(app.threeway.archives[role].sha256);
  }
  expect(reply.action).toBe(action);
  expect(reply.page).toMatchObject({
    offset, limit: 200, total: expected.length,
    returned: Math.min(200, expected.length - offset),
    has_previous: offset > 0, has_next: offset + 200 < expected.length,
  });
  expect(reply.page.id).toEqual(expect.any(String));
  expect(reply.counts).toEqual(app.threeway.counts);
  expect(reply.coverage).toEqual(app.threeway.coverage);
  expect(reply.rows).toEqual(expected.slice(offset, offset + 200));
  const rows = page.locator('#threeway-list li');
  await expect(rows).toHaveCount(reply.page.returned);
  const texts = await rows.allTextContents();
  for (const [index, row] of reply.rows.entries()) {
    expect(texts[index]).toContain(row.path);
    expect(texts[index]).toContain(labels[row.action]);
    for (const role of ['base', 'current', 'upstream']) {
      if (row[role] !== null) expect(texts[index]).toContain(row[role].raw_sha256);
      else expect(texts[index]).toContain(`${role[0].toUpperCase()}${role.slice(1)}: файл отсутствует`);
    }
  }
  await expect(page.locator('#threeway-result')).toBeVisible();
  await expect(page.locator('#threeway-coverage')).toContainText(`Полный инвентарь по точным путям: ${expectedRows(app, 'all').length}`);
  await expect(page.locator('#threeway-range')).toHaveText(
    `Пути ${offset + 1}–${offset + reply.rows.length} из ${expected.length}`);
  await expect(page.locator('#threeway-list img, #threeway-list svg, #threeway-list script, #threeway-list pre'))
    .toHaveCount(0);
  expect(await page.evaluate(() => globalThis.ownedThreewayInjected)).toBeUndefined();
  return reply;
}

export async function importCurrent(page, app) {
  await importZip(page, app.threeway.archives.current.path);
  await expect(page.locator('#progress-dialog')).not.toBeVisible();
  await expect(page.locator('#page-subtitle')).toContainText('threeway-current.zip');
  await expect(page.locator('#metric-objects')).toHaveText('1');
  await expect(page.locator('#metric-modules')).toHaveText(String(app.threeway.current_modules));
  await page.getByRole('button', {name: 'Три версии ZIP', exact: true}).click();
  await expect(page.locator('#threeway-confirm')).toBeEnabled();
  await expect(page.locator('#threeway-base-file')).toBeDisabled();
  await expect(page.locator('#threeway-upstream-file')).toBeDisabled();
  await expect(page.locator('#threeway-result')).not.toBeVisible();
}

export async function confirmCurrent(page, app) {
  const started = page.waitForResponse(response => response.url() === `${app.origin}/api/threeway-start`);
  await page.locator('#threeway-confirm').click();
  const response = await started;
  expect(response.status()).toBe(201);
  expect((await response.json()).current_sha256).toBe(app.threeway.archives.current.sha256);
  await expect(page.locator('#threeway-current')).toContainText(app.threeway.archives.current.sha256);
  await expect(page.locator('#threeway-current')).toContainText('threeway-current.zip');
  await expect(page.locator('#threeway-base-file')).toBeEnabled();
  await expect(page.locator('#threeway-upstream-file')).toBeEnabled();
}

export async function openThreeway(page, app) {
  await importCurrent(page, app);
  await confirmCurrent(page, app);
  await page.locator('#threeway-base-file').setInputFiles(app.threeway.archives.base.path);
  await expect(page.locator('#threeway-base')).toContainText(app.threeway.archives.base.sha256);
  await expect(page.locator('#threeway-upstream-file')).toBeEnabled();
  const received = nextPageResponse(page, app, 'changes');
  await page.locator('#threeway-upstream-file').setInputFiles(app.threeway.archives.upstream.path);
  await verifyPage(page, app, await received, 'changes');
  for (const role of ['base', 'current', 'upstream']) {
    await expect(page.locator(`#threeway-${role}`)).toContainText(app.threeway.archives[role].filename);
    await expect(page.locator(`#threeway-${role}`)).toContainText(app.threeway.archives[role].sha256);
  }
}

export async function selectAction(page, app, action) {
  const received = nextPageResponse(page, app, action);
  await page.locator('#threeway-filter').selectOption(action);
  return verifyPage(page, app, await received, action);
}

export async function deliveredFrames(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

// Delay only a genuine response from the production server. Never manufacture
// inventory data or route around the real Rust input boundary.
export async function holdReply(page, pattern, matches = () => true) {
  let release, observed, delivered, taken = false;
  const hold = new Promise(resolve => {release = resolve;});
  const seen = new Promise(resolve => {observed = resolve;});
  const sent = new Promise(resolve => {delivered = resolve;});
  const handler = async route => {
    const response = await route.fetch();
    const data = await response.json();
    if (!taken && matches(data)) {
      taken = true;
      observed(data);
      await hold;
      await route.fulfill({response});
      delivered();
    } else await route.fulfill({response});
  };
  await page.route(pattern, handler);
  return {seen, release, sent,
    async close() {release(); await page.unroute(pattern, handler);}};
}
