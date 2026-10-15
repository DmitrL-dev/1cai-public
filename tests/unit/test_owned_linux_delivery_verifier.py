"""Pure archive/installed-RECORD controls; no native Linux qualification on Mac."""
import asyncio
import base64
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
from threading import Event, Thread
import zipfile

import pytest

ROOT=Path(__file__).resolve().parents[2]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


subject=module("owned_delivery_test","scripts/verification/verify_owned_linux_delivery.py")
probe=module("owned_sdk_probe_test","scripts/verification/owned_linux_sdk_probe.py")
posix_files=pytest.mark.skipif(os.name!="posix",reason="Actual POSIX no-follow descriptor/namespace control")
posix_pipe=pytest.mark.skipif(os.name!="posix",reason="Actual POSIX nonblocking pipe drain control")


def digest(raw):return base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode()


def record(files,self_name):
    stream=io.StringIO();writer=csv.writer(stream,lineterminator="\n")
    for name,raw in sorted(files.items()):writer.writerow([name,"" if name==self_name else "sha256="+digest(raw),"" if name==self_name else str(len(raw))])
    return stream.getvalue().encode()


def wheel(name="demo",package="demo_pkg",extra=None):
    metadata=name+"-1.0.dist-info"
    files={package+"/__init__.py":b"VALUE=1\n",metadata+"/METADATA":("Metadata-Version: 2.1\nName: "+name+"\nVersion: 1.0\n").encode(),
        metadata+"/WHEEL":b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        metadata+"/entry_points.txt":("[console_scripts]\n"+name+" = "+package+":main\n").encode()}
    files.update(extra or {});files[metadata+"/RECORD"]=b"";files[metadata+"/RECORD"]=record(files,metadata+"/RECORD")
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w",zipfile.ZIP_DEFLATED) as archive:
        for path,raw in files.items():archive.writestr(path,raw)
    return stream.getvalue(),files


def test_original_wheel_record_and_metadata_derive_complete_owned_inventory():
    raw,files=wheel();expected=subject.wheel_expectations({"demo-1.0-py3-none-any.whl":raw})
    assert set(expected["files"])==set(files)
    assert expected["distributions"][0]["members"]==sorted(files)
    assert expected["scripts"]=={"demo":"demo_pkg:main"}


@pytest.mark.parametrize("path",["evil.pth","sitecustomize.py","usercustomize.py","demo.data/purelib/evil.py","../evil.py","/absolute.py"])
def test_unexecuted_wheel_startup_relocation_and_traversal_payloads_are_refused(path):
    raw,_=wheel(extra={path:b"raise RuntimeError('must never execute')"})
    with pytest.raises(subject.base.VerificationError):subject.wheel_expectations({"demo.whl":raw})


def test_forged_original_record_cannot_bootstrap_expected_installation():
    raw,files=wheel();name="demo-1.0.dist-info/RECORD";files[name]=files[name].replace(b"sha256=",b"sha255=",1)
    target=io.BytesIO()
    with zipfile.ZipFile(target,"w") as archive:
        for path,data in files.items():archive.writestr(path,data)
    with pytest.raises(subject.base.VerificationError,match="RECORD digest"):subject.wheel_expectations({"demo.whl":target.getvalue()})


def test_forged_zip_directory_is_refused_before_zipfile_allocation(monkeypatch):
    raw,_=wheel();raw=bytearray(raw);position=raw.rfind(b"PK\x05\x06")
    struct.pack_into("<HH",raw,position+8,10001,10001)
    monkeypatch.setattr(subject.zipfile,"ZipFile",lambda *a:pytest.fail("Unbounded directory passed to ZipFile"))
    with pytest.raises(subject.base.VerificationError,match="directory bound"):subject.wheel_expectations({"demo.whl":bytes(raw)})


def test_cross_wheel_case_alias_cannot_own_same_runtime_namespace():
    first,_=wheel("first","Module");second,_=wheel("second","module")
    with pytest.raises(subject.base.VerificationError,match="collision"):
        subject.wheel_expectations({"first.whl":first,"second.whl":second})


@pytest.mark.parametrize("which",["archive","manifest"])
def test_both_external_hashes_precede_untrusted_candidate_schema(which):
    class Never:
        def parse_json(self,*args):pytest.fail("Unpinned manifest parsed")
    archive=b"archive";manifest=b"manifest";hashes=[subject.base.sha(archive),subject.base.sha(manifest)]
    hashes[which=="manifest"]="0"*64
    with pytest.raises(subject.base.VerificationError,match="External candidate hash"):
        subject.validate_external(archive,manifest,*hashes,Never())


