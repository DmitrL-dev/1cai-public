#!/usr/bin/env python3
"""Generate the reviewed atlas from exact Git objects; never execute product code."""
import argparse
import collections
import copy
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
from extract_index import index_source

HERE=Path(__file__).resolve().parent

def read_source(repo,pin):
 def git(*args):return subprocess.check_output(['git','-C',str(repo),*args])
 exact=git('rev-parse','--verify',pin+'^{commit}').decode().strip();tree=git('rev-parse',pin+'^{tree}').decode().strip()
 if exact!=pin:raise ValueError('Expected exact full commit SHA')
 blobs={}
 for row in git('ls-tree','-r','-z',pin).decode().split('\0'):
  if not row:continue
  head,path=row.split('\t',1);mode,kind,sha=head.split()
  if kind!='blob' or mode not in ('100644','100755'):raise ValueError('Unsupported tree entry: '+path)
  blobs[path]={'blobSha':sha,'gitMode':mode}
 raw={}
 with tarfile.open(fileobj=io.BytesIO(git('archive','--format=tar',pin))) as archive:
  for member in archive:
   if member.isdir():continue
   path=PurePosixPath(member.name)
   if not member.isfile() or path.is_absolute() or '..' in path.parts or member.name not in blobs:raise ValueError('Unsafe or unexpected archive member')
   content=archive.extractfile(member).read()
   if hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()!=blobs[member.name]['blobSha']:raise ValueError('Git blob mismatch: '+member.name)
   raw[member.name]=content
 if set(raw)!=set(blobs):raise ValueError('Archive omitted tracked files')
 return {p:raw[p] for p in blobs},blobs,tree,git('show','-s','--format=%cI',pin).decode().strip()

