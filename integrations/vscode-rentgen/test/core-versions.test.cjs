'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const versions=require('../lib/core-versions.cjs');
test('one explicit Core version list with ordered capability floors',()=>{
 const {PROFILE_CORE_VERSIONS:all,REPAIR_CORE_VERSIONS:repair,NATIVE_CORE_VERSIONS:native}=versions;
 assert.ok(Object.isFrozen(all)&&Object.isFrozen(repair)&&Object.isFrozen(native));
 assert.equal(all[0],'0.1.0.dev4');assert.equal(repair[0],'0.1.0.dev7');assert.equal(native[0],'0.1.0.dev8');
 assert.deepEqual(repair,all.slice(all.indexOf('0.1.0.dev7')));assert.deepEqual(native,all.slice(all.indexOf('0.1.0.dev8')));
 assert.ok(!all.includes('0.1.0.dev18'));assert.equal(new Set(all).size,all.length);
 assert.ok(all.every(v=>/^0\.1\.0\.dev\d+$/.test(v)));
 const numbers=all.map(v=>Number(v.slice(9)));assert.deepEqual(numbers,[...numbers].sort((a,b)=>a-b));
});
test('no other Companion source enumerates Core versions',()=>{
 const root=path.join(__dirname,'..');
 const files=['extension.cjs',...fs.readdirSync(path.join(root,'lib')).filter(n=>n.endsWith('.cjs')&&n!=='core-versions.cjs').map(n=>'lib/'+n)];
 for(const file of files)assert.doesNotMatch(fs.readFileSync(path.join(root,file),'utf8'),/'0\.1\.0\.dev\d+'/,file);
});
