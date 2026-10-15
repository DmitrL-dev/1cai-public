"""Standalone stdlib bootstrap + installed-only SDK probe. Never import checkout."""
import asyncio
import base64
import csv
from datetime import timedelta
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import signal
import selectors
import sqlite3
import stat
import subprocess
from threading import Event, Thread
import sys
from time import monotonic, sleep
from uuid import uuid4
from contextlib import asynccontextmanager, closing


class ProbeFailure(Exception): pass


def require(condition, message):
    if not condition: raise ProbeFailure(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()


def sha(raw): return hashlib.sha256(raw).hexdigest()


def read(path, maximum=64*1024**2):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=maximum,"Unsafe installed file")
        with os.fdopen(fd,"rb",closefd=False) as stream: raw=stream.read(maximum+1)
        after=os.fstat(fd)
        stamp=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns)
        require(stamp(before)==stamp(after) and len(raw)==before.st_size,"Installed file changed")
        return raw
    finally: os.close(fd)


def audit(prefix,site,expected,baseline,wrappers):
    """Original payload exactness plus independently verified rewritten RECORD."""
    prefix,site=Path(prefix).resolve(),Path(site).resolve()
    require(site.is_relative_to(prefix),"Installed site is outside venv")
    observed={};claimed=set(baseline)
    for relative,entry in baseline.items():
        raw=read(site/relative)
        require(sha(raw)==entry["sha256"] and len(raw)==entry["size_bytes"],"Bootstrap/Core bytes changed")
        observed[(site/relative).relative_to(prefix).as_posix()]=entry
    for relative,entry in expected["files"].items():
        if relative.endswith(".dist-info/RECORD"): continue
        raw=read(site/relative)
        require(sha(raw)==entry["sha256"] and len(raw)==entry["size_bytes"],"Installed wheel payload differs")
        observed[(site/relative).relative_to(prefix).as_posix()]=entry
    allowed=set(expected["files"])|set(baseline)
    for distribution in expected["distributions"]:
        root=distribution["metadata_root"]
        generated={root+"/"+name for name in ("INSTALLER","REQUESTED")}
        if root+"/direct_url.json" in baseline:generated.add(root+"/direct_url.json")
        allowed.update(generated)
        records={}
        for row in csv.reader(io.StringIO(read(site/root/"RECORD",2*1024**2).decode())):
            require(len(row)==3 and row[0] not in records,"Invalid installed RECORD")
            records[row[0]]=row[1:]
        original=set(distribution["members"])
        pyc={str(Path(name).parent/"__pycache__"/(Path(name).stem+".cpython-311.pyc")) for name in original if name.endswith(".py")}
        # Package files are owned by this distribution's installed RECORD; they
        # must be exact original payload, existing trusted pyc, or derived script.
        for relative,(digest,size) in records.items():
            require(relative and "\\" not in relative and "\0" not in relative and len(relative)<=1024,"Invalid RECORD path")
            path=site/relative; resolved=path.resolve(strict=True)
            require(resolved.is_relative_to(prefix) and not path.is_symlink(),"Installed RECORD escapes venv")
            data=read(path)
            if relative==root+"/RECORD":
                require([digest,size]==["",""],"Installed self RECORD is not unsigned")
            elif relative in baseline and relative.endswith(".pyc"):
                require([digest,size]==["",""],"Unexpected bytecode RECORD binding")
            else:
                encoded=base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
                require(digest=="sha256="+encoded and size==str(len(data)),"Installed RECORD byte binding differs")
            if relative.startswith("../"):
                require(relative=="../../../bin/"+resolved.name and resolved.parent==prefix/"bin"
                    and resolved.name in distribution["entrypoints"] and data==wrappers[resolved.name],"Unexpected generated console script")
            else:
                require(relative in original or relative in generated or relative in baseline and relative in pyc,"Unexpected installed RECORD member")
                if relative.endswith("/INSTALLER"):require(data==b"pip\n","Unexpected installer identity")
                if relative.endswith("/REQUESTED"):require(not data,"Unexpected REQUESTED bytes")
                claimed.add(relative)
            observed[resolved.relative_to(prefix).as_posix()]=dict(sha256=sha(data),size_bytes=len(data))
        require(original<=records.keys(),"Installed metadata missing from RECORD")
        require({"../../../bin/"+name for name in distribution["entrypoints"]}<=records.keys(),"Console script missing from installed RECORD")
    actual=set()
    directories={str(parent) for name in allowed for parent in Path(name).parents if str(parent)!="."}
    for item in site.rglob("*"):
        require(not item.is_symlink(),"Installed namespace has an alias")
        if item.is_file():actual.add(item.relative_to(site).as_posix())
        else:require(item.is_dir() and item.relative_to(site).as_posix() in directories,"Unexpected installed namespace directory")
    require(actual<=allowed and actual<=claimed and set(expected["files"])<=actual and set(baseline)<=actual,"Unexpected installed namespace inventory")
    return dict(original_payload_files=len(expected["files"]),distributions=len(expected["distributions"]),
                verified_inventory_sha256=sha(canonical(observed)),baseline_files=len(baseline))


