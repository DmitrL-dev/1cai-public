"""Verify the externally pinned owned Linux candidate, not release authority."""
import argparse
import base64
import configparser
import csv
from email.parser import BytesParser
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import stat
import struct
import sys
import sysconfig
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HELPER = "scripts/verification/owned_linux_sdk_probe.py"
LOCK = "requirements/locks/mcp-py311-linux-x86_64.txt"
PROVENANCE = "requirements/locks/mcp-py311-linux-x86_64.provenance.json"


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load("scripts/verification/verify_linux_capture_delivery.py", "_owned_delivery_base")


def host():
    base.require(sys.platform == "linux" and platform.machine() in {"x86_64", "amd64"}
        and sys.implementation.name == "cpython" and sys.version_info[:3] == (3, 11, 15)
        and __debug__, "Owned SDK qualification requires actual Linux/amd64 CPython 3.11.15")
    libc, version = platform.libc_ver()
    kernel = re.match(r"(\d+)\.(\d+)", platform.release())
    base.require(libc == "glibc" and tuple(map(int, version.split(".")[:2])) >= (2, 34)
        and kernel is not None and tuple(map(int, kernel.groups())) >= (5, 9)
        and str(sysconfig.get_config_var("SOABI")).startswith("cpython-311-x86_64-linux-")
        and all(hasattr(os, name) for name in ("memfd_create", "pidfd_open"))
        and hasattr(signal, "pidfd_send_signal"), "Declared Linux ABI/kernel prerequisites are unavailable")
    return dict(implementation=sys.implementation.name,python=".".join(map(str,sys.version_info[:3])),
        architecture=platform.machine(),glibc=version,kernel_release=platform.release(),soabi=sysconfig.get_config_var("SOABI"))


def normalize(value):
    return re.sub(r"[-_.]+", "-", value).lower()


def safe_member(name):
    parts = PurePosixPath(name).parts
    base.require(type(name) is str and name and len(name.encode()) <= 1024
        and not name.startswith("/") and "\\" not in name and "\0" not in name
        and str(PurePosixPath(name)) == name and all(part not in {".", ".."} for part in parts),
        "Unsafe wheel inventory path")
    base.require(not any(part.endswith(".data") for part in parts)
        and not name.endswith(".pth") and parts[-1] not in {"sitecustomize.py", "usercustomize.py"},
        "Relocated or startup-executed wheel payload is not admitted")


