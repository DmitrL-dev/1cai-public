import test from 'node:test';
import assert from 'node:assert/strict';
import {boundedMetadataQuery,searchReplyMatches} from '../../rentgen_core/gui_assets/model.js';

test('metadata query limit is UTF-8 bytes, with explicit empty/Unicode boundaries',()=>{
  assert.deepEqual(boundedMetadataQuery('  '),{query:'',valid:true});
  assert.equal(boundedMetadataQuery('я'.repeat(128)).valid,true);
  assert.equal(boundedMetadataQuery('я'.repeat(129)).valid,false);
  assert.equal(boundedMetadataQuery('😀'.repeat(64)).valid,true);
  assert.equal(boundedMetadataQuery('😀'.repeat(65)).valid,false);
  assert.equal(boundedMetadataQuery('a'.repeat(256)).valid,true);
  assert.equal(boundedMetadataQuery('a'.repeat(257)).valid,false);
});
test('metadata search reply cannot cross job, archive, query or search generation',()=>{
  const binding={job:'owned-job',input_sha256:'a'.repeat(64),kind:'metadata',object_path:null,offset:0};
  const reply={...binding,search:'owned-search',prefix:null,query:'Товар',status:'ready',result:{input:{input_sha256:binding.input_sha256},objects:[],matching_objects:0,page:{offset:0,limit:200,total:0,returned:0,has_previous:false,has_next:false}}};
  assert.ok(searchReplyMatches(binding,'owned-search','Товар',reply));
  assert.equal(searchReplyMatches(binding,'owned-search','Товар',{...reply,result:{}}),false);
  for(const [key,value] of [['job','old-job'],['input_sha256','b'.repeat(64)],['search','old-search'],['query','Other']])assert.equal(searchReplyMatches(binding,'owned-search','Товар',{...reply,[key]:value}),false);
  assert.equal(searchReplyMatches(binding,'owned-search','Товар',{...reply,result:{...reply.result,input:{input_sha256:'b'.repeat(64)}}}),false);
  assert.equal(searchReplyMatches(binding,'owned-search','Товар',{...reply,result:{...reply.result,objects:Array(201).fill({})}}),false);
});

test('module discovery reply binds kind and related object and bounds module hits',()=>{
  const binding={job:'job',input_sha256:'a'.repeat(64),kind:'modules',object_path:'Catalogs/Late.xml',offset:0};
  const reply={...binding,search:'search',prefix:'Catalogs/Late/',query:'модуль',status:'ready',result:{input:{input_sha256:binding.input_sha256},modules:[],matching_modules:0,page:{offset:0,limit:200,total:0,returned:0,has_previous:false,has_next:false}}};
  assert.ok(searchReplyMatches(binding,'search','модуль',reply));
  for(const update of [{prefix:'Catalogs/LateNeighbor/'},{kind:'metadata'},{object_path:null},{object_path:'Catalogs/Other.xml'},{result:{...reply.result,modules:Array(201).fill({})}},{result:{...reply.result,objects:[],modules:undefined}}])assert.equal(searchReplyMatches(binding,'search','модуль',{...reply,...update}),false);
});

test('page replies bind offsets, exact range counts and navigation flags',()=>{
  const binding={job:'job',input_sha256:'a'.repeat(64),kind:'metadata',object_path:null,offset:400};
  const page={offset:400,limit:200,total:401,returned:1,has_previous:true,has_next:false};
  const result={input:{input_sha256:binding.input_sha256},objects:[{}],matching_objects:401,page};
  const reply={...binding,search:'search',prefix:null,query:'',status:'ready',result};
  assert.ok(searchReplyMatches(binding,'search','',reply));
  assert.equal(searchReplyMatches(binding,'search','',{...reply,offset:200}),false);
  for(const update of [{offset:200},{limit:201},{total:402},{returned:0},{has_previous:false},{has_next:true}])assert.equal(searchReplyMatches(binding,'search','',{...reply,result:{...result,page:{...page,...update}}}),false);
  assert.equal(searchReplyMatches(binding,'search','',{...reply,result:{...result,objects:[]}}),false);
  assert.equal(searchReplyMatches(binding,'search','',{...reply,result:{...result,matching_objects:400}}),false);
});

test('source literals preserve spaces and reject multiline/control/overflow values',async()=>{
  const {boundedSourceQuery}=await import('../../rentgen_core/gui_assets/model.js');
  assert.deepEqual(boundedSourceQuery(' needle '),{query:' needle ',valid:true});
  for(const query of ['', 'a\nb', 'a\rb', '\0', 'я'.repeat(129), '\ud800'])assert.equal(boundedSourceQuery(query).valid,false);
  assert.equal(boundedSourceQuery('\t'+'я'.repeat(127)).valid,true);
});
test('source result requires honest coverage and bounded first-match text',()=>{
  const binding={job:'job',input_sha256:'a'.repeat(64),kind:'source',object_path:null,offset:0};
  const row={analysis:'literal_first_match',first_match:{line:2,excerpt:'needle',truncated_before:false,truncated_after:false}};
  const coverage={in_scope:2,searched:1,skipped_oversized:1,skipped_invalid_utf8:0,skipped_controls:0,complete:false};
  const result={input:{input_sha256:binding.input_sha256},modules:[row],matching_modules:1,source_coverage:coverage,page:{offset:0,limit:200,total:1,returned:1,has_previous:false,has_next:false}};
  const reply={...binding,search:'search',prefix:null,query:'needle',status:'ready',result};
  assert.ok(searchReplyMatches(binding,'search','needle',reply));
  for(const update of [{source_coverage:{...coverage,complete:true}},{source_coverage:{...coverage,searched:2}},{modules:[{...row,first_match:{...row.first_match,line:0}}]},{modules:[{...row,first_match:{...row.first_match,excerpt:'x'.repeat(513)}}]}])assert.equal(searchReplyMatches(binding,'search','needle',{...reply,result:{...result,...update}}),false);
});


test('module search mode has an explicit stable label separate from option text',async()=>{
  const {readFile}=await import('node:fs/promises');
  const html=await readFile(new URL('../../rentgen_core/gui_assets/index.html',import.meta.url),'utf8');
  const select=html.match(/<select\b[^>]*\bid="module-search-mode"[^>]*>/)?.[0];
  assert.ok(select,'module mode selector exists');
  assert.match(select,/\baria-labelledby="module-search-mode-label"/);
  const labels=[...html.matchAll(/<span\b[^>]*\bid="module-search-mode-label"[^>]*>([^<]*)<\/span>/g)];
  assert.equal(labels.length,1,'exactly one dedicated text-only label');
  assert.equal(labels[0][1],'Режим поиска модулей');
  // Keep the browser's exact-label locator contract tied to the shipped label.
  for(const path of ['browser/source-search.spec.mjs','browser/acceptance.spec.mjs']){
    const spec=await readFile(new URL(path,import.meta.url),'utf8');
    assert.ok(spec.includes(`getByLabel('${labels[0][1]}',{exact:true}).selectOption('source')`));
    assert.ok(spec.includes(`toHaveAccessibleName('${labels[0][1]}')`));
  }
});