def check_imports(site,expected):
    import importlib.metadata
    from importlib.machinery import ExtensionFileLoader
    modules=[importlib.import_module(name) for name in ("rentgen_core","rentgen_graph","rentgen_diagnostics","mcp",
        "_cffi_backend","pydantic_core._pydantic_core","cryptography.hazmat.bindings._rust","rpds.rpds")]
    for module in modules:
        path=Path(module.__file__).resolve()
        require(path.is_relative_to(site),"Runtime module escaped installed venv")
        relative=path.relative_to(site).as_posix()
        require(relative in expected["files"] and sha(read(path))==expected["files"][relative]["sha256"],"Imported module differs from wheel bytes")
    native=sum(isinstance(module.__spec__.loader,ExtensionFileLoader) for module in modules[-4:])
    require(native==4,"Declared native dependencies did not load as extensions")
    for distribution in expected["distributions"]:
        installed=importlib.metadata.distribution(distribution["name"])
        require(installed.version==distribution["version"] and Path(installed._path).resolve()==site/distribution["metadata_root"],"Installed distribution origin/version differs")
    for module in list(sys.modules.values()):
        file=getattr(module,"__file__",None)
        if file and any(part in {"site-packages","dist-packages"} for part in Path(file).parts):
            require(Path(file).resolve().is_relative_to(site),"Third-party import escaped installed venv")
    return dict(mcp_version=importlib.metadata.version("mcp"),native_extension_modules=native,
                isolated_core_graph_sdk=True,third_party_imports_inside_venv=True)


def command(config,*args,expected_error=None):
    child=subprocess.Popen([sys.executable,"-I","-B","-X","pycache_prefix="+config["bytecode_prefix"],"-m","rentgen_core",*map(str,args)],
        cwd=config["workspace"],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    buffers={"out":bytearray(),"error":bytearray()};end=monotonic()+30;done=False
    try:
        with selectors.DefaultSelector() as selector:
            for stream,label in ((child.stdout,"out"),(child.stderr,"error")):
                os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,label)
            while selector.get_map():
                require(monotonic()<end,"Fixture CLI deadline exceeded")
                for key,_ in selector.select(.05):
                    raw=os.read(key.fileobj.fileno(),65536)
                    if not raw:selector.unregister(key.fileobj);continue
                    require(len(buffers[key.data])+len(raw)<=(1024**2 if key.data=="out" else 32768),"Fixture CLI output bound")
                    buffers[key.data].extend(raw)
        child.wait(timeout=max(.01,end-monotonic()));done=True
        document=json.loads(buffers["out"])
        require(not buffers["error"],"Installed SDK fixture CLI diagnostics differ")
        if expected_error is not None:
            require(child.returncode==2 and document.get("error",{}).get("code")==expected_error
                and "result" not in document,"Installed CLI refusal differs")
            return document
        require(child.returncode==0 and "error" not in document,"Installed SDK fixture CLI bootstrap failed")
        return document["result"]
    finally:
        if not done:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        child.wait(timeout=5);child.stdout.close();child.stderr.close()


CALLER="CommonModules/Caller/Ext/Module.bsl"
CALLEE="CommonModules/Callee/Ext/Module.bsl"
IMAGES={CALLER:b"Procedure Caller() Export\nValue = Callee.Target();\nEndProcedure\n",
        CALLEE:b"Function Target() Export\nReturn 1;\nEndFunction\n","fixture.bin":b"\0\xff","data.xml":b"<OwnedFixture/>"}


def project(config,label,large=False):
    work=Path(config["workspace"])/label;work.mkdir(mode=0o700)
    profile=work/"profile/identity.json";registry=work/"registry.sqlite3";source=work/"source";source.mkdir(mode=0o700)
    command(config,"identity-init","--identity-profile",profile)
    common=["--registry",registry,"--identity-profile",profile]
    command(config,"registry-init",*common)
    for relative,raw in IMAGES.items():
        path=source/relative;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes((b"// owned cancellation fixture\n"*250_000 if large and relative==CALLEE else b"")+raw)
    identity=command(config,"project-register",*common,"--source-root",source,"--state-root",work/"state","--name","Installed offline SDK fixture")["project_id"]
    return dict(profile=profile,registry=registry,source=source,project_id=identity,state=work/"state/state.sqlite3")


async def call(session,name,args):
    result=await session.call_tool(name,args,read_timeout_seconds=timedelta(seconds=90))
    require(not result.isError,"Installed SDK tool refused fixture: "+name)
    return result.structuredContent["result"]


class BoundedReceive:
    """Transparent SDK byte stream with a pre-parser whole-session byte cap."""
    def __init__(self,stream,overflow,kill,maximum=8*1024**2):
        self.stream,self.overflow,self.kill,self.maximum=stream,overflow,kill,maximum;self.used=0
    def __getattr__(self,name):return getattr(self.stream,name)
    async def receive(self,max_bytes=65536):
        require(not self.overflow.is_set(),"SDK transport output exceeded bound")
        raw=await self.stream.receive(min(max_bytes,65536));self.used+=len(raw)
        if self.used>self.maximum:self.overflow.set();self.kill()
        require(not self.overflow.is_set(),"SDK transport output exceeded bound")
        return raw
    async def aclose(self):await self.stream.aclose()
    async def __aenter__(self):await self.stream.__aenter__();return self
    async def __aexit__(self,*args):return await self.stream.__aexit__(*args)


def drain_stderr(fd,overflow,kill,stop,maximum=32768,result=None):
    """Discard private diagnostics; bound observed bytes before SDK success."""
    result={} if result is None else result
    count=0
    try:
        os.set_blocking(fd,False)
        while not stop.is_set():
            try:raw=os.read(fd,4096)
            except BlockingIOError:stop.wait(.01);continue
            if not raw:result["eof"]=True;return
            count+=len(raw)
            if count>maximum and not overflow.is_set():overflow.set();kill()
    except BaseException as error:
        result["error"]=type(error).__name__;overflow.set()
        try:kill()
        except BaseException as cleanup_error:result["cleanup_error"]=type(cleanup_error).__name__
    finally:
        try:os.close(fd)
        except OSError as error:result["error"]=type(error).__name__


