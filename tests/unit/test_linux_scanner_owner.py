"""Real Linux fixed-scanner process qualification, separate from public capture."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import struct
import subprocess
import sys
import threading
import time

import pytest

from rentgen_core import _linux_scanner as module
from rentgen_core._linux_scanner import LinuxScannerLimits, open_linux_scanner
from rentgen_core._posix_source_tree import open_directory
from rentgen_core.errors import CoreError

ROOT = Path(__file__).resolve().parents[2]
native = pytest.mark.skipif(sys.platform != "linux" or platform.machine() != "x86_64", reason="Actual Linux/amd64 owned scanner, seccomp and sealed exec")


def limits(**options):
    return replace(LinuxScannerLimits(resident_byte_budget=512*1024**2), **options)


@pytest.mark.parametrize("field,value", [("resident_byte_budget", True), ("max_stdout_bytes", 0), ("max_source_bytes", 1024**3+1), ("max_depth", 129), ("deadline_seconds", float("nan")), ("deadline_seconds", True), ("go_memory_target_bytes", 4*1024**3+1), ("max_transport_reads", 0)])
def test_typed_limits_reject_invalid_before_native_io(field, value):
    with pytest.raises(CoreError, match="Owned Linux scanner"):
        limits(**{field:value})


def test_output_image_budget_is_reserved_before_process():
    ceiling = 2*(100+200+300)+256+65536+512
    accepted = LinuxScannerLimits(resident_byte_budget=ceiling, max_stdout_bytes=100, max_coverage_bytes=200, max_stderr_bytes=300,max_transport_reads=1)
    with pytest.raises(CoreError):
        replace(accepted, resident_byte_budget=ceiling-1)


@pytest.mark.skipif(not hasattr(os,"pread"),reason="Actual POSIX pread ELF header policy")
@pytest.mark.parametrize("defect",[None,"interpreter","dynamic","pie","machine","count","truncated","format"])
def test_bounded_static_elf_policy_from_real_fd(tmp_path,defect):
    # Parser-only fixture, not an executable or native Linux acceptance.
    header=bytearray(64+56)
    header[:7]=b"\x7fELF\x02\x01\x01"
    struct.pack_into("<HHI",header,16,2,62,1)
    struct.pack_into("<Q",header,32,64)
    struct.pack_into("<HHH",header,52,64,56,1)
    struct.pack_into("<I",header,64,1)
    if defect=="interpreter":struct.pack_into("<I",header,64,3)
    elif defect=="dynamic":struct.pack_into("<I",header,64,2)
    elif defect=="pie":struct.pack_into("<H",header,16,3)
    elif defect=="machine":struct.pack_into("<H",header,18,183)
    elif defect=="count":struct.pack_into("<H",header,56,65535)
    elif defect=="truncated":header=header[:-1]
    elif defect=="format":header[0]=0
    path=tmp_path/"image";path.write_bytes(header)
    fd=os.open(path,os.O_RDONLY)
    try:
        if defect is None:module._static_image(fd)
        else:
            with pytest.raises(CoreError):module._static_image(fd)
    finally:os.close(fd)


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual unsupported macOS early refusal")
def test_actual_mac_refuses_without_executable_or_input_reads(tmp_path, monkeypatch):
    root = tmp_path/"private"; root.mkdir(mode=0o700)
    with open_directory(root, private=True) as directory:
        owner = open_linux_scanner(executable=tmp_path/"absent", executable_sha256="0"*64, scan_directory=directory, limits=limits(), authorize=lambda: pytest.fail("must refuse before authorization/native IO"))
        monkeypatch.setattr(module, "_executable", lambda *args: pytest.fail("unsupported exec"))
        with pytest.raises(CoreError) as caught:
            owner.__enter__()
        assert caught.value.code == "CAPTURE_PLATFORM_UNSUPPORTED"
        assert owner._phase == "closed" and owner._process is None


@pytest.fixture(scope="module")
def binary(tmp_path_factory):
    if sys.platform != "linux" or platform.machine() != "x86_64":
        pytest.skip("Actual Linux/amd64 scanner executable")
    go = shutil.which("go")
    assert go, "Pinned Go toolchain is required for Linux qualification"
    output = tmp_path_factory.mktemp("owned-scanner-bin")/"bsl-scan"
    subprocess.run([go,"build","-trimpath","-o",str(output),"./cmd/bsl-scan"], cwd=ROOT/"go", env={**os.environ,"CGO_ENABLED":"0"}, check=True, timeout=120)
    output.chmod(0o700)
    return output, hashlib.sha256(output.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def negative_binary(binary,tmp_path_factory):
    # Deliberately non-owned test image: only negative protocol/cleanup probes.
    root=tmp_path_factory.mktemp("negative-scanner")
    source=root/"main.go"
    source.write_text('''package main
import("fmt";"io";"os";"strconv";"time")
func main(){
  fd:=func(i int)*os.File { n,_:=strconv.Atoi(os.Args[i]);return os.NewFile(uintptr(n),"negative") }
  hello:=fd(5);fmt.Fprintf(hello,"rentgen-owned-scanner-linux-v1 %d %s\\n",os.Getpid(),os.Args[2]);hello.Close()
  var gate [1]byte;if _,err:=io.ReadFull(os.Stdin,gate[:]);err!=nil{return}
  if os.Args[8]=="2" {os.Stdout.Write(make([]byte,8192))}
  os.Stdout.Close();os.Stderr.Close();fd(4).Close();time.Sleep(60*time.Second)
}
''')
    output=root/"negative"
    subprocess.run([shutil.which("go"),"build","-trimpath","-o",str(output),str(source)],cwd=ROOT/"go",env={**os.environ,"CGO_ENABLED":"0"},check=True,timeout=120)
    output.chmod(0o700)
    return output,hashlib.sha256(output.read_bytes()).hexdigest()


@pytest.fixture
def inputs(tmp_path):
    root=tmp_path/"scan"; root.mkdir(mode=0o700)
    layer=root/"base"; layer.mkdir(mode=0o700)
    (layer/"A.bsl").write_bytes(b"\xef\xbb\xbfProcedure Demo()\r\nEndProcedure\r\n")
    (layer/"A.bsl").chmod(0o600)
    (layer/"Empty.os").write_bytes(b"// empty\n"); (layer/"Empty.os").chmod(0o600)
    return root


def opened(binary, directory, **options):
    return open_linux_scanner(executable=binary[0], executable_sha256=binary[1], scan_directory=directory, limits=options.pop("limits", limits()), authorize=options.pop("authorize",lambda:None), **options)


@native
def test_real_scanner_sealed_execution_and_bounded_exact_output(binary, inputs, tmp_path):
    # Mutating the original executable after HELLO cannot replace the executed image.
    local=tmp_path/"bsl-scan"; shutil.copyfile(binary[0],local); local.chmod(0o700)
    with open_directory(inputs,private=True) as directory:
        with opened((local,binary[1]),directory) as owner:
            local.write_bytes(b"no longer executable bytes")
            result=owner.scan(); process=owner._process
            assert process.returncode==0
            with pytest.raises(CoreError): owner.scan()
        assert owner._phase=="closed" and owner._selector is None
        assert result.executable_sha256==binary[1] and result.protocol==module._PROTOCOL
        report=json.loads(result.coverage)
        assert [item["source_path"] for item in report["files"]]==["base/A.bsl","base/Empty.os"]
        assert [item["routine_count"] for item in report["files"]]==[1,0]
        records=[json.loads(line) for line in result.ndjson.splitlines()]
        assert len(records)==1 and records[0]["source_path"]=="base/A.bsl"


@native
def test_same_borrowed_directory_has_independent_reusable_cursor_and_mixed_inputs(binary,inputs):
    (inputs/"base/Описание.xml").write_bytes("<Root>Данные</Root>".encode())
    (inputs/"base/Описание.xml").chmod(0o600)
    (inputs/"base/image.bin").write_bytes(b"\x00\xff");(inputs/"base/image.bin").chmod(0o600)
    with open_directory(inputs,private=True) as directory:
        offset=os.lseek(directory._fd,0,os.SEEK_CUR)
        outputs=[]
        for _ in range(2):
            with opened(binary,directory) as owner: outputs.append(owner.scan())
            assert os.lseek(directory._fd,0,os.SEEK_CUR)==offset
        assert outputs[0]==outputs[1] and outputs[0].ndjson
        assert len(json.loads(outputs[0].coverage)["files"])==2
        with pytest.raises(CoreError):
            with opened(binary,directory,limits=limits(max_files=2)) as owner: owner.scan()


@native
@pytest.mark.parametrize("defect",["digest","symlink","hardlink","public"])
def test_actual_executable_refusals_before_child(binary,inputs,tmp_path,defect):
    image=tmp_path/"image"; shutil.copyfile(binary[0],image); image.chmod(0o700); digest=binary[1]
    if defect=="digest": digest="0"*64
    elif defect=="symlink": image.unlink(); image.symlink_to(binary[0])
    elif defect=="hardlink": os.link(image,tmp_path/"alias")
    elif defect=="public": image.chmod(0o722)
    with open_directory(inputs,private=True) as directory:
        owner=opened((image,digest),directory)
        with pytest.raises(CoreError) as caught: owner.__enter__()
        assert caught.value.code=="GRAPH_SCANNER_EXECUTABLE_INVALID" and owner._process is None


@native
@pytest.mark.parametrize("defect",["symlink","hardlink","public","fifo","bad_utf8","too_big","file_count","entry_count","depth","source_bytes","output","coverage","transport_reads"])
def test_real_owned_input_and_output_refusals(binary,inputs,defect):
    source=inputs/"base/A.bsl"; bounded=limits()
    if defect=="symlink": source.unlink(); source.symlink_to(inputs/"base/Empty.os")
    elif defect=="hardlink": os.link(source,inputs/"alias.bsl")
    elif defect=="public": source.chmod(0o644)
    elif defect=="fifo": source.unlink(); os.mkfifo(source,0o600)
    elif defect=="bad_utf8": source.write_bytes(b"\xff")
    elif defect=="too_big": bounded=limits(max_file_bytes=1)
    elif defect=="file_count": bounded=limits(max_files=1)
    elif defect=="entry_count": bounded=limits(max_entries=1)
    elif defect=="depth":
        child=inputs/"base/deeper"; child.mkdir(mode=0o700); bounded=limits(max_depth=1)
    elif defect=="source_bytes": bounded=limits(max_source_bytes=1)
    elif defect=="output": bounded=limits(max_stdout_bytes=1)
    elif defect=="coverage": bounded=limits(max_coverage_bytes=1)
    elif defect=="transport_reads":bounded=limits(max_transport_reads=1)
    with open_directory(inputs,private=True) as directory:
        owner=opened(binary,directory,limits=bounded)
        with pytest.raises(CoreError):
            with owner:
                # HELLO proves no input scan before GO, even for FIFO/invalid input.
                owner.scan()
        assert owner._process.returncode is not None and owner._phase=="closed"
        assert not owner._buffers


@native
@pytest.mark.parametrize("directory_acl",[False,True])
def test_real_materialized_source_acl_refusal(binary,inputs,directory_acl):
    named_permissions=7 if directory_acl else 0
    entries=[(1,7,0xffffffff),(2,4,os.geteuid()),(4,0,0xffffffff),(16,named_permissions,0xffffffff),(32,0,0xffffffff)]
    acl=struct.pack("<I",2)+b"".join(struct.pack("<HHI",*entry) for entry in entries)
    path=inputs/"base" if directory_acl else inputs/"base/A.bsl"
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        os.setxattr(fd,"system.posix_acl_default" if directory_acl else "system.posix_acl_access",acl)
        assert os.fstat(fd).st_mode&0o077==0
    finally:os.close(fd)
    with open_directory(inputs,private=True) as directory:
        with pytest.raises(CoreError):
            with opened(binary,directory) as owner:owner.scan()
        assert owner._process.returncode is not None


@native
def test_native_timer_kills_child_waiting_for_go_without_parent_pump(binary,inputs):
    with open_directory(inputs,private=True) as directory:
        owner=opened(binary,directory,limits=limits(deadline_seconds=0.3))
        owner.__enter__()
        try:
            assert owner._process.wait(timeout=3)==-signal.SIGKILL
        finally:
            with pytest.raises(CoreError): owner.__exit__(None,None,None)
        assert owner._phase=="closed"


@native
def test_cancel_and_final_auth_failure_preserve_primary_and_reap(binary,inputs):
    for cancel in (True,False):
        event=threading.Event(); failure=RuntimeError("revoked")
        def authorize():
            if event.is_set() and not cancel: raise failure
        with open_directory(inputs,private=True) as directory:
            owner=opened(binary,directory,authorize=authorize,cancelled=lambda:event.is_set() and cancel)
            owner.__enter__(); event.set()
            with pytest.raises(CoreError if cancel else RuntimeError) as caught: owner.scan()
            if not cancel: assert caught.value is failure
            assert owner._process.returncode is not None and owner._phase=="closed"


@native
@pytest.mark.parametrize("failure_at",[1,2])
def test_partial_entry_fdopen_failure_closes_actual_pipe_fds(binary,inputs,monkeypatch,failure_at):
    pairs=[]; calls=0; original_pipe=os.pipe; original_fdopen=os.fdopen; denial=RuntimeError("pipe wrapper failed")
    def pipe():
        pair=original_pipe();pairs.append(pair);return pair
    def fdopen(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==failure_at: raise denial
        return original_fdopen(*args,**kwargs)
    with open_directory(inputs,private=True) as directory:
        owner=opened(binary,directory)
        monkeypatch.setattr(module.os,"pipe",pipe);monkeypatch.setattr(module.os,"fdopen",fdopen)
        with pytest.raises(RuntimeError) as caught:owner.__enter__()
        assert caught.value is denial and owner._process is None and owner._phase=="closed"
        for pair in pairs:
            for fd in pair:
                with pytest.raises(OSError):os.fstat(fd)
        os.fstat(directory._fd)


@native
def test_registration_failure_after_spawn_reaps_and_preserves_primary(binary,inputs,monkeypatch):
    with open_directory(inputs,private=True) as directory:
        owner=opened(binary,directory);original=owner._register;failure=RuntimeError("registration failed")
        def register(stream,label):
            if label=="stderr":raise failure
            return original(stream,label)
        monkeypatch.setattr(owner,"_register",register)
        with pytest.raises(RuntimeError) as caught:owner.__enter__()
        assert caught.value is failure and owner._process.returncode is not None
        assert all(stream.closed for stream in (owner._process.stdin,owner._process.stdout,owner._process.stderr))


@native
@pytest.mark.parametrize("revoke",[False,True])
def test_eof_wait_remains_cancellable_and_authorized(negative_binary,inputs,revoke):
    event=threading.Event();failure=RuntimeError("revoked after pipe EOF")
    def authorize():
        if revoke and event.is_set():raise failure
    with open_directory(inputs,private=True) as directory:
        owner=opened(negative_binary,directory,authorize=authorize,cancelled=lambda:event.is_set() and not revoke)
        owner.__enter__();trigger=threading.Timer(0.2,event.set);trigger.start();start=time.monotonic()
        try:
            with pytest.raises(RuntimeError if revoke else CoreError) as caught:owner.scan()
            if revoke:assert caught.value is failure
            else:assert caught.value.code=="GRAPH_SCANNER_CANCELLED"
            assert time.monotonic()-start<2 and owner._process.returncode is not None
        finally:trigger.cancel();trigger.join()


@native
def test_retained_output_limit_exception_has_no_raw_chunk(negative_binary,inputs):
    with open_directory(inputs,private=True) as directory:
        owner=opened(negative_binary,directory,limits=limits(max_file_bytes=2,max_stdout_bytes=1))
        with pytest.raises(CoreError) as caught:
            with owner:owner.scan()
        assert caught.value.code=="GRAPH_SCANNER_OUTPUT_LIMIT_EXCEEDED"
        trace=caught.value.__traceback__;seen=False
        while trace:
            if trace.tb_frame.f_code.co_name=="_pump":
                assert trace.tb_frame.f_locals["raw"] is None;seen=True
            trace=trace.tb_next
        assert seen and not owner._buffers and owner._process.returncode is not None


@native
def test_real_thread_and_fork_exit_cannot_consume_owner(binary,inputs):
    with open_directory(inputs,private=True) as directory:
        with opened(binary,directory) as owner:
            failures=[]
            def foreign():
                for call in (owner.scan,lambda:owner.__exit__(None,None,None)):
                    try: call()
                    except CoreError as exc: failures.append(exc.code)
            thread=threading.Thread(target=foreign); thread.start(); thread.join(timeout=2)
            assert failures==["GRAPH_SCANNER_SESSION_INVALID"]*2
            pid=os.fork()
            if pid==0:
                try:
                    owner.__exit__(None,None,None)
                except CoreError: os._exit(0)
                os._exit(1)
            assert os.waitpid(pid,0)[1]==0
            assert owner.scan().ndjson
        assert owner._process.returncode==0 and owner._phase=="closed"


@native
def test_reentrant_public_exit_refuses_before_teardown(binary,inputs):
    current=[]; attempts=[]
    def authorize():
        if current:
            with pytest.raises(CoreError): current[0].__exit__(None,None,None)
            attempts.append(True)
    with open_directory(inputs,private=True) as directory:
        with opened(binary,directory,authorize=authorize) as owner:
            current.append(owner); assert owner.scan().coverage
        assert attempts and owner._phase=="closed"


@native
def test_body_error_cause_remains_primary_and_child_is_reaped(binary,inputs):
    error=RuntimeError("caller denied");cause=ValueError("original cause")
    with open_directory(inputs,private=True) as directory:
        with pytest.raises(RuntimeError) as caught:
            with opened(binary,directory) as owner:raise error from cause
        assert caught.value is error and error.__cause__ is cause
        assert owner._process.returncode is not None and owner._phase=="closed"


_CONTROLLER="""
import array,socket,sys,time
from pathlib import Path
from rentgen_core._linux_scanner import *
from rentgen_core._posix_source_tree import open_directory
with open_directory(Path(sys.argv[3]),private=True) as directory:
    with open_linux_scanner(executable=Path(sys.argv[1]),executable_sha256=sys.argv[2],scan_directory=directory,limits=LinuxScannerLimits(resident_byte_budget=512*1024**2),authorize=lambda:None) as owner:
        connection=socket.socket(fileno=int(sys.argv[4]))
        connection.sendmsg([str(owner._process.pid).encode()],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[owner._process.stdin.fileno()]))])
        time.sleep(60)
