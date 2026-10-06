import test from 'node:test';
import assert from 'node:assert/strict';
import {escapeHTML,filterRows,relatedModules,displayName,formatBytes} from '../../rentgen_core/gui_assets/model.js';
const row={name:'Товары',type:'Catalog',input_ref:{relative_path:'Catalogs/Товары.xml'}};
test('escape untrusted archive names and markup',()=>{assert.equal(escapeHTML('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');assert.equal(escapeHTML("'&"),'&#39;&amp;');});
test('Russian search, type filters and paths are deterministic',()=>{assert.deepEqual(filterRows([row],'ТОВАР','Catalog'),[row]);assert.equal(filterRows([row],'товар','Document').length,0);assert.equal(filterRows([row],'Catalogs').length,1);assert.equal(filterRows([row],'не найдено').length,0);});
test('module relation uses exact object path boundary',()=>{const modules=[{input_ref:{relative_path:'Catalogs/Товары/Ext/ObjectModule.bsl'}},{input_ref:{relative_path:'Catalogs/ТоварыЕще/Ext/ObjectModule.bsl'}}];assert.deepEqual(relatedModules(row,modules),[modules[0]]);assert.equal(displayName(modules[0],true),'Товары');});
test('sizes use binary units',()=>{assert.equal(formatBytes(500),'500 Б');assert.equal(formatBytes(1024),'1 КиБ');assert.equal(formatBytes(1048576),'1 МиБ');});
