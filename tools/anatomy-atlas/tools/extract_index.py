"""Owned static indexer. Source bytes are data; no project module is executed."""
import ast
import collections
import hashlib
import posixpath
import re
from pathlib import PurePosixPath

LANG={'.py':'Python','.rs':'Rust','.go':'Go','.cjs':'JavaScript','.mjs':'JavaScript','.js':'JavaScript','.css':'CSS','.html':'HTML','.ps1':'PowerShell','.c':'C','.h':'C header','.yml':'YAML','.yaml':'YAML','.json':'JSON','.toml':'TOML','.md':'Markdown','.bsl':'BSL','.xml':'XML','.svg':'SVG','.txt':'Text','.lock':'Lockfile'}
PATTERNS={
 'Rust':r'^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:fn|struct|enum|trait)\s+(\w+)',
 'Go':r'^\s*(?:func\s+(?:\([^)]*\)\s+)?|type\s+)(\w+)',
 'JavaScript':r'^\s*(?:export\s+)?(?:(?:async\s+)?function\s+|class\s+)([\w$]+)|^\s*(?:export\s+)?(?:const|let)\s+([\w$]+)\s*=\s*(?:async\s*)?(?:\([^;]*\)|[\w$]+)\s*=>',
 'PowerShell':r'^\s*function\s+([\w-]+)',
 'C':r'^\s*(?:static\s+)?(?:int|void|BOOL|DWORD|HANDLE|size_t|char\s*\*)\s+(\w+)\s*\(',
 'C header':r'^\s*(?:static\s+)?(?:int|void|BOOL|DWORD|HANDLE|size_t|char\s*\*)\s+(\w+)\s*\('
}