def wheel_expectations(wheels):
    """Original bytes + complete original RECORD; no import/install of payload."""
    files, distributions, scripts, total = {}, [], {}, 0
    all_names=set();member_total=0
    for filename, raw in sorted(wheels.items()):
        base.require(filename.endswith(".whl") and len(raw) <= 64*1024**2, "Bounded wheel required")
        position=raw.rfind(b"PK\x05\x06",max(0,len(raw)-65557))
        base.require(position>=0 and position+22<=len(raw),"Wheel directory missing")
        disk,other,count_disk,count,size,offset,comment=struct.unpack_from("<HHHHIIH",raw,position+4)
        base.require(disk==other==0 and count_disk==count and 1<=count<=10_000
            and size<=8*1024**2 and offset+size==position and position+22+comment==len(raw),"Wheel directory bound exceeded")
        cursor=offset;actual=0
        while cursor<position:
            base.require(cursor+46<=position and raw[cursor:cursor+4]==b"PK\x01\x02","Invalid central record")
            names,extra,comments,disk=struct.unpack_from("<HHHH",raw,cursor+28)
            base.require(1<=names<=1024 and extra<=4096 and comments<=4096 and disk==0,"Central record field bound")
            cursor+=46+names+extra+comments;actual+=1
            base.require(cursor<=position and actual<=10_000,"Central record count bound")
        base.require(cursor==position and actual==count,"Wheel directory count differs")
        member_total+=count
        base.require(member_total<=10_000,"Combined wheel member bound exceeded")
        members = {};folded=set()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            base.require(len(archive.infolist()) <= 10_000, "Wheel member bound exceeded")
            for item in archive.infolist():
                if item.is_dir():
                    safe_member(item.filename.rstrip("/")); continue
                safe_member(item.filename)
                base.require(item.filename.casefold() not in folded
                    and stat.S_IFMT(item.external_attr >> 16) in {0, stat.S_IFREG}
                    and 0 <= item.file_size <= 64*1024**2, "Duplicate or unsafe wheel member")
                total += item.file_size
                base.require(total <= 256*1024**2, "Expanded Python image inventory bound exceeded")
                members[item.filename] = archive.read(item)
                folded.add(item.filename.casefold())
        roots = {name.split("/")[0] for name in members if name.split("/")[0].endswith(".dist-info")}
        base.require(len(roots) == 1, "One distribution metadata root required")
        root = roots.pop(); record_name = root + "/RECORD"
        base.require(root+"/METADATA" in members and record_name in members, "Wheel metadata/RECORD missing")
        metadata = BytesParser().parsebytes(members[root+"/METADATA"])
        name, version = metadata.get("Name"), metadata.get("Version")
        base.require(type(name) is str and type(version) is str and name and version
            and not any(d["name"] == normalize(name) for d in distributions), "Duplicate distribution identity")
        base.require(metadata.get_all("Name")==[name] and metadata.get_all("Version")==[version]
            and root==normalize(name).replace("-","_")+"-"+version+".dist-info","Ambiguous wheel metadata identity")
        records = {}
        for row in csv.reader(io.StringIO(members[record_name].decode("utf-8"))):
            base.require(len(row) == 3 and row[0] not in records, "Invalid wheel RECORD")
            records[row[0]] = row[1:]
        base.require(set(records) == set(members), "Wheel RECORD inventory differs")
        for path, content in members.items():
            if path == record_name:
                base.require(records[path] == ["", ""], "Wheel self RECORD must be unsigned")
            else:
                encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
                base.require(records[path] == ["sha256="+encoded, str(len(content))], "Wheel RECORD digest differs")
            base.require(path.casefold() not in all_names, "Cross-wheel installation collision")
            files[path] = dict(sha256=base.sha(content), size_bytes=len(content))
            all_names.add(path.casefold())
        entrypoints = {}
        if root+"/entry_points.txt" in members:
            parser = configparser.ConfigParser(interpolation=None, strict=True)
            parser.optionxform = str
            parser.read_string(members[root+"/entry_points.txt"].decode())
            if parser.has_section("console_scripts"):
                for script, target in parser.items("console_scripts"):
                    base.require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", script)
                        and script not in scripts, "Ambiguous console script")
                    scripts[script] = target
                    entrypoints[script] = target
        distributions.append(dict(name=normalize(name), version=version, metadata_root=root,
                                  wheel_sha256=base.sha(raw), entrypoints=entrypoints, members=sorted(members)))
    base.require(files and distributions, "Python inventory empty")
    return dict(files=files, distributions=distributions, scripts=scripts)


def site_snapshot(root):
    result = {}
    for path in root.rglob("*"):
        base.require(not path.is_symlink(), "Installed tree contains an alias")
        if path.is_file():
            raw = base.read_regular(path, 64*1024**2)
            result[path.relative_to(root).as_posix()] = dict(sha256=base.sha(raw), size_bytes=len(raw))
    return result


def installation_arguments(python, wheelhouse, lock):
    return [python, "-I", "-B", "-m", "pip", "--isolated", "--disable-pip-version-check", "--no-cache-dir",
        "install", "--no-index", "--require-hashes", "--only-binary=:all:", "--no-compile",
        "--find-links", wheelhouse, "-r", lock]


def source_blob(commit, relative):
    return base.git("show", commit + ":" + relative)


def validate_external(archive_raw, manifest_raw, archive_sha256, manifest_sha256, kit):
    for digest in (archive_sha256, manifest_sha256):
        base.require(type(digest) is str and re.fullmatch("[0-9a-f]{64}", digest), "External SHA-256 required")
    base.require(base.sha(archive_raw) == archive_sha256 and base.sha(manifest_raw) == manifest_sha256,
                 "External candidate hash differs")
    manifest = kit.parse_json(manifest_raw)
    return manifest, kit.verified_payload(archive_raw, manifest)