async def acquire_pidfd(process):
    """A failed observer acquisition cannot abandon the already owned child."""
    import anyio
    try:
        descriptor=os.pidfd_open(process.pid)
        try:
            status=process_stat(process.pid)
            require(process.returncode is None and status and status[1]==os.getpid(),"SDK child identity changed during observation")
        except BaseException:os.close(descriptor);raise
        return descriptor
    except BaseException as primary:
        cleanup_error=None
        with anyio.CancelScope(shield=True):
            try:process.kill()
            except ProcessLookupError:pass
            except BaseException as error:cleanup_error=error
            try:
                with anyio.fail_after(5):
                    try:await process.wait()
                    finally:await process.aclose()
            except BaseException as error:cleanup_error=cleanup_error or error
        if cleanup_error is not None:raise primary from cleanup_error
        raise


def bounded_process(actual,overflow,kill):
    """Keep SDK 1.30's concrete Process contract during failure escalation."""
    from anyio.abc import Process as SDKProcess
    class Process(SDKProcess):
        def __init__(self):self._stdout=BoundedReceive(actual.stdout,overflow,kill)
        @property
        def pid(self):return actual.pid
        @property
        def returncode(self):return actual.returncode
        @property
        def stdin(self):return actual.stdin
        @property
        def stdout(self):return self._stdout
        @property
        def stderr(self):return actual.stderr
        async def wait(self):return await actual.wait()
        async def aclose(self):await actual.aclose()
        def terminate(self):actual.terminate()
        def kill(self):actual.kill()
        def send_signal(self,value):actual.send_signal(value)
    return Process()


def parent_lifetime_guard(parent):
    require(type(parent) is int and parent>0,"Expected owned parent identity")
    return ("import ctypes,os,runpy,signal,sys;"
        "lib=ctypes.CDLL(None,use_errno=True);"
        "result=lib.prctl(1,signal.SIGKILL,0,0,0);"
        "sys.exit(71) if result!=0 or os.getppid()!="+str(parent)+" else None;")


@asynccontextmanager
async def server(config,fixture,*,scanner=True,observe=None):
    import anyio
    from mcp import ClientSession,StdioServerParameters
    import mcp.client.stdio as transport
    original=transport._create_platform_compatible_process;processes=[];handles=[]
    overflow=Event();stop=Event()
    def kill():
        for fd in handles:
            try:signal.pidfd_send_signal(fd,signal.SIGKILL)
            except ProcessLookupError:pass
    async def spawn(*args,**kwargs):
        process=await original(*args,**kwargs);processes.append(process)
        handles.append(await acquire_pidfd(process))
        if overflow.is_set():kill()
        return bounded_process(process,overflow,kill)
    class Write:
        def __init__(self,stream):self.stream=stream
        async def send(self,message):
            root=message.message.root
            if getattr(root,"method",None)=="tools/call" and root.params.get("name")=="rentgen_capture":observe(root.id)
            await self.stream.send(message)
        async def __aenter__(self):await self.stream.__aenter__();return self
        async def __aexit__(self,*args):return await self.stream.__aexit__(*args)
        async def aclose(self):await self.stream.aclose()
    # SDK starts its server in a separate session. Bind that exact child to this
    # probe's lifetime too, including an outer verifier SIGKILL/timeout. The guard
    # runs only stdlib setup before the same installed module's normal __main__.
    launch=(parent_lifetime_guard(os.getpid())+
        "sys.argv=['rentgen_core.stdio_mcp',*sys.argv[1:]];"
        "runpy.run_module('rentgen_core.stdio_mcp',run_name='__main__')")
    args=["-I","-B","-X","pycache_prefix="+config["bytecode_prefix"],"-c",launch,
          "--registry",str(fixture["registry"]),"--identity-profile",str(fixture["profile"]),"--project",fixture["project_id"]]
    if scanner:args += ["--scanner",config["scanner"],"--scanner-sha256",config["scanner_sha256"]]
    params=StdioServerParameters(command=sys.executable,args=args,cwd=config["workspace"],
        env={"PYTHONDONTWRITEBYTECODE":"1","PYTHONNOUSERSITE":"1","PYTHONUTF8":"1"})
    read_fd,write_fd=os.pipe();errors=os.fdopen(write_fd,"w")
    drain_result={}
    drainer=Thread(target=drain_stderr,args=(read_fd,overflow,kill,stop,32768,drain_result),daemon=True);drainer.start()
    transport._create_platform_compatible_process=spawn
    try:
        with anyio.fail_after(120):
            async with transport.stdio_client(params,errlog=errors) as (read_stream,write_stream):
                async with ClientSession(read_stream,Write(write_stream) if observe else write_stream) as session:
                    await session.initialize();require(len(processes)==1,"SDK subprocess identity missing")
                    yield session,processes[0].pid
    finally:
        primary=sys.exc_info()[0] is not None
        transport._create_platform_compatible_process=original
        cleanup_failed=False
        try:errors.close()
        except OSError:cleanup_failed=True
        drainer.join(timeout=2)
        if drainer.is_alive():stop.set();drainer.join(timeout=1)
        for fd in handles:
            try:os.close(fd)
            except OSError:cleanup_failed=True
        if not primary:
            require(not cleanup_failed and not drainer.is_alive() and drain_result.get("eof") is True and "error" not in drain_result,"SDK private stderr clean EOF/cleanup unconfirmed")
            require(all(p.returncode is not None for p in processes),"Owned SDK subprocess cleanup unconfirmed")
    require(not overflow.is_set(),"SDK transport output exceeded bound")


def source_args(fixture,snapshot):return dict(project_id=fixture["project_id"],snapshot_id=snapshot,layer_id="base",relative_path=CALLEE)


async def read_source(session,fixture,snapshot,raw):
    value=await call(session,"rentgen_source_read",source_args(fixture,snapshot))
    require(base64.b64decode(value["data"],validate=True)==raw and value["raw_sha256"]==sha(raw),"Historical SDK bytes differ")


