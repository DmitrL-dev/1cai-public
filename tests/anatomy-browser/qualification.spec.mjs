import {test, expect, state, evidence, noOverflow} from './fixtures.mjs';
import {readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sources=JSON.parse(await readFile(process.env.ATLAS_SOURCES||'../../tools/anatomy-atlas/source-texts.json','utf8'));
const SOURCE_COMMIT='6c8feb291dd251826eebb99e145f4a39f56cda47';
const NATIVE_PARTITIONS=[
  {label:'Проверки и preview',files:['edt_command.py','edt_fixture_executor.py','metadata_apply_gate.py','metadata_native_apply.py','metadata_preview.py','platform_check.py','test_execution.py','yaxunit_runner.py']},
  {label:'Live writer / sealed recovery',files:['_live_recovery_stage.py','metadata_live_apply.py','proposal_live_apply.py']},
  {label:'Workspace и runtime',files:['edt_runtime.py','metadata_workspace.py','native_platform.py','native_process.py','native_resources.py','native_scratch.py']},
  {label:'Профили и evidence',files:['edt_execution.py','edt_profiles.py','metadata_apply.py','metadata_runs.py','platform_runs.py','test_profiles.py','yaxunit_report.py']},
].map(partition=>({...partition,fileIds:partition.files.map(name=>'file:rentgen_core/'+name)}));
const q=id=>JSON.stringify(id);
const label=(page,id)=>page.locator(`#exOverlay .ex-label[data-ex-id=${q(id)}]`);
const treeFile=(page,id)=>page.locator(`#exSourceTree [data-tree-file=${q(id)}]`);
const camera=s=>Object.fromEntries(['yaw','pitch','panX','panY','zoom'].map(k=>[k,s[k]]));
const listIds=page=>page.locator('#exObjectList [data-ex-list]').evaluateAll(els=>els.map(el=>el.dataset.exList));
async function openTools(page,selector){
  const details=page.locator(selector);
  if(!await details.evaluate(el=>el.open))await details.locator(':scope > summary').click();
  await expect(details).toHaveJSProperty('open',true);
}
async function selectFilter(page,selector,value){await openTools(page,'#exFiltersDetails');await page.locator(selector).selectOption(value)}
async function selectRoute(page,value){await openTools(page,'#exRouteTools');await page.locator('#exRouteSelect').selectOption(value)}
async function compactDetail(page){
  await expect(page.locator('#explorerView')).toHaveClass(/ex-detail-mode/);
  expect(await page.locator('.ex-tree-details').evaluate(el=>el.open),'A new detail opens with its complete tree collapsed').toBe(false);
  await expect(page.locator('#exTreeSearch')).toBeHidden();
  for(const selector of ['.ex-list-details','.ex-status','#exExplode','#exNodeExplode'])await expect(page.locator(selector)).toBeHidden();
}
async function firstScreen(page,info,name){
  for(const selector of ['#exFiltersDetails','#exRouteTools']){
    const details=page.locator(selector),summary=details.locator(':scope > summary');
    await expect(details).toHaveJSProperty('open',page.viewportSize().width>760);
    if(page.viewportSize().width<=760){await expect(summary).toBeVisible();expect((await summary.boundingBox()).height,`${selector} mobile disclosure target`).toBeGreaterThanOrEqual(44);}
    else await expect(summary).toBeHidden();
  }
  await page.evaluate(()=>window.scrollTo(0,0));await expect.poll(()=>page.evaluate(()=>scrollY)).toBe(0);
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const layout=await page.locator('#exViewport').evaluate(el=>{
    const b=el.getBoundingClientRect(),top=Math.max(0,b.top),bottom=Math.min(innerHeight,b.bottom),left=Math.max(0,b.left),right=Math.min(innerWidth,b.right);
    const solidCount=[...el.querySelectorAll('#exStage [data-p][data-ex-id]:not([data-hidden])')].filter(n=>{const r=n.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>top&&r.top<bottom&&r.right>left&&r.left<right}).length;
    const namedParts=['stand.shell.base','focus.file'].map(name=>{
      const parts=el.querySelectorAll(`#exStage [data-p][data-name="${name}"]`);if(parts.length!==1)return{name,count:parts.length};
      const part=parts[0],r=part.getBoundingClientRect(),area=r.width*r.height,visibleArea=Math.max(0,Math.min(r.right,right)-Math.max(r.left,left))*Math.max(0,Math.min(r.bottom,bottom)-Math.max(r.top,top));
      return{name,count:1,area,visibleArea,visibleFraction:area?visibleArea/area:0,hidden:part.hasAttribute('data-hidden')||getComputedStyle(part).display==='none',bounds:{x:r.x,y:r.y,width:r.width,height:r.height}};
    });
    return{scrollY,top:b.top,bottom:b.bottom,visibleHeight:Math.max(0,bottom-top),visibleWidth:Math.max(0,right-left),solidCount,namedParts,windowWidth:innerWidth,windowHeight:innerHeight};
  });
  expect(layout.top,'The scene starts on the first screen at page top').toBeLessThan(layout.windowHeight);
  expect(layout.visibleHeight,'More than 200px of scene is visible before scrolling').toBeGreaterThan(200);
  expect(layout.visibleWidth).toBeGreaterThan(200);expect(layout.solidCount,'Actual rendered solids appear in the first-screen scene area').toBeGreaterThan(0);
  await noOverflow(page);
  const path=info.outputPath(`${name}.png`),bytes=await page.screenshot({path,fullPage:false,animations:'disabled'});
  expect(bytes.readUInt32BE(16)).toBe(page.viewportSize().width);expect(bytes.readUInt32BE(20)).toBe(page.viewportSize().height);
  await writeFile(info.outputPath(`${name}.json`),JSON.stringify({name,layout,state:await state(page),viewport:page.viewportSize(),sha256:createHash('sha256').update(bytes).digest('hex')},null,2));
  await info.attach(name,{path,contentType:'image/png'});
  if(page.viewportSize().width<=760)for(const part of layout.namedParts){
    expect(part.count,`${part.name} must identify one actual solid`).toBe(1);expect(part.hidden,part.name).toBe(false);
    expect(part.area,`${part.name} has nonzero rendered bbox area`).toBeGreaterThan(0);expect(part.visibleArea,part.name).toBeGreaterThan(0);
    expect(part.visibleFraction,`${part.name}: at least 70% of its bbox area must be on the initial mobile screen`).toBeGreaterThanOrEqual(.7);
  }
}
async function openTree(page){
  const details=page.locator('.ex-tree-details');
  if(!await details.evaluate(el=>el.open))await details.locator(':scope > summary').click();
  await expect(page.locator('#exTreeSearch')).toBeVisible();
}
async function selectTreeFile(page,path){
  await openTree(page);await page.locator('#exTreeSearch').fill(path);
  await treeFile(page,`file:${path}`).click();
  await expect.poll(async()=>(await state(page)).selected).toBe(`file:${path}`);
}
async function cutaway(page,systemId,focusedId){
  const s=await state(page),data=await page.evaluate(({systemId,focusedId})=>{
    const D=window.atlas.data,scene=JSON.parse(document.getElementById('detailSceneData').textContent);
    const files=D.nodes.filter(n=>n.id.startsWith('file:')&&n.systemId===systemId),focus=D.nodes.find(n=>n.id===focusedId);
    const fileId=focus?.path?'file:'+focus.path:null;
    const edges=D.edges.filter(e=>e.kind==='import'&&(e.source===fileId||e.target===fileId));
    return{model:scene.models[systemId],files:files.map(n=>n.id),focus,neighbors:[...new Set(edges.flatMap(e=>[e.source,e.target]).filter(id=>id!==fileId))],parts:scene.parts.length,imports:edges.map(e=>({source:e.source,target:e.target}))};
  },{systemId,focusedId});
  expect(s.cutawayRoot).toBe(systemId);expect(s.focusedFile).toBe(`file:${data.focus.path}`);
  expect(s.selected).toBe(focusedId);expect(data.model.sourceCommit).toBe(SOURCE_COMMIT);
  expect(data.model.fileCount).toBe(data.files.length);expect(data.model.fileCount).toBeGreaterThan(0);
  expect(data.model.compartments.length).toBeGreaterThan(0);expect(data.model.compartments.length).toBeLessThanOrEqual(4);
  expect(s.compartmentCount).toBe(data.model.compartments.length);
  const memberships=data.model.compartments.flatMap(c=>c.fileIds);
  expect(new Set(memberships).size,'Every source belongs to exactly one compartment').toBe(memberships.length);
  expect([...memberships].sort(),'Compartments retain the complete system source membership').toEqual([...data.files].sort());
  for(const [index,compartment] of data.model.compartments.entries()){
    expect(compartment.fileIds.length).toBeGreaterThan(0);expect(compartment.refs.length).toBeGreaterThan(0);
    expect(compartment.representativeIds).toHaveLength(Math.min(2,compartment.fileIds.length));
    expect(compartment.representativeIds.every(id=>compartment.fileIds.includes(id))).toBe(true);
    for(const [slot,id] of compartment.representativeIds.entries())await expect(page.locator(`#exStage [data-name="source${index}_${slot}.module"][data-ex-id=${q(id)}]:not([data-hidden])`).first()).toBeVisible();
  }
  const compartments=data.model.compartments.map((_,i)=>`@compartment:${systemId}:${i}`);
  const representatives=data.model.compartments.flatMap(c=>c.representativeIds),fixed=[systemId,...compartments,focusedId];
  expect(s.representativeIds.sort()).toEqual([...representatives].sort());expect(s.representativeIds.length).toBeLessThanOrEqual(8);
  expect(s.visibleIds).toEqual(expect.arrayContaining(fixed));expect(new Set(s.visibleIds).size).toBe(s.visibleIds.length);
  const importsEnabled=['selection','all'].includes(s.relations);
  expect(s.neighborCount).toBe(importsEnabled?Math.min(6,data.neighbors.length):0);expect(s.neighborIds).toHaveLength(s.neighborCount);
  expect(s.neighborIds.every(id=>data.neighbors.includes(id)),'Neighbor markers are immediate imports, independently of compartment representatives').toBe(true);
  expect([...s.visibleIds].sort()).toEqual([...new Set([...fixed,...representatives,...(s.detailOpening>=99?s.neighborIds:[])])].sort());
  expect(s.visibleIds.length).toBeLessThanOrEqual(2+data.model.compartments.length+8+6);
  expect(s.detailBudget).toMatchObject({movingChildGroups:4,neighborLabels:6,projectedRelations:12});
  expect(s.detailBudget.solids).toBe(data.parts);expect(data.parts).toBeGreaterThan(0);
  expect(await page.locator('#exOverlay [data-ex-edge]').count()).toBeLessThanOrEqual(12);
  if(!importsEnabled)await expect(page.locator('#exOverlay [data-ex-edge],#exOverlay .neighbor')).toHaveCount(0);
  await expect(page.locator('#exNeighborList [data-neighbor-file]')).toHaveCount(s.neighborCount);
  for(const id of s.neighborIds){
    const neighbor=page.locator(`#exNeighborList [data-neighbor-file=${q(id)}]`);
    await expect(neighbor).toContainText(id.replace(/^file:/,''));
    await expect(neighbor).toContainText(data.imports.some(e=>e.source===s.focusedFile&&e.target===id)?'импортирует →':'← импортируется из');
  }
  await expect(page.locator('#exCutaway')).toBeVisible();
  await expect(page.locator('#exContainerName')).toContainText(data.model.label);
  await expect(page.locator('#exContainerName')).toContainText(`${data.files.length} файлов`);
  await expect(page.locator('#exCompartmentTabs [data-compartment]')).toHaveCount(data.model.compartments.length);
  await expect(page.locator('#exFocusedPath')).toContainText(data.focus.path);
  await expect(page.locator(`#exStage [data-ex-id=${q(systemId)}]:not([data-hidden])`).first()).toBeVisible();
  return data;
}
async function searchFile(page,path){
  await page.locator('#exSearch').fill(`file:${path}`);
  await expect.poll(async()=>(await state(page)).query).toBe(`file:${path}`);
  const disclosure=page.locator('.ex-list-details');await expect(disclosure).toBeVisible();
  if(page.viewportSize().width<760&&!await disclosure.evaluate(el=>el.open))await disclosure.locator('summary').click();
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
async function exactSource(page,id){
  const node=await page.evaluate(id=>window.atlas.data.nodes.find(n=>n.id===id),id);
  const code=page.locator('#exInlineSource .ex-source-code');await expect(code).toBeVisible();
  const entry=sources.files[node.path];expect(entry).toBeTruthy();expect(sources.meta.sourceCommit).toBe(SOURCE_COMMIT);
  expect(createHash('sha256').update(entry.text).digest('hex')).toBe(entry.sha256);
  const rendered=await code.locator(':scope > span').evaluateAll(rows=>rows.map(row=>({line:Number(row.querySelector('.line-no').textContent),text:[...row.childNodes].filter(n=>!(n.nodeType===1&&n.classList.contains('line-no'))).map(n=>n.textContent).join('')})));
  const lines=entry.text.split(/\r\n|\n|\r/);expect(rendered.length).toBeGreaterThan(0);
  expect(rendered.some(row=>row.line===(node.line||1)),'The selected declaration or file start is in the code fragment').toBe(true);
  for(const row of rendered)expect(row.text,`Exact source line ${row.line}`).toBe(lines[row.line-1]);
  await expect(code.locator('script,iframe,img,svg')).toHaveCount(0);
  await expect(page.locator('#exInlineSource .ex-source-head')).toContainText(node.path);
  await expect(page.locator('#exInlineSource a[href*="/blob/"]').first()).toHaveAttribute('href',node.refs[0].url);
  expect(node.refs.every(ref=>ref.url.includes(`/blob/${SOURCE_COMMIT}/`))).toBe(true);
  if(!id.startsWith('file:'))await expect(code.locator('.target-line').first()).toBeVisible();
  return code;
}
async function inlineSource(page,id){await page.locator('#exSource').click();return exactSource(page,id)}

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
  test.setTimeout(180000);
  expect(await page.evaluate(()=>window.atlas.data.meta.sourceCommit)).toBe(SOURCE_COMMIT);
  await page.locator('#exViewport').scrollIntoViewIfNeeded();
  const hit=await page.locator('#exStage').evaluate(stage=>{
    const b=stage.getBoundingClientRect();
    for(let y=Math.max(0,b.y)+10;y<Math.min(innerHeight,b.bottom)-10;y+=12)for(let x=b.x+10;x<b.right-10;x+=12){const target=document.elementFromPoint(x,y)?.closest('#exStage [data-ex-id]');if(target)return{x,y,id:target.dataset.exId}}
    return null;
  });
  expect(hit,'At least one solid must be directly pointer-pickable').not.toBeNull();await page.mouse.click(hit.x,hit.y);await expect.poll(async()=>(await state(page)).selected).toBe(hit.id);
  await label(page,'snapshots').focus();await page.keyboard.press(' ');
  await page.locator('#exOpen').click();expect((await state(page)).root).toBe('snapshots');
  await compactDetail(page);await firstScreen(page,info,'desktop-cutaway-first-screen');
  const snapshot=await cutaway(page,'snapshots','file:rentgen_core/capture.py');
  expect(snapshot.files).toHaveLength(11);
  expect(snapshot.files).toEqual(expect.arrayContaining(['capture.py','manifests.py','publication.py','sources.py'].map(name=>'file:rentgen_core/'+name)));
  await expect(page.locator('#exContainerTruth')).toContainText('не оборудование');
  await expect(page.locator('#exContainerTruth')).toContainText('Редакторская группировка');
  const metadata=await page.locator('#exOverlay .ex-label').evaluateAll(groups=>groups.map(g=>{const text=g.querySelector('.ex-label-sub'),box=text.getBoundingClientRect(),card=g.querySelector('rect').getBoundingClientRect(),ctm=text.getScreenCTM();return{font:parseFloat(getComputedStyle(text).fontSize)*Math.hypot(ctm.a,ctm.b),left:box.left,right:box.right,cardLeft:card.left,cardRight:card.right}}));
  expect(metadata.length).toBeGreaterThan(0);for(const m of metadata){expect(m.font).toBeGreaterThanOrEqual(11);expect(m.left).toBeGreaterThanOrEqual(m.cardLeft);expect(m.right).toBeLessThanOrEqual(m.cardRight);}
  await openTree(page);await expect(page.locator('#exSourceTree [data-tree-file]')).toHaveCount(11);
  await evidence(page,info,'snapshot-persistent-source-cutaway');
  const representative=snapshot.model.compartments[1].representativeIds[0];
  await page.locator(`#exOverlay .ex-source-hit[data-ex-id=${q(representative)}]`).focus();await page.keyboard.press(' ');
  await cutaway(page,'snapshots',representative);await inlineSource(page,representative);
  for(const name of ['capture.py','manifests.py','publication.py','sources.py']){
    const id='file:rentgen_core/'+name;await selectTreeFile(page,'rentgen_core/'+name);
    await cutaway(page,'snapshots',id);const code=await exactSource(page,id);expect(await code.locator(':scope > span').count()).toBeGreaterThan(20);
  }
  await selectTreeFile(page,'rentgen_core/capture.py');
  await page.locator('#exOpen').click();expect((await state(page)).root).toBe('file:rentgen_core/capture.py');
  await cutaway(page,'snapshots','file:rentgen_core/capture.py');
  const declarations=await page.evaluate(()=>window.atlas.data.nodes.filter(n=>n.parentId==='file:rentgen_core/capture.py'));
  const symbol=declarations.find(n=>n.id.endsWith(':capture_sources'))||declarations[0];expect(symbol).toBeTruthy();
  await page.locator('#exDeclarationList').selectOption(symbol.id);
  await cutaway(page,'snapshots',symbol.id);await exactSource(page,symbol.id);
  await expect(page.locator('#exFocusedPath')).toContainText(symbol.label);
  await evidence(page,info,'selected-declaration-with-parent',page.locator('#exViewport'));
  await evidence(page,info,'selected-symbol-readable-source',page.locator('#inspector'));
  await searchFile(page,'rentgen_core/cli.py');await inlineSource(page,'file:rentgen_core/cli.py');
  await evidence(page,info,'selected-file-readable-source',page.locator('#inspector'));
  await searchFile(page,'site/index.html');await inlineSource(page,'file:site/index.html');
  await test.step('Opening an unparsed file retains its selectable source instead of an empty declaration view',async()=>{
    const id='file:site/index.html';
    expect(await page.evaluate(id=>window.atlas.data.nodes.filter(n=>n.parentId===id).length,id)).toBe(0);
    await expect(page.locator('#exDeclarationList')).toBeDisabled();
    const before=await state(page),beforeCamera=camera(before);
    for(const open of [()=>page.locator('#exOpen').click(),()=>page.evaluate(id=>window.explorer.open(id),id)]){
      await open();const after=await state(page);
      expect(after).toMatchObject({selected:id,focusedFile:id,cutawayRoot:'delivery',mode:before.mode,root:before.root,query:before.query,total:before.total});
      expect(after.total).toBeGreaterThan(0);expect(after.visibleIds).toContain(id);expect(camera(after)).toEqual(beforeCamera);
      await expect(page.locator('#exEmpty')).toBeHidden();await expect(label(page,id)).toHaveCount(1);
      await expect(label(page,id).locator('rect')).toBeVisible();expect(await listIds(page)).toContain(id);
      await cutaway(page,'delivery',id);await exactSource(page,id);
    }
    await label(page,id).focus();await page.keyboard.press(' ');
    expect((await state(page)).selected).toBe(id);await expect(page.locator('#exEmpty')).toBeHidden();
    await evidence(page,info,'unparsed-file-retains-source-cutaway');
  });

  // The public open API makes the exhaustive catalog check independent of label overlap.
  // Main Snapshot navigation, tree selection and declaration selection above use real controls.
  const systems=await page.evaluate(()=>window.atlas.data.sections.map(n=>({id:n.id,label:n.label})));
  expect(systems).toHaveLength(14);
  const models=await page.evaluate(()=>JSON.parse(document.getElementById('detailSceneData').textContent).models);
  expect(Object.keys(models).sort()).toEqual(systems.map(s=>s.id).sort());
  const coverage=[];
  for(const system of systems){
    await test.step(`Populated cutaway and complete source tree: ${system.id}`,async()=>{
      await page.evaluate(id=>window.explorer.open(id),system.id);
      await compactDetail(page);
      await openTree(page);await page.locator('#exTreeSearch').fill('');
      const initial=await state(page),model=await cutaway(page,system.id,initial.selected);
      const treeIds=await page.locator('#exSourceTree [data-tree-file]').evaluateAll(els=>els.map(el=>el.dataset.treeFile));
      expect([...treeIds].sort(),`${system.id}: every source file is in the tree, without paging loss`).toEqual([...model.files].sort());
      if(system.id==='native'){
        expect(model.files).toHaveLength(24);expect(model.model.compartments.map(c=>c.fileIds.length)).toEqual([8,3,6,7]);
        expect(model.model.compartments).toHaveLength(NATIVE_PARTITIONS.length);
        for(const [index,expected] of NATIVE_PARTITIONS.entries()){
          const actual=model.model.compartments[index];
          expect(actual.label).toBe(expected.label);expect(actual.basis).toBe('editorial');
          expect([...actual.fileIds].sort(),`${expected.label} uses the exact pinned source paths`).toEqual([...expected.fileIds].sort());
          await expect(page.locator(`#exCompartmentTabs [data-compartment="${index}"]`)).toContainText(expected.label);
        }
        await expect(page.locator('#exContainerTruth')).toContainText('Проверки не дают разрешение на запись');
        await expect(page.locator('#exContainerTruth')).toContainText('recovery восстанавливает только sealed recovery files');
        await expect(page.locator('#exContainerTruth')).toContainText('не произвольная live infobase');
      }
      for(let i=0;i<model.model.compartments.length;i++){
        await page.locator(`#exCompartmentTabs [data-compartment="${i}"]`).click();
        const current=await state(page);expect(current.compartment).toBe(i);
        expect(model.model.compartments[i].fileIds).toContain(current.focusedFile);
        await cutaway(page,system.id,current.selected);
        await expect(page.locator(`#exCompartmentTabs [data-compartment="${i}"]`)).toHaveAttribute('aria-pressed','true');
        if(system.id==='native'){
          expect(NATIVE_PARTITIONS[i].fileIds).toContain(current.focusedFile);
          await exactSource(page,current.selected);
        }
      }
      if(system.id==='native')await evidence(page,info,'native-four-exact-source-compartments');
      const lastFile=model.files.at(-1);
      await selectTreeFile(page,lastFile.replace(/^file:/,''));await cutaway(page,system.id,lastFile);
      await page.locator('#exTreeSearch').fill('');
      expect(await page.locator('#exSourceTree [data-tree-file]').count()).toBe(model.files.length);
      coverage.push({systemId:system.id,sourceCommit:SOURCE_COMMIT,fileCount:model.files.length,compartments:model.model.compartments.map(c=>({label:c.label,basis:c.basis,fileCount:c.fileIds.length})),state:await state(page)});
    });
  }
  await writeFile(info.outputPath('system-cutaway-coverage.json'),JSON.stringify(coverage,null,2));
});