def require_snapshot_diff_acceptance(value):
    """The newly qualified route is mandatory; an older capture receipt fails."""
    base.require(type(value) is dict and set(value)=={"schema","scope","sdk","cli","trusted_library_controls","limitations"}
        and type(value["schema"]) is int and value["schema"]==1
        and value["scope"]=="actual installed explicit retained-pair fixture only", "Installed retained-pair receipt required")
    sdk_flags={"explicit_forward","reverse_pair","self_pair","historical_bytes","broken_unrelated_head_ignored",
        "live_inputs_removed","unknown_snapshot_refused","wrong_pair_cursor_refused","wrong_limit_cursor_refused",
        "tampered_before_refused","tampered_after_refused","revoked_current_read_refused","output_scope_private"}
    ids={"before_snapshot_sha256","after_snapshot_sha256","unrelated_head_snapshot_sha256"}
    sdk=value["sdk"]
    base.require(type(sdk) is dict and set(sdk)==sdk_flags|ids|{"pagination"}
        and all(sdk[name] is True for name in sdk_flags)
        and all(type(sdk[name]) is str and re.fullmatch("[0-9a-f]{64}",sdk[name]) for name in ids)
        and len({sdk[name] for name in ids})==3, "Installed SDK retained-pair scenarios incomplete")
    page=sdk["pagination"]
    base.require(type(page) is dict and set(page)=={"pages","changes","limit","counts"}
        and all(type(page[name]) is int and page[name]==expected for name,expected in (("pages",3),("changes",3),("limit",1)))
        and type(page["counts"]) is dict and page["counts"]==dict(added=1,removed=1,modified=1,unchanged=2)
        and all(type(n) is int for n in page["counts"].values()), "Installed retained-pair pagination differs")
    cli_flags={"explicit_forward","reverse_pair","self_pair","pagination","historical_bytes",
        "broken_unrelated_head_ignored","unknown_snapshot_refused","wrong_pair_cursor_refused","head_database_unchanged"}
    cli=value["cli"]
    base.require(type(cli) is dict and set(cli)==cli_flags and all(cli[name] is True for name in cli_flags), "Installed CLI retained-pair scenarios incomplete")
    library_flags={"separate_owners_fit","combined_copy_budget_refused","pre_cancel_refused",
        "descriptors_restored_after_refusals","post_success_authority_revocation_refused",
        "output_scope_pair_mismatch_refused","expired_output_scope_refused"}
    library=value["trusted_library_controls"]
    base.require(type(library) is dict and set(library)==library_flags|{"scope"}
        and library["scope"]=="isolated installed-library negative controls, not SDK protocol acceptance"
        and all(library[name] is True for name in library_flags), "Installed library refusal controls incomplete")
    base.require(value["limitations"]==[
        "Source-path byte comparison only; no semantic identity or graph delta.",
        "Read-operation accounting is conservative; no hard RSS limit or precise during-copy SDK cancellation claim.",
        "Actual synthetic fixture only; no minimum-platform, native 1C/EDT or model qualification.",
    ], "Installed retained-pair limitations differ")


