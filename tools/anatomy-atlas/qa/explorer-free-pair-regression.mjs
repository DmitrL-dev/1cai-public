import {readFileSync,writeFileSync,mkdirSync,copyFileSync,readdirSync,mkdtempSync} from 'node:fs';
import {tmpdir} from 'node:os';import {join,resolve} from 'node:path';import {pathToFileURL} from 'node:url';import {createHash} from 'node:crypto';import assert from 'node:assert/strict';
import {turning as patched} from '../reference/kit/turn-build.mjs';import {TURN} from '../reference/kit/turn.mjs';import * as A from '../reference/kit/audit.mjs';import * as TA from '../reference/kit/turn-audit.mjs';
const root=resolve('.'),temp=mkdtempSync(join(tmpdir(),'rentgen-free-pair-'));
const patchedText=readFileSync('reference/kit/turn-build.mjs','utf8');
const localFix='// Local conservative fix: distant rigid parts can overlap after free rotation.\n          // Keep all same-group separating planes; proximity is not a visibility bound.\n          if (a.group && a.group.loose) near = true;';
assert.ok(patchedText.includes(localFix));const upstream=patchedText.replace(localFix,'if (a.group && a.group.loose) near = G.len3(sub3(sb.c, sa.c)) < sa.r + sb.r + 1;');
const bytes=Buffer.from(upstream),sha=createHash('sha1').update('blob '+bytes.length+'\0').update(bytes).digest('hex');assert.equal(sha,'3bfe31b9bb87c7d0b7b75f62054149bfa583fb1a');
for(const name of readdirSync('reference/kit'))if(name.endsWith('.mjs'))copyFileSync(join(root,'reference/kit',name),join(temp,name));writeFileSync(join(temp,'turn-build.mjs'),upstream);
const {turning:original}=await import(pathToFileURL(join(temp,'turn-build.mjs')).href);
const P={origin:[500,360],scale:1,azimuth:38,elevation:43};
const pose=(pitch,yaw=30)=>({world:{R:TURN.compose(TURN.rotation([1,0,0],pitch),TURN.rotation([0,0,1],yaw)),t:[0,0,0]},sys:0});
function fixture(builder,kind){const R=A.recorder(P),T=builder(P,{recorder:R}),w=T.group('world',{free:{origin:[0,35,12]}}),g=T.group('sys',{parent:w,slide:{direction:[0,-1,0],travel:22}}),l=T.layer('test');T.stack(['test']);
 const box=(name,x,y,z,width,depth,height)=>T.prism({name,group:g,layer:l,plan:{x,y,w:width,d:depth,r:.55},z,h:height,bevel:.25,steps:2});
 if(kind==='distant'){box('stand.graph',-29,-99,0,58,48,3);box('graph.near',7,-90,3,10,10,9);box('graph.far',7,-71,3,10,10,9);}
 else{box('stand.state',-29,-24,0,58,48,3);for(let i=0;i<4;i++)box('state.receipt'+i,-19,-13,3+4*i,38,26,4);}
 T.build({poses:[pose(-85),pose(0),pose(85)],verify:true});return{T,R};}
const results=[];
for(const kind of ['distant','contact'])for(const [name,builder]of [['upstream',original],['patched',patched]]){
 const {T,R}=fixture(builder,kind),sweep=kind==='distant'?{at:()=>pose(-85),from:0,to:1,frame:1}:{at:t=>pose(50+15*t),from:0,to:1,frame:1/60};
 const report=TA.orbit(T,R,P,{quick:true,only:['order','depth'],sweep,poses:[pose(-85),pose(85)]});
 results.push({fixture:kind,builder:name,planes:T.data.layers[0].planar?.length??null,depth:report.depth.length,swaps:report.swaps.length,cycles:report.cycles.length,forced:report.forced.length,unseparated:report.unseparated.length,failures:TA.orbitFailures(report),messages:[...report.depth,...report.swaps]});
}
assert.ok(results.find(x=>x.fixture==='distant'&&x.builder==='upstream').depth>0,'Original exact pin must reproduce missing-pair depth error');
for(const r of results.filter(x=>x.builder==='patched'))assert.equal(r.failures,0,JSON.stringify(r));
const report={upstreamCommit:'e6600ffc4e8e6620eeb45bf49bcdbd5e4b84163f',originalBuilderBlob:sha,scope:'Exact upstream-fails/patched-passes depth regression plus flush-contact order sweep; official order/depth checks only, not full audit.',results};writeFileSync('qa/explorer-free-pair-regression.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
