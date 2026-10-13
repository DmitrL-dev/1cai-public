import {readFileSync,writeFileSync} from 'node:fs';
import * as k from './reference/kit/iso-kit.mjs';
import * as G from './reference/kit/lathe.mjs';
import * as A from './reference/kit/audit.mjs';
import {turning} from './reference/kit/turn-build.mjs';
import {TURN} from './reference/kit/turn.mjs';
import * as TA from './reference/kit/turn-audit.mjs';
const D=JSON.parse(readFileSync(new URL('./architecture.json',import.meta.url),'utf8'));
export const P=k.fitProjection(k.boxCorners({x:-213,y:-125,w:426,d:328,r:0},-5,65),1000,720,{pad:58,azimuth:38,elevation:43});
export const R=A.recorder(P),T=turning(P,{recorder:R});
const world=T.group('world',{free:{origin:[0,35,12]}}),layer=T.layer('architecture');T.stack(['architecture']);
const objects=[],parts=[];
const plans=[['interfaces',-160,-48,'entry','CLI / MCP'],['gui',-160,48,'entry','ZIP / HTTP'],['identity',-80,-75,'trust','IDENTITY'],['state',-80,0,'state','RECEIPTS'],['snapshots',-80,75,'immutable','SNAPSHOT'],['graph',0,-75,'analysis','BSL GRAPH'],['metadata',0,0,'analysis','METADATA'],['diagnostics',0,75,'analysis','DIAGNOSTIC'],['drafts',80,-48,'write','DRAFT'],['native',80,48,'write','CHECK / APPLY'],['observer',160,-75,'evidence','OBSERVER'],['evidence',160,0,'evidence','EVIDENCE'],['delivery',160,75,'delivery','BUILD / TEST'],['kernel',0,155,'experimental','RUST KERNEL']];
const materials={entry:'steel',trust:'brass',state:'steel',immutable:'steel',analysis:'gunmetal',write:'copper',evidence:'steel',delivery:'steel',experimental:'gunmetal'};
const descriptions={interfaces:'Внешние точки входа CLI и MCP',gui:'Ограниченный локальный ZIP workspace и HTTP',identity:'Проверка контекста и полномочий',state:'Состояние операций и квитанции',snapshots:'Зафиксированный захват и неизменяемое чтение',graph:'Извлечённый BSL-граф',metadata:'Метаданные и план обновления',diagnostics:'Подключаемая BSL-диагностика',drafts:'Предложение до контролируемой записи',native:'Отдельные проверки и явно разрешённая запись',observer:'Наблюдение за Git и службами',evidence:'Свидетельства, отчёты и доставка',delivery:'Проверки, поставка и планы',kernel:'Отдельный экспериментальный Rust контур'};
function makeSystem([id,cx,cy,role,mark],index){
 const section=D.sections.find(s=>s.id===id);if(!section)throw Error('Missing source system '+id);
 const len=Math.hypot(cx,cy-35)||1,direction=[cx/len,(cy-35)/len,0];
 const g=T.group('sys_'+id,{parent:world,slide:{direction,travel:22}}),material=materials[role];let serial=0,maxZ=3;
 const remember=(p,feature)=>{parts.push({name:p.name,entityId:id,system:id,group:g.name,feature});return p;};
 const name=feature=>`${feature==='source-domain'?'stand':'system'}.${id}.${serial++}.${feature}`;
 const box=(feature,x,y,z,w,d,h,mat=material)=>{maxZ=Math.max(maxZ,z+h);return remember(T.prism({name:name(feature),group:g,layer,plan:{x:cx+x,y:cy+y,w,d,r:.55},z,h,bevel:.25,steps:2,tone:mat?'hi':'mid',...(mat?{material:mat}:{})}),feature);};
 const round=(feature,x,y,z,r,h,mat=material)=>{maxZ=Math.max(maxZ,z+h);return remember(T.round({name:name(feature),group:g,layer,F:G.frameOf([cx+x,cy+y,0],[0,0,1],[1,0,0],[0,1,0]),s0:z,s1:z+h,r,material:mat,tone:'hi'}),feature);};
 // Each stand.* domain plinth lies at rest z=0; the ordinary Anatomy support rule applies.
 const base=box('source-domain',-29,-24,0,58,48,3,null);
 // Motifs express semantic roles, never hardware or runtime metrics.
 if(id==='interfaces'){
  box('entry-hub',-13,-7,3,26,19,13);for(const x of [-22,-5,12])box('entry-port',x,-19,3,10,9,7);
  box('adapter',-21,14,3,42,4,5);box('command-surface',-10,-4,16,20,13,1,'gunmetal');
 }else if(id==='gui'){
  box('workspace-back',-22,-13,3,44,3,23);box('window-left',-22,-10,3,3,23,23);box('window-right',19,-10,3,3,23,23);
  box('window-top',-19,-10,23,38,23,3);box('submitted-archive',-11,-3,3,22,14,7,'gunmetal');
 }else if(id==='identity'){
  box('context-gate-left',-20,-13,3,7,27,18);box('context-gate-right',13,-13,3,7,27,18);box('authorization-gate',-13,-13,17,26,27,4);round('capability-key',0,0,3,6,7,'brass');box('scope-card',-22,17,3,44,3,3);
 }else if(id==='state'){
  for(let i=0;i<4;i++)box('receipt-layer',-19,-13,3+i*4,38,26,4,i%2?'gunmetal':'steel');box('receipt-index',-22,16,3,44,3,4,'brass');
 }else if(id==='snapshots'){
  for(let i=0;i<3;i++)box('immutable-snapshot',-22+i*15,-14,3,11,28,16);box('retained-source-lock',-18,16,3,36,3,4,'brass');box('snapshot-index',-22,-20,3,44,3,3);
 }else if(id==='graph'){
  for(const [x,y]of [[-17,-10],[12,-10],[-17,9],[12,9]])box('source-node',x-5,y-5,3,10,10,9);
  box('adjacency-row',-12,-12,6,19,4,3);box('adjacency-column',-19,-5,6,4,9,3);box('adjacency-row',-12,7,6,19,4,3);
 }else if(id==='metadata'){
  for(let i=0;i<4;i++)box('metadata-record',-22+i*12,-15,3,9,30,10+i*3);box('bounded-plan',-22,17,3,44,3,3,'brass');
 }else if(id==='diagnostics'){
  box('input',-22,-10,3,15,21,6);box('result',9,-10,3,13,21,11);box('probe-rail',-22,-18,3,44,4,4);box('probe-carriage',-4,-14,3,7,27,13,'brass');box('finding',-2,-7,16,3,11,3);
 }else if(id==='drafts'){
  box('retained-before',-22,-13,3,18,27,6,'steel');box('proposed-after',4,-13,3,18,27,11,'copper');box('revision-history',-22,17,3,44,3,4);box('explicit-approval',-2,-7,3,4,15,5,'brass');
 }else if(id==='native'){
  box('check-domain',-22,-13,3,14,27,14,'steel');box('write-domain',8,-13,3,14,27,19,'copper');box('explicit-gate-left',-5,-10,3,3,20,11,'brass');box('explicit-gate-right',2,-10,3,3,20,11,'brass');box('explicit-gate-top',-2,-10,11,4,20,3,'brass');
 }else if(id==='observer'){
  round('watched-source',0,0,3,16,5);round('committed-snapshot',0,0,8,11,3,'gunmetal');box('watch-marker',-1,-9,11,2,12,2,'brass');box('watch-service',-22,-20,3,44,4,5);box('outbox',-18,17,3,36,3,5);
 }else if(id==='evidence'){
  for(let i=0;i<3;i++)box('evidence-record',-22+i*15,-15+i*3,3,12,28-i*3,7+i*5,'steel');box('provenance-band',-22,17,3,44,3,4,'brass');
 }else if(id==='delivery'){
  box('source-checks',-23,-14,3,14,28,8);box('verification-harness',-7,-14,3,14,28,14,'gunmetal');box('distribution',9,-14,3,14,28,20);box('release-evidence',-23,17,3,46,3,4,'brass');
 }else if(id==='kernel'){
  for(const x of [-17,3])for(const y of [-13,4])box('experimental-core',x,y,3,14,12,9,'gunmetal');box('separate-contract',-22,17,3,44,3,4,'brass');
 }
 T.plane({part:base,o:[0,0,3],u:[1,0,0],v:[0,1,0],svg:`<text x="${cx}" y="${cy+22}" text-anchor="middle" style="font:2.45px ui-monospace,monospace;fill:var(--anatomy-hi)">${mark.replaceAll('&','&amp;')}</text>`});
 objects.push({id,group:g.name,anchor:[cx,cy,maxZ+1],bounds:{min:[cx-29,cy-24,0],max:[cx+29,cy+24,maxZ]},label:section.label,role,description:descriptions[id],mark,direction,travel:22,index,refs:section.refs||[],geometrySemantics:'Explanatory semantic motif; not physical hardware or a quantitative encoding.'});
}
plans.forEach(makeSystem);
export const follow=values=>{const next={...values};for(const o of objects)if(next[o.group]===undefined)next[o.group]=(values.apart??0)*o.travel;return next;};
export const poses=()=>{const states=[];for(const yaw of [0,30,45,90,135,180,225,270,315])for(const pitch of [-85,-45,0,45,85])for(const apart of [0,1])states.push(follow({world:{R:TURN.compose(TURN.rotation([1,0,0],pitch),TURN.rotation([0,0,1],yaw)),t:[0,0,0]},apart}));for(const o of objects)states.push(follow({world:null,apart:0,[o.group]:o.travel}));return states;};
export const out=T.build({statics:R.items,poses,verify:true});
const scene={P,width:1000,height:720,objects,parts,turn:out.data,verify:out.verify,report:out.report,sourceCommit:D.meta.sourceCommit,worldOrigin:[0,35,12],interaction:{yaw:'full turn',pitchRange:[-85,85],independentSlide:[0,22]},semantics:'Source architecture, not physical hardware. Geometry and distance are explanatory. Each assembly maps to a source-backed system.'};
writeFileSync('explorer-scene.json',JSON.stringify(scene));writeFileSync('explorer-scene.svg',out.layerSvg('architecture',{width:1000,height:720}));writeFileSync('explorer-scene.css',k.ISO_CSS+'\n'+out.css);
writeFileSync('qa/explorer-scene-build.json',JSON.stringify({parts:parts.length,objects:objects.length,report:out.report,poseCount:poses().length,bytes:JSON.stringify(out.data).length},null,2));
console.log(JSON.stringify({parts:parts.length,objects:objects.length,bytes:JSON.stringify(out.data).length,groups:out.report.groups,seconds:out.report.seconds}));
if(process.argv.includes('--audit')){A.settle(R,P);A.auditOrExit(R,P);TA.orbitOrExit(T,R,P,{poses,quick:process.argv.includes('--quick'),sweep:{at:yaw=>follow({world:{R:TURN.rotation([0,0,1],yaw),t:[0,0,0]},apart:0}),from:0,to:360,frame:1},clips:[{name:'pitch',at:t=>follow({world:{R:TURN.compose(TURN.rotation([1,0,0],-85+170*t),TURN.rotation([0,0,1],30)),t:[0,0,0]},apart:0}),from:0,to:1,frame:1/60},{name:'explode',at:t=>follow({world:null,apart:t}),from:0,to:1,frame:1/60}],log:x=>console.log(x)});}
