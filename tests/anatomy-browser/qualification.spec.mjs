import {test, expect, state, evidence, noOverflow} from './fixtures.mjs';
import {readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sources=JSON.parse(await readFile(process.env.ATLAS_SOURCES||'../../tools/anatomy-atlas/source-texts.json','utf8'));
const q=id=>JSON.stringify(id);
const label=(page,id)=>page.locator(`#exOverlay [data-ex-id=${q(id)}]`);
async function searchFile(page,path){
  await page.locator('#exSearch').fill(`file:${path}`);
  await expect.poll(async()=>(await state(page)).query).toBe(`file:${path}`);
  const target=page.viewportSize().width<760?page.locator(`#exObjectList [data-ex-list=${q(`file:${path}`)}]`):label(page,`file:${path}`).locator('rect');
  await target.click();await expect.poll(async()=>(await state(page)).selected).toBe(`file:${path}`);
}
async function blankPoint(page){return page.locator('#exViewport').evaluate(el=>{
  const b=el.getBoundingClientRect();
  for(const fx of [.12,.25,.5,.75,.85])for(const fy of [.23,.4,.6,.75]){
    const x=b.x+b.width*fx,y=b.y+b.height*fy,t=document.elementFromPoint(x,y);
    if(t&&el.contains(t)&&!t.closest('button,input,select,[data-ex-id],[data-ex-edge]'))return{x,y};
  }
  throw Error('No real pointer surface found');
})}
async function cameraDrag(page,dx,dy,shift=false){
  await page.locator('#exViewport').scrollIntoViewIfNeeded();const p=await blankPoint(page);
  if(shift)await page.keyboard.down('Shift');
  await page.mouse.move(p.x,p.y);await page.mouse.down();await page.mouse.move(p.x+dx,p.y+dy,{steps:12});await page.mouse.up();
  if(shift)await page.keyboard.up('Shift');
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
}
async function inlineSource(page,id){
  await page.locator('#exSource').click();const code=page.locator('#exInlineSource .ex-source-code');await expect(code).toBeVisible();
  const entry=sources.files[id.replace(/^file:/,'')];expect(entry).toBeTruthy();
  expect(createHash('sha256').update(entry.text).digest('hex')).toBe(entry.sha256);
  const rendered=await code.locator(':scope > span').evaluateAll(rows=>rows.map(row=>({line:Number(row.querySelector('.line-no').textContent),text:[...row.childNodes].filter(n=>!(n.nodeType===1&&n.classList.contains('line-no'))).map(n=>n.textContent).join('')})));
  const lines=entry.text.split('\n');expect(rendered.length).toBeGreaterThan(20);
  for(const row of rendered)expect(row.text.replace(/\r$/,''),`Exact source line ${row.line}`).toBe((lines[row.line-1]||' ').replace(/\r$/,''));
  await expect(code.locator('script,iframe,img,svg')).toHaveCount(0);
  await expect(page.locator('#exInlineSource a[href*="/blob/"]').first()).toHaveAttribute('href',new RegExp(`/blob/${sources.meta.sourceCommit}/`));
  return code;
}

test('Q01 orbit pitch pan zoom changes rendered geometry',async({page},info)=>{
  const initialZoom=(await state(page)).zoom;
  const before=await evidence(page,info,'overview-fit',page.locator('#exViewport'));
  const geometry=await page.locator('#exStage').innerHTML();await cameraDrag(page,85,-55);
  const rotated=await state(page);expect(Math.abs(rotated.yaw)).toBeGreaterThan(20);expect(Math.abs(rotated.pitch)).toBeGreaterThan(10);
  expect(await page.locator('#exStage').innerHTML()).not.toBe(geometry);
  const after=await evidence(page,info,'overview-orbit-pitch',page.locator('#exViewport'));expect(after.sha256).not.toBe(before.sha256);
  const beforePan=await state(page);await cameraDrag(page,55,35,true);
  expect(Math.abs((await state(page)).panX-beforePan.panX)).toBeGreaterThan(20);expect(Math.abs((await state(page)).panY-beforePan.panY)).toBeGreaterThan(15);
  await page.locator('#exZoomIn').click();expect((await state(page)).zoom).toBeGreaterThan(initialZoom);
  const p=await blankPoint(page);await page.mouse.move(p.x,p.y);await page.mouse.wheel(0,-120);
  await expect.poll(async()=>(await state(page)).zoom).toBeGreaterThan(initialZoom*1.25);
  await evidence(page,info,'overview-pan-zoom',page.locator('#exViewport'));await page.locator('#exReset').click();
  expect(await state(page)).toMatchObject({yaw:0,pitch:0,panX:0,panY:0,zoom:1});
  await page.locator('#exExplode').focus();await page.keyboard.press('End');await expect.poll(async()=>(await state(page)).explode).toBe(100);
  await evidence(page,info,'exploded-source-layers',page.locator('#exViewport'));
  await page.locator('#exTop').click();expect((await state(page)).pitch).toBe(50);
  await page.locator('#exFront').click();expect(await state(page)).toMatchObject({pitch:-25,yaw:-35});
  await page.locator('#exReset').click();expect((await state(page)).explode).toBe(0);
});

test('Q02 direct scene picking hierarchy and exact source',async({page},info)=>{
  await page.locator('#exViewport').scrollIntoViewIfNeeded();
  const hit=await page.locator('#exStage').evaluate(stage=>{
    const b=stage.getBoundingClientRect();
    for(let y=Math.max(0,b.y)+10;y<Math.min(innerHeight,b.bottom)-10;y+=12)for(let x=b.x+10;x<b.right-10;x+=12){const target=document.elementFromPoint(x,y)?.closest('#exStage [data-ex-id]');if(target)return{x,y,id:target.dataset.exId}}
    return null;
  });
  expect(hit,'At least one solid must be directly pointer-pickable').not.toBeNull();await page.mouse.click(hit.x,hit.y);await expect.poll(async()=>(await state(page)).selected).toBe(hit.id);
  await label(page,'interfaces').locator('rect').click();expect((await state(page)).selected).toBe('interfaces');
  await page.locator('#exOpen').click();expect((await state(page)).root).toBe('interfaces');
  expect((await state(page)).visibleIds.every(id=>id.startsWith('file:'))).toBe(true);await evidence(page,info,'system-files');
  await searchFile(page,'rentgen_core/cli.py');await inlineSource(page,'file:rentgen_core/cli.py');
  await evidence(page,info,'selected-file-readable-source',page.locator('#inspector'));
  await page.locator('#exOpen').click();expect((await state(page)).root).toBe('file:rentgen_core/cli.py');
  expect((await state(page)).visibleIds.every(id=>id.startsWith('symbol:'))).toBe(true);
  const symbol=(await state(page)).visibleIds[0];await label(page,symbol).locator('rect').click();await page.locator('#exSource').click();
  await expect(page.locator('#exInlineSource .target-line').first()).toBeVisible();await evidence(page,info,'selected-symbol-readable-source',page.locator('#inspector'));
  await searchFile(page,'site/index.html');await inlineSource(page,'file:site/index.html');
});

test('Q03 dependency evidence and source routes',async({page},info)=>{
  await searchFile(page,'rentgen_core/capture.py');await page.locator('#exDependencies').click();expect((await state(page)).mode).toBe('dependencies');
  const edge=page.locator('#exOverlay [data-ex-edge]').first();await expect(edge).toBeVisible();expect(await edge.getAttribute('aria-label')).toContain('→');
  await page.locator('#exViewport').scrollIntoViewIfNeeded();
  const edgeHit=await page.locator('#exOverlay').evaluate(svg=>{
    for(const g of svg.querySelectorAll('[data-ex-edge]')){const path=g.querySelector('.ex-link'),length=path.getTotalLength(),matrix=path.getScreenCTM();for(const t of [.25,.4,.5,.6,.75]){const p=path.getPointAtLength(length*t),screen=new DOMPoint(p.x,p.y).matrixTransform(matrix);if(document.elementFromPoint(screen.x,screen.y)?.closest('[data-ex-edge]')===g)return{x:screen.x,y:screen.y}}}
    return null;
  });
  expect(edgeHit,'A dependency edge must be pointer-pickable').not.toBeNull();await page.mouse.click(edgeHit.x,edgeHit.y);
  await expect(page.locator('#exEvidence')).toContainText('→');await expect(page.locator('#exEvidence a[href*="/blob/"]').first()).toHaveAttribute('href',new RegExp(`/blob/${sources.meta.sourceCommit}/`));
  await evidence(page,info,'dependency-direction-and-proof');await page.locator('#exEdgeTo').click();expect((await state(page)).selected).not.toBeNull();
  const flow=await page.evaluate(()=>window.atlas.data.flows[0]);await page.locator('#flowSelect').selectOption('0');await page.locator('#showFlowGraph').click();
  await expect(page.locator('#graphCanvas [data-flow-step]')).toHaveCount(flow.steps.length);
  for(let i=0;i<flow.steps.length;i++){await page.locator(`#graphCanvas [data-flow-step="${i}"]`).click();await expect.poll(()=>page.evaluate(()=>window.atlas.state.selected)).toBe(flow.steps[i].nodeId)}
  await evidence(page,info,'complete-source-route',page.locator('#graphView'));
  await page.locator('[data-view="explorer"]').click();await page.locator('#exHome').click();await page.locator('#exRelations').selectOption('route');
  await expect(page.locator('#exOverlay .ex-route').first()).toBeVisible();await evidence(page,info,'route-on-spatial-systems');
});

test('Q04 navigation history isolation and filtering',async({page},info)=>{
  await label(page,'interfaces').locator('rect').click();await page.locator('#exOpen').click();
  await page.locator('#exBack').click();expect((await state(page)).mode).toBe('overview');await page.locator('#exForward').click();expect((await state(page)).root).toBe('interfaces');
  await page.locator('#exDirectory').selectOption('rentgen_core/');expect((await state(page)).visibleIds.every(id=>id.startsWith('file:rentgen_core/'))).toBe(true);expect((await state(page)).visibleIds.length).toBeGreaterThan(0);await page.locator('#exDirectory').selectOption('all');
  await page.locator('#exPageNext').click();expect((await state(page)).page).toBe(1);await page.locator('#exPagePrev').click();expect((await state(page)).page).toBe(0);
  await page.locator('#exRole').selectOption('test');const ids=(await state(page)).visibleIds;expect(ids.length).toBeGreaterThan(0);expect(await page.evaluate(ids=>ids.every(id=>window.atlas.data.nodes.find(n=>n.id===id)?.role==='test'),ids)).toBe(true);
  await page.locator('#exHome').click();await label(page,'interfaces').locator('rect').click();await page.locator('#exIsolate').click();expect((await state(page)).visibleIds).toEqual(['interfaces']);
  await evidence(page,info,'isolated-layer');await page.locator('#exIsolate').click();await page.locator('.ex-list-details summary').click();
  await page.locator('[data-ex-visible="interfaces"]').uncheck();expect((await state(page)).visibleIds).not.toContain('interfaces');await page.locator('[data-ex-visible="interfaces"]').check();expect((await state(page)).visibleIds).toContain('interfaces');
  await page.locator('#exSearch').fill('no-result-qualification-unique');await expect(page.locator('#exEmpty')).toBeVisible();await page.locator('#exClearSearch').click();await expect(page.locator('#exEmpty')).toBeHidden();
});

test('Q05 keyboard focus and reduced motion',async({page},info)=>{
  await page.locator('#exStage').focus();await expect(page.locator('#exStage')).toBeFocused();await page.keyboard.press('ArrowRight');await page.keyboard.press('ArrowUp');expect(await state(page)).toMatchObject({yaw:15,pitch:10});
  const beforeZoom=(await state(page)).zoom;await page.keyboard.press('+');expect((await state(page)).zoom).toBeGreaterThan(beforeZoom);await page.keyboard.press('Home');expect(await state(page)).toMatchObject({yaw:0,pitch:0,zoom:1});
  await label(page,'interfaces').focus();await page.keyboard.press('Enter');expect((await state(page)).root).toBe('interfaces');await page.locator('#exStage').focus();await page.keyboard.press('Escape');expect((await state(page)).mode).toBe('overview');
  expect(await page.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true);
  const first=await evidence(page,info,'reduced-motion-before',page.locator('#exViewport'));await page.waitForTimeout(400);const second=await evidence(page,info,'reduced-motion-after',page.locator('#exViewport'));expect(second.sha256).toBe(first.sha256);
});

test('Q06 mobile touch navigation and readable detail',async({page,context},info)=>{
  await page.setViewportSize({width:390,height:844});const cdp=await context.newCDPSession(page);await cdp.send('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:5});
  await page.locator('#exViewport').scrollIntoViewIfNeeded();const p=await blankPoint(page);
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:p.x,y:p.y,id:1}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:p.x+45,y:p.y-35,id:1}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await expect.poll(async()=>Math.abs((await state(page)).yaw)).toBeGreaterThan(10);
  const z=(await state(page)).zoom,center=await blankPoint(page);
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:center.x-15,y:center.y,id:1},{x:center.x+15,y:center.y,id:2}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:center.x-30,y:center.y,id:1},{x:center.x+30,y:center.y,id:2}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await expect.poll(async()=>(await state(page)).zoom).toBeGreaterThan(z);
  await page.locator('#exReset').click();const target=page.locator('#exObjectList [data-ex-list="graph"]');await target.scrollIntoViewIfNeeded();const box=await target.boundingBox();
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:box.x+box.width/2,y:box.y+box.height/2,id:1}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await expect.poll(async()=>(await state(page)).selected).toBe('graph');
  await expect(page.locator('#exMobileSelection')).toBeVisible();await expect(page.locator('#exMobileLabel')).toHaveText(await page.evaluate(()=>window.atlas.data.sections.find(n=>n.id==='graph').label));
  await page.locator('#exMobileOpen').click();await noOverflow(page);await evidence(page,info,'mobile-system-files');
  await searchFile(page,'rentgen_core/capture.py');await inlineSource(page,'file:rentgen_core/capture.py');await noOverflow(page);await evidence(page,info,'mobile-readable-code',page.locator('#inspector'));
  expect((await page.locator('#exOpen').boundingBox()).height).toBeGreaterThanOrEqual(40);await cdp.detach();
});

