import {readFile,writeFile,readdir,mkdir} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import path from 'node:path';
import assert from 'node:assert/strict';
const expected=[
  'Q01 orbit pitch pan zoom changes rendered geometry',
  'Q02 direct scene picking hierarchy and exact source',
  'Q03 dependency evidence and source routes',
  'Q04 navigation history isolation and filtering',
  'Q05 keyboard focus and reduced motion',
  'Q06 mobile touch navigation and readable detail',
  'Q07 light dark and narrow desktop readability',
  'Q08 bounded browser interaction performance',
  'Q09 selected-system opening is independent and reversible',
];
const errors=[],specs=[],artifacts=[];
async function check(name,fn){try{return await fn()}catch(error){errors.push({check:name,message:error.message});return null}}
const hash=async file=>createHash('sha256').update(await readFile(file)).digest('hex');
const report=await check('test-report',async()=>JSON.parse(await readFile('output/report.json','utf8')));
function visit(s){for(const spec of s.specs||[])specs.push(spec);for(const child of s.suites||[])visit(child)}if(report)visit(report);
await check('all-named-cases',()=>assert.deepEqual(specs.map(s=>s.title).sort(),[...expected].sort(),'Exact named qualification cases must all execute'));
for(const s of specs)await check(s.title,()=>{assert.equal(s.ok,true,s.title);assert.equal(s.tests.length,1);assert.equal(s.tests[0].expectedStatus,'passed');assert.equal(s.tests[0].results.length,1,'No retries or hidden flaky pass');assert.equal(s.tests[0].results[0].status,'passed',s.title)});
const checkout=await check('checkout-readable',()=>execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim());await check('exact-head',()=>{assert.ok(process.env.EXPECTED_HEAD,'EXPECTED_HEAD is mandatory');assert.equal(checkout,process.env.EXPECTED_HEAD)});
async function walk(dir){for(const f of await readdir(dir,{withFileTypes:true})){const p=path.join(dir,f.name);if(f.isDirectory())await walk(p);else if(/\.(png|json)$/.test(f.name))artifacts.push({path:p,sha256:await hash(p)})}}
await check('artifact-directory',()=>walk('output/results'));await check('detailed-screenshot-evidence',()=>assert.ok(artifacts.filter(x=>x.path.endsWith('.png')).length>=12,'Require detailed browser evidence, not case count alone'));
const dist=process.env.ATLAS_DIST||'../../tools/anatomy-atlas/dist';const htmlHash=await check('built-html-hash',()=>hash(path.join(dist,'index.html')));const sourceHash=await check('source-payload-hash',()=>hash(path.join(dist,'source-texts.json')));
const receipt={status:errors.length?'browser_assertions_failed_or_incomplete':'automated_browser_assertions_passed',checkout_commit:checkout,expected_commit:process.env.EXPECTED_HEAD||null,workflow_sha:process.env.GITHUB_SHA||null,atlas_html_sha256:htmlHash,source_payload_sha256:sourceHash,expected_cases:expected,observed_cases:specs.map(s=>s.title),sandbox_enabled_in_config:true,loopback_only_in_config:true,no_product_runtime:true,screenshot_visual_review:'pending',errors,artifacts};
await mkdir('output',{recursive:true});await writeFile('output/qualification.json',JSON.stringify(receipt,null,2)+'\n');console.log(`Qualification receipt: ${receipt.status}; ${errors.length} failed or incomplete gates`);if(errors.length)process.exitCode=1;