@pytest.mark.skipif(sys.platform=="linux",reason="Actual unsupported non-Linux host before candidate IO")
def test_actual_unsupported_host_cannot_read_inputs_or_create_output(tmp_path,monkeypatch):
    monkeypatch.setattr(subject.base,"read_regular",lambda *a:pytest.fail("Unsupported host read candidate"))
    output=tmp_path/"not-created"
    with pytest.raises(subject.base.VerificationError,match="actual Linux"):
        subject.verify("missing","missing","0"*64,"0"*64,output,"0.1.0.dev20","1"*40,"2"*64,"3"*64)
    assert not output.exists()


def installed(tmp_path,two=False):
    prefix=tmp_path/"venv";site=prefix/"lib/python3.11/site-packages";site.mkdir(parents=True)
    (prefix/"bin").mkdir();wheels={};original={};wrappers={}
    for name in (["alpha","beta"] if two else ["demo"]):
        raw,files=wheel(name,name+"_pkg");wheels[name+".whl"]=raw;original[name]=files
        for relative,data in files.items():
            path=site/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        wrappers[name]=("#!/synthetic/venv/python\nfrom "+name+"_pkg import main\nmain()\n").encode()
        (prefix/"bin"/name).write_bytes(wrappers[name])
        files=dict(files);files[name+"-1.0.dist-info/INSTALLER"]=b"pip\n";files[name+"-1.0.dist-info/REQUESTED"]=b""
        files["../../../bin/"+name]=wrappers[name]
        for relative in (name+"-1.0.dist-info/INSTALLER",name+"-1.0.dist-info/REQUESTED"):(site/relative).write_bytes(files[relative])
        (site/(name+"-1.0.dist-info/RECORD")).write_bytes(record(files,name+"-1.0.dist-info/RECORD"))
    expected=subject.wheel_expectations(wheels)
    return prefix,site,expected,{},wrappers


def rewrite_record(site,root,change):
    path=site/root/"RECORD";rows=list(csv.reader(io.StringIO(path.read_text())));rows=change(rows)
    output=io.StringIO();csv.writer(output,lineterminator="\n").writerows(rows);path.write_text(output.getvalue())


@posix_files
def test_constructed_installation_audit_verifies_payload_record_and_regenerated_wrapper(tmp_path):
    args=installed(tmp_path);result=probe.audit(*args)
    assert result["distributions"]==1 and len(result["verified_inventory_sha256"])==64


@posix_files
def test_installed_self_reported_record_cannot_authorize_changed_console_code(tmp_path):
    prefix,site,expected,baseline,wrappers=installed(tmp_path)
    bad=b"raise RuntimeError('changed wrapper')\n";(prefix/"bin/demo").write_bytes(bad)
    rewrite_record(site,"demo-1.0.dist-info",lambda rows:[[r[0],"sha256="+digest(bad),str(len(bad))] if r[0]=="../../../bin/demo" else r for r in rows])
    with pytest.raises(probe.ProbeFailure,match="console script"):probe.audit(prefix,site,expected,baseline,wrappers)


@pytest.mark.parametrize("defect",["omitted_package","foreign_package","new_startup","new_directory","new_direct_url","unclaimed_installer","alias"])
@posix_files
def test_installed_record_namespace_and_distribution_ownership_are_not_self_authorizing(tmp_path,defect):
    prefix,site,expected,baseline,wrappers=installed(tmp_path,two=True)
    root="alpha-1.0.dist-info"
    if defect=="omitted_package":rewrite_record(site,root,lambda rows:[r for r in rows if r[0]!="alpha_pkg/__init__.py"])
    elif defect=="foreign_package":
        raw=(site/"beta_pkg/__init__.py").read_bytes();rewrite_record(site,root,lambda rows:rows+[["beta_pkg/__init__.py","sha256="+digest(raw),str(len(raw))]])
    elif defect=="new_startup":(site/"evil.pth").write_bytes(b"must not execute")
    elif defect=="new_directory":(site/"foreign_namespace").mkdir()
    elif defect=="new_direct_url":
        raw=b"{}";(site/root/"direct_url.json").write_bytes(raw)
        rewrite_record(site,root,lambda rows:rows+[[root+"/direct_url.json","sha256="+digest(raw),str(len(raw))]])
    elif defect=="unclaimed_installer":
        (site/root/"INSTALLER").write_bytes(b"foreign installer\n")
        rewrite_record(site,root,lambda rows:[row for row in rows if row[0]!=root+"/INSTALLER"])
    else:(site/"alias").symlink_to(site/"alpha_pkg",target_is_directory=True)
    with pytest.raises(probe.ProbeFailure):probe.audit(prefix,site,expected,baseline,wrappers)