test('Q03 dependency evidence and source routes',async({page},info)=>{
  test.setTimeout(120000);
  await searchFile(page,'rentgen_core/capture.py');await page.locator('#exDependencies').click();expect((await state(page)).mode).toBe('dependencies');
  await cutaway(page,'snapshots','file:rentgen_core/capture.py');
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
  await page.locator('[data-view="explorer"]').click();await page.locator('#exHome').click();await selectFilter(page,'#exRelations','route');
  await expect(page.locator('#exOverlay .ex-route').first()).toBeVisible();await evidence(page,info,'route-on-spatial-systems');
  await expect(page.locator('.ex-route-rail')).toContainText('Порядок чтения, не выполнение');
  await openTools(page,'#exRouteTools');
  await expect(page.locator('#exRouteSelect')).toBeVisible();
  await expect(page.locator('#exRouteFocus')).toBeVisible();
  expect(await page.locator('#exRouteDetails').evaluate(el=>el.open)).toBe(false);
  await page.locator('#exRouteDetails > summary').click();await expect(page.locator('#exRouteCopy')).toBeVisible();
  await selectRoute(page,'0');
  await page.locator('#exRouteFocus').click();
  const routeChecks=[];
  async function routeStep(index){
    const step=flow.steps[index],node=await page.evaluate(id=>window.atlas.data.nodes.find(n=>n.id===id),step.nodeId);
    await expect.poll(async()=>{const s=await state(page);return{flowIndex:s.flowIndex,stepIndex:s.stepIndex,selected:s.selected,root:s.root,cutawayRoot:s.cutawayRoot,focusedFile:s.focusedFile}}).toEqual({flowIndex:0,stepIndex:index,selected:node.id,root:node.systemId,cutawayRoot:node.systemId,focusedFile:'file:'+node.path});
    await cutaway(page,node.systemId,node.id);await exactSource(page,node.id);
    await expect(page.locator('#exRoutePosition')).toHaveText(`${index+1} / ${flow.steps.length}`);
    await expect(page.locator('#exRouteCopy')).toContainText(step.description);
    await expect(page.locator('#exRouteCopy a[href*="/blob/"]').first()).toHaveAttribute('href',step.refs[0].url);
    await expect(page.locator('#exRouteSelect')).toHaveValue('0');
    await expect(page.locator('#exRouteFocus')).toBeVisible();
    if(node.id.startsWith('symbol:')){
      await expect(page.locator('#exDeclarationList')).toHaveValue(node.id);
      const option=page.locator('#exDeclarationList option:checked');
      await expect(option).toHaveAttribute('data-source-parent',node.parentId);
      await expect(option).toHaveAttribute('data-evidence-kind',node.evidenceKind);
      await expect(option).toContainText(node.label);
      await expect(page.locator('#exInlineSource a[href*="/blob/"]').first()).toHaveAttribute('href',node.refs[0].url);
    }
    routeChecks.push({index,nodeId:node.id,systemId:node.systemId,file:node.path,refs:step.refs,state:await state(page)});
  }
  for(let i=0;i<flow.steps.length;i++){
    if(i)await page.locator('#exRouteNext').click();
    await routeStep(i);
    if(i===0)await expect(page.locator('#exRoutePrev')).toBeDisabled();
  }
  await expect(page.locator('#exRouteNext')).toBeDisabled();
  await evidence(page,info,'persistent-route-focused-source');
  await page.locator('#exRoutePrev').click();await routeStep(flow.steps.length-2);
  await page.locator('#exRouteNext').click();await routeStep(flow.steps.length-1);
  const alternate=await page.evaluate(()=>({index:window.atlas.data.flows.length-1,nodeId:window.atlas.data.flows.at(-1).steps[0].nodeId}));
  await selectRoute(page,String(alternate.index));
  expect(await state(page)).toMatchObject({flowIndex:alternate.index,stepIndex:0,selected:alternate.nodeId});
  await exactSource(page,alternate.nodeId);await expect(page.locator('#exRoutePrev')).toBeDisabled();
  await writeFile(info.outputPath('persistent-source-route.json'),JSON.stringify(routeChecks,null,2));
});