DIFF_SCOPE="actual installed explicit retained-pair fixture only"
DIFF_LIBRARY_SCOPE="isolated installed-library negative controls, not SDK protocol acceptance"
DIFF_COUNTS=dict(added=1,removed=1,modified=1,unchanged=2)
DIFF_LIMITATIONS=[
    "Source-path byte comparison only; no semantic identity or graph delta.",
    "Read-operation accounting is conservative; no hard RSS limit or precise during-copy SDK cancellation claim.",
    "Actual synthetic fixture only; no minimum-platform, native 1C/EDT or model qualification.",
]


def diff_args(fixture,before,after,**options):
    return dict(project_id=fixture["project_id"],before_snapshot_id=before,after_snapshot_id=after,**options)


def diff_page(value,project_id,before,after):
    """Check the actual public page's pair and every retained SourceRef."""
    require(type(value) is dict and set(value)=={"before_snapshot","after_snapshot","scope","identity","counts","changes","next_cursor"},"Unexpected comparison output scope")
    refs={side:dict(project_id=project_id,snapshot_id=snapshot,manifest_hash=snapshot)
          for side,snapshot in (("before",before),("after",after))}
    require(value["before_snapshot"]==refs["before"] and value["after_snapshot"]==refs["after"]
        and value["scope"]=="source_bytes_by_layer_and_path" and value["identity"]=="source_path_only","Comparison pair identity differs")
    require(type(value["counts"]) is dict and set(value["counts"])=={"added","removed","modified","unchanged"}
        and all(type(n) is int and n>=0 for n in value["counts"].values())
        and type(value["changes"]) is list and len(value["changes"])<=100
        and (value["next_cursor"] is None or type(value["next_cursor"]) is str and len(value["next_cursor"])<=128),"Comparison page bounds differ")
    for change in value["changes"]:
        require(type(change) is dict and set(change)=={"kind","before","after"}
            and change["kind"] in {"added","removed","modified"},"Comparison change shape differs")
        require((change["before"] is None)==(change["kind"]=="added")
            and (change["after"] is None)==(change["kind"]=="removed"),"Comparison change sides differ")
        paths=[]
        for side in ("before","after"):
            entry=change[side]
            if entry is None:continue
            require(type(entry) is dict and set(entry)=={"ref","size_bytes","encoding","identity_status"}
                and type(entry["size_bytes"]) is int and entry["size_bytes"]>=0
                and entry["identity_status"]=="unresolved" and (entry["encoding"] is None or type(entry["encoding"]) is str),"Comparison entry differs")
            ref=entry["ref"]
            require(type(ref) is dict and set(ref)=={"snapshot","layer_id","relative_path","raw_sha256"}
                and ref["snapshot"]==refs[side] and ref["layer_id"]=="base"
                and type(ref["relative_path"]) is str and ref["relative_path"]
                and type(ref["raw_sha256"]) is str and len(ref["raw_sha256"])==64
                and all(c in "0123456789abcdef" for c in ref["raw_sha256"]),"Comparison retained SourceRef differs")
            paths.append(ref["relative_path"])
        require(len(set(paths))==1,"Modified comparison paths differ")
    return value


def diff_expected_changes(images,changed,old_xml="data.xml",new_xml="renamed.xml"):
    """Independent fixed fixture oracle, including renamed bytes and sizes."""
    entry=lambda path,raw:(path,sha(raw),len(raw))
    original,modified=entry(CALLEE,images[CALLEE]),entry(CALLEE,changed)
    old,new=entry(old_xml,images[old_xml]),entry(new_xml,images[old_xml])
    return ([("modified",original,modified),("removed",old,None),("added",None,new)],
            [("modified",modified,original),("added",None,old),("removed",new,None)])


def check_diff_changes(changes,expected):
    def entry(value):
        return None if value is None else (value["ref"]["relative_path"],value["ref"]["raw_sha256"],value["size_bytes"])
    actual=[(change["kind"],entry(change["before"]),entry(change["after"])) for change in changes]
    require(actual==expected,"Comparison fixture changes, hashes or sizes differ")


def diff_wire(reply):
    """The public SDK message must not carry private authorization metadata."""
    document=reply.model_dump(by_alias=True,mode="json",exclude_none=True)
    require(type(document) is dict and set(document)=={"content","structuredContent","isError"}
        and type(document["isError"]) is bool and type(document["content"]) is list and len(document["content"])==1,
        "Comparison private output scope escaped")
    block=document["content"][0]
    require(type(block) is dict and set(block)=={"type","text"} and block["type"]=="text"
        and type(block["text"]) is str and len(reply.content)==1 and reply.content[0].type=="text"
        and reply.content[0].text==block["text"],"Comparison content metadata escaped")
    payload=document["structuredContent"]
    require(type(payload) is dict,"Comparison public payload missing")
    if document["isError"]:
        require(set(payload)=={"error"} and type(payload["error"]) is dict
            and set(payload["error"])=={"code","message","request_id","details"},"Comparison CoreError schema differs")
        error=payload["error"]
        require(all(type(error[name]) is str and error[name] for name in ("code","message","request_id"))
            and type(error["details"]) is dict and not error["details"],"Unexpected comparison refusal details")
    else:
        require(set(payload)=={"result","request_id"} and type(payload["request_id"]) is str and payload["request_id"]
            and type(payload["result"]) is dict and set(payload["result"])=={"snapshot_diff"},"Comparison success payload schema differs")
    def unique(pairs):
        value={}
        for key,item in pairs:
            require(key not in value,"Ambiguous SDK comparison text")
            value[key]=item
        return value
    def invalid_constant(value):raise ProbeFailure("Nonfinite SDK comparison text")
    text=json.loads(reply.content[0].text,object_pairs_hook=unique,parse_constant=invalid_constant)
    try:
        # Python equality conflates True/1 and 1.0/1. Compare their JSON types
        # too; both representations must describe exactly the same value.
        exact=lambda value:json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
        require(exact(text)==exact(payload),"SDK comparison representations differ")
    except (TypeError,ValueError) as error:
        raise ProbeFailure("Invalid SDK comparison JSON") from error
    return payload