def index_source(raw_files, pin, classification):
 def src(p,line=1,end=None,symbol=None):
  d=dict(path=p,line=line,endLine=end or line,url=f'https://github.com/DmitrL-dev/1cai-public/blob/{pin}/{p}#L{line}'+(f'-L{end}' if end and end!=line else ''))
  if symbol:d['symbol']=symbol
  return d
 nodes=[];edges=[];inventory=[];trees={};texts={};files={};errors=[];symbols={};constants=[];sql=[]
 for p,raw in raw_files.items():
  txt=raw.decode('utf-8',errors='replace');lines=txt.splitlines();texts[p]=txt
  prior=classification.get(p,{})
  lang=prior.get('language',LANG.get(PurePosixPath(p).suffix,'Other'))
  role=prior.get('role','test' if p.startswith('tests/') else 'supporting_file');group=prior.get('systemId','delivery')
  status='experimental_source' if group=='kernel' else 'accepted_main_source'
  info=dict(path=p,bytes=len(raw),lines=len(lines),sha256=hashlib.sha256(raw).hexdigest(),language=lang,role=role,systemId=group,status=status);inventory.append(info)
  doc=None
  if lang=='Python':
   try:tree=ast.parse(txt,filename=p);trees[p]=tree;doc=ast.get_docstring(tree)
   except SyntaxError as e:errors.append(dict(path=p,error=str(e)))
  elif lang in ('Rust','Go','JavaScript'):
   comment=[]
   for line in lines[:30]:
    if re.match(r'^\s*(//!|//|/\*|\*|\*/)',line):comment.append(re.sub(r'^\s*(//!|//|/\*|\*|\*/)\s?','',line))
    elif line.strip() and comment:break
   doc='\n'.join(comment) or None
  if p.endswith('.md'):
   m=re.search(r'^#\s+(.+)$',txt,re.M);doc=m.group(1) if m else None
  node=dict(id='file:'+p,parentId=group,systemId=group,label=p.split('/')[-1],kind='module' if role=='production_source' else 'file',language=lang,path=p,line=1,endLine=max(1,len(lines)),summary=(doc.split('\n\n')[0] if doc else {'test':'Контрактные тесты; наличие файла не свидетельствует о текущем pass.','verification_harness':'Harness ограниченного сценария проверки; не production entrypoint.','historical_evidence':'Историческое доказательство, привязанное к своей версии/дате.','fixture':'Фикстура для воспроизводимого ограниченного сценария.','build_and_delivery':'Конфигурация или инструмент сборки/проверки поставки.','documentation':'Документация; возможности сверяются с исходным кодом и статусом.','license':'Лицензионные данные и provenance сторонних компонентов.'}.get(role,'Файл исходного дерева; индексирован для полноты навигации.')),technicalDoc=doc,status=status,role=role,refs=[src(p,1,min(len(lines),15))],tags=[group,lang,role],symbolIds=[])
  nodes.append(node);files[p]=node
  for table in re.finditer(r'CREATE TABLE(?: IF NOT EXISTS)?\s+([A-Za-z_]\w*)\s*\(',txt):
   line=txt[:table.start()].count('\n')+1;sql.append(dict(table=table.group(1),path=p,line=line,systemId=group,ref=src(p,line)))
  if p in trees:
   def walk(body,parents=()):
    for n in body:
     if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
      q='.'.join((*parents,n.name));sid='symbol:'+p+':'+q
      if sid in symbols:sid+='@'+str(n.lineno)
      end=getattr(n,'end_lineno',n.lineno);ndoc=ast.get_docstring(n);kind='class' if isinstance(n,ast.ClassDef) else 'method' if parents else 'function';signature=lines[n.lineno-1].strip()
      for cont in lines[n.lineno:min(end,n.lineno+12)]:
       if signature.rstrip().endswith(':'):break
       signature+=' '+cont.strip()
      item=dict(id=sid,parentId='symbol:'+p+':'+'.'.join(parents) if parents else 'file:'+p,systemId=group,label=q,kind=kind,language=lang,path=p,line=n.lineno,endLine=end,summary=ndoc.split('\n\n')[0] if ndoc else f'{"Класс" if kind=="class" else "Метод" if kind=="method" else "Функция"} {q}; декларация и точный диапазон исходного кода.',technicalDoc=ndoc,signature=signature[:1600],status=status,role=role,refs=[src(p,n.lineno,end,q)],tags=[group,lang,kind])
      if isinstance(n,ast.ClassDef):item['bases']=[ast.unparse(x) for x in n.bases]
      nodes.append(item);symbols[sid]=item;node['symbolIds'].append(sid);walk(n.body,(*parents,n.name))
     elif isinstance(n,(ast.If,ast.Try,ast.With,ast.AsyncWith,ast.For,ast.While)):
      walk(n.body,parents);walk(getattr(n,'orelse',[]),parents)
      for handler in getattr(n,'handlers',[]):walk(handler.body,parents)
   walk(trees[p].body)
   for n in trees[p].body:
    if isinstance(n,(ast.Assign,ast.AnnAssign)):
     for target in n.targets if isinstance(n,ast.Assign) else [n.target]:
      if isinstance(target,ast.Name) and target.id.isupper():
       try:value=ast.literal_eval(n.value)
       except Exception:continue
       if isinstance(value,(str,int,float,bool,list,tuple,set,dict)) and len(repr(value))<=18000:
        if isinstance(value,set):value=sorted(value)
        constants.append(dict(name=target.id,path=p,line=n.lineno,value=value,systemId=group,ref=src(p,n.lineno,getattr(n,'end_lineno',n.lineno))))
  elif lang in PATTERNS:
   for idx,line in enumerate(lines,1):
    m=re.match(PATTERNS[lang],line)
    if not m:continue
    name=next(x for x in m.groups() if x);sid=f'symbol:{p}:{name}@{idx}'
    item=dict(id=sid,parentId='file:'+p,systemId=group,label=name,kind='declaration',language=lang,path=p,line=idx,endLine=idx,summary='Статически обнаруженная декларация; ссылка указывает на реальную строку. Тело и динамическая достижимость не выводятся regex-анализом.',signature=line.strip(),status=status,role=role,refs=[src(p,idx,symbol=name)],tags=[group,lang,'declaration'])
    nodes.append(item);symbols[sid]=item;node['symbolIds'].append(sid)
 modules={p[:-3].replace('/','.') :p for p in trees if '/' in p and '-' not in p}
 for p in list(modules.values()):
  if p.endswith('/__init__.py'):modules[p[:-12].replace('/','.')]=p
 for p,tree in trees.items():
  package=p.rsplit('/',1)[0].replace('/','.') if '/' in p else '';seen=set()
  for n in ast.walk(tree):
   candidates=[]
   if isinstance(n,ast.Import):candidates=[a.name for a in n.names]
   if isinstance(n,ast.ImportFrom):
    prefix='.'.join(package.split('.')[:len(package.split('.'))-n.level+1]) if n.level else '';base='.'.join(x for x in [prefix,n.module or ''] if x);candidates=[base+'.'+a.name for a in n.names]+[base]
   for module in candidates:
    target=modules.get(module)
    if target and target!=p and (target,n.lineno) not in seen:
     seen.add((target,n.lineno));edges.append(dict(id=f'import:{p}:{n.lineno}:{target}',source='file:'+p,target='file:'+target,kind='import',label='Импорт модуля',semantics='Статическая зависимость импорта; не доказательство выполнения или передачи данных.',refs=[src(p,n.lineno,getattr(n,'end_lineno',n.lineno))]))
 for p,txt in texts.items():
  if PurePosixPath(p).suffix not in ('.js','.cjs','.mjs'):continue
  for m in re.finditer(r'(?:require\(\s*[\"\']|from\s*[\"\'])(\.[^\"\']+)',txt):
   path=posixpath.normpath(str(PurePosixPath(p).parent/m.group(1)));target=next((x for x in [path,path+'.js',path+'.cjs',path+'/index.js'] if x in files),None)
   if target:
    line=txt[:m.start()].count('\n')+1;edges.append(dict(id=f'import:{p}:{line}:{target}',source='file:'+p,target='file:'+target,kind='import',label='Импорт JavaScript',semantics='Разрешённый относительный import/require из исходника, не runtime telemetry.',refs=[src(p,line)]))
 coverage=dict(trackedFiles=len(raw_files),indexedFiles=len(inventory),unindexedFiles=[],symbolCount=len(symbols),pythonAstFiles=len(trees),pythonParseErrors=errors,importEdges=len(edges),filesByLanguage=dict(collections.Counter(x['language'] for x in inventory)),filesByRole=dict(collections.Counter(x['role'] for x in inventory)),filesBySystem=dict(collections.Counter(x['systemId'] for x in inventory)),changedSinceAcceptedMain=0,sourceLines=sum(x['lines'] for x in inventory),coverageMeaning='100% tracked-file indexing; Python symbols parsed by AST, other languages declaration-indexed by regex. Not test coverage or exhaustive semantic verification.')
 return dict(nodes=nodes,edges=edges,inventory=inventory,coverage=coverage,constants=constants,storageTables=sql)
