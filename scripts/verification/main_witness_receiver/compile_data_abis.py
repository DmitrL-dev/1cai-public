from pathlib import Path
import argparse,ctypes,datetime,hashlib,json,os,subprocess,sys,uuid
def absolute(value):
 assert type(value) is str and value
 p=Path(value)
 assert p.is_absolute() and len(p.drive)==2 and p.drive[1]==':' and not str(p).startswith('\\\\')
 return p
def pin(p):
 b=p.read_bytes();return {'path':str(p),'size_bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def read(r):
 p=absolute(r['path']);assert p.resolve().is_relative_to(B.resolve()) or r in ad['sources'].values();b=p.read_bytes();assert len(b)==r['size_bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'];return b
def save(p,v):
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 return pin(p)
parser=argparse.ArgumentParser()
parser.add_argument('--evidence-root',required=True)
parser.add_argument('--admission',required=True)
parser.add_argument('--admission-sha',required=True)
cli=parser.parse_args()
B=absolute(cli.evidence_root);assert B.is_dir()
ap=absolute(cli.admission);assert ap.resolve().is_relative_to(B.resolve())
ab=ap.read_bytes();assert hashlib.sha256(ab).hexdigest()==cli.admission_sha;ad=json.loads(ab)
assert ad['schema']=='rentgen-Root-public-Main-receiver-compile-dataABI-admission/1'
assert str(absolute(ad['evidence_root']))==str(B)
assert pin(Path(__file__))==ad['compiler_helper']
assert ad['Root_full_Source_read'] is True and ad['Root_compile_admitted'] is True and ad['Root_data_ABI_only_admitted'] is True and ad['fixture_runtime_admitted'] is False
assert absolute(ad['independent_Source_peer']['path']).resolve().is_relative_to(B.resolve())
peer=json.loads(read(ad['independent_Source_peer']));assert peer['accepted'] is True and peer['current_sources']==ad['sources']
assert ad['expected_rld_abi']==[1,8,65536,8,8368,24,16,32,152,120,20624,40]
assert 1<=len(ad['expected_rwr_abi'])<=32 and all(type(x)is int and 0<=x<=0xffffffff for x in ad['expected_rwr_abi'])
assert set(ad['sources'])=={'C','receiver_H','original_H'}
snapshots={k:read(v) for k,v in ad['sources'].items()}
assert ad['sources']['original_H']['sha256']=='b14f94f5674ec55b2f8fc15900bb63e5b466ce21406042c6c204bdefae84328c'
gcc=Path(r'C:\mingw64\bin\gcc.exe');gp=pin(gcc);assert (gp['size_bytes'],gp['sha256'])==(3020288,'690d171db384af0f69002374a7fc4755128ee82c688d22818bd981f869a65890')
d=B/('Root-reviewed-Main-receiver-compile-'+uuid.uuid4().hex);d.mkdir();frozen={}
for k,b in snapshots.items():
 p=d/Path(ad['sources'][k]['path']).name
 with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 frozen[k]=pin(p)
assert len({r['path'] for r in frozen.values()})==3
dl=d/'root_main_receiver.dll';so=d/'gcc.stdout';se=d/'gcc.stderr';argv=[str(gcc),'-std=c11','-Wall','-Wextra','-Werror','-O2','-shared',frozen['C']['path'],'-o',str(dl),'-lbcrypt','-ladvapi32']
env=os.environ.copy();env['PATH']=str(gcc.parent)+os.pathsep+env.get('PATH','')
with so.open('xb') as a,se.open('xb') as z:
 try:p=subprocess.run(argv,cwd=str(d),env=env,stdin=subprocess.DEVNULL,stdout=a,stderr=z,timeout=45,check=False);rc=p.returncode;to=False
 except subprocess.TimeoutExpired:rc=None;to=True
r={'schema':'rentgen-Root-reviewed-Main-receiver-compile-and-data-ABI-only/1','recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'Root_admission':pin(ap),'reviewed_sources':ad['sources'],'source_peer':ad['independent_Source_peer'],'compile_input_snapshots':frozen,'compiler':gp,'argv':argv,'returncode':rc,'timed_out':to,'stdout':pin(so),'stderr':pin(se),'DLL':pin(dl) if dl.exists() else None,'expected_rld_abi':ad['expected_rld_abi'],'expected_rwr_abi':ad['expected_rwr_abi'],'actual_rld_abi':None,'actual_rwr_abi':None,'fixture_runtime_executed':False,'init_register_run_submit_called':False,'EditorRole':False,'OwnerIPC':False,'daily_model_task_accepted':False,'new_tag_release_admitted':False,'full_product_ready':False,'production_deployment':False}
if rc==0:
 try:
  lib=ctypes.WinDLL(str(dl));out1=(ctypes.c_uint32*len(ad['expected_rld_abi']))();out2=(ctypes.c_uint32*32)()
  for name,out in (('rld_abi',out1),('rwr_abi',out2)):
   fn=getattr(lib,name);fn.argtypes=[ctypes.POINTER(ctypes.c_uint32)];fn.restype=None;fn(out)
  raw2=list(out2);n2=len(ad['expected_rwr_abi']);r['actual_rld_abi']=list(out1);r['actual_rwr_abi_raw32']=raw2;r['actual_rwr_abi']=raw2[:n2];r['ABI_matches']=list(out1)==ad['expected_rld_abi'] and raw2[:n2]==ad['expected_rwr_abi'] and all(x==0 for x in raw2[n2:])
 except Exception as e:r['data_ABI_error']=type(e).__name__+': '+str(e)
rr=save(d/'Root-actual-compile-and-two-data-ABIs-before-qualification.json',r)
print(json.dumps({'receipt':rr,'returncode':rc,'DLL':r['DLL'],'stderr':r['stderr'],'actual_rld_abi':r['actual_rld_abi'],'actual_rwr_abi':r['actual_rwr_abi']}),flush=True)
assert rc==0 and r.get('ABI_matches') is True,'Actual compile/data ABI evidence retained before assertion; no runtime qualified'
