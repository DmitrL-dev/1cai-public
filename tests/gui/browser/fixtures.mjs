import {test as base, expect, chromium} from '@playwright/test';
import {spawn} from 'node:child_process';
import {mkdtemp, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createInterface} from 'node:readline';

const here = path.dirname(fileURLToPath(import.meta.url));
export const test = base.extend({
  app: async ({}, use) => {
    if (!process.env.RENTGEN_INPUT_CORE_TEST_BINARY) throw new Error('Set RENTGEN_INPUT_CORE_TEST_BINARY; real Rust acceptance must not skip');
    const installed = process.env.RENTGEN_GUI_INSTALLED_PYTHON;
    const args = installed ? ['-I', path.join(here, 'server.py'), '--installed'] : [path.join(here, 'server.py')];
    const child = spawn(installed || process.env.PYTHON || 'python', args, {stdio: ['pipe', 'pipe', 'pipe']});
    let stderr = '';
    child.stderr.on('data', data => { stderr += data; });
    const closed = new Promise(resolve => child.once('close', (code, signal) => resolve({code, signal})));
    const lines = createInterface({input: child.stdout});
    let timer;
    try {
      const app = await Promise.race([
        new Promise((resolve, reject) => {
          lines.once('line', line => {try {resolve(JSON.parse(line));} catch {reject(new Error('Invalid private bootstrap'));}});
          child.once('error', reject);
        }),
        closed.then(() => {throw new Error(`Synthetic server exited before readiness: ${stderr}`);}),
        new Promise((_, reject) => {timer = setTimeout(() => reject(new Error('Synthetic server readiness timed out')), 15000);}),
      ]);
      clearTimeout(timer);
      const origin = new URL(app.origin);
      if (origin.protocol !== 'http:' || origin.hostname !== '127.0.0.1' || !origin.port) throw new Error('Server must bind exact IPv4 loopback');
      await use(app);
    } finally {
      clearTimeout(timer);
      child.stdin.end('\n');
      const killTimer = setTimeout(() => child.kill('SIGTERM'), 10000);
      const result = await closed;
      clearTimeout(killTimer);
      lines.close();
      expect(result, `Server cleanup/state-integrity verification failed: ${stderr}`).toEqual({code: 0, signal: null});
    }
  },
  context: async ({app}, use) => {
    const profile = await mkdtemp(path.join(tmpdir(), 'rentgen-browser-profile-'));
    const extension = path.join(here, 'zoom-extension');
    let context;
    const unexpected = [];
    try {
      context = await chromium.launchPersistentContext(profile, {
        channel: 'chromium', headless: true, chromiumSandbox: true,
        viewport: null, reducedMotion: 'reduce',
        args: ['--window-size=1280,900', `--disable-extensions-except=${extension}`, `--load-extension=${extension}`],
      });
      await context.route('**/*', async route => {
        if (new URL(route.request().url()).origin === app.origin) await route.continue();
        else {unexpected.push(new URL(route.request().url()).origin); await route.abort('blockedbyclient');}
      });
      await use(context);
      expect(unexpected, 'App attempted non-loopback network access').toEqual([]);
    } finally {
      try {await context?.close();}
      finally {await rm(profile, {recursive: true, force: true});}
    }
  },
  page: async ({context, app}, use) => {
    const page = context.pages()[0] || await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    // Bootstrap token is never attached to reports/traces or printed by this harness.
    try {await page.goto(`${app.origin}/#${app.token}`);} catch {throw new Error('Loopback GUI navigation failed');}
    await expect(page.locator('#runtime-status')).toHaveText('Локальный сервис подключён');
    expect(new URL(page.url()).hash).toBe('');
    await use(page);
    expect(errors).toEqual([]);
  },
});
export {expect};

export async function importZip(page, file) {
  await page.locator('#import-button').click();
  await expect(page.locator('#import-dialog')).toBeVisible();
  await page.locator('#file-input').setInputFiles(file);
}
export async function ready(page, filename) {
  await expect(page.locator('#progress-dialog')).not.toBeVisible();
  await expect(page.locator('#page-subtitle')).toContainText(filename);
  await expect(page.locator('#metric-objects')).toHaveText('1');
  await expect(page.locator('#metric-modules')).toHaveText('1');
}
export async function noHorizontalOverflow(page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
}
export async function keyboardReach(page, locator) {
  for (let i = 0; i < 40; i++) {
    if (await locator.evaluate(element => element === document.activeElement)) return;
    await page.keyboard.press('Tab');
  }
  throw new Error('Control cannot be reached with Tab within one bounded traversal');
}