test('Q04 navigation history isolation and filtering',async({page},info)=>{
  await label(page,'interfaces').locator('rect').click();await page.locator('#exOpen').click();
  await page.locator('#exBack').click();expect((await state(page)).mode).toBe('overview');await page.locator('#exForward').click();expect((await state(page)).root).toBe('interfaces');
  await compactDetail(page);await selectTreeFile(page,'rentgen_core/cli.py');
  await page.locator('#exOpen').click();await compactDetail(page);
  await page.locator('#exBack').click();expect((await state(page)).root).toBe('interfaces');
  expect(await page.locator('.ex-tree-details').evaluate(el=>el.open),'Back restores an intentionally expanded tree').toBe(true);
  await expect(page.locator('#exTreeSearch')).toHaveValue('rentgen_core/cli.py');await expect(treeFile(page,'file:rentgen_core/cli.py')).toBeVisible();
  await page.locator('#exTreeSearch').fill('');
  expect(await page.locator('#exSourceTree [data-tree-file]').count()).toBe(await page.evaluate(()=>window.atlas.data.nodes.filter(n=>n.systemId==='interfaces'&&n.id.startsWith('file:')).length));
  await page.locator('#exSearch').fill('file:');await expect.poll(async()=>(await state(page)).query).toBe('file:');
  await expect(page.locator('.ex-list-details')).toBeVisible();await expect(page.locator('.ex-status')).toBeVisible();
  if(!await page.locator('.ex-list-details').evaluate(el=>el.open))await page.locator('.ex-list-details > summary').click();
  await expect(page.locator('#exObjectList [data-ex-list]').first()).toBeVisible();
  await expect(page.locator('#exExplode')).toBeHidden();await expect(page.locator('#exNodeExplode')).toBeHidden();
  await selectFilter(page,'#exDirectory','rentgen_core/');const directoryIds=await listIds(page);expect(directoryIds.every(id=>id.startsWith('file:rentgen_core/'))).toBe(true);expect(directoryIds.length).toBeGreaterThan(0);expect((await state(page)).visibleIds).toContain('interfaces');await selectFilter(page,'#exDirectory','all');
  const firstPage=await listIds(page);await page.locator('#exPageNext').click();expect((await state(page)).page).toBe(1);expect(await listIds(page)).not.toEqual(firstPage);await page.locator('#exPagePrev').click();expect((await state(page)).page).toBe(0);expect(await listIds(page)).toEqual(firstPage);
  await selectFilter(page,'#exRole','test');const ids=await listIds(page);expect(ids.length).toBeGreaterThan(0);expect(await page.evaluate(ids=>ids.every(id=>window.atlas.data.nodes.find(n=>n.id===id)?.role==='test'),ids)).toBe(true);const filtered=await state(page);expect(filtered.visibleIds).toContain(filtered.cutawayRoot);
  await selectFilter(page,'#exRole','all');await searchFile(page,'rentgen_core/cli.py');
  await page.locator('#exIsolate').click();const isolatedDetail=await state(page);
  expect(isolatedDetail.visibleIds).toContain('interfaces');expect(isolatedDetail.visibleIds).toContain(isolatedDetail.selected);
  expect(isolatedDetail.visibleIds.filter(id=>id.startsWith('@compartment:interfaces:'))).toHaveLength(isolatedDetail.compartmentCount);
  await page.locator('#exIsolate').click();
  await page.locator('#exHome').click();await expect(page.locator('.ex-list-details')).toBeVisible();await expect(page.locator('#exExplode')).toBeVisible();await expect(page.locator('#exNodeExplode')).toBeVisible();await label(page,'interfaces').locator('rect').click();await page.locator('#exIsolate').click();expect((await state(page)).visibleIds).toEqual(['interfaces']);
  await evidence(page,info,'isolated-layer');await page.locator('#exIsolate').click();const disclosure=page.locator('.ex-list-details');if(!await disclosure.evaluate(el=>el.open))await disclosure.locator('summary').click();await expect(page.locator('[data-ex-visible="interfaces"]')).toBeVisible();
  await page.locator('[data-ex-visible="interfaces"]').uncheck();expect((await state(page)).visibleIds).not.toContain('interfaces');await page.locator('[data-ex-visible="interfaces"]').check();expect((await state(page)).visibleIds).toContain('interfaces');await disclosure.locator('summary').click();await expect(page.locator('[data-ex-visible="interfaces"]')).toBeHidden();await disclosure.locator('summary').click();await expect(page.locator('[data-ex-visible="interfaces"]')).toBeVisible();
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
  await page.locator('#exMobileOpen').click();await compactDetail(page);await firstScreen(page,info,'mobile-cutaway-first-screen');await noOverflow(page);await evidence(page,info,'mobile-system-files');
  await page.locator('#exFiltersDetails > summary').focus();await page.keyboard.press('Enter');await expect(page.locator('#exFiltersDetails')).toHaveJSProperty('open',true);
  for(const selector of ['#exRole','#exDirectory','#exRelations'])await expect(page.locator(selector)).toBeVisible();
  await selectFilter(page,'#exRole','production_source');expect((await state(page)).role).toBe('production_source');await selectFilter(page,'#exRole','all');
  await page.locator('#exFiltersDetails > summary').click();await expect(page.locator('#exFiltersDetails')).toHaveJSProperty('open',false);
  await searchFile(page,'rentgen_core/capture.py');await inlineSource(page,'file:rentgen_core/capture.py');await noOverflow(page);await evidence(page,info,'mobile-readable-code',page.locator('#inspector'));
  await cutaway(page,'snapshots','file:rentgen_core/capture.py');
  await page.locator('#exOpen').click();await openTree(page);
  await expect(page.locator('#exSourceTree [data-tree-file]')).toHaveCount(11);
  const declaration=await page.evaluate(()=>window.atlas.data.nodes.find(n=>n.id==='symbol:rentgen_core/capture.py:capture_sources').id);
  await page.locator('#exDeclarationList').selectOption(declaration);await cutaway(page,'snapshots',declaration);await exactSource(page,declaration);
  await page.locator('#exRouteTools > summary').focus();await page.keyboard.press('Enter');await expect(page.locator('#exRouteTools')).toHaveJSProperty('open',true);
  await expect(page.locator('#exRouteSelect')).toBeVisible();await expect(page.locator('#exRouteFocus')).toBeVisible();
  for(const selector of ['#exOpen','#exCloseCutaway','#exDeclarationList','#exRouteFocus','#exRouteNext','#exRoutePrev'])expect((await page.locator(selector).boundingBox()).height,`${selector} mobile touch target`).toBeGreaterThanOrEqual(40);
  await noOverflow(page);await evidence(page,info,'mobile-focused-declaration-and-tree');
  const mobileRoute=await page.evaluate(()=>window.atlas.data.flows[0]);await selectRoute(page,'0');
  await page.locator('#exRouteNext').click();expect((await state(page)).selected).toBe(mobileRoute.steps[1].nodeId);
  await expect(page.locator('#exRouteTools')).toHaveJSProperty('open',true);await expect(page.locator('#exRoutePrev')).toBeVisible();await expect(page.locator('#exRouteNext')).toBeVisible();await exactSource(page,mobileRoute.steps[1].nodeId);
  await page.locator('#exRoutePrev').click();expect((await state(page)).selected).toBe(mobileRoute.steps[0].nodeId);await exactSource(page,mobileRoute.steps[0].nodeId);await expect(page.locator('#exRouteTools')).toHaveJSProperty('open',true);await cdp.detach();
});

