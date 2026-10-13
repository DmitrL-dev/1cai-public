import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir: '.', testMatch: '**/*.spec.mjs', workers: 1,
  fullyParallel: false, forbidOnly: !!process.env.CI, retries: 0,
  timeout: 60000, expect: {timeout: 10000},
  outputDir: '../../../output/gui-browser/results',
  reporter: [['line'], ['junit', {outputFile: '../../../output/gui-browser/junit.xml'}]],
  // Never persist session-bearing network traces or browser profiles.
  use: {trace: 'off', video: 'off', screenshot: 'off'},
});