async def diff_call(session,fixture,before,after,**options):
    reply=await session.call_tool("rentgen_snapshot_diff",diff_args(fixture,before,after,**options),read_timeout_seconds=timedelta(seconds=60))
    payload=diff_wire(reply)
    require(not reply.isError and set(payload["result"])=={"snapshot_diff"},"Installed SDK comparison refused")
    return diff_page(payload["result"]["snapshot_diff"],fixture["project_id"],before,after)


async def diff_refused(session,fixture,before,after,code,**options):
    reply=await session.call_tool("rentgen_snapshot_diff",diff_args(fixture,before,after,**options),read_timeout_seconds=timedelta(seconds=60))
    payload=diff_wire(reply)
    require(reply.isError and payload.get("error",{}).get("code")==code and "result" not in payload,"Installed SDK comparison refusal differs")


def generation(fixture,snapshot):
    with closing(sqlite3.connect(fixture["state"].as_uri()+"?mode=ro",uri=True)) as db:
        rows=db.execute("SELECT generation_relpath FROM snapshots WHERE project_id=? AND snapshot_id=?",(fixture["project_id"],snapshot)).fetchall()
    require(len(rows)==1 and type(rows[0][0]) is str,"Fixture generation binding missing")
    relative=Path(rows[0][0])
    require(not relative.is_absolute() and len(relative.parts)==2 and relative.parts[0]=="generations"
        and all(p not in {".",".."} for p in relative.parts),"Fixture generation binding unsafe")
    return fixture["state"].parent/relative


def diff_cli(config,fixture,before,after,**options):
    args=["snapshot-diff","--registry",fixture["registry"],"--identity-profile",fixture["profile"],"--project",fixture["project_id"],"--before",before,"--after",after]
    for name in ("limit","cursor"):
        if name in options:args += ["--"+name,str(options[name])]
    value=command(config,*args,expected_error=options.get("expected_error"))
    return value if "expected_error" in options else diff_page(value,fixture["project_id"],before,after)


def diff_admin(config,fixture):
    """Two real owned Linux profiles, with ordinary audited memberships."""
    from rentgen_core.authorization import OWNER_PERMISSIONS
    from rentgen_core.local_identity import current_local_principal
    from rentgen_core.state import ProjectState
    profile=fixture["profile"].parent.parent/"administrator/identity.json"
    command(config,"identity-init","--identity-profile",profile)
    owner=current_local_principal(identity_profile=fixture["profile"])
    admin=current_local_principal(identity_profile=profile)
    require(owner!=admin,"Fixture administrator identity was not distinct")
    state=ProjectState(fixture["state"],fixture["project_id"])
    with state.transaction(owner,write=True) as tx:
        tx.set_membership(admin,OWNER_PERMISSIONS,operation_id=str(uuid4()),expected_revision=tx.membership_revision())
    def set_owner(present):
        with state.transaction(admin,write=True) as tx:
            options=dict(operation_id=str(uuid4()),expected_revision=tx.membership_revision())
            if present:tx.set_membership(owner,OWNER_PERMISSIONS,**options)
            else:tx.revoke_membership(owner,**options)
    return owner,state,set_owner


def diff_owner_limits(budget):
    from rentgen_core._posix_snapshot_session import PosixSnapshotLimits
    from rentgen_core._verified_graph import VerifiedGraphLimits
    return (PosixSnapshotLimits(copied_byte_budget=min(budget.limits.copied_bytes,2560*1024**2),
                resident_byte_budget=min(budget.limits.image_bytes,4*1024**3)),
            VerifiedGraphLimits(image_buffer_budget=2*1024**3))


def diff_library_controls(fixture,before,after,principal,state,set_owner):
    """Installed trusted library negatives, separate from the SDK protocol."""
    from dataclasses import replace
    from rentgen_core._posix_snapshot_session import open_posix_snapshot_session
    from rentgen_core._read_operation_budget import ReadOperationBudget,ReadOperationLimits
    from rentgen_core.context import SnapshotRef
    from rentgen_core.errors import CoreError
    from rentgen_core.local import LocalRuntime
    from rentgen_core.snapshot_diff import compare_retained_pair,authorize_diff_output
    from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory
    factory=RentgenGraphReaderFactory();runtime=LocalRuntime(fixture["registry"],graph_reader_factory=factory)
    def compare(**options):return compare_retained_pair(runtime,principal,fixture["project_id"],before,after,**options)
    def refused(action,code):
        try:action()
        except CoreError as error:require(error.code==code,"Installed library refusal differs")
        else:raise ProbeFailure("Installed library negative control unexpectedly succeeded")
    def descriptors():return len(list(Path("/proc/self/fd").iterdir()))
    counts=[];baseline=descriptors()
    for snapshot in (before,after):
        budget=ReadOperationBudget()
        limits,graph_limits=diff_owner_limits(budget)
        with open_posix_snapshot_session(state=state,principal=principal,
                snapshot=SnapshotRef(fixture["project_id"],snapshot,snapshot),graph_reader_factory=factory,
                limits=limits,graph_limits=graph_limits,authorize_read=budget.checkpoint,
                operation_budget=budget) as session:require(len(session.entries())==4,"Installed individual owner inventory differs")
        budget.close();summary=budget.summary()
        require(summary["closed"] and summary["owners_closed"]==2 and summary["active_owners"]==0
            and not any(summary["held"].values()),"Installed individual owner cleanup differs")
        counts.append(summary["cumulative"]["copied_bytes"])
    bound=max(counts)
    require(bound>0,"Installed individual copy accounting missing")
    refused(lambda:compare(operation_limits=replace(ReadOperationLimits(),copied_bytes=bound)),"SNAPSHOT_READ_LIMIT_EXCEEDED")
    refused(lambda:compare(cancelled=lambda:True),"REQUEST_CANCELLED")
    operation=compare();scope=operation.output_scope
    refused(lambda:authorize_diff_output(runtime,principal,replace(scope,before_snapshot_id=after)),"SNAPSHOT_CORRUPT")
    set_owner(False)
    try:refused(lambda:authorize_diff_output(runtime,principal,scope),"PROJECT_FORBIDDEN")
    finally:set_owner(True)
    operation=compare(operation_limits=replace(ReadOperationLimits(),deadline_seconds=3))
    sleep(max(0,operation.output_scope.deadline-monotonic())+.02)
    refused(lambda:authorize_diff_output(runtime,principal,operation.output_scope),"SNAPSHOT_READ_DEADLINE_EXCEEDED")
    require(descriptors()==baseline,"Installed comparison descriptor cleanup differs")
    return dict(scope=DIFF_LIBRARY_SCOPE,separate_owners_fit=True,combined_copy_budget_refused=True,
        pre_cancel_refused=True,descriptors_restored_after_refusals=True,post_success_authority_revocation_refused=True,
        output_scope_pair_mismatch_refused=True,expired_output_scope_refused=True)


