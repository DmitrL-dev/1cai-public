import test from 'node:test';
import assert from 'node:assert/strict';
import {escapeHTML,filterRows,relatedModules,displayName,formatBytes} from '../../rentgen_core/gui_assets/model.js';
const row={name:'Товары',type:'Catalog',input_ref:{relative_path:'Catalogs/Товары.xml'}};
test('escape untrusted archive names and markup',()=>{assert.equal(escapeHTML('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');assert.equal(escapeHTML("'&"),'&#39;&amp;');});
test('Russian search, type filters and paths are deterministic',()=>{assert.deepEqual(filterRows([row],'ТОВАР','Catalog'),[row]);assert.equal(filterRows([row],'товар','Document').length,0);assert.equal(filterRows([row],'Catalogs').length,1);assert.equal(filterRows([row],'не найдено').length,0);});
test('module relation uses exact object path boundary',()=>{const modules=[{input_ref:{relative_path:'Catalogs/Товары/Ext/ObjectModule.bsl'}},{input_ref:{relative_path:'Catalogs/ТоварыЕще/Ext/ObjectModule.bsl'}}];assert.deepEqual(relatedModules(row,modules),[modules[0]]);assert.equal(displayName(modules[0],true),'Товары');});
test('sizes use binary units',()=>{assert.equal(formatBytes(500),'500 Б');assert.equal(formatBytes(1024),'1 КиБ');assert.equal(formatBytes(1048576),'1 МиБ');});

test('secondary copy keeps AA contrast on white and canvas', async()=>{
  const {readFile}=await import('node:fs/promises');
  const css=await readFile(new URL('../../rentgen_core/gui_assets/app.css',import.meta.url),'utf8');
  const foreground=css.match(/--muted:(#[0-9a-f]{6})/)[1];
  const background=css.match(/--canvas:(#[0-9a-f]{6})/)[1];
  const luminance=hex=>hex.slice(1).match(/../g).map(c=>parseInt(c,16)/255).map(c=>c<=.04045?c/12.92:((c+.055)/1.055)**2.4).reduce((n,c,i)=>n+c*[.2126,.7152,.0722][i],0);
  const ratio=(a,b)=>{const values=[luminance(a),luminance(b)].sort((x,y)=>x-y);return (values[1]+.05)/(values[0]+.05);};
  assert.ok(ratio(foreground,background)>=4.5);
  assert.ok(ratio(foreground,'#ffffff')>=4.5);
  assert.ok(ratio('#4e6b82','#edf3f8')>=4.5);
  for(const lowContrast of ['#677787','#6d8292','#6d8293','#728696','#7e91a0'])assert.ok(!css.includes(lowContrast));
});
