import {writeFileSync} from 'node:fs';
import * as k from './reference/kit/iso-kit.mjs';
import {turning} from './reference/kit/turn-build.mjs';
const P=k.fitProjection(k.boxCorners({x:-105,y:-90,w:210,d:180,r:0},-15,28),1000,720,{pad:70,azimuth:35,elevation:40});
const T=turning(P),world=T.group('world',{free:{origin:[0,0,0]}}),layer=T.layer('detail');T.stack(['detail']);const objects=[];
for(let i=0;i<18;i++){const x=(i%6-2.5)*31,y=(Math.floor(i/6)-1)*48,g=T.group('slot'+i,{parent:world,slide:{direction:[0,0,1],travel:20}});const p=T.prism({name:'slot'+i+'.document',group:g,layer,plan:{x:x-11,y:y-14,w:22,d:28,r:1},z:0,h:3,bevel:.5,tone:'hi'});T.prism({name:'slot'+i+'.declaration',group:g,layer,plan:{x:x-8,y:y-10,w:16,d:17,r:.7},z:3,h:3,bevel:.4,material:'steel'});T.plane({part:p,o:[0,0,3.02],u:[1,0,0],v:[0,1,0],svg:`<text x="${x}" y="${y+10}" text-anchor="middle" style="font:2.6px monospace;fill:var(--anatomy-hi)">${String(i+1).padStart(2,'0')}</text>`});objects.push({id:'slot'+i,group:'slot'+i,anchor:[x,y,6],label:''});}
const out=T.build({poses:[{world:null}],verify:true});writeFileSync('detail-scene.json',JSON.stringify({P,turn:out.data,objects,report:out.report,width:1000,height:720}));writeFileSync('detail-scene.svg',out.layerSvg('detail',{width:1000,height:720}));writeFileSync('detail-scene.css',k.ISO_CSS+'\n'+out.css);console.log(JSON.stringify(out.report));
