import {test as base,expect} from '@playwright/test';
import {createHash} from 'node:crypto';
import {writeFile} from 'node:fs/promises';
export const test=base.extend({page:async({page,context},use)=>{
  const errors=[],remote=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await context.route('**/*',async route=>{const origin=new URL(route.request().url()).origin;if(origin==='http://127.0.0.1:4179')await route.continue();else{remote.push(origin);await route.abort('blockedbyclient')}});
  await page.goto('/');await expect(page.locator('#exStage')).toBeVisible();await expect.poll(()=>page.evaluate(()=>!!window.explorer)).toBe(true);
  await use(page);expect(errors,'Browser errors').toEqual([]);expect(remote,'External app requests').toEqual([]);
}});
export {expect};
export const state=page=>page.evaluate(()=>JSON.parse(JSON.stringify(window.explorer.state)));
export async function evidence(page,info,name,locator=page.locator('#explorerView')){
  const file=info.outputPath(`${name}.png`),bytes=await locator.screenshot({path:file,animations:'disabled'});
  const width=bytes.readUInt32BE(16),height=bytes.readUInt32BE(20);expect(width).toBeGreaterThan(200);expect(height).toBeGreaterThan(100);expect(bytes.length).toBeGreaterThan(4000);
  const textMetrics=await locator.locator('.ex-label text,.ex-source-code,.ex-evidence,.ex-source-head').evaluateAll(els=>els.slice(0,60).map(el=>{const b=el.getBoundingClientRect(),css=getComputedStyle(el),ctm=el.getScreenCTM?.();return{text:el.textContent.slice(0,100),cssFontPx:parseFloat(css.fontSize),effectiveFontPx:parseFloat(css.fontSize)*(ctm?Math.hypot(ctm.a,ctm.b):1),width:b.width,height:b.height}}));
  const receipt={name,width,height,textMetrics,sha256:createHash('sha256').update(bytes).digest('hex'),state:await state(page),viewport:page.viewportSize()};await writeFile(info.outputPath(`${name}.json`),JSON.stringify(receipt,null,2));await info.attach(name,{path:file,contentType:'image/png'});return receipt;
}
export async function noOverflow(page){expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Page must fit viewport').toBe(true)}
