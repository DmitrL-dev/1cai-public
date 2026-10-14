import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
const read=path=>readFile(new URL(path,import.meta.url),'utf8');

test('integrated app retains independent source and comparison view guards and import recovery',async()=>{
 const app=await read('../../rentgen_core/gui_assets/app.js');
 assert.match(app,/import \{createComparison\} from '\.\/comparison.js'/);
 assert.match(app,/boundedMetadataQuery,boundedSourceQuery,searchReplyMatches/);
 const setView=app.slice(app.indexOf('function setView('),app.indexOf('function render('));
 assert.ok(setView.includes("'comparison'"));assert.ok(setView.includes('comparison.leave()'));
 assert.ok(setView.includes("state.moduleSearchMode='modules'"));assert.ok(setView.includes('invalidateMetadataSearch()'));
 const search=app.slice(app.indexOf('function queueMetadataSearch('),app.indexOf('async function runMetadataSearch('));
 assert.ok(search.includes("!['objects','modules'].includes(state.view)"));assert.ok(search.includes('boundedSourceQuery'));
 for(const name of ['startImport','checkUncertainImport']){
  const segment=app.slice(app.indexOf(`async function ${name}(`));
  assert.ok(segment.includes("if(state.view==='comparison')comparison.enter()"));
 }
});

test('combined browser gate retains all distinct scenarios and both reflow feature paths',async()=>{
 const files=(await readdir(new URL('browser/',import.meta.url))).filter(name=>name.endsWith('.spec.mjs'));
 const titles=[];
 for(const file of files){const spec=await read('browser/'+file);titles.push(...[...spec.matchAll(/^test\('([^']+)'/gm)].map(match=>match[1]));}
 assert.equal(titles.length,43);assert.equal(new Set(titles).size,43);
 const threeway=await read('browser/threeway.spec.mjs');
 assert.equal([...threeway.matchAll(/^test\('([^']+)'/gm)].length,7);
 const inline=await read('browser/line-diff.spec.mjs');
 assert.equal([...inline.matchAll(/^test\('([^']+)'/gm)].length,6);
 assert.equal(titles.length-[...threeway.matchAll(/^test\('([^']+)'/gm)].length-[...inline.matchAll(/^test\('([^']+)'/gm)].length,30);
 for(const file of ['source-search.spec.mjs','comparison.spec.mjs','search-comparison.spec.mjs','report.spec.mjs','attribute-search.spec.mjs','occurrence-navigation.spec.mjs','threeway.spec.mjs','line-diff.spec.mjs'])assert.ok(files.includes(file));
 const acceptance=await read('browser/acceptance.spec.mjs');
 assert.equal(acceptance.match(/await exerciseLiteralSearch\(page,app\)/g).length,2);
 assert.equal(acceptance.match(/await exerciseComparison\(page,app\)/g).length,2);
 const workflow=await read('../../.github/workflows/gui-browser-ci.yml');
 assert.ok(workflow.includes('assert len(cases) == 43'));
 for(const name of ['test_local_gui_source_search.py','test_local_gui_comparison.py','test_local_gui_search_comparison.py','test_local_gui_report.py'])assert.ok(workflow.includes(name));
});