def verify(archive, manifest, archive_sha256, manifest_sha256, output, expected_version,
           source_commit, scanner_sha256, rust_sha256):
    runtime=host()  # Before candidate IO or output creation, never a spoofed Linux path.
    base.labels(expected_version, source_commit, scanner_sha256)
    base.require(type(rust_sha256) is str and re.fullmatch("[0-9a-f]{64}", rust_sha256), "Explicit Rust SHA-256 required")
    kit = load("scripts/release/prepare_owned_linux.py", "_owned_delivery_kit")
    lockcheck = load("requirements/locks/check_linux_mcp_lock.py", "_owned_delivery_lock")
    archive_raw = base.read_regular(Path(archive).absolute(), 128*1024**2)
    manifest_raw = base.read_regular(Path(manifest).absolute(), 1024**2)
    document, payload = validate_external(archive_raw, manifest_raw, archive_sha256, manifest_sha256, kit)
    inputs = document["inputs"]
    base.require(inputs["version"] == expected_version and inputs["source_commit"] == source_commit
        and inputs["scanner"]["sha256"] == scanner_sha256 and inputs["rust_helper"]["sha256"] == rust_sha256,
        "Pinned source/component identities differ")
    base.require(payload["requirements-mcp-py311-linux.txt"] == source_blob(source_commit, LOCK)
        and payload["python-dependency-provenance.json"] == source_blob(source_commit, PROVENANCE),
        "Kit SDK lock/provenance differs from committed source")
    helper_raw = base.read_regular(ROOT / HELPER, 1024**2)
    base.require(helper_raw == source_blob(source_commit, HELPER), "Installed probe differs from committed source")
    tooling={}
    generation_helper="scripts/verification/generation_delivery_probe.py"
    for relative in (HELPER,generation_helper,"scripts/verification/publication_overlap_probe.py","scripts/verification/verify_owned_linux_delivery.py",
            "scripts/verification/verify_linux_capture_delivery.py","scripts/release/prepare_owned_linux.py",
            "requirements/locks/check_linux_mcp_lock.py"):
        raw=base.read_regular(ROOT/relative,1024**2)
        base.require(raw==source_blob(source_commit,relative),"Qualification tooling differs from selected source")
        tooling[relative]=base.sha(raw)
    output = Path(output).absolute(); output = output.parent.resolve(strict=True) / output.name
    output.mkdir(mode=0o700, exist_ok=False)
    staged = output / "kit"; staged.mkdir(mode=0o700)
    for relative, raw in payload.items():
        path = staged / relative
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        base.copy_owned(path, raw, 0o700 if relative.startswith("bin/") else 0o600)
    sdk_wheels = output / "sdk-wheelhouse"; sdk_wheels.mkdir(mode=0o700)
    core_name = inputs["wheel"]["asset"]
    for relative, raw in payload.items():
        if relative.startswith("wheelhouse/") and relative.split("/",1)[1] != core_name:
            base.copy_owned(sdk_wheels / relative.split("/",1)[1], raw, 0o600)
    lock_receipt = lockcheck.verify_wheelhouse(sdk_wheels,
        provenance_path=staged/"python-dependency-provenance.json", lock_path=staged/"requirements-mcp-py311-linux.txt")
    expectations = wheel_expectations({name.split("/",1)[1]: raw for name, raw in payload.items() if name.startswith("wheelhouse/")})
    base.require(len(lock_receipt["wheels"]) == 29 and len(expectations["distributions"]) == 30,
                 "Exact Core plus 29 SDK distributions required")
    cli_output = output / "cli"
    cli_receipt = base.verify(staged/"wheelhouse"/core_name, staged/"bin/bsl-scan-owned-linux",
        scanner_sha256, cli_output, expected_version, source_commit)
    base.require(cli_receipt["source_tree"] == inputs["source_tree"], "Kit source tree differs from CLI source proof")
    environment = cli_output / "environment"; python = environment / "bin/python"
    site = environment / "lib/python3.11/site-packages"
    baseline = site_snapshot(site)
    work = output / "sdk-work"; work.mkdir(mode=0o700)
    code, _, _ = base.run(installation_arguments(python, sdk_wheels, staged/"requirements-mcp-py311-linux.txt"), cwd=work, timeout=120)
    base.require(code == 0, "Exact offline SDK installation failed")
    after = site_snapshot(site)
    base.require(all(after.get(name) == value for name, value in baseline.items()), "SDK install changed bootstrap or Core bytes")
    allowed = set(expectations["files"])
    for distribution in expectations["distributions"]:
        allowed.update(distribution["metadata_root"]+"/"+name for name in ("INSTALLER", "REQUESTED"))
    base.require(set(after)-set(baseline) <= allowed, "SDK install created unexpected startup/runtime files")
    code, _, error = base.run([python, "-I", "-B", "-m", "pip", "--isolated", "--disable-pip-version-check", "check"], cwd=work, timeout=30)
    base.require(code == 0 and not error, "Offline installed dependency consistency check failed")
    helper = work / "probe.py"; base.copy_owned(helper, helper_raw, 0o600)
    base.copy_owned(work / "generation_delivery_probe.py", source_blob(source_commit, generation_helper), 0o600)
    cache = work / "unused-bytecode"; cache.mkdir(mode=0o700)
    config = work / "probe-inputs.json"
    base.save(config, dict(prefix=str(environment), site=str(site), workspace=str(work),
        scanner=str(staged/"bin/bsl-scan-owned-linux"), scanner_sha256=scanner_sha256,
        expected=expectations, baseline=baseline, bytecode_prefix=str(cache)))
    code, stdout, stderr = base.run([python, "-I", "-B", "-X", "pycache_prefix="+str(cache), helper, config],
        cwd=work, timeout=300, stdout_limit=1024**2, stderr_limit=32*1024)
    base.require(code == 0 and not stderr, "Installed SDK isolated fixture verification failed")
    sdk_receipt = json.loads(stdout)
    base.require(sdk_receipt.get("schema") == 1 and sdk_receipt.get("accepted") is True,
                 "Installed SDK fixture did not produce positive receipt")
    require_snapshot_diff_acceptance(sdk_receipt.get("snapshot_diff"))
    generations=sdk_receipt.get("mcp_generations")
    base.require(type(generations) is dict and generations.get("transport")=="official_sdk_stdio"
        and generations.get("output_scope_private") is True
        and len(generations.get("checks",[]))==29
        and generations.get("damage_cases")==["source","derived","graph","manifest","extra","sidecar","missing"]
        and generations.get("outcomes")==dict(historical_verified=True,current_verified=True,unreferenced_refused=True,
            damaged_refused=True,state_unchanged=True,retained_bytes_restored=True,live_source_absent=True),
        "Installed generation SDK receipt required")
    receipt = dict(schema=1, profile=kit.PROFILE, candidate=True, release_authority=False,
        runtime=runtime,qualification_tooling_sha256=tooling,
        source_commit=source_commit, source_tree=inputs["source_tree"], version=expected_version,
        archive=dict(sha256=archive_sha256, size_bytes=len(archive_raw)),
        manifest=dict(sha256=manifest_sha256, size_bytes=len(manifest_raw)),
        scanner=dict(sha256=scanner_sha256, size_bytes=len(payload["bin/bsl-scan-owned-linux"])),
        rust_helper=dict(sha256=rust_sha256, size_bytes=len(payload["bin/rentgen-input-core"]), executed=False),
        sdk_lock_sha256=base.sha(payload["requirements-mcp-py311-linux.txt"]),
        sdk_provenance_sha256=base.sha(payload["python-dependency-provenance.json"]),
        sdk_wheels=lock_receipt["wheels"], source_probe_sha256=base.sha(helper_raw),
        cli_receipt_sha256=base.sha(base.canonical(cli_receipt)), sdk=sdk_receipt,
        offline_install=dict(no_index=True, require_hashes=True, binary_only=True, pip_check=True,
                             bootstrap_and_core_unchanged=True),
        limitations=["Actual synthetic installed CLI+SDK stdio fixture only, not full Linux product or native 1C/EDT",
            "No optional MCP CLI extra acceptance; interpreter/OS/libgcc remain declared prerequisites",
            "No OS-wide network airgap proof; pip was restricted to exact local wheels",
            "Candidate profile is not qualification/publication authority; no release or tag changed"])
    base.save(output/"acceptance.json", receipt)
    print(json.dumps(receipt, indent=2))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "manifest", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    for name in ("archive-sha256", "manifest-sha256", "expected-version", "source-commit", "scanner-sha256", "rust-sha256"):
        parser.add_argument("--"+name, required=True)
    args = parser.parse_args(argv)
    try: verify(**vars(args))
    except Exception as exc:
        parser.exit(1, "Owned Linux qualification failed: "+(str(exc) if type(exc) is base.VerificationError else type(exc).__name__)+"\n")


if __name__ == "__main__": main()