async def snapshot_diff(config):
    fixture=project(config,"sdk-diff");changed=IMAGES[CALLEE].replace(b"Return 1",b"Return 2")
    async with server(config,fixture) as (session,_):
        names={tool.name for tool in (await session.list_tools()).tools}
        require("rentgen_snapshot_diff" in names and not any(name.startswith(("rentgen_metadata_","rentgen_draft_","rentgen_proposal_")) for name in names),"Installed comparison tool scope differs")
        head=await call(session,"rentgen_project_head",dict(project_id=fixture["project_id"]))
        async def capture(head):return await call(session,"rentgen_capture",dict(project_id=fixture["project_id"],operation_id=str(uuid4()),expected_head=head))
        first=await capture(head);before=first["snapshot"]["snapshot_id"]
        (fixture["source"]/CALLEE).write_bytes(changed);(fixture["source"]/"data.xml").rename(fixture["source"]/"renamed.xml")
        second=await capture(first["head"]);after=second["snapshot"]["snapshot_id"]
        (fixture["source"]/CALLEE).write_bytes(changed.replace(b"Return 2",b"Return 3"))
        third=await capture(second["head"]);unrelated=third["snapshot"]["snapshot_id"]
        require(len({before,after,unrelated})==3 and third["head"]["revision"]==3,"Comparison fixture publications differ")
    (generation(fixture,unrelated)/"manifest.json").write_bytes(b"deliberately broken unrelated head")
    fixture["source"].rename(fixture["source"].with_name("source-relocated"))
    principal,state,set_owner=diff_admin(config,fixture)
    state_bytes=read(fixture["state"]);registry_bytes=read(fixture["registry"])
    async with server(config,fixture,scanner=False) as (session,_):
        pages=[];cursor=None
        while True:
            require(len(pages)<3,"Comparison pagination did not terminate")
            page=await diff_call(session,fixture,before,after,limit=1,**({"cursor":cursor} if cursor else {}));pages.append(page)
            require(page["counts"]==DIFF_COUNTS,"SDK comparison counts differ")
            cursor=page["next_cursor"]
            if cursor is None:break
        changes=[change for page in pages for change in page["changes"]]
        expected_forward,expected_reverse=diff_expected_changes(IMAGES,changed)
        require(len(pages)==3,"SDK comparison page count differs")
        check_diff_changes(changes,expected_forward)
        reverse=await diff_call(session,fixture,after,before)
        require(reverse["counts"]==DIFF_COUNTS and reverse["next_cursor"] is None,"SDK reverse comparison differs")
        check_diff_changes(reverse["changes"],expected_reverse)
        same=await diff_call(session,fixture,before,before)
        require(same["counts"]==dict(added=0,removed=0,modified=0,unchanged=4) and not same["changes"] and same["next_cursor"] is None,"SDK self comparison differs")
        await read_source(session,fixture,before,IMAGES[CALLEE]);await read_source(session,fixture,after,changed)
        await diff_refused(session,fixture,"0"*64,after,"SNAPSHOT_NOT_FOUND")
        await diff_refused(session,fixture,after,before,"INVALID_DIFF_CURSOR",limit=1,cursor=pages[0]["next_cursor"])
        await diff_refused(session,fixture,before,after,"INVALID_DIFF_CURSOR",limit=2,cursor=pages[0]["next_cursor"])
        for selected in (before,after):
            manifest=generation(fixture,selected)/"manifest.json";raw=read(manifest);manifest.write_bytes(b"deliberately corrupt selected snapshot")
            try:await diff_refused(session,fixture,before,after,"SNAPSHOT_CORRUPT")
            finally:manifest.write_bytes(raw)
        require(await call(session,"rentgen_project_head",dict(project_id=fixture["project_id"]))==third["head"],"SDK explicit comparison changed head")
    cli_pages=[];cursor=None
    while True:
        require(len(cli_pages)<3,"CLI comparison pagination did not terminate")
        page=diff_cli(config,fixture,before,after,limit=1,**({"cursor":cursor} if cursor else {}));cli_pages.append(page);cursor=page["next_cursor"]
        if cursor is None:break
    require(cli_pages==pages and diff_cli(config,fixture,after,before)==reverse
        and diff_cli(config,fixture,before,before)==same,"Installed CLI/SDK comparisons differ")
    diff_cli(config,fixture,"0"*64,after,expected_error="SNAPSHOT_NOT_FOUND")
    diff_cli(config,fixture,after,before,limit=1,cursor=pages[0]["next_cursor"],expected_error="INVALID_DIFF_CURSOR")
    retained=command(config,"source-read","--registry",fixture["registry"],"--identity-profile",fixture["profile"],"--project",fixture["project_id"],"--snapshot",before,"--layer","base","--path",CALLEE,"--base64")
    require(base64.b64decode(retained["data"],validate=True)==IMAGES[CALLEE],"Installed CLI historical bytes differ")
    require(read(fixture["state"])==state_bytes and read(fixture["registry"])==registry_bytes,"Readonly comparisons changed project data")
    controls=diff_library_controls(fixture,before,after,principal,state,set_owner)
    async with server(config,fixture,scanner=False) as (session,_):
        set_owner(False)
        try:
            await diff_refused(session,fixture,before,after,"PROJECT_FORBIDDEN")
        finally:set_owner(True)
    return dict(schema=1,scope=DIFF_SCOPE,sdk=dict(explicit_forward=True,reverse_pair=True,self_pair=True,
        historical_bytes=True,broken_unrelated_head_ignored=True,live_inputs_removed=True,unknown_snapshot_refused=True,
        wrong_pair_cursor_refused=True,wrong_limit_cursor_refused=True,tampered_before_refused=True,tampered_after_refused=True,
        revoked_current_read_refused=True,output_scope_private=True,pagination=dict(pages=3,changes=3,limit=1,counts=DIFF_COUNTS),
        before_snapshot_sha256=before,after_snapshot_sha256=after,unrelated_head_snapshot_sha256=unrelated),
        cli=dict(explicit_forward=True,reverse_pair=True,self_pair=True,pagination=True,historical_bytes=True,
            broken_unrelated_head_ignored=True,unknown_snapshot_refused=True,wrong_pair_cursor_refused=True,head_database_unchanged=True),
        trusted_library_controls=controls,limitations=DIFF_LIMITATIONS)


