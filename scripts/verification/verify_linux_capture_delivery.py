"""Qualify one installed Linux/amd64 CLI capture fixture, not full OS support.

All product operations use fresh isolated venv processes. Only owned synthetic
state is inspected with the standard library. No SDK/MCP/native-1C/model claim.
"""

import argparse
import configparser
from contextlib import closing
from email.parser import BytesParser
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import selectors
import signal
import sqlite3
import stat
import struct
import subprocess
import sys
import time
import tomllib
from uuid import UUID, uuid4
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("rentgen_core", "rentgen_graph", "rentgen_diagnostics")
ENTRY_POINTS = {
    "rentgen": "rentgen_core.cli:main",
    "rentgen-mcp": "rentgen_core.stdio_mcp:main",
    "rentgen-observer": "rentgen_core.observer_cli:main",
    "rentgen-service": "rentgen_core.service_entry:main",
    "rentgen-gui": "rentgen_core.gui:main",
}
CALLER = "CommonModules/Caller/Ext/Module.bsl"
CALLEE = "CommonModules/Callee/Ext/Module.bsl"
IMAGES = {
    CALLER: b"Procedure Caller() Export\nCallee.Target();\nEndProcedure\n",
    CALLEE: b"Procedure Target() Export\nReturn;\nEndProcedure\n",
    "data.xml": b"<fixture>owned Linux CLI capture</fixture>\n",
    "binary.bin": b"\x00\xff\x80owned-fixture\x00",
}
CAPTURE_DIAGNOSTICS = (
    b"[stage] reading source identity and declarations ...",
    b"[bind] retaining calls and resolving bounded static targets ...",
)


class VerificationError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def labels(version, source_commit, scanner_sha256):
    require(type(version) is str and re.fullmatch(r"[0-9]+(?:\.[0-9]+)+(?:[A-Za-z0-9.]*)", version),
            "Expected a bounded product version")
    require(len(version) <= 64, "Expected a bounded product version")
    for value, length in ((source_commit, 40), (scanner_sha256, 64)):
        require(type(value) is str and re.fullmatch("[0-9a-f]{" + str(length) + "}", value),
                "Expected exact lowercase source/scanner hashes")


def host():
    require(sys.platform == "linux" and platform.machine() in {"x86_64", "amd64"},
            "Installed capture qualification requires actual Linux/amd64")
    require(sys.version_info >= (3, 11) and __debug__, "Python 3.11+ without -O is required")