test('Q07 light dark and narrow desktop readability',async({page},info)=>{
  await searchFile(page,'rentgen_core/capture.py');await inlineSource(page,'file:rentgen_core/capture.py');await evidence(page,info,'desktop-light-code',page.locator('#inspector'));
  await page.locator('#theme').click();await expect(page.locator('body')).toHaveAttribute('data-theme','dark');await evidence(page,info,'desktop-dark-code',page.locator('#inspector'));
  await page.setViewportSize({width:1024,height:768});await noOverflow(page);await evidence(page,info,'narrow-desktop-explorer');await evidence(page,info,'narrow-desktop-code',page.locator('#inspector'));
});

test('Q08 bounded browser interaction performance',async({page,browser},info)=>{
  const samples=[];await page.locator('#exStage').focus();
  for(let i=0;i<20;i++){const start=performance.now();await page.keyboard.press('ArrowRight');await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));samples.push(performance.now()-start)}
  const sorted=[...samples].sort((a,b)=>a-b),p95=sorted[Math.ceil(sorted.length*.95)-1];expect((await state(page)).yaw).toBe(300);expect(p95,'Input and two-frame acknowledgement must finish below 1.5 seconds on CI').toBeLessThan(1500);
  const frameIntervals=await page.evaluate(()=>new Promise(resolve=>{const spans=[];let last;function tick(now){if(last!==undefined)spans.push(now-last);last=now;if(spans.length===60)resolve(spans);else requestAnimationFrame(tick)}requestAnimationFrame(tick)}));
  await writeFile(info.outputPath('browser-performance.json'),JSON.stringify({browserVersion:browser.version(),sampleCount:samples.length,inputAndTwoFramesMs:samples,p95Ms:p95,idleFrameIntervalsMs:frameIntervals,scope:'Current Chromium CI host; not a mobile FPS claim'},null,2));await evidence(page,info,'performance-final-camera',page.locator('#exViewport'));
});