"""

_DEATH_PROBE="""
import array,ctypes,json,os,signal,socket,subprocess,sys,time
library=ctypes.CDLL(None,use_errno=True)
assert library.prctl(36,1,0,0,0)==0
result={}
for name,path,digest in [('owned',sys.argv[2],sys.argv[3]),('control',sys.argv[4],sys.argv[5])]:
    parent,child=socket.socketpair();parent.settimeout(5);controller=None;pid=None;held=None;reaped=False
    try:
        controller=subprocess.Popen([sys.executable,'-c',sys.argv[1],path,digest,sys.argv[6],str(child.fileno())],pass_fds=(child.fileno(),),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        child.close();data,ancillary,flags,address=parent.recvmsg(128,socket.CMSG_SPACE(4));pid=int(data)
        descriptors=array.array('i');descriptors.frombytes(ancillary[0][2][:4]);held=descriptors[0]
        controller.kill();controller.wait(timeout=2)
        until=time.monotonic()+(2 if name=='owned' else .4);status=None
        while time.monotonic()<until:
            found,value=os.waitpid(pid,os.WNOHANG)
            if found:status=value;reaped=True;break
            time.sleep(.01)
        if name=='owned':
            assert status is not None and os.WIFSIGNALED(status) and os.WTERMSIG(status)==signal.SIGKILL,status
            result[name]='SIGKILL_reaped_with_stdin_writer_retained'
        else:
            assert status is None,'negative control died despite retained stdin writer'
            result[name]='survived_controller_death_without_PDEATHSIG'
    finally:
        if controller is not None:
            if controller.poll() is None:controller.kill()
            controller.wait(timeout=2);controller.stderr.close()
        if pid is not None and not reaped:
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
            os.waitpid(pid,0)
        if held is not None:os.close(held)
        parent.close();child.close()
print(json.dumps(result))
"""


@native
def test_abrupt_controller_death_sigkill_with_retained_stdin_and_negative_control(binary,negative_binary,inputs):
    probe=subprocess.run([sys.executable,"-c",_DEATH_PROBE,_CONTROLLER,str(binary[0]),binary[1],str(negative_binary[0]),negative_binary[1],str(inputs)],cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert probe.returncode==0,(probe.stdout,probe.stderr)
    assert json.loads(probe.stdout)=={"owned":"SIGKILL_reaped_with_stdin_writer_retained","control":"survived_controller_death_without_PDEATHSIG"}