test('Q07 light dark and narrow desktop readability',async({page},info)=>{
  await searchFile(page,'rentgen_core/capture.py');await inlineSource(page,'file:rentgen_core/capture.py');await evidence(page,info,'desktop-light-code',page.locator('#inspector'));
  await page.locator('#theme').click();await expect(page.locator('body')).toHaveAttribute('data-theme','dark');await evidence(page,info,'desktop-dark-code',page.locator('#inspector'));
  await page.setViewportSize({width:1024,height:768});await page.locator('#exHome').click();await label(page,'snapshots').focus();await page.keyboard.press(' ');await page.locator('#exOpen').click();
  await compactDetail(page);await firstScreen(page,info,'narrow-desktop-cutaway-first-screen');await noOverflow(page);await evidence(page,info,'narrow-desktop-explorer');await inlineSource(page,'file:rentgen_core/capture.py');await evidence(page,info,'narrow-desktop-code',page.locator('#inspector'));
});

test('Q08 bounded browser interaction performance',async({page,browser},info)=>{
  test.setTimeout(120000);
  const samples=[];await page.locator('#exStage').focus();
  for(let i=0;i<20;i++){const start=performance.now();await page.keyboard.press('ArrowRight');await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));samples.push(performance.now()-start)}
  const sorted=[...samples].sort((a,b)=>a-b),p95=sorted[Math.ceil(sorted.length*.95)-1];expect((await state(page)).yaw).toBe(300);expect(p95,'Input and two-frame acknowledgement must finish below 1.5 seconds on CI').toBeLessThan(1500);
  const frameIntervals=await page.evaluate(()=>new Promise(resolve=>{const spans=[];let last;function tick(now){if(last!==undefined)spans.push(now-last);last=now;if(spans.length===60)resolve(spans);else requestAnimationFrame(tick)}requestAnimationFrame(tick)}));
  await page.evaluate(()=>window.explorer.open('snapshots'));await page.locator('#exStage').focus();
  const detailStart=await state(page),detailSamples=[];
  for(let i=0;i<20;i++){const start=performance.now();await page.keyboard.press('ArrowRight');await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));detailSamples.push(performance.now()-start)}
  const detailSorted=[...detailSamples].sort((a,b)=>a-b),detailP95=detailSorted[Math.ceil(detailSorted.length*.95)-1];
  expect((await state(page)).yaw).toBe(detailStart.yaw+300);expect(detailP95,'Bounded cutaway input and two-frame acknowledgement').toBeLessThan(1500);
  await cutaway(page,'snapshots','file:rentgen_core/capture.py');
  const navigationSamples=[];await selectRoute(page,'0');
  for(let i=0;i<3;i++){const start=performance.now();await page.locator('#exRouteNext').click();await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));navigationSamples.push(performance.now()-start);expect((await state(page)).stepIndex).toBe(i+1);}
  expect(Math.max(...navigationSamples),'Source-route navigation and two-frame acknowledgement').toBeLessThan(1500);
  await writeFile(info.outputPath('browser-performance.json'),JSON.stringify({browserVersion:browser.version(),sampleCount:samples.length,inputAndTwoFramesMs:samples,p95Ms:p95,detailInputAndTwoFramesMs:detailSamples,detailP95Ms:detailP95,routeNavigationAndTwoFramesMs:navigationSamples,idleFrameIntervalsMs:frameIntervals,scope:'Current Chromium CI host; not a mobile FPS claim'},null,2));await evidence(page,info,'performance-final-camera',page.locator('#exViewport'));
});


