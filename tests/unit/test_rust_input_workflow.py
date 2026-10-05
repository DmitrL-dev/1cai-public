"""Actual Rust/Python parity and isolated Linux submitted-export acceptance."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import threading
import time
import zipfile

import pytest

from rentgen_core import cli
from rentgen_core.errors import CoreError
from rentgen_core.local import LocalRuntime
from rentgen_core.local_identity import current_local_principal
from rentgen_core.rust_input import RustInputSession
from rentgen_core.submitted_export import analyze_export
from test_metadata_three_way_materialize import PATH, xml
from test_portable_local_workflow import portable_project, command, ROOT

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Experimental Rust import is Linux-only")


@pytest.fixture(scope="module")
def binary(tmp_path_factory):
    configured = os.environ.get("RENTGEN_INPUT_CORE_TEST_BINARY")
    if not configured:
        pytest.skip("Build Rust input-core and set RENTGEN_INPUT_CORE_TEST_BINARY")
    source = Path(configured).resolve(strict=True)
    path = tmp_path_factory.mktemp("input-core-bin") / "rentgen-input-core"
    shutil.copyfile(source, path); path.chmod(0o700)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def zip_bytes(files, compression=zipfile.ZIP_DEFLATED):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return output.getvalue()


@pytest.fixture
def exported(portable_project):
    profile, registry, project, source, common = portable_project
    files = {
        PATH: xml("<Code>ARTICLE</Code>"),
        "Catalogs/Other.xml": xml("<Code>OTHER</Code>", name="Other"),
        "CommonModules/Shared/Ext/Module.bsl": "Процедура Тест()\nКонецПроцедуры\n".encode(),
        "assets/readme.txt": b"opaque asset\x00\xff",
    }
    path = registry.parent / "export.zip"; path.write_bytes(zip_bytes(files))
    return path, hashlib.sha256(path.read_bytes()).hexdigest(), files


def context(project):
    profile, registry, project_id, _, _ = project
    principal = current_local_principal(identity_profile=profile)
    return LocalRuntime(registry).state_context(principal, project_id)


def options(binary, exported):
    return {"input_core": binary[0], "input_core_sha256": binary[1], "archive": exported[0], "archive_sha256": exported[1]}


def test_real_rust_session_parity_and_immutable_read_after_path_replacement(binary, exported):
    path, digest, files = exported
    expected = {name: (data, hashlib.sha256(data).hexdigest()) for name, data in files.items()}
    # Standard-library ZIP is a test oracle only, never a production fallback.
    with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as oracle:
        assert {name: oracle.read(name) for name in oracle.namelist()} == files
    with RustInputSession(*binary, authorize=lambda: None) as session:
        manifest = session.open_import(path, digest)
        entries = session.entries(manifest)
        assert manifest["files_count"] == len(files)
        assert manifest["total_bytes"] == sum(map(len, files.values()))
        saved_process = session.process
        replacement = path.with_suffix(".new"); replacement.write_bytes(b"changed after acceptance")
        os.replace(replacement, path)
        for entry in entries:
            assert session.read_entry(entry) == expected[entry["path"]][0]
            assert session.read_entry(entry) == expected[entry["path"]][0]
            assert entry["raw_sha256"] == expected[entry["path"]][1]
    assert saved_process.returncode == 0


def test_real_cli_ready_export_summary_query_and_unchanged_project(binary, exported, portable_project):
    archive, digest, files = exported
    profile, registry, project, source, common = portable_project
    sentinel = source / "foreign.bsl"
    before = sentinel.read_bytes()
    args = ["export-analyze", *common, "--project", project, "--archive", archive, "--archive-sha256", digest, "--input-core", binary[0], "--input-core-sha256", binary[1]]
    code, response = command(*args)
    assert code == 0, response
    result = response["result"]
    assert result["scope"] == "submitted_designer_export"
    assert result["counts"] == {"files": 4, "metadata_candidates": 2, "metadata_objects": 2, "unsupported_metadata_roots": 0, "modules": 1, "other_files": 1}
    assert result["by_type"] == {"Catalog": 2}
    assert result["coverage"]["published_snapshot"] is False
    assert all("snapshot" not in row["input_ref"] for row in result["objects"])
    assert command(*args)[1]["result"] == result
    selected = command(*args, "--query", "other", "--limit", "1")[1]["result"]
    assert selected["matching_objects"] == 1 and selected["objects"][0]["name"] == "Other"
    assert sentinel.read_bytes() == before
    assert command("project-head", *common, "--project", project)[1]["result"]["snapshot"] is None


def test_permission_denied_before_process_or_archive_access(portable_project, monkeypatch):
    ctx = context(portable_project)
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        tx._connection.execute("DELETE FROM membership_permissions WHERE permission='analysis:run'")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("Forbidden child launch"))
    with pytest.raises(CoreError) as error:
        analyze_export(ctx, archive="missing", archive_sha256="a" * 64, input_core="missing", input_core_sha256="a" * 64)
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_revocation_after_verified_read_discards_result_and_reaps_child(binary, exported, portable_project, monkeypatch):
    ctx = context(portable_project)
    original = RustInputSession.read_entry
    owned = []
    def revoke(session, entry):
        raw = original(session, entry)
        owned.append(session.process)
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            tx._connection.execute("DELETE FROM membership_permissions WHERE permission='project:read'")
        return raw
    monkeypatch.setattr(RustInputSession, "read_entry", revoke)
    with pytest.raises(CoreError) as error:
        analyze_export(ctx, **options(binary, exported))
    assert error.value.code == "PROJECT_FORBIDDEN"
    assert owned and all(p.poll() is not None for p in owned)


def test_revoked_parser_error_does_not_expose_original_diagnostic(binary, exported, portable_project, monkeypatch):
    import rentgen_core.submitted_export as module
    ctx = context(portable_project)
    def denied_parser(raw):
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            tx._connection.execute("DELETE FROM membership_permissions WHERE permission='project:read'")
        raise CoreError("XML_INVALID", "PRIVATE_ARCHIVE_DIAGNOSTIC")
    monkeypatch.setattr(module, "parse_xml", denied_parser)
    with pytest.raises(CoreError) as error:
        analyze_export(ctx, **options(binary, exported))
    assert error.value.code == "PROJECT_FORBIDDEN"
    assert "PRIVATE" not in str(error.value)


def test_final_cli_serialization_rechecks_permission(binary, exported, portable_project, monkeypatch, capsys):
    ctx = context(portable_project)
    original = json.dumps
    revoked = []
    def serialize(value, *a, **kw):
        encoded = original(value, *a, **kw)
        if not revoked and isinstance(value, dict) and isinstance(value.get("result"), dict) and value["result"].get("scope") == "submitted_designer_export":
            with ctx.state.transaction(ctx.principal, write=True) as tx:
                tx._connection.execute("DELETE FROM membership_permissions WHERE permission='project:read'")
            revoked.append(True)
        return encoded
    monkeypatch.setattr(json, "dumps", serialize)
    _, _, project, _, common = portable_project
    argv = ["export-analyze", *common, "--project", project, "--archive", exported[0], "--archive-sha256", exported[1], "--input-core", binary[0], "--input-core-sha256", binary[1]]
    assert cli.main(list(map(str, argv))) == 2
    output = capsys.readouterr()
    assert json.loads(output.out)["error"]["code"] == "PROJECT_FORBIDDEN"
    assert "Products" not in output.out


@pytest.mark.parametrize("defect", ["hash", "truncated", "leaf_symlink", "ancestor_symlink", "hardlink", "fifo", "traversal", "duplicate", "unicode_alias", "case_alias", "directory_file_alias", "symlink_entry", "xml_entity"])
def test_real_rust_and_cli_reject_hostile_inputs(binary, portable_project, tmp_path, defect):
    path = tmp_path / "input.zip"
    raw = zip_bytes({PATH: xml()})
    path.write_bytes(raw)
    expected = hashlib.sha256(raw).hexdigest()
    if defect == "hash":
        expected = "0" * 64
    elif defect == "truncated":
        path.write_bytes(raw[:-12]); expected = hashlib.sha256(path.read_bytes()).hexdigest()
    elif defect == "leaf_symlink":
        target = tmp_path / "target.zip"; path.rename(target); path.symlink_to(target)
    elif defect == "ancestor_symlink":
        actual = tmp_path / "actual"; actual.mkdir(); path.rename(actual / "input.zip")
        alias = tmp_path / "alias"; alias.symlink_to(actual, target_is_directory=True); path = alias / "input.zip"
    elif defect == "hardlink":
        os.link(path, tmp_path / "other.zip")
    elif defect == "fifo":
        path.unlink(); os.mkfifo(path)
    elif defect == "duplicate":
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as z:
            z.writestr(PATH, xml())
            with pytest.warns(UserWarning, match="Duplicate name"):
                z.writestr(PATH, xml())
        path.write_bytes(output.getvalue()); expected = hashlib.sha256(path.read_bytes()).hexdigest()
    elif defect == "symlink_entry":
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as z:
            item = zipfile.ZipInfo("link"); item.create_system = 3; item.external_attr = (0o120777 << 16)
            z.writestr(item, "../outside")
        path.write_bytes(output.getvalue()); expected = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        files = {
            "traversal": {"../outside": b"bad"},
            "unicode_alias": {"Straße.xml": b"one", "STRASSE.xml": b"two"},
            "case_alias": {"a.xml": b"one", "A.xml": b"two"},
            "directory_file_alias": {"a": b"one", "a/b.xml": b"two"},
            "xml_entity": {PATH: b'<!DOCTYPE x [<!ENTITY y "ENTITY">]><MetaDataObject>&y;</MetaDataObject>'},
        }[defect]
        path.write_bytes(zip_bytes(files)); expected = hashlib.sha256(path.read_bytes()).hexdigest()
    ctx = context(portable_project)
    with pytest.raises(CoreError) as error:
        analyze_export(ctx, **options(binary, (path, expected, {})))
    assert error.value.code.startswith(("IMPORT_", "XML_", "SOURCE_")), error.value
    assert not (tmp_path.parent / "outside").exists()


def test_keyboard_interrupt_reaps_exact_owned_process(binary, exported, portable_project, monkeypatch):
    owned = []
    original = RustInputSession.read_entry
    def interrupt(session, entry):
        original(session, entry); owned.append(session.process)
        raise KeyboardInterrupt()
    monkeypatch.setattr(RustInputSession, "read_entry", interrupt)
    with pytest.raises(KeyboardInterrupt):
        analyze_export(context(portable_project), **options(binary, exported))
    assert owned and all(process.poll() is not None for process in owned)


def test_concurrent_writer_never_changes_accepted_bytes(binary, tmp_path):
    files = {"data.bin": os.urandom(1024 * 1024)}
    raw = zip_bytes(files, zipfile.ZIP_STORED)
    path = tmp_path / "racing.zip"; path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    stop = threading.Event()
    def mutate():
        while not stop.is_set():
            with path.open("r+b") as stream:
                stream.seek(30); stream.write(b"changed during import")
                stream.flush()
            time.sleep(.001)
            with path.open("r+b") as stream:
                stream.seek(0); stream.write(raw); stream.truncate(); stream.flush()
    writer = threading.Thread(target=mutate); writer.start()
    try:
        for _ in range(4):
            try:
                with RustInputSession(*binary, authorize=lambda: None) as session:
                    manifest = session.open_import(path, digest)
                    entries = session.entries(manifest)
                    assert manifest["input_sha256"] == digest
                    assert session.read_entry(entries[0]) == files["data.bin"]
            except CoreError as error:
                assert error.code in {"IMPORT_INPUT_CHANGED", "IMPORT_HASH_MISMATCH"}, error
    finally:
        stop.set(); writer.join(timeout=5)
    assert not writer.is_alive()


def test_pinned_executable_hash_and_symlink_rejected_before_launch(binary, monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("Invalid executable launch"))
    with pytest.raises(CoreError) as error:
        with RustInputSession(binary[0], "0" * 64, authorize=lambda: None):
            pass
    assert error.value.code == "INPUT_CORE_EXECUTABLE_INVALID"
    link = tmp_path / "core-link"; link.symlink_to(binary[0])
    with pytest.raises(OSError):
        with RustInputSession(link, binary[1], authorize=lambda: None):
            pass


@pytest.mark.parametrize("files", [{}, {"Catalogs/Products/Products.mdo": b"<Catalog/>"}, {"wrapped/" + PATH: xml()}])
def test_no_designer_evidence_is_not_reported_as_success(binary, portable_project, tmp_path, files):
    path = tmp_path / "unsupported.zip"; path.write_bytes(zip_bytes(files))
    with pytest.raises(CoreError) as error:
        analyze_export(context(portable_project), **options(binary, (path, hashlib.sha256(path.read_bytes()).hexdigest(), files)))
    assert error.value.code == "IMPORTED_EXPORT_UNSUPPORTED"


@pytest.mark.parametrize("defect", ["utf16", "oversized", "truncated", "duplicate", "late_stdout", "late_stderr", "exit_failure"])
def test_fake_sidecar_protocol_faults_never_escape_as_success(tmp_path, defect):
    # Executable fixtures are isolated, explicitly hash-pinned test inputs.
    script = tmp_path / "fake-core"
    source = '''#!/usr/bin/python3
import json,struct,sys,time
mode=MODE
hello={"protocol":1,"kind":"hello","implementation":"rentgen-input-core","contract":"submitted-zip-v1"}
def send(value):
 raw=json.dumps(value,separators=(",",":")).encode()
 sys.stdout.buffer.write(struct.pack("<I",len(raw))+raw);sys.stdout.buffer.flush()
if mode=="oversized":
 sys.stdout.buffer.write(struct.pack("<I",0xffffffff));sys.stdout.buffer.flush();sys.exit()
if mode=="truncated":
 sys.stdout.buffer.write(struct.pack("<I",50)+b"{");sys.stdout.buffer.flush();sys.exit()
if mode in ("utf16","duplicate"):
 raw=json.dumps(hello).encode("utf-16") if mode=="utf16" else b'{"protocol":1,"protocol":1,"kind":"hello","implementation":"rentgen-input-core","contract":"submitted-zip-v1"}'
 sys.stdout.buffer.write(struct.pack("<I",len(raw))+raw);sys.stdout.buffer.flush();sys.exit()
send(hello)
size=struct.unpack("<I",sys.stdin.buffer.read(4))[0];request=json.loads(sys.stdin.buffer.read(size))
send({"protocol":1,"seq":request["seq"],"result":{"closed":True}})
time.sleep(.02)
if mode=="late_stdout":sys.stdout.buffer.write(b"PRIVATE_UNFRAMED_DATA");sys.stdout.buffer.flush()
if mode=="late_stderr":sys.stderr.write("PRIVATE_DIAGNOSTIC"*6000);sys.stderr.flush()
if mode=="exit_failure":sys.exit(1)
'''.replace("MODE", repr(defect))
    script.write_text(source); script.chmod(0o700)
    digest = hashlib.sha256(script.read_bytes()).hexdigest()
    session = RustInputSession(script, digest, authorize=lambda: None)
    with pytest.raises(CoreError) as error:
        with session:
            pass
    assert error.value.code.startswith("INPUT_CORE_")
    assert "PRIVATE" not in str(error.value)
    assert session.process is not None and session.process.poll() is not None


def test_parent_death_kills_sidecar_during_owned_session(binary, tmp_path):
    # An isolated subreaper observes the orphaned child's actual exit; this does
    # not change pytest's or the host's process-supervision configuration.
    driver = tmp_path / "parent_death.py"
    driver.write_text('''import ctypes,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
libc=ctypes.CDLL(None,use_errno=True)
assert libc.prctl(36,1,0,0,0)==0
code="from rentgen_core.rust_input import RustInputSession;import sys,time;session=RustInputSession(sys.argv[1],sys.argv[2],authorize=lambda:None);session.__enter__();print(session.process.pid,flush=True);time.sleep(60)"
parent=subprocess.Popen([sys.executable,"-c",code,sys.argv[1],sys.argv[2]],stdout=subprocess.PIPE,text=True)
child=int(parent.stdout.readline())
parent.kill();parent.wait(timeout=5)
end=time.monotonic()+5
while time.monotonic()<end:
 observed,status=os.waitpid(child,os.WNOHANG)
 if observed:
  assert os.WIFSIGNALED(status) and os.WTERMSIG(status)==signal.SIGKILL
  print(json.dumps({"parent_reaped":True,"sidecar_reaped":True,"signal":"SIGKILL"}));break
 time.sleep(.01)
else:
 os.kill(child,signal.SIGKILL);os.waitpid(child,0);raise RuntimeError("Parent-death signal failed")
''')
    result = subprocess.run([sys.executable, str(driver), str(binary[0]), binary[1]], cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert json.loads(result.stdout)["sidecar_reaped"] is True


def test_verified_executable_copy_is_sealed_against_later_original_changes(tmp_path):
    from contextlib import ExitStack
    from rentgen_core.rust_input import _executable
    import fcntl
    path = tmp_path / "original-executable"
    original = b"#!/usr/bin/python3\nprint('original image')\n"
    path.write_bytes(original); path.chmod(0o700)
    with ExitStack() as stack:
        image = _executable(path, hashlib.sha256(original).hexdigest(), stack)
        path.write_bytes(b"changed executable after copy")
        os.lseek(image, 0, os.SEEK_SET)
        assert os.read(image, 1024) == original
        assert fcntl.fcntl(image, getattr(fcntl, "F_GET_SEALS", 1034)) & 0x0f == 0x0f
        with pytest.raises(OSError):
            os.write(image, b"tampered")
        with pytest.raises(OSError):
            os.ftruncate(image, 1)
        result = subprocess.run([f"/proc/self/fd/{image}"], pass_fds=(image,), capture_output=True, text=True, timeout=5)
        assert result.returncode == 0 and result.stdout == "original image\n"


@pytest.mark.parametrize("name", ["CON/", "NUL.txt/", "COM1/", "LPT¹/", "bad?.txt/", "bad|dir/", "bad<dir/", 'bad"dir/'])
def test_directory_only_entries_obey_portable_path_policy(binary, portable_project, tmp_path, name):
    path = tmp_path / "reserved-directory.zip"
    path.write_bytes(zip_bytes({PATH: xml(), name: b""}, zipfile.ZIP_STORED))
    with pytest.raises(CoreError) as error:
        analyze_export(context(portable_project), **options(binary, (path, hashlib.sha256(path.read_bytes()).hexdigest(), {})))
    assert error.value.code.startswith("IMPORT_")


@pytest.mark.parametrize("placement", ["comment", "payload"])
def test_narrow_profile_rejects_alternate_eocd_before_library_allocation(binary, portable_project, tmp_path, placement):
    path = tmp_path / "alternate-eocd.zip"
    fake_eocd = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 50000, 50000, 0, 0, 0)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(PATH, xml())
        archive.writestr("assets/payload.bin", b"a" * 70000 + (fake_eocd if placement == "payload" else b""))
        if placement == "comment":
            archive.comment = fake_eocd + b"x"
    with pytest.raises(CoreError) as error:
        analyze_export(context(portable_project), **options(binary, (path, hashlib.sha256(path.read_bytes()).hexdigest(), {})))
    assert error.value.code.startswith("IMPORT_")


def test_valid_stored_directory_fixture_is_accepted(binary, portable_project, tmp_path):
    path = tmp_path / "valid-directory.zip"
    path.write_bytes(zip_bytes({PATH: xml(), "Catalogs/": b"", "Empty/": b""}, zipfile.ZIP_STORED))
    result = analyze_export(context(portable_project), **options(binary, (path, hashlib.sha256(path.read_bytes()).hexdigest(), {})))
    assert result["counts"]["metadata_objects"] == 1
    assert result["input"]["entries_count"] == 3 and result["input"]["files_count"] == 1
