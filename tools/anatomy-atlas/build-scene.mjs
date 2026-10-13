import {writeFileSync} from 'node:fs';
import * as k from './reference/kit/iso-kit.mjs';
import * as G from './reference/kit/lathe.mjs';
import * as A from './reference/kit/audit.mjs';
import {turning} from './reference/kit/turn-build.mjs';
import * as TA from './reference/kit/turn-audit.mjs';
import {TURN} from './reference/kit/turn.mjs';
TURN.exact(true);
import {turnScript} from './reference/scripts/inline-kit.mjs';
export const P=k.fitProjection(k.boxCorners({x:-105,y:-95,w:210,d:260,r:0},-8,159),900,680,{pad:30,azimuth:42,elevation:30});
export const R=A.recorder(P);export const T=turning(P,{recorder:R});
const body=T.group('cabinet',{turn:{pivot:[0,0]}}),layer=T.layer('instrument');T.stack(['instrument']);
const parts=[];const V=(x,y)=>G.frameOf([x,y,0],[0,0,1],[1,0,0],[0,1,0]);
function box(name,x,y,z,w,d,h,group=body,opts={}){const p=T.prism({name,group,layer,plan:{x,y,w,d,r:opts.r??.8},z,h,bevel:opts.bevel??.45,steps:3,tone:opts.tone??'mid',material:opts.material,details:{seams:opts.seams??[],dots:opts.screws?k.corners({x,y,w,d},Math.min(2,w/4,d/4)).map(([a,b])=>({at:[z+h,a,b],normal:[0,0,1],size:.4,tone:'lo'})):[],...opts.details}});if(p.planPath&&p.spec.ring){const xy=p.spec.ring;p.planPath=Array.from({length:xy.length/2},(_,i)=>(i?'L':'M')+xy[i*2].toFixed(6)+' '+xy[i*2+1].toFixed(6)).join('')+'Z';}parts.push({name,group,system:opts.system??null});return p;}
function round(name,x,y,z,h,r,group=body,opts={}){const p=T.round({name,group,layer,F:V(x,y),s0:z,s1:z+h,r,material:opts.material??'steel',tone:opts.tone??'mid',details:opts.details??{seams:[z+.7,z+h-.7]}});parts.push({name,group,system:opts.system??null});return p;}
for(const [x,y] of [[-48,-33],[48,-33],[-48,33],[48,33]]){round(`stand.foot.${x}.${y}`,x,y,-8,4,5,body,{material:'rubber'});round(`stand.flange.${x}.${y}`,x,y,-4,4,4,body);}
box('stand.plinth',-61,-46,0,122,92,5,body,{r:5,tone:'lo',seams:[2],screws:true});box('stand.deck',-58,-43,5,116,86,3,body,{r:3,tone:'mid',screws:true});
for(const x of [-54,50])for(const y of [-36,32])box(`stand.upright.${x}.${y}`,x,y,8,4,4,139,body,{r:.7,material:'steel'});
box('stand.crown',-57,-39,147,114,78,4,body,{r:3,screws:true});box('stand.cap',-53,-35,151,106,70,1.2,body,{r:2,tone:'lo',screws:true});
const drawers=[];
for(let i=0;i<7;i++){
 const z=14+i*18,group=T.group('drawer'+i,{parent:body,slide:{direction:[0,1,0],travel:90-i*11}});drawers.push({id:'drawer'+i,z,travel:90-i*11});
 for(const x of [-50,46])box(`stand.rail.${i}.${x}`,x,-34,z-2,4,66,2,body,{r:0,tone:'lo'});
 box(`tray${i}.floor`,-46,-32,z,92,61,2,group,{r:.3,screws:true});for(const x of [-46,44])box(`tray${i}.wall.${x}`,x,-32,z+2,2,61,5,group,{r:0,tone:'lo'});
 box(`tray${i}.front`,-44,27,z+2,88,2,5,group,{r:.2,material:'steel'});for(const x of [-20,18])box(`tray${i}.pull-neck.${x}`,x,29,z+3,2,5,2,group,{r:.4,material:'steel'});box(`tray${i}.pull`,-20,34,z+3,40,2,2,group,{r:.7,material:'steel'});
 for(let col=0;col<2;col++){
  const x=-39+col*43,sys=i*2+col;box(`system${sys}.board`,x,-27,z+2,35,45,1,group,{r:.8,tone:'lo',system:sys,screws:true});
  const chip=box(`system${sys}.core`,x+5,-19,z+3,24,22,4,group,{r:1.2,material:'gunmetal',system:sys,bevel:.7});
  // Fourteen etched, closed instrument glyphs explain each system without floating labels.
  const glyphs=[
   '<path d="M-7-6H-2V-2H-7ZM2-6H7V-2H2ZM-2 3H2V7H-2Z"/><path d="M-4.5-2V0H0V3M4.5-2V0H0"/><circle cx="0" cy="0" r=".7"/>',
   '<path d="M0-8L7-5V1L0 8L-7 1V-5Z"/><circle cx="0" cy="-2" r="2"/><path d="M-1 0H1V4H-1Z"/>',
   '<path d="M-7-7H7V-3H-7ZM-7-1H7V3H-7ZM-7 5H7V8H-7Z"/>',
   '<path d="M-7-7H4V4H-7ZM-4-4H7V7H-4Z"/>',
   '<path d="M-6-5L6-5L0 6ZM-6-5L0-1L6-5M0-1V6"/><circle cx="-6" cy="-5" r="1.5"/><circle cx="6" cy="-5" r="1.5"/><circle cx="0" cy="6" r="1.5"/><circle cx="0" cy="-1" r="1.5"/>',
   '<path d="M-8-7H8V7H-8ZM-8-3H8M-3-3V7"/><circle cx="-5" cy="-5" r=".6"/><circle cx="-2" cy="-5" r=".6"/>',
   '<path d="M-7-7H3V7H-7ZM-1 3L5-6L8-4L2 5L-1 6Z"/>',
   '<path d="M-7-6H-3V-4H-5V4H-3V6H-7ZM7-6H3V-4H5V4H3V6H7ZM-1-5H1V5H-1Z"/>',
   '<path d="M-8-7H-4V7H-8ZM4-7H8V7H4ZM-4-2H4V2H-4Z"/>',
   '<circle cx="-1" cy="-1" r="5"/><path d="M3 3L8 7L6 9L2 5Z"/><path d="M-4-1H2M-1-4V2"/><circle cx="-4" cy="-1" r=".5"/><circle cx="2" cy="-1" r=".5"/><circle cx="-1" cy="-4" r=".5"/><circle cx="-1" cy="2" r=".5"/>',
   '<circle cx="0" cy="0" r="7"/><path d="M0-5V0L4 2"/><circle cx="0" cy="-5" r=".6"/><circle cx="4" cy="2" r=".6"/>',
   '<path d="M-6-8H6V8L3 6L0 8L-3 6L-6 8Z"/><path d="M-3-1L-1 2L4-4"/><circle cx="-3" cy="-1" r=".6"/><circle cx="4" cy="-4" r=".6"/>',
   '<path d="M-6-6H6V6H-6ZM-3-3H3V3H-3Z"/><path d="M-8-3H-6M-8 0H-6M-8 3H-6M6-3H8M6 0H8M6 3H8"/><circle cx="-8" cy="-3" r=".5"/><circle cx="-8" cy="0" r=".5"/><circle cx="-8" cy="3" r=".5"/><circle cx="8" cy="-3" r=".5"/><circle cx="8" cy="0" r=".5"/><circle cx="8" cy="3" r=".5"/>',
   '<path d="M-7-4L0-8L7-4V5L0 9L-7 5ZM-7-4L0 0L7-4M0 0V9"/>'
  ];
  const glyph=`<g transform="translate(${x+17} -8)" style="fill:none;stroke:var(--anatomy-hi);stroke-width:.55;stroke-linejoin:round;stroke-linecap:round">${glyphs[sys].replaceAll('<path ' , '<path class="iso-line" data-tone="hi" ').replaceAll('<circle ' , '<circle fill="var(--anatomy-hi)" stroke="none" ')}</g>`;
  T.plane({part:chip,o:[0,0,z+7],u:[1,0,0],v:[0,1,0],svg:glyph});

  box(`system${sys}.connector`,x+3,9,z+3,29,5,3,group,{r:.5,material:'steel',system:sys,details:{dots:Array.from({length:8},(_,j)=>({at:[z+6,x+5+j*3.4,11.5],normal:[0,0,1],size:.4,tone:'lo'}))}});
 }
}
const label=box('stand.nameplate',-28,-12,152.2,56,22,.6,body,{r:1,tone:'hi',screws:true});T.plane({part:label,o:[0,0,152.8],u:[1,0,0],v:[0,1,0],svg:'<text x="0" y="2" text-anchor="middle" style="font:5px ui-monospace,monospace;fill:var(--anatomy-hi)">RENTGEN</text>'});
export const follow=values=>{const v={...values};for(let i=0;i<7;i++)v['drawer'+i]=(values.apart??0)*drawers[i].travel;return v;};
export const poses=()=>[...Array.from({length:73},(_,i)=>follow({cabinet:i*5,apart:0})),...Array.from({length:73},(_,i)=>follow({cabinet:i*5,apart:1})),...Array.from({length:61},(_,i)=>follow({cabinet:25,apart:i/60}))];
export const out=T.build({statics:R.items,poses,verify:true});const css=k.ISO_CSS+'\n'+out.css;const scene={P,drawers,parts,turn:out.data,verify:out.verify,report:out.report,width:900,height:680};
writeFileSync('scene.json',JSON.stringify(scene));writeFileSync('scene.svg',out.layerSvg('instrument',{width:900,height:680}));writeFileSync('scene.css',css);writeFileSync('turn-runtime.js',turnScript());writeFileSync('qa/scene-build.json',JSON.stringify({createdAt:new Date().toISOString(),parts:parts.length,drawers:drawers.length,report:out.report,turnBytes:JSON.stringify(out.data).length},null,2));
const html=theme=>`<!doctype html><html lang="ru"><head><meta charset="utf-8"><style>${css}body{margin:0}.iso-plate{width:900px;max-width:100%;margin:auto}.iso-stage{position:relative}.iso-svg{display:block;width:100%;height:auto}</style></head><body class="iso" data-theme="${theme}"><div class="iso-plate"><div class="iso-stage iso-turn" tabindex="0" role="group" aria-label="Рентген: исследовательский шкаф">${out.layerSvg('instrument',{width:900,height:680})}</div><span data-readout>Собрано</span></div><script type="module">${turnScript()}const data=${JSON.stringify(scene)};window.__isoVerify=data.verify;const follow=${follow.toString()};const drawers=data.drawers;window.controller=TURN.mount(document.querySelector('.iso-stage'),data.turn,{follow});</script></body></html>`;
writeFileSync('qa/scene-light.html',html('light'));writeFileSync('qa/scene-dark.html',html('dark'));console.log(JSON.stringify({parts:parts.length,turnBytes:JSON.stringify(out.data).length,groups:out.report.groups}));
if(process.argv.includes('--audit')){A.settle(R,P);A.auditOrExit(R,P);TA.orbitOrExit(T,R,P,{log:line=>console.log(new Date().toISOString()+' '+line),poses,sweep:{at:x=>follow({cabinet:x,apart:0}),from:0,to:360,frame:.5},clips:[{name:'explode',at:t=>follow({cabinet:25,apart:(1-Math.cos(Math.PI*t))/2}),from:0,to:2,frame:1/60}],quick:process.argv.includes('--quick'),only:process.argv.find(a=>a.startsWith('--only='))?.slice(7).split(',')});}
