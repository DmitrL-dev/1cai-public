from pathlib import Path
import argparse, ctypes as C, datetime, hashlib, json, os, subprocess, sys, uuid
from ctypes import wintypes as W
def absolute(value):
 assert type(value) is str and value
 p=Path(value)
 assert p.is_absolute() and len(p.drive)==2 and p.drive[1]==':' and not str(p).startswith('\\\\')
 return p
def pin(p):
 b=p.read_bytes();return {'path':str(p),'size_bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def read(r):
 p=Path(r['path']);assert p.resolve().is_relative_to(B.resolve()) or p.resolve().is_relative_to(S.resolve()) or p==Path(sys.executable) or p==Path(r'C:\Program Files\nodejs\node.exe');b=p.read_bytes();assert len(b)==r['size_bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'];return b
def put(p,v):
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 return pin(p)
def normalized_ref(r):
 return {**r,'path':str(Path(r['path']))}
ap=argparse.ArgumentParser()
ap.add_argument('--evidence-root',required=True)
ap.add_argument('--request',required=True)
ap.add_argument('--request-sha',required=True)
cli=ap.parse_args()
B=absolute(cli.evidence_root);assert B.is_dir()
rp=absolute(cli.request);assert rp.resolve().is_relative_to(B.resolve())
rb=rp.read_bytes();assert hashlib.sha256(rb).hexdigest()==cli.request_sha;rq=json.loads(rb)
assert rq['schema']=='rentgen-Root-public-Main-receiver-runtime-request/1'
assert str(absolute(rq['evidence_root']))==str(B)
S=absolute(rq['source_root']);assert S.is_dir()
assert not S.resolve().is_relative_to(B.resolve()) and not B.resolve().is_relative_to(S.resolve())
assert rq['Root_full_Source_read'] is True and rq['Root_fixture_runtime_admitted'] is True
assert set(rq['inputs'])=={'C','header','base_header','dll','node','parent','child'}
for r in list(rq['inputs'].values())+[rq['outer_helper'],rq['launcher'],rq['verifier']]:read(r)
assert pin(Path(__file__))==rq['outer_helper']
assert all(Path(rq[k]['path']).resolve().is_relative_to(S.resolve()) for k in ('outer_helper','launcher','verifier'))
assert all(Path(rq['inputs'][k]['path']).resolve().is_relative_to(S.resolve()) for k in ('C','header','base_header','parent','child'))
assert Path(rq['inputs']['dll']['path']).resolve().is_relative_to(B.resolve())
expected_sources={'C':rq['inputs']['C'],'receiver_H':rq['inputs']['header'],'original_H':rq['inputs']['base_header']}
expected_harness={k:rq[k] for k in ('outer_helper','launcher','verifier')}
assert type(rq['independent_Source_peers']) is list and 1<=len(rq['independent_Source_peers'])<=8
native_peer=harness_peer=False
for r in rq['independent_Source_peers']:
 peer=json.loads(read(r));assert peer['accepted'] is True
 native_peer=native_peer or peer.get('current_sources')==expected_sources
 harness_peer=harness_peer or peer.get('current_harness_sources')==expected_harness
assert native_peer and harness_peer
cr=json.loads(read(rq['compile_receipt']));assert cr['returncode']==0 and cr['timed_out'] is False and cr['ABI_matches'] is True
assert cr['DLL']==rq['inputs']['dll'] and cr['reviewed_sources']=={ 'C':rq['inputs']['C'],'receiver_H':rq['inputs']['header'],'original_H':rq['inputs']['base_header'] }
assert cr['actual_rld_abi']==[1,8,65536,8,8368,24,16,32,152,120,20624,40]
assert cr['actual_rwr_abi']==[1,8,32768,8,1472,24,184,152,16,1024,4096,2,16]
assert os.name=='nt' and sys.version_info[:3]==(3,11,9) and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize
pr=pin(Path(sys.executable));assert (pr['size_bytes'],pr['sha256'])==(103192,'5f7b89a612c9b8af1d6456cdfcd1dbe5ca630849e79aebced9bee9a6694952ec')
for k in ('launcher','verifier'):compile(read(rq[k]),rq[k]['path'],'exec')
d=B/('Root-Main-receiver-two-new-cases-'+uuid.uuid4().hex);d.mkdir()
# Root queries only its own current token. Native receiver rechecks actual SID.
k=C.WinDLL('kernel32',use_last_error=True);a=C.WinDLL('advapi32',use_last_error=True)
k.GetCurrentProcess.argtypes=[];k.GetCurrentProcess.restype=W.HANDLE
k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle.restype=W.BOOL
a.OpenProcessToken.argtypes=[W.HANDLE,W.DWORD,C.POINTER(W.HANDLE)];a.OpenProcessToken.restype=W.BOOL
a.GetTokenInformation.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.POINTER(W.DWORD)];a.GetTokenInformation.restype=W.BOOL
a.IsValidSid.argtypes=[C.c_void_p];a.IsValidSid.restype=W.BOOL
a.GetLengthSid.argtypes=[C.c_void_p];a.GetLengthSid.restype=W.DWORD
token=W.HANDLE();rawsid=None;native={'token_opened':False,'SID_copied':False,'token_close_attempted':False,'token_checked_closed':False,'query_error':None}
try:
 assert a.OpenProcessToken(k.GetCurrentProcess(),8,C.byref(token));native['token_opened']=True
 needed=W.DWORD();ok=a.GetTokenInformation(token,1,None,0,C.byref(needed));assert not ok and C.get_last_error()==122 and 8<=needed.value<=4096
 buf=C.create_string_buffer(needed.value);assert a.GetTokenInformation(token,1,buf,len(buf),C.byref(needed))
 sidp=C.cast(buf,C.POINTER(C.c_void_p))[0];assert sidp and a.IsValidSid(sidp)
 size=a.GetLengthSid(sidp);assert 8<=size<=68;rawsid=C.string_at(sidp,size)
 assert rawsid[0]==1 and rawsid[1]<=15 and len(rawsid)==8+4*rawsid[1];native['SID_copied']=True
