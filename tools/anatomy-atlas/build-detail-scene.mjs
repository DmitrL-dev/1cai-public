import {readFileSync,writeFileSync} from 'node:fs';
import * as k from './reference/kit/iso-kit.mjs';
import * as A from './reference/kit/audit.mjs';
import * as TA from './reference/kit/turn-audit.mjs';
import {turning} from './reference/kit/turn-build.mjs';
import {TURN} from './reference/kit/turn.mjs';
import {cutawayModels} from './cutaway-model.mjs';
const D=JSON.parse(readFileSync('architecture.json','utf8'));
export const P=k.fitProjection(k.boxCorners({x:-118,y:-100,w:236,d:205,r:0},-4,110),1000,720,{pad:80,azimuth:32,elevation:38});
export const R=A.recorder(P),T=turning(P,{recorder:R});
const world=T.group('world',{free:{origin:[0,0,0]}}),cover=T.group('cover',{parent:world,hinge:{point:[0,-58,27.2],axis:[1,0,0],range:[0,105]}}),left=T.group('leftCompartments',{parent:world,slide:{direction:[-1,0,3],travel:31.6227766017}}),right=T.group('rightCompartments',{parent:world,slide:{direction:[1,0,3],travel:31.6227766017}}),focus=T.group('focus',{parent:left,free:{origin:[-39,-28,0]}}),layer=T.layer('detail');T.stack(['detail']);
const objects=[],parts=[];
const box=(name,group,x,y,z,w,d,h,material='steel')=>{const p=T.prism({name,group,layer,plan:{x,y,w,d,r:.3},z,h,bevel:.2,steps:2,material,tone:'hi'});parts.push({name,group:group.name});return p;};
box('stand.shell.base',world,-80,-58,0,160,116,3,'gunmetal');
box('shell.back',world,-80,-58,3.1,160,3,22);
box('shell.left',world,-80,-55,3.1,3,110,14);
box('shell.right',world,77,-55,3.1,3,110,14);
box('shell.front',world,-77,55,3.1,154,3,8);
const coverPart=box('cover.surface',cover,-77,-56,25.2,154,110,2,'steel');
for(const [z,sign] of [[25.19,-1],[27.21,1]])T.plane({part:coverPart,o:[0,0,z],u:[1,0,0],v:[0,sign,0],svg:'<text data-cutaway-name x="0" y="-10" text-anchor="middle" style="font:8px monospace;fill:var(--anatomy-hi)">SYSTEM</text><text data-cutaway-caption x="0" y="0" text-anchor="middle" style="font:3.5px monospace;fill:var(--anatomy-hi)">SOURCE SNAPSHOT</text>'});
box('cover.index',cover,-30,35,27.3,60,5,1,'brass');
objects.push({slot:'shell',group:'world',anchor:[0,57,12],bounds:{min:[-98,-90,0],max:[98,60,130]}});
const centers=[[-39,-28],[39,-28],[-39,28],[39,28]];
for(let i=0;i<4;i++){const [x,y]=centers[i],g=i%2?right:left;box('compartment'+i+'.tray',g,x-32,y-23,3.1,64,46,2,'gunmetal');box('compartment'+i+'.index',g,x-30,y+17,5.2,60,3,3,['brass','copper','steel','gunmetal'][i]);objects.push({slot:'compartment'+i,group:g.name,anchor:[x,y+18,8],center:[x,y],bounds:{min:[x-32,y-23,3],max:[x+32,y+23,8]}});for(let j=0;j<2;j++){const sx=x-30+j*32;box('source'+i+'_'+j+'.module',g,sx,y-21,5.2,28,5,5,'steel');objects.push({slot:'source'+i+'_'+j,group:g.name,anchor:[sx+14,y-18,11],bounds:{min:[sx,y-21,5],max:[sx+28,y-16,10]}});}}
box('focus.file',focus,-62,-42,5.2,46,28,5,'steel');box('focus.declaration',focus,-57,-38,10.3,36,17,2,'brass');
objects.push({slot:'focus',group:'focus',anchor:[-39,-28,13],bounds:{min:[-62,-42,5],max:[-16,-14,12]}});
for(let i=0;i<6;i++){const x=-62+i*25;box('stand.neighbor'+i+'.file',world,x-9,65,0,18,15,3,'steel');objects.push({slot:'neighbor'+i,group:'world',anchor:[x,73,4],bounds:{min:[x-9,65,0],max:[x+9,80,3]}});}
export function detailPose({yaw=0,pitch=0,opening=1,compartment=0}={}){const [x,y]=centers[compartment];return{world:{R:TURN.compose(TURN.rotation([1,0,0],pitch),TURN.rotation([0,0,1],yaw))},cover:opening*105,leftCompartments:opening*31.6227766017,rightCompartments:opening*31.6227766017,focus:{R:TURN.rotation([0,0,1],0),t:[x+39+(compartment%2?opening*20:0),y+28,opening*8]}};}
export const poses=()=>[-85,-45,0,45,85].flatMap(pitch=>[0,45,90,180,270,315].flatMap(yaw=>[0,.5,1].flatMap(opening=>[0,1,2,3].map(compartment=>detailPose({yaw,pitch,opening,compartment})))));
export const out=T.build({statics:R.items,poses,verify:true});
const model={P,turn:out.data,objects,parts,report:out.report,verify:out.verify,width:1000,height:720,models:cutawayModels(D),sourceCommit:D.meta.sourceCommit,budget:{solids:parts.length,movingChildGroups:4,neighborLabels:6,projectedRelations:12},semantics:'Persistent source-system enclosure, editorial directory/role compartments, one focused source; not runtime or physical hardware.'};
writeFileSync('detail-scene.json',JSON.stringify(model));writeFileSync('detail-scene.svg',out.layerSvg('detail',{width:1000,height:720}));writeFileSync('detail-scene.css',k.ISO_CSS+'\n'+out.css);console.log(JSON.stringify({detail:true,parts:parts.length,report:out.report}));
if(process.argv.includes('--audit')){A.settle(R,P);A.auditOrExit(R,P);TA.orbitOrExit(T,R,P,{poses,quick:process.argv.includes('--quick'),sweep:{at:yaw=>detailPose({yaw}),from:0,to:360,frame:1},clips:[{name:'cover',at:opening=>detailPose({opening}),from:0,to:1,frame:1/60},{name:'pitch',at:t=>detailPose({pitch:-85+170*t,yaw:30}),from:0,to:1,frame:1/60}],log:x=>console.log(x)});}