async def happy(config):
    fixture=project(config,"sdk-history");operation=str(uuid4())
    async with server(config,fixture) as (session,_):
        names={tool.name for tool in (await session.list_tools()).tools}
        require({"rentgen_capture","rentgen_source_list","rentgen_source_read","rentgen_graph_resolve","rentgen_impact"}<=names
                and "rentgen_proposal_live_apply" not in names,"Installed SDK capability list differs")
        head=await call(session,"rentgen_project_head",dict(project_id=fixture["project_id"]))
        first=await call(session,"rentgen_capture",dict(project_id=fixture["project_id"],operation_id=operation,expected_head=head))
        snapshot=first["snapshot"]["snapshot_id"]
        page=await call(session,"rentgen_source_list",dict(project_id=fixture["project_id"],snapshot_id=snapshot,limit=200))
        require({entry["ref"]["relative_path"] for entry in page["entries"]}==set(IMAGES) and page["next_cursor"] is None,"SDK source inventory differs")
        await read_source(session,fixture,snapshot,IMAGES[CALLEE])
        resolved=await call(session,"rentgen_graph_resolve",source_args(fixture,snapshot))
        impact=await call(session,"rentgen_impact",source_args(fixture,snapshot)|dict(depth=5))
        require([row["source_path"] for row in resolved["result"]["graph_modules"]]==["base/"+CALLEE]
                and impact["result"]["total"]==1 and impact["result"]["complete"],"SDK nontrivial graph differs")
        changed=IMAGES[CALLEE].replace(b"Return 1",b"Return 2");(fixture["source"]/CALLEE).write_bytes(changed)
        second=await call(session,"rentgen_capture",dict(project_id=fixture["project_id"],operation_id=str(uuid4()),expected_head=first["head"]))
        require(second["snapshot"]!=first["snapshot"] and second["head"]["revision"]==2,"SDK second capture did not advance")
    fixture["source"].rename(fixture["source"].with_name("source-relocated"))
    async with server(config,fixture,scanner=False) as (session,_):
        require(await call(session,"rentgen_capture",dict(project_id=fixture["project_id"],operation_id=operation,expected_head=head))==first,"SDK replay changed receipt")
        require(await call(session,"rentgen_publication_receipt",dict(project_id=fixture["project_id"],operation_id=operation))==first,"SDK durable receipt differs")
        await read_source(session,fixture,snapshot,IMAGES[CALLEE]);await read_source(session,fixture,second["snapshot"]["snapshot_id"],changed)
        require(await call(session,"rentgen_graph_resolve",source_args(fixture,snapshot))==resolved,"Historical SDK graph changed")
    return dict(two_captures=True,historical_bytes=True,graph_resolve=True,nontrivial_impact=True,
                replay_without_live_source_or_configured_scanner=True,first_snapshot_sha256=snapshot,
                second_snapshot_sha256=second["snapshot"]["snapshot_id"])


def process_stat(pid):
    try:raw=(Path("/proc")/str(pid)/"stat").read_text()
    except FileNotFoundError:return None
    parts=raw.rsplit(")",1)[1].split();return parts[0],int(parts[1]),int(parts[19])


def child_identity(parent):
    paths=list((Path("/proc")/str(parent)/"task").glob("*/children"));require(len(paths)<=64,"SDK thread bound exceeded")
    children=set()
    for path in paths:
        try:raw=path.read_bytes()
        except FileNotFoundError:continue
        require(len(raw)<=4096,"SDK child inventory bound exceeded");children.update(map(int,raw.split()))
    for pid in children:
        try:
            with (Path("/proc")/str(pid)/"cmdline").open("rb") as stream:raw=stream.read(8193)
        except FileNotFoundError:continue
        require(len(raw)<=8192,"Owned process argument bound exceeded")
        args=raw.rstrip(b"\0").split(b"\0");status=process_stat(pid)
        if len(args)==16 and args[1]==b"--owned-linux-v1" and args[2]==str(parent).encode() and status and status[1]==parent:return pid,status[2]
    return None


