/** Hash the actual static ES-module import closure, not a directory inventory. Run from atlas root. */
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve,relative,dirname} from 'node:path';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const hash=b=>createHash('sha256').update(b).digest('hex');
const root=process.cwd(),entries=['qa/overview-geometry.mjs','qa/cutaway-geometry.mjs'],seen=new Set(),builtins=new Set();
function visit(path){const absolute=resolve(root,path);if(seen.has(absolute))return;seen.add(absolute);const text=readFileSync(absolute,'utf8');for(const m of text.matchAll(/(?:^|\n)\s*(?:import|export)\s+(?:[^;]*?\s+from\s*)?['"]([^'"]+)['"]/g)){const spec=m[1];if(spec.startsWith('node:'))builtins.add(spec);else if(spec.startsWith('.'))visit(relative(root,resolve(dirname(absolute),spec)));else throw new Error('Unpinned external import: '+spec);}}
entries.forEach(visit);
const sources=Object.fromEntries([...seen].sort().map(path=>{const p=relative(root,path),bytes=readFileSync(path);execFileSync('git',['ls-files','--error-unmatch',p],{stdio:'pipe'});return[p,{sha256:hash(bytes),gitBlob:execFileSync('git',['hash-object',p],{encoding:'utf8'}).trim()}];}));
const detail=JSON.parse(readFileSync('detail-scene.json')),overview=JSON.parse(readFileSync('explorer-scene.json'));
const geometry=x=>Object.fromEntries(['P','turn','objects','parts','width','height','budget'].filter(k=>k in x).map(k=>[k,x[k]]));
const report={scope:'Actual static import closure for both full audit entry points. Builtins excluded from source hashes. Generated source input listed separately. Geometry digest excludes editorial model metadata and timing reports.',entries,sources,builtins:[...builtins].sort(),generatedInput:{'architecture.json':hash(readFileSync('architecture.json'))},geometry:{detail:hash(JSON.stringify(geometry(detail))),overview:hash(JSON.stringify(geometry(overview)))},sourceCommit:detail.sourceCommit};
const output=process.argv[2]||'qa/qualification-import-closure.json';writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({output,sourceFiles:Object.keys(sources).length,geometry:report.geometry}));
