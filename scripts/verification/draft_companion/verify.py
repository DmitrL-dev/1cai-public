"""Run an installed Windows Core and checkout Companion against one draft store."""
import argparse
import base64
from dataclasses import asdict
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

PACKAGES = ("rentgen_core", "rentgen_graph", "rentgen_diagnostics")
COMPANION = "integrations/vscode-rentgen/lib"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bind_checkout(checkout, expected, trigger_head):
    if any(not re.fullmatch(r"[0-9a-f]{40}", value) for value in (expected, trigger_head)):
        raise ValueError("Both checkout and triggering HEAD must be exact commit SHAs")
    commit = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], timeout=10).decode().strip()
    if commit != expected:
        raise ValueError("Checkout commit does not match the CI event")
    tree = subprocess.check_output(["git", "-C", str(checkout), "ls-tree", "-rz", commit,
                                   "--", *PACKAGES, COMPANION, "LICENSE"], timeout=10)
    files = {}
    for record in tree.split(b"\0"):
        if not record:
            continue
        metadata, encoded_name = record.split(b"\t", 1)
        mode, kind, blob = metadata.decode().split()
        name = encoded_name.decode("utf-8")
        if kind != "blob" or mode not in ("100644", "100755"):
            raise ValueError("Expected ordinary tracked source files")
        path = checkout / name
        if path.is_symlink():
            raise ValueError("Source symlinks are not accepted")
        raw = path.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if actual != blob:
            raise ValueError("Raw checkout bytes differ from Git: " + name)
        files[name] = {"git_blob": blob, "sha256": hashlib.sha256(raw).hexdigest()}
    if not files or not any(name.startswith(COMPANION + "/") for name in files):
        raise ValueError("Missing bound Companion source")
    return {"checkout_commit": commit, "trigger_head": trigger_head, "files": files,
            "scope": "actual CI checkout; on pull_request this may be GitHub's test merge"}


def prepare_fixture(manifest_file, root, scanner):
    if os.name != "nt":
        raise RuntimeError("Windows is required; no emulated adapter or skipped success")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    bound_packages = {}
    for name in PACKAGES:
        package = Path(importlib.import_module(name).__file__).resolve().parent
        prefix = name + "/"
        expected = {key[len(prefix):]: item["sha256"] for key, item in manifest["files"].items()
                    if key.startswith(prefix) and key.endswith(".py")}
        actual = {path.relative_to(package).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in package.rglob("*.py")}
        if not expected or actual != expected:
            changed = sorted(key for key in set(actual) | set(expected)
                             if actual.get(key) != expected.get(key))
            raise RuntimeError("Installed package differs from checkout: " + name + ": " + ", ".join(changed))
        bound_packages[name] = len(expected)
    import rentgen_core as core
    from rentgen_core.local_identity import current_local_principal
    from rentgen_graph.snapshot_adapter import RentgenCapturedGoBuilder, RentgenGraphReaderFactory

    root = root.resolve(strict=True)
    scanner = scanner.resolve(strict=True)
    if not scanner.is_file():
        raise ValueError("Expected the existing kit scanner")
    source = root / "source"
    source.mkdir()
    module = source / "CommonModules" / "ОбщийМодуль" / "Ext" / "Module.bsl"
    module.parent.mkdir(parents=True)
    original = "\ufeffФункция Значение() Экспорт\r\nВозврат 1;\r\nКонецФункции\r\n".encode("utf-8")
    module.write_bytes(original)
    actor = current_local_principal()
    registry = core.ProjectRegistry.create(root / "registry.sqlite3")
    registered = registry.register(actor, source_root=source, state_root=root / "state",
                                   display_name="Synthetic cross-client draft regression")
    resolver = core.ContextResolver(registry, graph_reader_factory=RentgenGraphReaderFactory())
    ctx = resolver.resolve_context(actor, core.Explicit(registered.project_id))
    with ctx.state.transaction(actor) as tx:
        if tx.state_schema_version() != 4:
            raise RuntimeError("The fixture requires the real schema-4 store")
    published = core.capture_and_publish(ctx, expected_head=core.get_project_head(ctx),
        builder=RentgenCapturedGoBuilder(scanner), operation_id=str(uuid4()))
    selected = resolver.resolve_context(actor, core.Explicit(registered.project_id), published.snapshot.snapshot_id)
    ref = selected.sources.resolve("base", "CommonModules/ОбщийМодуль/Ext/Module.bsl")
    if selected.sources.read_source(ref) != original:
        raise RuntimeError("Retained source bytes changed")
    return {"config": {"schema": 1, "core_version": "0.1.0.dev17", "python": sys.executable,
                       "registry": str(registry.path), "project_id": registered.project_id},
            "ref": asdict(ref), "module": str(module), "original_base64": base64.b64encode(original).decode(),
            "bound_packages": bound_packages, "python_version": sys.version,
            "scanner_sha256": hashlib.sha256(scanner.read_bytes()).hexdigest()}


