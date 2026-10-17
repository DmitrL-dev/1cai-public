"""Actual child termination at publication boundaries; markers live outside generations."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import rentgen_core as api
from rentgen_core.local import LocalRuntime

ROOT = Path(__file__).resolve().parents[2]


def backend(executable, digest):
    if sys.platform == "linux":
        from rentgen_core._linux_capture import LinuxCaptureBackend

        return LinuxCaptureBackend(Path(executable), digest)
    from rentgen_graph.snapshot_adapter import RentgenCapturedGoBuilder

    return RentgenCapturedGoBuilder(Path(executable))


def _worker(config_path):
    options = json.loads(Path(config_path).read_text())
    directory = Path(config_path).parent
    principal = api.Principal("kill-test-owner", "local_os")
    ctx = LocalRuntime(options["registry"]).state_context(principal, options["project"])
    head = options["head"]
    head["snapshot"] = api.SnapshotRef(**head["snapshot"]) if head["snapshot"] else None
    expected = api.ProjectHead(**head)
    physical_locator = None

    def block(name, **values):
        nonlocal physical_locator
        if name == "after_capture":
            physical_locator = "generations/" + values["captured"].staging_path.name
        if "complete" in values:
            physical_locator = values["complete"].catalog.generation_relpath
        if name != options["boundary"]:
            return
        catalog = values.get("catalog")
        if catalog is None:
            catalog = values["complete"].catalog
        marker = dict(boundary=name, pid=os.getpid(), catalog=asdict(catalog),
                      physical_locator=physical_locator or catalog.generation_relpath)
        temporary = directory / "ready.tmp"
        temporary.write_text(json.dumps(marker), encoding="utf-8")
        temporary.replace(directory / "ready.json")
        # A timeout is a harness failure, never permission to publish.
        time.sleep(240)
        raise AssertionError("Parent did not kill the blocked publisher")

    try:
        if options["mode"] == "storage":
            catalog = api.SnapshotCatalogEntry(
                api.SnapshotRef(ctx.project_id, "a" * 64, "a" * 64),
                "b" * 64, "c" * 64, options["locator"], 1,
                datetime.now(timezone.utc).isoformat())
            with ctx.state.transaction(principal, write=True) as tx:
                result = tx.commit_publication(expected_head=expected, catalog=catalog,
                    layers=(api.SnapshotLayer("base", 0, "base", None, "unresolved", "unknown"),),
                    operation_id=options["operation"])
                block("before_commit", catalog=catalog)
            block("after_commit", catalog=catalog)
        else:
            if sys.platform == "linux":
                import rentgen_core._linux_capture as implementation
            else:
                import rentgen_core.publication as implementation
            implementation._boundary = block
            result = api.capture_and_publish(ctx, expected_head=expected,
                builder=backend(options["scanner"], options["scanner_digest"]),
                operation_id=options["operation"])
        (directory / "ack.json").write_text(json.dumps(asdict(result)), encoding="utf-8")
    finally:
        (directory / "unwound").write_text("Python finally executed", encoding="utf-8")


@contextmanager
def killed_publisher(directory, options, *, timeout=180):
    """Yield the boundary marker while alive, then force termination and reap."""
    directory.mkdir()
    config = directory / "request.json"
    config.write_text(json.dumps(options), encoding="utf-8")
    ready = directory / "ready.json"
    with (directory / "child.log").open("wb") as log:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), str(config)],
            cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)},
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + timeout
            while not ready.exists():
                if child.poll() is not None:
                    raise AssertionError("Publisher exited before boundary: " +
                        (directory / "child.log").read_text(errors="replace")[-2000:])
                if time.monotonic() >= deadline:
                    raise AssertionError("Publisher did not reach boundary")
                time.sleep(0.025)
            marker = json.loads(ready.read_text(encoding="utf-8"))
            assert marker["boundary"] == options["boundary"] and marker["pid"] == child.pid
            assert child.poll() is None
            yield marker
            assert child.poll() is None, "Publisher must still be blocked before kill"
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=30)
    assert child.returncode == (1 if os.name == "nt" else -signal.SIGKILL)
    assert not (directory / "ack.json").exists(), "Publisher must not acknowledge"
    assert not (directory / "unwound").exists(), "Kill must bypass Python cleanup"


if __name__ == "__main__":
    _worker(sys.argv[1])