test('Q09 selected-system opening is independent and reversible',async({page},info)=>{
  test.setTimeout(120000);
  await page.locator('#exReset').click();
  await label(page,'interfaces').locator('rect').click();
  const capture=()=>page.evaluate(()=>({
    selectedPose:window.explorer.controller.pose('sys_interfaces'),
    otherPose:window.explorer.controller.pose('sys_identity'),
    selectedGeometry:[...document.querySelectorAll('#exStage [data-ex-id="interfaces"]')].map(n=>n.outerHTML),
    otherGeometry:[...document.querySelectorAll('#exStage [data-ex-id="identity"]')].map(n=>n.outerHTML),
  }));
  const closed=await capture();
  await expect(page.locator('#exNodeExplode')).toBeEnabled();
  await page.locator('#exNodeExplode').focus();await page.keyboard.press('End');
  await expect.poll(async()=>(await state(page)).nodeExplosions.interfaces).toBe(100);
  const opened=await capture();
  expect(opened.selectedPose.t).not.toEqual(closed.selectedPose.t);
  expect(opened.selectedGeometry).not.toEqual(closed.selectedGeometry);
  expect(opened.otherPose).toEqual(closed.otherPose);
  expect(opened.otherGeometry).toEqual(closed.otherGeometry);
  await evidence(page,info,'selected-system-opened',page.locator('#exViewport'));
  await page.locator('#exOpen').click();await expect(page.locator('#exNodeExplode')).toBeDisabled();
  await page.locator('#exBack').click();
  expect((await state(page)).nodeExplosions.interfaces).toBe(100);
  expect((await capture()).selectedPose).toEqual(opened.selectedPose);
  await page.locator('#exNodeExplode').focus();await page.keyboard.press('Home');
  const reversed=await capture();expect(reversed.selectedPose).toEqual(closed.selectedPose);expect(reversed.otherPose).toEqual(closed.otherPose);
  await page.keyboard.press('End');
  await page.locator('#exExplode').focus();await page.keyboard.press('End');
  expect((await state(page)).nodeExplosions).toEqual({});
  const shared=await capture();expect(shared.selectedPose).toEqual(opened.selectedPose);expect(shared.otherPose.t).not.toEqual(closed.otherPose.t);expect(shared.otherGeometry).not.toEqual(closed.otherGeometry);
  await expect(page.locator('#exNodeExplode')).toHaveValue('100');
  await page.keyboard.press('Home');const sharedClosed=await capture();expect(sharedClosed.selectedPose).toEqual(closed.selectedPose);expect(sharedClosed.otherPose).toEqual(closed.otherPose);
  await page.locator('#exNodeExplode').focus();await page.keyboard.press('End');await page.locator('#exReset').click();
  expect((await state(page)).nodeExplosions).toEqual({});
  expect((await capture()).selectedPose).toEqual(closed.selectedPose);
  await evidence(page,info,'selected-system-reset',page.locator('#exViewport'));

  // The source cutaway has an actual parented hinge and nested slides, independently
  // of the whole-system overview opening control qualified above.
  await label(page,'snapshots').focus();await page.keyboard.press(' ');
  await page.locator('#exStage').focus();await page.keyboard.press('ArrowRight');await page.keyboard.press('ArrowUp');
  await cameraDrag(page,35,25,true);await page.locator('#exZoomIn').click();
  const overview=await state(page),overviewCamera=camera(overview);
  await page.locator('#exOpen').click();await cutaway(page,'snapshots','file:rentgen_core/capture.py');
  await selectFilter(page,'#exRelations','all');await cutaway(page,'snapshots','file:rentgen_core/capture.py');
  expect((await state(page)).neighborCount).toBeGreaterThan(0);
  const pose=()=>page.evaluate(()=>{
    const c=window.explorer.controller,geometry=prefix=>[...document.querySelectorAll('#exStage [data-name]')].filter(n=>n.dataset.name.startsWith(prefix)).map(n=>n.outerHTML);
    return{world:c.pose('world'),cover:c.pose('cover'),left:c.pose('leftCompartments'),right:c.pose('rightCompartments'),focus:c.pose('focus'),baseGeometry:[...document.querySelectorAll('#exStage [data-name]')].filter(n=>n.dataset.name.endsWith('shell.base')).map(n=>n.outerHTML),coverGeometry:geometry('cover.'),trayGeometry:geometry('compartment0.'),focusGeometry:geometry('focus.')};
  });
  await page.locator('#exDetailOpening').focus();await page.keyboard.press('Home');
  await expect.poll(async()=>(await state(page)).detailOpening).toBe(0);
  const shut=await pose(),detailCamera=camera(await state(page));
  for(const key of ['baseGeometry','coverGeometry','trayGeometry','focusGeometry'])expect(shut[key].length).toBeGreaterThan(0);
  async function closedHitTargets(opening){
    expect((await state(page)).detailOpening).toBe(opening);
    await expect(page.locator('#exOverlay .ex-source-hit,#exOverlay .ex-compartment-callout,#exOverlay .neighbor,#exOverlay [data-ex-edge]')).toHaveCount(0);
    const overlayIds=await page.locator('#exOverlay [data-ex-id]').evaluateAll(els=>els.map(el=>el.dataset.exId));
    expect(overlayIds,'Only the parent shell may be interactive while the lid is not fully open').toEqual(['snapshots']);
    const parts=await page.locator('#exStage [data-name][data-ex-id]').evaluateAll(els=>els.filter(el=>/^(source|focus|compartment)/.test(el.dataset.name)).map(el=>({name:el.dataset.name,pointerEvents:getComputedStyle(el).pointerEvents,ariaHidden:el.getAttribute('aria-hidden')})));
    expect(parts.length).toBeGreaterThan(0);for(const part of parts){expect(part.pointerEvents,part.name).toBe('none');expect(part.ariaHidden,part.name).toBe('true');}
    const neighbors=await page.locator('#exStage [data-name][data-ex-id]').evaluateAll(els=>els.filter(el=>/^(stand\.)?neighbor/.test(el.dataset.name)).map(el=>({name:el.dataset.name,display:getComputedStyle(el).display})));
    expect(neighbors.length).toBeGreaterThan(0);for(const neighbor of neighbors)expect(neighbor.display,`${neighbor.name} is hidden even if its file is also a compartment representative`).toBe('none');
    await page.locator('#exViewport').scrollIntoViewIfNeeded();
    const hitTest=await page.locator('#exViewport').evaluate(el=>{
      const b=el.getBoundingClientRect(),hits=[];let scanned=0;
      for(let y=Math.max(0,b.top)+8;y<Math.min(innerHeight,b.bottom);y+=16)for(let x=Math.max(0,b.left)+8;x<Math.min(innerWidth,b.right);x+=16){
        scanned++;const target=document.elementFromPoint(x,y)?.closest('#exStage [data-name][data-ex-id]');
        if(target&&/^(source|focus|compartment|(stand\.)?neighbor)/.test(target.dataset.name))hits.push(target.dataset.name);
      }
      return{scanned,hits};
    });
    expect(hitTest.scanned).toBeGreaterThan(20);expect(hitTest.hits,'Real browser hit-testing cannot select covered interior source geometry').toEqual([]);
  }
  await closedHitTargets(0);
  await openTree(page);await expect(page.locator('#exSourceTree [data-tree-file]')).toHaveCount(11);
  await selectTreeFile(page,'rentgen_core/capture.py');await exactSource(page,'file:rentgen_core/capture.py');
  expect((await state(page)).detailOpening,'The complete source tree remains usable with the lid closed').toBe(0);
  await page.locator('#exTreeSearch').fill('');
  const shutPixels=await evidence(page,info,'snapshot-cover-closed',page.locator('#exViewport'));
  await page.locator('#exDetailOpening').focus();await page.keyboard.press('End');await page.keyboard.press('ArrowLeft');await page.keyboard.press('ArrowLeft');
  await closedHitTargets(98);
  await page.locator('#exDetailOpening').focus();await page.keyboard.press('End');
  await expect.poll(async()=>(await state(page)).detailOpening).toBe(100);
  const open=await pose();
  expect(open.world,'The parent shell stays in place while its children open').toEqual(shut.world);
  expect(open.baseGeometry).toEqual(shut.baseGeometry);expect(open.cover.R).not.toEqual(shut.cover.R);
  expect(open.left.t).not.toEqual(shut.left.t);expect(open.right.t).not.toEqual(shut.right.t);expect(open.focus.t).not.toEqual(shut.focus.t);
  for(const key of ['coverGeometry','trayGeometry','focusGeometry'])expect(open[key]).not.toEqual(shut[key]);
  expect(camera(await state(page))).toEqual(detailCamera);await cutaway(page,'snapshots','file:rentgen_core/capture.py');
  await expect(page.locator('#exOverlay .ex-source-hit').first()).toBeVisible();
  const enabledParts=await page.locator('#exStage [data-name][data-ex-id]').evaluateAll(els=>els.filter(el=>/^(source|focus|compartment)/.test(el.dataset.name)).map(el=>({pointerEvents:getComputedStyle(el).pointerEvents,ariaHidden:el.getAttribute('aria-hidden')})));
  expect(enabledParts.length).toBeGreaterThan(0);for(const part of enabledParts){expect(part.pointerEvents).not.toBe('none');expect(part.ariaHidden).toBe('false');}
  const openPixels=await evidence(page,info,'snapshot-cover-and-nested-slides-open',page.locator('#exViewport'));
  expect(openPixels.sha256).not.toBe(shutPixels.sha256);
  await page.locator('#exDetailOpening').focus();await page.keyboard.press('Home');expect(await pose()).toEqual(shut);
  await page.locator('#exDetailOpening').focus();await page.keyboard.press('End');expect(await pose()).toEqual(open);
  await page.locator('#exCloseCutaway').click();
  expect((await state(page)).mode).toBe('overview');expect((await state(page)).selected).toBe(overview.selected);expect(camera(await state(page))).toEqual(overviewCamera);
  await expect(page.locator('#exCutaway')).toBeHidden();
  await page.locator('#exOpen').click();await page.locator('#exStage').focus();await page.keyboard.press('ArrowLeft');
  await page.locator('#exBack').click();expect((await state(page)).mode).toBe('overview');expect(camera(await state(page))).toEqual(overviewCamera);
  await page.locator('#exForward').click();expect((await state(page)).cutawayRoot).toBe('snapshots');
  await cutaway(page,'snapshots','file:rentgen_core/capture.py');
  await evidence(page,info,'snapshot-history-restored',page.locator('#exViewport'));
});