def read_regular(path, maximum):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and 0 <= info.st_size <= maximum, "Input is not a bounded single-link regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(maximum + 1)
        require(len(raw) == info.st_size, "Input size changed during reading")
        after = os.fstat(descriptor)
        require((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                "Input changed during reading")
        return raw
    finally:
        os.close(descriptor)


def static_scanner(raw):
    require(64 <= len(raw) <= 32 * 1024**2 and raw[:7] == b"\x7fELF\x02\x01\x01"
            and raw[7] in (0, 3), "Scanner must be a bounded static amd64 ELF")
    kind, machine, version = struct.unpack_from("<HHI", raw, 16)
    offset = struct.unpack_from("<Q", raw, 32)[0]
    header, entry, count = struct.unpack_from("<HHH", raw, 52)
    require((kind, machine, version, header, entry) == (2, 62, 1, 64, 56)
            and 1 <= count <= 256 and offset >= 64 and offset + entry * count <= len(raw),
            "Scanner must be a bounded static amd64 ELF")
    require(all(struct.unpack_from("<I", raw, offset + index * entry)[0] not in (2, 3)
                for index in range(count)), "Dynamic scanner images are not admitted")


def recovery_stderr(raw, recovery, *, built):
    lines = raw.splitlines()
    require(0 < len(raw) <= 16384 and len(lines) == (3 if built else 1),
            "Capture stderr exceeded its exact protocol")
    require(json.loads(lines[0]) == {"recovery": recovery}
            and tuple(lines[1:]) == (CAPTURE_DIAGNOSTICS if built else ()),
            "Capture recovery/diagnostic protocol differs")


def process_environment(variables):
    environment = {key: value for key, value in variables.items()
                   if not key.startswith(("PIP_", "LD_", "DYLD_"))
                   and key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT"}}
    environment.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
                       PIP_CONFIG_FILE=os.devnull)
    return environment


def install_arguments(python, wheel):
    return [python, "-I", "-m", "pip", "--isolated", "--disable-pip-version-check", "--no-cache-dir",
            "install", "--no-index", "--no-deps", str(wheel)]


def run(arguments, *, cwd, timeout=30, stdout_limit=2 * 1024**2, stderr_limit=32 * 1024):
    """Bound both streams while reading; never log child output or command paths."""
    child = subprocess.Popen(list(map(str, arguments)), cwd=cwd, env=process_environment(os.environ),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {"stdout": stdout_limit, "stderr": stderr_limit}
    deadline = time.monotonic() + timeout
    completed = False
    try:
        with selectors.DefaultSelector() as selector:
            for stream, label in ((child.stdout, "stdout"), (child.stderr, "stderr")):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, label)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                require(remaining > 0, "Child process exceeded its deadline")
                for key, _ in selector.select(min(remaining, .25)):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    target = buffers[key.data]
                    require(len(target) + len(chunk) <= limits[key.data], "Child output exceeded its bound")
                    target.extend(chunk)
            remaining = deadline - time.monotonic()
            require(remaining > 0, "Child process exceeded its deadline")
            child.wait(timeout=remaining)
        completed = True
        return child.returncode, bytes(buffers["stdout"]), bytes(buffers["stderr"])
    finally:
        if not completed:
            # Do not reap/poll first: a dead leader can leave descendants holding
            # our pipes. Its unreaped PID still identifies this owned session.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        child.wait(timeout=5)
        child.stdout.close()
        child.stderr.close()


def git(*args):
    code, out, error = run(["git", *args], cwd=ROOT, timeout=15)
    require(code == 0 and not error, "Git source identity check failed")
    return out


def checkout_files(source_commit):
    require(git("rev-parse", "HEAD").decode().strip() == source_commit, "Checkout HEAD differs from source commit")
    require(not git("diff", "--name-only", "HEAD", "--"), "Checkout has modified tracked source files")
    require(not git("ls-files", "--others", "--exclude-standard", "--", *PACKAGES, "go"),
            "Checkout has untracked product/scanner source files")
    require(tomllib.loads(read_regular(ROOT / "pyproject.toml", 1024**2).decode("utf-8"))["project"]["scripts"]
            == ENTRY_POINTS, "Committed console entry points differ from reviewed installer authority")
    files = {}
    for record in git("ls-tree", "-rz", source_commit, "--", *PACKAGES).split(b"\0"):
        if not record:
            continue
        metadata, raw_name = record.split(b"\t", 1)
        mode, kind, object_id = metadata.split()
        name = raw_name.decode("utf-8")
        require(mode in {b"100644", b"100755"} and kind == b"blob", "Unsupported product source object")
        path = ROOT / name
        require(path.resolve().is_relative_to(ROOT), "Product source path escapes checkout")
        raw = read_regular(path, 64 * 1024**2)
        require(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest().encode() == object_id,
                "Product source bytes differ from committed checkout")
        files[name] = raw
    require(files and all(any(name.startswith(root + "/") for name in files) for root in PACKAGES),
            "Product source inventory is incomplete")
    return files, git("rev-parse", "HEAD^{tree}").decode().strip()


def wheel_product(raw, expected, version):
    """Pure wheel-input check against independently supplied committed bytes."""
    metadata_root = "rentgen_core-" + version + ".dist-info"
    expected_metadata = {metadata_root + "/" + name for name in
                         ("METADATA", "WHEEL", "entry_points.txt", "RECORD", "licenses/LICENSE")}
    actual, metadata, seen, expanded = {}, {}, set(), 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        require(0 < len(members) <= 4096, "Wheel member count is invalid")
        for member in members:
            name = member.orig_filename
            parts = PurePosixPath(name).parts
            require(name and "\0" not in name and "\\" not in name and not name.startswith("/")
                    and name == str(PurePosixPath(name)) + ("/" if member.is_dir() else "")
                    and all(part not in {".", ".."} for part in parts)
                    and name.casefold() not in seen, "Unsafe or duplicate wheel member")
            seen.add(name.casefold())
            require(stat.S_IFMT(member.external_attr >> 16) in (0, stat.S_IFREG, stat.S_IFDIR)
                    and 0 <= member.file_size <= 64 * 1024**2, "Unsupported wheel member")
            expanded += member.file_size
            require(expanded <= 256 * 1024**2, "Expanded wheel exceeds its bound")
            data = archive.read(member)
            require(len(data) == member.file_size, "Wheel member size differs")
            if member.is_dir():
                require(not data and any(item.startswith(name) for item in (*expected, *expected_metadata)),
                        "Unexpected wheel directory")
            elif parts[0] in PACKAGES:
                actual[name] = data
            else:
                require(name in expected_metadata, "Unexpected wheel payload outside product packages")
                metadata[name] = data
    require(actual == expected and set(metadata) == expected_metadata, "Wheel product bytes differ from checkout")
    value = BytesParser().parsebytes(metadata[metadata_root + "/METADATA"])
    require(value.get_all("Name") == ["rentgen-core"] and value.get_all("Version") == [version],
            "Wheel metadata name/version differs")
    try:
        points = configparser.ConfigParser(interpolation=None, strict=True)
        points.optionxform = str
        points.read_string(metadata[metadata_root + "/entry_points.txt"].decode("utf-8"))
        require(not points.defaults() and points.sections() == ["console_scripts"]
                and dict(points.items("console_scripts", raw=True)) == ENTRY_POINTS,
                "Wheel console entry points differ from reviewed installer authority")
    except (configparser.Error, UnicodeError):
        raise VerificationError("Wheel console entry point metadata is invalid") from None
    return sha(canonical([{ "path": name, "sha256": sha(data), "size_bytes": len(data)}
                          for name, data in sorted(actual.items())]))


def save(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def copy_owned(path, raw, mode):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode)
    with os.fdopen(descriptor, "wb") as stream:
        os.fchmod(stream.fileno(), mode)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    require(stat.S_IMODE(path.stat().st_mode) == mode and read_regular(path, max(1, len(raw))) == raw,
            "Owned artifact copy differs from verified input")


def state_records(state, project):
    with closing(sqlite3.connect(state.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        counts = {name: connection.execute("SELECT count(*) FROM " + name + " WHERE project_id=?", (project,)).fetchone()[0]
                  for name in ("snapshots", "publication_receipts", "snapshot_events", "snapshot_outbox")}
        catalogs = {row[0]: row[1:] for row in connection.execute(
            "SELECT snapshot_id,manifest_hash,source_digest,graph_hash,generation_relpath FROM snapshots WHERE project_id=?", (project,))}
    return counts, catalogs


def inspect_generation(state_root, project, publication, images, scanner_sha256):
    snapshot = publication["snapshot"]
    counts, catalogs = state_records(state_root / "state.sqlite3", project)
    row = catalogs[snapshot["snapshot_id"]]
    manifest_hash, source_digest, graph_hash, relative = row
    parts = PurePosixPath(relative).parts
    require(len(parts) == 2 and parts[0] == "generations" and parts[1] not in {".", ".."}
            and (re.fullmatch("[0-9a-f]{64}", parts[1]) or str(UUID(parts[1])) == parts[1]),
            "Catalog generation locator is invalid")
    root = state_root / relative
    manifest_raw = read_regular(root / "manifest.json", 8 * 1024**2)
    document = json.loads(manifest_raw)
    require(sha(manifest_raw) == manifest_hash == snapshot["manifest_hash"] == snapshot["snapshot_id"],
            "Catalog/manifest/snapshot identity differs")
    require(document["project_id"] == project == snapshot["project_id"]
            and sha(canonical(document["source"])) == source_digest == document["source_digest"]
            and document["graph"]["raw_sha256"] == graph_hash,
            "Catalog source/graph binding differs")
    require(document["capture"] == dict(bytes_immutable=True, method="working_tree_verified_passes_v1", temporal_atomicity="not_proven")
            and document["graph"]["identity_version"] == "source-path-v1"
            and document["graph"]["quality"] == "unavailable"
            and document["graph"]["adapter_version"] == "rentgen-captured-owned-go-v1"
            and document["graph"]["scanner_version"] == "rentgen-owned-scanner-linux-v1;sha256=" + scanner_sha256,
            "Capture/scanner/identity scope differs")
    require(all(layer["identity_status"] == "unresolved" and layer["configuration_uuid"] is None
                for layer in document["source"]["layers"]), "Capture fabricates metadata identity")
    expected = {"manifest.json": sha(manifest_raw), "graph.sqlite3": graph_hash}
    entries = document["source"]["entries"]
    require({entry["relative_path"] for entry in entries} == set(images)
            and all(entry["layer_id"] == "base" and entry["raw_sha256"] == sha(images[entry["relative_path"]])
                    and entry["size_bytes"] == len(images[entry["relative_path"]]) for entry in entries),
            "Captured source inventory differs from owned fixture")
    for name, raw in images.items():
        expected["sources/base/" + name] = sha(raw)
    for entry in document["derived_inputs"]:
        require(entry["relative_path"] in {"inputs/callgraph.ndjson", "inputs/scanner-coverage.json"}, "Unexpected derived input")
        expected[entry["relative_path"]] = entry["raw_sha256"]
    require(len(document["derived_inputs"]) == 2 and {entry["relative_path"] for entry in document["derived_inputs"]}
            == {"inputs/callgraph.ndjson", "inputs/scanner-coverage.json"}, "Incomplete derived inputs")
    allowed_directories = {str(parent) for name in expected for parent in PurePosixPath(name).parents
                           if str(parent) != "."}
    actual, actual_directories = {}, set()
    for path in root.rglob("*"):
        require(not path.is_symlink(), "Generation contains an alias")
        if path.is_file():
            require(path.relative_to(root).as_posix() in expected, "Generation contains an unlisted file")
            actual[path.relative_to(root).as_posix()] = sha(read_regular(path, 64 * 1024**2))
        else:
            relative_directory = path.relative_to(root).as_posix()
            require(path.is_dir() and relative_directory in allowed_directories, "Unexpected generation object")
            actual_directories.add(relative_directory)
    require(actual == expected and actual_directories == allowed_directories,
            "Generation exact file/directory inventory or bytes differ")
    return dict(snapshot_id=snapshot["snapshot_id"], manifest_sha256=manifest_hash,
                source_digest=source_digest, graph_sha256=graph_hash,
                publication_receipt_sha256=sha(canonical(publication)),
                files=len(expected), source_files=len(images), counts=counts)


def verify(wheel, scanner, scanner_sha256, output, expected_version, source_commit):
    host()  # Before input IO or output creation; never fake a Linux runtime.
    labels(expected_version, source_commit, scanner_sha256)
    wheel = Path(wheel).absolute()
    require(wheel.name == "rentgen_core-" + expected_version + "-py3-none-any.whl", "Unexpected wheel filename")
    wheel_raw = read_regular(wheel, 64 * 1024**2)
    product, source_tree = checkout_files(source_commit)
    product_digest = wheel_product(wheel_raw, product, expected_version)
    scanner_raw = read_regular(Path(scanner).absolute(), 32 * 1024**2)
    require(sha(scanner_raw) == scanner_sha256, "Scanner digest differs from explicit trusted hash")
    static_scanner(scanner_raw)
    output = Path(output).absolute()
    output = output.parent.resolve(strict=True) / output.name
    output.mkdir(mode=0o700, exist_ok=False)
    require(stat.S_IMODE(output.stat().st_mode) == 0o700, "New output must be private 0700")
    workspace = output / "work"
    workspace.mkdir(mode=0o700)
    wheel_directory = output / "wheel"
    wheel_directory.mkdir(mode=0o700)
    owned_wheel = wheel_directory / wheel.name
    copy_owned(owned_wheel, wheel_raw, 0o600)
    product_record = output / "installed-product-inputs.json"
    save(product_record, {name: sha(raw) for name, raw in sorted(product.items())})
    environment = output / "environment"
    code, _, _ = run([sys.executable, "-I", "-m", "venv", str(environment)], cwd=workspace, timeout=90)
    require(code == 0, "Fresh venv creation failed")
    python = environment / "bin/python"
    code, _, _ = run(install_arguments(python, owned_wheel), cwd=workspace, timeout=60)
    require(code == 0, "Exact offline wheel installation failed")
    probe = """
import hashlib,importlib.metadata,json,rentgen_core,rentgen_graph,rentgen_diagnostics,sys
from pathlib import Path
modules=(rentgen_core,rentgen_graph,rentgen_diagnostics)
prefix=Path(sys.prefix).resolve(); root=Path(rentgen_core.__file__).resolve().parent.parent
expected=json.loads(Path(sys.argv[1]).read_text())
actual={}
for module in modules:
    for path in Path(module.__file__).resolve().parent.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc','.pyo'}:
            actual[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
print(json.dumps({'version':importlib.metadata.version('rentgen-core'),
    'installed':all(Path(m.__file__).resolve().is_relative_to(prefix) for m in modules),
    'product_bytes':actual==expected,'prefix':str(prefix)}))
"""
    code, out, error = run([python, "-I", "-c", probe, product_record], cwd=workspace, timeout=15)
    require(code == 0 and not error and json.loads(out) == dict(version=expected_version, installed=True,
            product_bytes=True, prefix=str(environment.resolve())),
            "Product modules are not isolated under the fresh venv")
    owned_scanner = output / "bsl-scan"
    copy_owned(owned_scanner, scanner_raw, 0o700)
    checks = []
    def cli(command, *arguments, expected=0, error_code=None, recovery=None, built=False):
        code, out, error = run([python, "-I", "-m", "rentgen_core", command, *arguments], cwd=workspace, timeout=120)
        require(code == expected, "Installed CLI exit differs: " + command)
        if recovery is None:
            require(not error, "Unexpected installed CLI stderr: " + command)
        else:
            recovery_stderr(error, recovery, built=built)
        value = json.loads(out)
        if error_code is not None:
            require(set(value) == {"error"} and value["error"]["code"] == error_code,
                    "Installed CLI refusal differs: " + command)
        else:
            require(set(value) == {"result", "request_id"}, "Installed CLI envelope differs: " + command)
        checks.append(dict(command=command, exit=code, recovery_json=recovery is not None,
                           fixed_diagnostic_lines=2 if built else 0))
        return value.get("result")

    profile, registry, state_root = workspace / "profile/identity.json", workspace / "registry.sqlite3", workspace / "state"
    source = workspace / "source"
    source.mkdir(mode=0o700)
    for name, raw in IMAGES.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    cli("identity-init", "--identity-profile", profile)
    common = ["--registry", registry, "--identity-profile", profile]
    cli("registry-init", *common)
    project = cli("project-register", *common, "--source-root", source, "--state-root", state_root,
                  "--name", "Installed Linux capture fixture")["project_id"]
    selected = [*common, "--project", project]
    original_head = cli("project-head", *selected)
    original_configuration = cli("layers-get", *selected)
    require(original_head == dict(project_id=project, revision=0, snapshot=None, source_revision=1)
            and original_configuration["revision"] == 1 and len(original_configuration["layers"]) == 1
            and original_configuration["layers"][0]["layer_id"] == "base", "Initial default project state differs")
    head0 = workspace / "head-0.json"; save(head0, original_head)
    op1, op2 = str(uuid4()), str(uuid4())
    scanner_arguments = ["--scanner", owned_scanner, "--scanner-sha256", scanner_sha256]
    def capture(operation, head, head_file, *scanner_args, **options):
        return cli("capture", *selected, "--operation-id", operation, "--expected-head-json", head_file,
                   *scanner_args, recovery=dict(operation_id=operation, expected_head=head),
                   built=bool(scanner_args) and options.get("expected", 0) == 0, **options)
    first = capture(op1, original_head, head0, *scanner_arguments)
    require(first["operation_id"] == op1 and first["publication"] == "committed"
            and first["head"]["revision"] == 1 and first["head"]["snapshot"] == first["snapshot"]
            and first["head"]["source_revision"] == 1, "First capture receipt differs")
    require(cli("project-head", *selected) == first["head"]
            and cli("publication-receipt", *selected, "--operation-id", op1) == first, "First durable receipt/head differs")
    first_binding = inspect_generation(state_root, project, first, IMAGES, scanner_sha256)
    require(set(first_binding["counts"].values()) == {1}, "First publication counts differ")
    reference_files = {}
    def read_snapshot(snapshot, images):
        page = cli("source-list", *selected, "--snapshot", snapshot["snapshot_id"], "--limit", "200")
        require(page["next_cursor"] is None and len(page["entries"]) == len(images), "Source inventory page differs")
        refs = {}
        for entry in page["entries"]:
            ref = entry["ref"]; name = ref["relative_path"]
            require(name in images and ref["snapshot"] == snapshot and ref["layer_id"] == "base"
                    and ref["raw_sha256"] == sha(images[name]) and entry["size_bytes"] == len(images[name]), "SourceRef binding differs")
            key = (snapshot["snapshot_id"], name)
            if key not in reference_files:
                reference_files[key] = workspace / ("ref-" + sha(canonical(ref)) + ".json")
                save(reference_files[key], ref)
            result = cli("source-read", *selected, "--snapshot", snapshot["snapshot_id"],
                         "--source-ref-json", reference_files[key], "--base64")
            import base64
            raw = base64.b64decode(result["data"], validate=True)
            require(result["ref"] == ref and result["encoding"] == "base64"
                    and result["raw_sha256"] == sha(raw) == ref["raw_sha256"]
                    and result["size_bytes"] == len(raw) and raw == images[name], "Installed source bytes differ")
            refs[name] = ref
        require(set(refs) == set(images), "Source paths are incomplete")
        return refs
    def graph(snapshot, refs):
        def query(command, name, *extra):
            value = cli(command, *selected, "--snapshot", snapshot["snapshot_id"],
                "--source-ref-json", reference_files[(snapshot["snapshot_id"], name)], *extra)
            require(value["project_id"] == project and value["snapshot_id"] == snapshot["snapshot_id"]
                    and value["manifest_hash"] == snapshot["manifest_hash"]
                    and value["capabilities"]["identity"] == "source_path_only"
                    and value["capabilities"]["quality"] == "unavailable"
                    and value["capabilities"]["temporal_atomicity"] == "not_proven", "Graph envelope binding differs")
            return value
        resolved = query("graph-resolve", CALLER)
        impact = query("impact", CALLEE, "--depth", "5")
        require(any(row["source_path"] == "base/" + CALLER for row in resolved["result"]["graph_modules"]), "Caller module is absent from graph")
        require(impact["result"]["complete"] and impact["result"]["total"] >= 1
                and any(edge["caller"] == "Caller" and edge["callee"] == "Target"
                        and edge["caller_source_path"] == "base/" + CALLER
                        and edge["callee_source_path"] == "base/" + CALLEE
                        for edge in impact["result"]["edges"]), "Nontrivial Caller-to-Callee impact is absent")
        return dict(resolve_sha256=sha(canonical(resolved)), impact_sha256=sha(canonical(impact)))
    first_refs = read_snapshot(first["snapshot"], IMAGES)
    first_graph = graph(first["snapshot"], first_refs)
    changed = dict(IMAGES)
    changed[CALLER] = b"// second owned capture\n" + IMAGES[CALLER]
    for name in ("data.xml", "binary.bin"):
        del changed[name]; (source / name).unlink()
    (source / CALLER).write_bytes(changed[CALLER])
    require(read_snapshot(first["snapshot"], IMAGES) == first_refs
            and graph(first["snapshot"], first_refs) == first_graph
            and cli("project-head", *selected) == first["head"], "Live mutation changed retained snapshot reads")
    head1 = workspace / "head-1.json"; save(head1, first["head"])
    second = capture(op2, first["head"], head1, *scanner_arguments)
    require(second["operation_id"] == op2 and second["publication"] == "committed"
            and second["head"]["revision"] == 2 and second["head"]["source_revision"] == 1
            and second["snapshot"] != first["snapshot"] and second["head"]["snapshot"] == second["snapshot"], "Second capture did not advance head")
    require(cli("project-head", *selected) == second["head"]
            and cli("publication-receipt", *selected, "--operation-id", op2) == second, "Second durable receipt/head differs")
    second_binding = inspect_generation(state_root, project, second, changed, scanner_sha256)
    require(set(second_binding["counts"].values()) == {2}, "Second publication counts differ")
    read_snapshot(second["snapshot"], changed)
    require(read_snapshot(first["snapshot"], IMAGES) == first_refs
            and graph(first["snapshot"], first_refs) == first_graph, "Historical snapshot changed after new head")
    source.rename(workspace / "live-source-after-two")
    owned_scanner.rename(output / "scanner-after-two")
    require(not source.exists() and not owned_scanner.exists(), "Replay inputs were not made absent")
    require(capture(op1, original_head, head0) == first
            and cli("publication-receipt", *selected, "--operation-id", op1) == first, "Exact operation replay changed its durable receipt")
    forged = dict(first_refs[CALLER], raw_sha256="0" * 64)
    forged_path = workspace / "forged-ref.json"; save(forged_path, forged)
    cli("source-read", *selected, "--snapshot", first["snapshot"]["snapshot_id"], "--source-ref-json", forged_path,
        "--base64", expected=2, error_code="SOURCE_REF_MISMATCH")
    head2 = workspace / "head-2.json"; save(head2, second["head"])
    capture(op1, second["head"], head2, expected=2, error_code="OPERATION_CONFLICT")
    capture(str(uuid4()), original_head, head0, *scanner_arguments, expected=2, error_code="HEAD_CONFLICT")
    require(cli("project-head", *selected) == second["head"]
            and cli("layers-get", *selected) == original_configuration
            and cli("publication-receipt", *selected, "--operation-id", op1) == first
            and cli("publication-receipt", *selected, "--operation-id", op2) == second
            and state_records(state_root / "state.sqlite3", project)[0] == second_binding["counts"], "Replay/refusal changed publication state")
    require(inspect_generation(state_root, project, first, IMAGES, scanner_sha256)["manifest_sha256"] == first_binding["manifest_sha256"], "Replay changed historical generation")
    probe_spec = importlib.util.spec_from_file_location("generation_delivery_probe",
        Path(__file__).with_name("generation_delivery_probe.py"))
    probe = importlib.util.module_from_spec(probe_spec)
    probe_spec.loader.exec_module(probe)
    generation_diagnostics = probe.verify(
        lambda name, *args, **kwargs: cli(name, *selected, *args, **kwargs),
        state_root, source, first, second)
    receipt = dict(schema=1, scope="actual Linux/amd64 installed CLI synthetic capture/restart/history/replay fixture only",
        source_commit=source_commit, source_tree=source_tree, version=expected_version,
        wheel=dict(sha256=sha(wheel_raw), size_bytes=len(wheel_raw), product_files=len(product), product_source_inventory_sha256=product_digest),
        scanner=dict(sha256=scanner_sha256, size_bytes=len(scanner_raw), static_amd64_elf=True, owned_mode="rentgen-owned-scanner-linux-v1"),
        isolated_installed_core_and_graph=True, installed_product_bytes_equal_checkout=True,
        every_cli_call_fresh_isolated_process=True,
        input_bindings=dict(original_head_sha256=sha(canonical(original_head)),
            source_configuration_sha256=sha(canonical(original_configuration)),
            original_fixture_sha256=sha(canonical({name: sha(raw) for name, raw in sorted(IMAGES.items())})),
            changed_fixture_sha256=sha(canonical({name: sha(raw) for name, raw in sorted(changed.items())}))),
        first=first_binding, second=second_binding, original_graph=first_graph, checks=checks,
        generation_diagnostics=generation_diagnostics,
        outcomes=dict(capture=True, fresh_process_reads=True, historical_snapshot=True,
            live_mutation_independent=True, replay_without_source_or_scanner=True,
            forged_ref_refused=True, stale_operation_refused=True, stale_head_refused=True,
            publication_receipts_stable=True, source_configuration_unchanged=True),
        limitations=["No full Linux or 100000-file/performance qualification", "No native 1C/EDT, model, optional MCP or SDK closure qualification", "Source-path identity only; temporal atomicity not proven", "Owned synthetic fixtures retained; no user profile or project touched"])
    save(output / "acceptance.json", receipt)
    print(json.dumps(receipt, indent=2))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("wheel", "scanner", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("scanner-sha256", "expected-version", "source-commit"):
        parser.add_argument("--" + name, required=True)
    arguments = parser.parse_args(argv)
    try:
        verify(**vars(arguments))
    except Exception as exc:
        message = str(exc) if type(exc) is VerificationError else type(exc).__name__
        parser.exit(1, "Installed Linux capture verification failed: " + message + "\n")


if __name__ == "__main__":
    main()