def alive(identity):
    value=process_stat(identity[0]);return value if value and value[2]==identity[1] else None


async def gone(identity):
    end=monotonic()+8
    while alive(identity):require(monotonic()<end,"Owned scanner was not reaped");await asyncio.sleep(.01)


async def cancelled(config):
    from mcp import types
    from mcp.shared.exceptions import McpError
    fixture=project(config,"sdk-cancel",large=True);requests=[]
    async with server(config,fixture,observe=requests.append) as (session,parent):
        head=await call(session,"rentgen_project_head",dict(project_id=fixture["project_id"]));operation=str(uuid4())
        pending=asyncio.create_task(session.call_tool("rentgen_capture",dict(project_id=fixture["project_id"],operation_id=operation,expected_head=head),read_timeout_seconds=timedelta(seconds=60)))
        identity=None;pidfd=None
        try:
            end=monotonic()+25
            while identity is None:
                require(not pending.done() and monotonic()<end,"Owned SDK cancellation barrier was not observed")
                identity=child_identity(parent)
                if identity is None:await asyncio.sleep(.001)
            require(len(requests)==1,"Exact outgoing SDK request ID missing")
            pidfd=os.pidfd_open(identity[0]);value=alive(identity)
            require(value and value[1]==parent,"Owned scanner identity changed")
            signal.pidfd_send_signal(pidfd,signal.SIGSTOP);end=monotonic()+2
            while True:
                value=alive(identity);require(value and monotonic()<end,"Owned scanner stop was not confirmed")
                if value[0]=="T":break
                await asyncio.sleep(.001)
            await session.send_notification(types.ClientNotification(types.CancelledNotification(params=types.CancelledNotificationParams(requestId=requests[0],reason="Owned installed fixture cancellation"))))
            try:result=await pending
            except McpError as error:require(error.error.code==0 and error.error.message=="Request cancelled","SDK cancellation error differs")
            else:require(result.isError and result.structuredContent["error"]["code"]=="GRAPH_SCANNER_CANCELLED","Worker cancellation outcome differs")
            require(await call(session,"rentgen_project_head",dict(project_id=fixture["project_id"]))==head,"Cancellation changed head")
            receipt=await session.call_tool("rentgen_publication_receipt",dict(project_id=fixture["project_id"],operation_id=operation),read_timeout_seconds=timedelta(seconds=15))
            require(receipt.isError and receipt.structuredContent["error"]["code"]=="PUBLICATION_NOT_FOUND","Cancelled operation has durable receipt")
            await gone(identity)
        finally:
            if pidfd is not None:
                if identity is not None and alive(identity):
                    try:signal.pidfd_send_signal(pidfd,signal.SIGKILL)
                    except ProcessLookupError:pass
                    await gone(identity)
                os.close(pidfd)
            if not pending.done():
                try:await asyncio.wait_for(asyncio.shield(pending),8)
                except McpError:pass
                except asyncio.TimeoutError:
                    pending.cancel()
                    try:await pending
                    except (McpError,asyncio.CancelledError):pass
            elif not pending.cancelled():pending.exception()
    with closing(sqlite3.connect(fixture["state"].as_uri()+"?mode=ro",uri=True)) as db:
        counts={name:db.execute("SELECT count(*) FROM "+name).fetchone()[0] for name in ("snapshots","publication_receipts","snapshot_events","snapshot_outbox")}
    require(set(counts.values())=={0},"Cancelled SDK capture partially published")
    return dict(real_notification=True,exact_request_id=True,pidfd_owned_barrier=True,scanner_reaped=True,
                worker_drained=True,no_publication=True,scope="deliberately paused pre-CAS child; late cancellation can lose to commit")


def main():
    config=json.loads(read(Path(sys.argv[1]),8*1024**2))
    prefix=Path(config["prefix"]).resolve();site=Path(config["site"]).resolve()
    require(Path(sys.prefix).resolve()==prefix and sys.flags.isolated and sys.dont_write_bytecode
        and Path(sys.pycache_prefix).resolve()==Path(config["bytecode_prefix"]).resolve(),"Probe isolation differs")
    # Regenerate exact console bytes with the already bound bootstrap pip, not
    # the self-reported installed RECORD. These wrappers are audited, not run.
    from pip._vendor.distlib.scripts import ScriptMaker
    wrapper_root=Path(config["workspace"])/"expected-console-scripts";wrapper_root.mkdir(mode=0o700)
    maker=ScriptMaker(None,str(wrapper_root));maker.clobber=True;maker.variants={""};maker.set_mode=True;maker.executable=sys.executable
    maker.make_multiple([name+" = "+target for name,target in config["expected"]["scripts"].items()])
    wrappers={name:read(wrapper_root/name,65536) for name in config["expected"]["scripts"]}
    audit_before=audit(prefix,site,config["expected"],config["baseline"],wrappers)
    imports=check_imports(site,config["expected"])
    async def scenario():return await happy(config),await cancelled(config),await snapshot_diff(config)
    history,cancellation,comparison=asyncio.run(scenario())
    check_imports(site,config["expected"])
    audit_after=audit(prefix,site,config["expected"],config["baseline"],wrappers)
    require(audit_before==audit_after,"Installed bytes changed during SDK scenarios")
    print(json.dumps(dict(schema=1,accepted=True,scope="actual installed offline-input SDK synthetic fixture only",
        inventory=audit_after,imports=imports,history=history,cancellation=cancellation,snapshot_diff=comparison,
        no_source_checkout_imports=True,old_bytecode_not_loaded=True)))


if __name__=="__main__":
    try:main()
    except Exception as error:
        print("Installed SDK probe failed: "+(str(error) if type(error) is ProbeFailure else type(error).__name__),file=sys.stderr)
        raise SystemExit(1)