def generate(repo,pin,seed):
 if pin!=seed['sourceCommit']:raise ValueError('Commit does not match reviewed editorial seed')
 raw,blobs,tree,stamp=read_source(repo,pin)
 if tree!=seed['sourceTree']:raise ValueError('Source tree does not match reviewed seed')
 d=index_source(raw,pin,seed['classification']);d.update(copy.deepcopy(seed['topLevel']));d['meta'].update(generatedAt=stamp,acceptanceUpdatedAt=stamp)
 d['coverage'].update(seed.get('coverageExtras',{}));texts={};omitted=[]
 for f in d['inventory']:
  p=f['path'];f.update(blobs[p]);f['sourceCommit']=pin
  try:txt=raw[p].decode('utf-8')
  except UnicodeDecodeError:omitted.append({'path':p,'reason':'not_utf8'});continue
  if '\0' in txt:omitted.append({'path':p,'reason':'binary_null_bytes'});continue
  texts[p]={'text':txt,'lineCount':len(txt.splitlines()),'sha256':f['sha256'],'blobSha':f['blobSha'],'encoding':'utf-8'}
 for n in d['nodes']:
  n.update(copy.deepcopy(seed['nodePatches'].get(n['id'],{})))
  n['sourceCommit']=pin;n['sourceTextAvailable']=n['path'] in texts
  n['evidenceKind']='tracked_file' if n['kind'] in ('file','module') else 'python_ast_declaration' if n['language']=='Python' else 'lexical_declaration'
  # Legacy role tags are normalized deterministically; tags are navigation hints.
  n['tags']=list(dict.fromkeys([*n['tags'],n['role']]))
  if not n['sourceTextAvailable']:
   n.pop('line',None);n.pop('endLine',None);n['evidenceKind']='tracked_binary_file';n['refs']=[{'path':n['path'],'url':f'https://github.com/DmitrL-dev/1cai-public/blob/{pin}/'+n['path']}]
 for e in d['edges']:
  e['evidenceKind']='static_import';e['sourceSyntax']='\n'.join('\n'.join(texts[r['path']]['text'].splitlines()[r['line']-1:r.get('endLine',r['line'])]) for r in e.get('refs',[]) if r['path'] in texts)
 d['edges'].extend(copy.deepcopy(seed['editorialEdges']))
 for section in d['sections']:
  members=[n for n in d['nodes'] if n['systemId']==section['id']];files=[n for n in members if n['kind'] in ('file','module')]
  section.update(nodeIds=[n['id'] for n in files],fileCount=len(files),moduleCount=sum(n['role']=='production_source' for n in files),symbolCount=len(members)-len(files),sourceSymbolCount=sum(n['role']=='production_source' and n['kind'] not in ('file','module') for n in members))
 directories={}
 for f in d['inventory']:
  path=PurePosixPath(f['path']).parent
  while str(path)!='.':
   key='directory:'+str(path)
   if key not in directories:directories[key]={'id':key,'path':str(path),'label':path.name,'kind':'directory','parentId':'directory:'+str(path.parent) if str(path.parent)!='.' else 'repository','childIds':[],'evidenceKind':'tracked_path_hierarchy'}
   path=path.parent
 for directory in directories.values():
  if directory['parentId'] in directories:directories[directory['parentId']]['childIds'].append(directory['id'])
 for n in d['nodes']:
  if n['kind'] in ('file','module'):
   parent=str(PurePosixPath(n['path']).parent);n['directoryId']='directory:'+parent if parent!='.' else 'repository'
   if n['directoryId'] in directories:directories[n['directoryId']]['childIds'].append(n['id'])
 d['directories']=sorted(directories.values(),key=lambda x:x['path']);d['semanticRoutes']=d['flows']
 d['coverage'].update(trackedTextLines=sum(f['lines'] for f in d['inventory']),symbolsByRole=dict(collections.Counter(n['role'] for n in d['nodes'] if n['kind'] not in ('file','module'))),sourceTextFiles=len(texts),sourceTextOmissions=omitted,curatedArchitectureEdges=len(seed['editorialEdges']))
 errors=[];identifiers=[n['id'] for n in d['nodes']];ids=set(identifiers)|{s['id'] for s in d['sections']};files={f['path']:f for f in d['inventory']};refs=0
 if len(identifiers)!=len(set(identifiers)):errors.append('Duplicate node IDs')
 for n in d['nodes']:
  if n['parentId'] not in ids:errors.append('Missing parent: '+n['id'])
 for e in d['edges']:
  if e['source'] not in ids or e['target'] not in ids:errors.append('Missing edge endpoint: '+e['id'])
 def validate(value):
  nonlocal refs
  if isinstance(value,dict):
   if 'path' in value and 'line' in value:
    refs+=1;p=value['path'];a=value['line'];b=value.get('endLine',a)
    if p not in files or not 1<=a<=b<=max(1,files[p]['lines']):errors.append('Invalid span: '+p)
    if '/blob/' in value.get('url','') and '/blob/'+pin+'/' not in value['url']:errors.append('Unpinned reference: '+p)
   if 'nodeId' in value and value['nodeId'] not in ids:errors.append('Missing route node: '+value['nodeId'])
   for k,v in value.items():
    if k in ('nodeIds','symbolIds','primaryNodeIds'):errors.extend('Missing member: '+i for i in v if i not in ids)
    validate(v)
  elif isinstance(value,list):
   for v in value:validate(v)
 validate(d)
 if errors or d['coverage']['pythonParseErrors']:raise ValueError(json.dumps({'errors':errors,'pythonParseErrors':d['coverage']['pythonParseErrors']}))
 report={'ok':True,'errors':[],'sourceCommit':pin,'sourceTree':tree,'trackedFiles':len(files),'indexedFiles':len(files),'symbols':len(identifiers)-len(files),'nodes':len(identifiers),'sourceReferencesChecked':refs,'sourceTextFiles':len(texts),'sourceTextOmissions':omitted,'sourceBytesMatchGitBlobs':True,'pythonParseErrors':[],'staticOnly':True,'productCodeExecuted':False,'testsExecuted':False,'reconstruction':'Recreated extractor; annotations recovered from original published atlas; source independently retrieved and verified after workspace reset.','knownLimits':['Non-Python declarations are lexical declaration lines, not full bodies.','Import edges are static dependencies, not runtime calls.','Semantic routes and system groups are editorial interpretations.','Dynamic/unresolved imports and calls are not exhaustively indexed.','Historical CI records are not new test runs.']}
 return {'architecture.json':d,'source-texts.json':{'meta':{'sourceCommit':pin,'sourceTree':tree,'repository':d['meta']['repository'],'encoding':'utf-8','omitted':omitted},'files':texts},'validation.json':report,'inventory.json':d['inventory'],'coverage.json':d['coverage'],'sections.json':d['sections']}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repo',type=Path,required=True);parser.add_argument('--commit',required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--seed',type=Path,default=HERE.parent/'data/editorial-seed.json');args=parser.parse_args();seed=json.loads(args.seed.read_text(encoding='utf-8'))
 artifacts=generate(args.repo,args.commit,seed);args.output.mkdir(parents=True,exist_ok=True)
 for name,value in artifacts.items():(args.output/name).write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),default=lambda x:sorted(x) if isinstance(x,set) else str(x)),encoding='utf-8')
 manifest={name:{'bytes':(args.output/name).stat().st_size,'sha256':hashlib.sha256((args.output/name).read_bytes()).hexdigest()} for name in artifacts};(args.output/'artifact-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');print(json.dumps(artifacts['validation.json'],ensure_ascii=False))

if __name__=='__main__':main()
