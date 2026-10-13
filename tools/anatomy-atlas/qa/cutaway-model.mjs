import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {cutawayModels} from '../cutaway-model.mjs';
const D=JSON.parse(readFileSync('architecture.json')),models=cutawayModels(D);
assert.equal(Object.keys(models).length,14);
for(const section of D.sections){
 const model=models[section.id],files=D.nodes.filter(n=>n.id.startsWith('file:')&&n.systemId===section.id),ids=files.map(n=>n.id).sort();
 assert.equal(model.sourceCommit,'6c8feb291dd251826eebb99e145f4a39f56cda47');
 assert.ok(model.compartments.length>=1&&model.compartments.length<=4);
 assert.equal(model.fileCount,ids.length);
 assert.deepEqual(model.compartments.flatMap(c=>c.fileIds).sort(),ids,'Complete disjoint partition: '+section.id);
 for(const c of model.compartments){assert.ok(c.label&&c.basis);assert.ok(c.fileIds.length);assert.ok(c.refs.length);assert.ok(c.representativeIds.length<=2);for(const id of c.representativeIds)assert.ok(c.fileIds.includes(id));}
}
const native=models.native;
assert.equal(native.fileCount,24);assert.equal(native.compartments.length,4);
assert.deepEqual(native.compartments.map(c=>c.fileIds.length),[8,3,6,7]);
assert.ok(native.caveat.includes('Проверки не дают разрешение'));
assert.ok(native.caveat.includes('sealed'));
// A same-basename file cannot accidentally inherit a curated responsibility.
const injected=structuredClone(D),original=D.nodes.find(n=>n.id==='file:rentgen_core/capture.py');
injected.nodes.push({...original,id:'file:other/capture.py',path:'other/capture.py'});
const probe=cutawayModels(injected).snapshots;
assert.ok(probe.compartments.find(c=>c.label==='Другие файлы системы').fileIds.includes('file:other/capture.py'));
assert.ok(!probe.compartments[0].fileIds.includes('file:other/capture.py'));
const missing=structuredClone(D);missing.nodes=missing.nodes.filter(n=>n.id!==original.id);
assert.throws(()=>cutawayModels(missing),/Curated source path/);
console.log(JSON.stringify({scope:'Source partitions and exact-path editorial assignment',systems:14,files:Object.values(models).reduce((a,m)=>a+m.fileCount,0),nativePartitions:[8,3,6,7],passed:true}));