def verify(args):
    if os.name != "nt":
        raise RuntimeError("This gate requires real Windows execution; it cannot pass by skipping")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = {"accepted": False, "checkout_commit": args.expected_checkout, "trigger_head": args.trigger_head,
              "editor_gui": "NOT_RUN", "scope": "installed Core and Companion service integration"}
    temporary = None
    try:
        checkout = args.checkout.resolve(strict=True)
        manifest = bind_checkout(checkout, args.expected_checkout, args.trigger_head)
        write_json(output / "source-binding.json", manifest)
        temporary = Path(tempfile.mkdtemp(prefix="rentgen-draft-interop-"))
        write_json(output / "input.json", {"source": str(checkout), "fixture_root": str(temporary),
            "manifest": str(output / "source-binding.json"), "output": str(output),
            "python": str(args.python.resolve(strict=True)), "scanner": str(args.scanner.resolve(strict=True))})
        env = dict(os.environ, RENTGEN_DRAFT_TEST_INPUT=str(output / "input.json"))
        child = subprocess.Popen(["node", "--test", "--test-concurrency=1",
                                  str(Path(__file__).with_name("regression.cjs"))],
                                 env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = child.communicate(timeout=150)
        except subprocess.TimeoutExpired:
            if child.poll() is None:
                subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True, timeout=15)
            stdout, stderr = child.communicate(timeout=15)
            (output / "node.log").write_bytes(stdout + stderr)
            raise RuntimeError("Cross-client regression exceeded 150 seconds")
        (output / "node.log").write_bytes(stdout + stderr)
        sys.stdout.buffer.write(stdout + stderr)
        if child.returncode != 0:
            raise RuntimeError("Cross-client regression failed; inspect node.log")
        scenario = json.loads((output / "scenario.json").read_text(encoding="utf-8"))
        if scenario.get("accepted") is not True:
            raise RuntimeError("No positive scenario evidence was produced")
        result.update(accepted=True, scenario=scenario)
    except Exception as exc:
        result["error"] = str(exc)
        raise
    finally:
        cleanup_error = None
        if temporary is not None:
            for attempt in range(6):
                try:
                    shutil.rmtree(temporary)
                    result["fixture_cleanup"] = "removed_by_supervisor"
                    break
                except FileNotFoundError:
                    result["fixture_cleanup"] = "removed_by_node"
                    break
                except OSError as exc:
                    if attempt < 5:
                        time.sleep(0.1)
                    else:
                        cleanup_error = exc
                        result.update(accepted=False, fixture_cleanup="failed", cleanup_error=str(exc))
        write_json(output / "acceptance.json", result)
        if cleanup_error is not None:
            raise RuntimeError("Owned fixture cleanup failed") from cleanup_error


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fixture":
        try:
            value = prepare_fixture(*map(Path, sys.argv[2:]))
            sys.stdout.buffer.write((json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8"))
        except Exception as exc:
            sys.stdout.buffer.write((json.dumps({"fixture_error": type(exc).__name__, "message": str(exc)}) + "\n").encode("utf-8"))
            raise SystemExit(2)
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        for name in ("python", "scanner", "checkout", "output"):
            parser.add_argument("--" + name, type=Path, required=True)
        parser.add_argument("--expected-checkout", required=True)
        parser.add_argument("--trigger-head", required=True)
        verify(parser.parse_args())
