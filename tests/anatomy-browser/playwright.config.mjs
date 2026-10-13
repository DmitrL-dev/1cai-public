import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'.',testMatch:'qualification.spec.mjs',workers:1,retries:0,fullyParallel:false,forbidOnly:true,timeout:60000,expect:{timeout:12000},outputDir:'output/results',
  reporter:[['line'],['json',{outputFile:'output/report.json'}],['junit',{outputFile:'output/junit.xml'}]],
  use:{browserName:'chromium',headless:true,launchOptions:{chromiumSandbox:true},viewport:{width:1440,height:1000},baseURL:'http://127.0.0.1:4179',reducedMotion:'reduce',screenshot:'only-on-failure',trace:'off',video:'off'},
  webServer:{command:'node server.mjs',url:'http://127.0.0.1:4179',reuseExistingServer:false,timeout:15000},
});
