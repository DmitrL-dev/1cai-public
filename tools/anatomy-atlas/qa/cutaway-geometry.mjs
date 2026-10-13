import {readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {T,R,P,poses,detailPose} from '../build-detail-scene.mjs';
import {TURN} from '../reference/kit/turn.mjs';
TURN.exact(true); // Match the viewer contract set in app.js; no audit threshold changes.
import * as A from '../reference/kit/audit.mjs';
import * as TA from '../reference/kit/turn-audit.mjs';
const quick=process.argv.includes('--quick'),focused=process.argv.includes('--focused');
A.settle(R,P);A.auditOrExit(R,P);
const result=TA.orbit(T,R,P,{poses,quick,...(focused?{only:['order','rigid','posed']}:{ }),sweep:{at:yaw=>detailPose({yaw}),from:0,to:360,frame:1},clips:[...Array.from({length:4},(_,compartment)=>({name:'cover-'+compartment,at:opening=>detailPose({opening,compartment}),from:0,to:1,frame:1/60})),{name:'pitch',at:t=>detailPose({pitch:-85+170*t,yaw:30}),from:0,to:1,frame:1/60}],log:x=>console.log(x)});
const paths=['build-detail-scene.mjs','cutaway-model.mjs','qa/cutaway-geometry.mjs','reference/kit/turn-build.mjs','reference/kit/turn.mjs','reference/kit/turn-audit.mjs','detail-scene.json'];
const report={scope:focused?'Focused preflight, not full qualification.':'Full official orbit audit of31convex solids,4moving child groups, free world orbit and synchronized hinge/slide opening. Discrete file focus in4compartments. Finite samples; not a continuous mathematical proof or browser QA.',quick,focused,sourceCommit:'6c8feb291dd251826eebb99e145f4a39f56cda47',hashes:Object.fromEntries(paths.map(p=>[p,createHash('sha256').update(readFileSync(p)).digest('hex')])),failures:TA.orbitFailures(result),result};
writeFileSync('qa/cutaway-geometry'+(focused?'-focused':'')+'.json',JSON.stringify(report,null,2));console.log(TA.orbitReport(result));process.exitCode=report.failures?1:process.exitCode||0;