except BaseException as e:native['query_error']=type(e).__name__+': '+str(e)
finally:
 if native['token_opened']:
  native['token_close_attempted']=True;native['token_checked_closed']=bool(k.CloseHandle(token));native['token_close_error']=0 if native['token_checked_closed'] else C.get_last_error()
sr=put(d/'Root-actual-own-token-SID-copy-and-checked-close.json',native)
assert native['query_error'] is None and native['SID_copied'] and native['token_checked_closed']
sp=d/'Root-actual-current-user-SID.bin'
with sp.open('xb') as f:f.write(rawsid);f.flush();os.fsync(f.fileno())
sidref=pin(sp);seeds={};cookies=set()
for i,name in enumerate(('expected_parent_slot0','expected_child_slot1'),1):
 cd=d/name;cd.mkdir();cookie=int.from_bytes(os.urandom(8),'little') or 1
 while cookie in cookies:cookie=int.from_bytes(os.urandom(8),'little') or 1
 cookies.add(cookie)
 seeds[name]=put(cd/'Root-case-seed.json',{'schema':'rentgen-Root-Main-receiver-case-seed/1','case':name,'working_directory':str(cd),'generation':i,'session_cookie':cookie,'receiver':{'expected_slot':i-1,'sid_ref':sidref,'instance':uuid.uuid4().hex,'nonce':uuid.uuid4().hex,'run':'Root-'+uuid.uuid4().hex,'source_copy_pin':rq['inputs']['parent']['sha256']}})
ad=put(d/'Root-two-cases-execution-admission.json',{'schema':'rentgen-Root-Main-receiver-two-hosts-execution-admission/2','Root_execution_admitted':True,'evidence_root':str(B),'outer_helper':normalized_ref(rq['outer_helper']),'launcher':normalized_ref(rq['launcher']),'verifier':normalized_ref(rq['verifier']),'python':pr,'inputs':{name:normalized_ref(r) for name,r in rq['inputs'].items()},'case_seeds':seeds,'additional_frozen_inputs':[sidref,sr,normalized_ref(rq['compile_receipt']),pin(rp),normalized_ref(rq['outer_helper'])]+[normalized_ref(r) for r in rq['independent_Source_peers']],'owned_directory':str(d)})
argv=[sys.executable,'-I','-S','-B','-X','utf8','-u',rq['launcher']['path'],'--evidence-root',str(B),'--admission',ad['path'],'--admission-size',str(ad['size_bytes']),'--admission-sha',ad['sha256']]
so=d/'Root-launcher.stdout';se=d/'Root-launcher.stderr'
with so.open('xb') as x,se.open('xb') as z:
 try:p=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=x,stderr=z,timeout=45,cwd=str(d),close_fds=True,check=False);rc=p.returncode;timed=False
 except subprocess.TimeoutExpired:rc=None;timed=True
rr=put(d/'Root-outer-two-new-hosts-execution-before-qualification.json',{'schema':'rentgen-Root-Main-receiver-two-new-hosts-outer-actual/1','recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'Root_request':pin(rp),'admission':ad,'argv':argv,'returncode':rc,'timed_out':timed,'stdout':pin(so),'stderr':pin(se),'EditorRole':False,'OwnerIPC':False,'runtime_qualified':False,'release':False,'production_deployment':False})
assert so.stat().st_size<=32768 and se.stat().st_size<=32768
print(json.dumps({'receipt':rr,'returncode':rc,'timed_out':timed,'stdout_lines':so.read_text('utf-8').splitlines(),'stderr_text':se.read_text('utf-8',errors='replace')}),flush=True)