@posix_files
def test_bootstrap_bytes_are_bound_independently_of_sdk_metadata(tmp_path):
    prefix,site,expected,_,wrappers=installed(tmp_path)
    target=site/"bootstrap.py";target.write_bytes(b"original")
    baseline={"bootstrap.py":dict(sha256=probe.sha(b"original"),size_bytes=8)};target.write_bytes(b"changed!")
    with pytest.raises(probe.ProbeFailure,match="Bootstrap/Core"):probe.audit(prefix,site,expected,baseline,wrappers)


def test_sdk_stdout_cap_refuses_bytes_before_sdk_parser_and_keeps_forwarding_exact():
    class Stream:
        def __init__(self,chunks):self.chunks=iter(chunks);self.requests=[]
        async def receive(self,n):self.requests.append(n);return next(self.chunks)
    async def scenario():
        flag=Event();kills=[];stream=Stream([b"abc",b"d"]);bounded=probe.BoundedReceive(stream,flag,lambda:kills.append(True),maximum=3)
        assert await bounded.receive(10**9)==b"abc"
        with pytest.raises(probe.ProbeFailure,match="output exceeded"):await bounded.receive()
        assert flag.is_set() and kills==[True] and max(stream.requests)<=65536
    asyncio.run(scenario())


@posix_pipe
def test_private_stderr_drain_is_bounded_discards_bytes_and_terminates_once():
    read_fd,write_fd=os.pipe();overflow=Event();stop=Event();kills=[]
    thread=Thread(target=probe.drain_stderr,args=(read_fd,overflow,lambda:kills.append(True),stop,1024));thread.start()
    try:
        for _ in range(4):os.write(write_fd,b"x"*4096)
    finally:os.close(write_fd)
    thread.join(timeout=3)
    assert not thread.is_alive() and overflow.is_set() and kills==[True]


@posix_pipe
def test_forced_stderr_stop_is_cleanup_not_a_verified_eof():
    read_fd,write_fd=os.pipe();overflow=Event();stop=Event();stop.set();result={}
    try:probe.drain_stderr(read_fd,overflow,lambda:None,stop,result=result)
    finally:os.close(write_fd)
    assert result.get("eof") is not True


@posix_pipe
def test_stderr_cleanup_failure_is_recorded_without_unhandled_thread_output():
    read_fd,write_fd=os.pipe();overflow=Event();stop=Event();result={}
    def unavailable():raise OSError("owned signal failed")
    thread=Thread(target=probe.drain_stderr,args=(read_fd,overflow,unavailable,stop,1,result));thread.start()
    try:os.write(write_fd,b"over limit")
    finally:os.close(write_fd)
    thread.join(timeout=3)
    assert not thread.is_alive() and overflow.is_set() and result.get("error")=="OSError"
    assert result.get("cleanup_error")=="OSError" and result.get("eof") is not True


def test_failed_pidfd_acquisition_reaps_the_exact_already_owned_subprocess(monkeypatch):
    # A real host process validates failure cleanup; it does not exercise Linux
    # pidfds or qualify the SDK server route on this host.
    import anyio
    def unavailable(pid):raise OSError("pidfd resource unavailable")
    monkeypatch.setattr(probe.os,"pidfd_open",unavailable,raising=False)
    async def scenario():
        process=await anyio.open_process([sys.executable,"-I","-c","import time;time.sleep(60)"],stdout=-1,stderr=-1)
        try:
            with pytest.raises(OSError,match="pidfd resource"):await probe.acquire_pidfd(process)
            assert process.returncode is not None
            for stream in (process.stdout,process.stderr):
                with pytest.raises(anyio.ClosedResourceError):await stream.receive()
        finally:
            if process.returncode is None:process.kill();await process.wait()
            await process.aclose()
    anyio.run(scenario)


