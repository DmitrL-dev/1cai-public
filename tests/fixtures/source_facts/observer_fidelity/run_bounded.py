"""Execute only the fixed synthetic observers, with owned exception-safe cleanup."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

CAPS=('CapInh','CapPrm','CapEff','CapAmb')
STOP_SIGNAL=0

def stop_requested(signum, frame):
    global STOP_SIGNAL
    STOP_SIGNAL=signum


def zero_capability_receipt():
    fields=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    uid=list(map(int,fields['Uid'].split()));gid=list(map(int,fields['Gid'].split()))
    if len(uid)!=4 or len(gid)!=4 or not all(x==os.getuid()!=0 for x in uid) or not all(x==os.getgid()!=0 for x in gid):
        raise RuntimeError('unexpected non-root process identity')
    if any(int(fields[k],16) for k in CAPS) or int(fields['NoNewPrivs'])!=1:
        raise RuntimeError('zero-capability no-new-privileges requirement failed')
    return {'pid':os.getpid(),'parent_pid':os.getppid(),'uid':uid,'gid':gid,
            'groups':list(map(int,fields['Groups'].split())),
            'capabilities':{k:fields[k].strip() for k in (*CAPS,'CapBnd')},'no_new_privs':1}


def write_results(root,results):
    temporary=root/'run-results.json.tmp'
    temporary.write_text(json.dumps(results,indent=2)+'\n')
    temporary.replace(root/'run-results.json')


def cleanup_owned(child):
    """The sole session anchor stays unreaped until any group signal is sent."""
    errors=[];reaped=[];empty=False
    if child is not None:
        try:
            if child.poll() is None:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            child.wait(timeout=5)
        except Exception as error:
            errors.append(type(error).__name__)
            try:
                child.kill()  # Popen checks the exact still-owned direct child.
                child.wait(timeout=1)
            except Exception as final:errors.append(type(final).__name__)
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        try:pid,code=os.waitpid(-1,os.WNOHANG)
        except ChildProcessError:empty=True;break
        except InterruptedError:continue
        except Exception as error:errors.append(type(error).__name__);break
        if pid:reaped.append([pid,code])
        else:time.sleep(.01)
    return {'cleanup_empty':empty,'adopted_reaped':reaped,'cleanup_errors':errors}


def main():
    if len(sys.argv)!=2:raise SystemExit('one disposable evidence directory required')
    root=Path(sys.argv[1]).resolve()
    if not root.is_dir():raise RuntimeError('missing prepared directory')
    try:os.waitid(os.P_ALL,0,os.WEXITED|os.WNOHANG|os.WNOWAIT)
    except ChildProcessError:pass
    else:raise RuntimeError('preexisting child prevents scoped ownership')
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(36,1,0,0,0)!=0 or libc.prctl(38,1,0,0,0)!=0:
        raise RuntimeError('scoped subreaper/no-new-privileges unavailable')
    controller=zero_capability_receipt()
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop_requested)
    (root/'synthetic-home').mkdir(exist_ok=True)
    results=[]
    for version in ('6.8','6.12'):
        if STOP_SIGNAL:break
        binary=root/f'strace-{version}/src/strace';parent=os.getpid()
        command=[str(binary),'--kill-on-exit','-f','-q','-ttt','-yy','-s','256','-o',str(root/f'trace-{version}.log'),
                 '--',str(root/'exit-race-probe'),str(root/'synthetic-stat-target')]
        def bounds():
            # If the controller is hard-killed, kill this tracer. EXITKILL then
            # kills its tracees. Check the parent-death setup race explicitly.
            if libc.prctl(1,signal.SIGKILL,0,0,0)!=0 or os.getppid()!=parent:os._exit(125)
            pdeath=ctypes.c_int()
            if libc.prctl(2,ctypes.byref(pdeath),0,0,0)!=0 or pdeath.value!=signal.SIGKILL:os._exit(125)
            resource.setrlimit(resource.RLIMIT_FSIZE,(32*1024*1024,32*1024*1024))
            resource.setrlimit(resource.RLIMIT_CORE,(0,0))
            resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
            resource.setrlimit(resource.RLIMIT_CPU,(25,25))
            receipt=zero_capability_receipt();receipt['parent_death_signal']=pdeath.value
            (root/f'preexec-capabilities-{version}.json').write_text(json.dumps(receipt)+'\n')
            if os.getppid()!=parent:os._exit(125)
        started=time.monotonic();child=None;timed_out=False;failure=None
        cleanup={'cleanup_empty':False,'adopted_reaped':[],'cleanup_errors':[]}
        try:
            with (root/f'ledger-{version}.log').open('wb') as err,(root/f'probe-{version}.stdout').open('wb') as out:
                child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True,preexec_fn=bounds,
                                       env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C','HOME':str(root/'synthetic-home')})
                while child.poll() is None:
                    if STOP_SIGNAL:raise InterruptedError('controller stop requested')
                    left=30-(time.monotonic()-started)
                    if left<=0:timed_out=True;raise TimeoutError('observer wall limit')
                    try:child.wait(timeout=min(.1,left))
                    except subprocess.TimeoutExpired:pass
        except Exception as error:failure=type(error).__name__
        finally:
            cleanup=cleanup_owned(child)
            result={'version':version,'exit':None if child is None else child.returncode,'timeout':timed_out,'interrupted':bool(STOP_SIGNAL),
                    'failure':failure,'seconds':time.monotonic()-started,**cleanup,'command':command,
                    'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'controller':controller,'instrumented':True}
            results.append(result);write_results(root,results);print(json.dumps(result),flush=True)
        if not cleanup['cleanup_empty'] or cleanup['cleanup_errors'] or STOP_SIGNAL:break
    if len(results)!=2 or any(r['exit']!=0 or r['timeout'] or r['interrupted'] or r['failure'] or not r['cleanup_empty'] or r['cleanup_errors'] for r in results):
        raise SystemExit(2)

if __name__=='__main__':main()