def test_observer_identity_mismatch_closes_descriptor_without_signalling_it(monkeypatch):
    # The injected pipe represents an untrusted acquired handle. This is a
    # cleanup fault control; it does not pretend the host supports pidfds.
    import anyio
    async def scenario():
        process=await anyio.open_process([sys.executable,"-I","-c","import time;time.sleep(60)"],stdout=-1,stderr=-1)
        read_fd,write_fd=os.pipe()
        monkeypatch.setattr(probe.os,"pidfd_open",lambda pid:read_fd,raising=False)
        monkeypatch.setattr(probe,"process_stat",lambda pid:("S",os.getpid()+1,123))
        try:
            with pytest.raises(probe.ProbeFailure,match="identity changed"):await probe.acquire_pidfd(process)
            with pytest.raises(OSError):os.fstat(read_fd)
            assert process.returncode is not None
            for stream in (process.stdout,process.stderr):
                with pytest.raises(anyio.ClosedResourceError):await stream.receive()
        finally:
            os.close(write_fd)
            if process.returncode is None:process.kill();await process.wait()
            await process.aclose()
    anyio.run(scenario)


@pytest.mark.skipif(os.name!="posix",reason="Actual host POSIX SDK process-group cleanup contract")
def test_sdk_process_proxy_retains_real_shutdown_escalation_contract():
    import anyio
    import mcp.client.stdio as transport
    from anyio.abc import Process
    async def scenario():
        code="import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print('ready',flush=True);time.sleep(60)"
        process=await anyio.open_process([sys.executable,"-I","-c",code],stdout=-1,stderr=-1,start_new_session=True)
        wrapped=probe.bounded_process(process,Event(),lambda:None)
        try:
            with anyio.fail_after(5):assert await wrapped.stdout.receive()==b"ready\n"
            assert isinstance(wrapped,Process) and wrapped.pid==process.pid
            # Match stdio_client: escalation runs inside the process resource,
            # whose exit then waits/reaps and closes its pipe transports.
            with anyio.fail_after(5):
                async with wrapped:await transport._terminate_process_tree(wrapped,timeout_seconds=.02)
            assert wrapped.returncode is not None
        finally:
            if process.returncode is None:process.kill();await process.wait()
            await wrapped.aclose()
    anyio.run(scenario)


@pytest.mark.skipif(sys.platform!="linux",reason="Actual Linux pidfd/direct-child identity control")
def test_native_linux_pidfd_acquisition_binds_the_actual_live_direct_child():
    import anyio
    async def scenario():
        process=await anyio.open_process([sys.executable,"-I","-c","import time;time.sleep(60)"],stdout=-1,stderr=-1)
        descriptor=None
        try:
            descriptor=await probe.acquire_pidfd(process)
            status=probe.process_stat(process.pid)
            assert status and status[1]==os.getpid() and process.returncode is None
            import signal
            signal.pidfd_send_signal(descriptor,signal.SIGKILL)
            with anyio.fail_after(5):await process.wait()
            assert process.returncode is not None
        finally:
            if descriptor is not None:os.close(descriptor)
            if process.returncode is None:process.kill();await process.wait()
            await process.aclose()
    anyio.run(scenario)


@pytest.mark.skipif(sys.platform!="linux",reason="Actual Linux prctl/PDEATHSIG parent-death control")
def test_native_linux_sdk_lifetime_guard_kills_owned_child_when_probe_parent_dies(tmp_path):
    # A private supervisor becomes subreaper so this deliberate parent-death
    # scenario can reap both controlled processes without changing pytest.
    parent_code="""
import json,os,subprocess,sys,time
launch=json.loads(sys.stdin.readline(8193))
child=subprocess.Popen([sys.executable,'-I','-B','-c',launch],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
assert child.stdout.readline(64)==b'ready\\n'
print(child.pid,flush=True)
time.sleep(60)
"""
    supervisor="""
import ctypes,importlib.util,json,os,select,signal,subprocess,sys,time
spec=importlib.util.spec_from_file_location('kernel_control_only',sys.argv[1]);probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
parent=subprocess.Popen([sys.executable,'-I','-B','-c',sys.argv[2]],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
descriptor=None;child=None;reaped=False
try:
    launch=probe.parent_lifetime_guard(parent.pid)+"print('ready',flush=True);import time;time.sleep(60)"
    parent.stdin.write(json.dumps(launch).encode()+b'\\n');parent.stdin.close()
    child=int(parent.stdout.readline(64));status=probe.process_stat(child)
    assert status and status[1]==parent.pid
    descriptor=os.pidfd_open(child);current=probe.process_stat(child)
    assert current and current[1:]==status[1:] and parent.poll() is None
    parent.kill();parent.wait(timeout=5)
    assert select.select([descriptor],[],[],5)[0]
    end=time.monotonic()+5
    while True:
        pid,exit_status=os.waitpid(child,os.WNOHANG)
        if pid:break
        assert time.monotonic()<end
        time.sleep(.01)
    reaped=True
    assert os.WIFSIGNALED(exit_status) and os.WTERMSIG(exit_status)==signal.SIGKILL
    print(json.dumps({'parent_reaped':True,'child_reaped':True,'parent_death_signal':True}))
finally:
    if descriptor is not None:
        if not reaped:
            try:signal.pidfd_send_signal(descriptor,signal.SIGKILL)
            except ProcessLookupError:pass
        os.close(descriptor)
    if parent.poll() is None:parent.kill();parent.wait(timeout=5)
    if child is not None and not reaped:
        end=time.monotonic()+5
        while time.monotonic()<end:
            try:pid,_=os.waitpid(child,os.WNOHANG)
            except ChildProcessError:break
            if pid:break
            time.sleep(.01)
    parent.stdout.close()
"""
    code,out,error=subject.base.run([sys.executable,"-I","-B","-c",supervisor,
        ROOT/"scripts/verification/owned_linux_sdk_probe.py",parent_code],cwd=tmp_path,timeout=20,stdout_limit=4096,stderr_limit=4096)
    assert code==0 and not error and json.loads(out)==dict(parent_reaped=True,child_reaped=True,parent_death_signal=True)


@pytest.mark.skipif(sys.version_info[:2]!=(3,11) or os.name!="posix",reason="Actual host CPython3.11 POSIX pip RECORD codec")
def test_real_host_offline_pip_record_and_wrapper_codec_with_constructed_pure_wheel(tmp_path):
    # This executes host pip against one synthetic pure wheel. It is a RECORD
    # codec control, not the Linux/SDK/native-extension acceptance route.
    environment=tmp_path/"environment"
    code,_,_=subject.base.run([sys.executable,"-I","-m","venv",environment],cwd=tmp_path,timeout=90)
    assert code==0
    python=environment/"bin/python";site=environment/"lib/python3.11/site-packages"
    baseline=subject.site_snapshot(site)
    wheelhouse=tmp_path/"wheelhouse";wheelhouse.mkdir()
    raw,_=wheel();(wheelhouse/"demo-1.0-py3-none-any.whl").write_bytes(raw)
    lock=tmp_path/"lock.txt";lock.write_text("demo==1.0 --hash=sha256:"+subject.base.sha(raw)+"\n")
    code,_,_=subject.base.run(subject.installation_arguments(python,wheelhouse,lock),cwd=tmp_path,timeout=60)
    assert code==0
    config=tmp_path/"inputs.json";config.write_text(json.dumps(dict(prefix=str(environment),site=str(site),baseline=baseline,
        expected=subject.wheel_expectations({"demo-1.0-py3-none-any.whl":raw}),helper=str(ROOT/"scripts/verification/owned_linux_sdk_probe.py"))))
    script="""
import importlib.util,json,sys
from pathlib import Path
from pip._vendor.distlib.scripts import ScriptMaker
c=json.loads(Path(sys.argv[1]).read_text());p=Path(c['prefix']);target=p.parent/'expected';target.mkdir()
m=ScriptMaker(None,str(target));m.executable=sys.executable;m.clobber=True;m.variants={''};m.set_mode=True
m.make_multiple([name+' = '+value for name,value in c['expected']['scripts'].items()])
s=importlib.util.spec_from_file_location('codec_only',c['helper']);h=importlib.util.module_from_spec(s);s.loader.exec_module(h)
r=h.audit(p,Path(c['site']),c['expected'],c['baseline'],{name:(target/name).read_bytes() for name in c['expected']['scripts']})
print(json.dumps({'distributions':r['distributions'],'bound':len(r['verified_inventory_sha256'])==64}))
"""
    code,out,error=subject.base.run([python,"-I","-B","-c",script,config],cwd=tmp_path,timeout=30)
    assert code==0 and not error and json.loads(out)==dict(distributions=1,bound=True)
