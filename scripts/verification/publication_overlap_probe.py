"""Owned two-process CLI publication fixture; barriers are never product options."""
from contextlib import closing, contextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4

TABLES = ("snapshots", "publication_receipts", "snapshot_events", "snapshot_outbox")
MODES = ("same-operation-same-content", "different-operations-same-content", "same-operation-different-content")
CASES = tuple((mode, winner) for mode in MODES for winner in (0, 1))
IMAGE = b"Function Value() Export\nReturn 1;\nEndFunction\n"


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(path)


def state_view(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        return dict(counts={name: db.execute("SELECT count(*) FROM " + name).fetchone()[0] for name in TABLES},
            head=list(db.execute("SELECT snapshot_id,revision FROM project_head").fetchone()),
            locators=[row[0] for row in db.execute("SELECT generation_relpath FROM snapshots ORDER BY snapshot_id")],
            operations=[row[0] for row in db.execute("SELECT operation_id FROM publication_receipts ORDER BY operation_id")],
            fingerprint=digest("\n".join(db.iterdump()).encode()))


def inventory(root):
    return {p.relative_to(root).as_posix(): digest(p.read_bytes()) for p in root.rglob("*") if p.is_file()}


def worker(config_path):
    from rentgen_core import cli
    if sys.platform == "linux":
        from rentgen_core import _linux_capture as implementation
    else:
        from rentgen_core import publication as implementation
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    directory = Path(config_path).parent
    require(bool(sys.flags.isolated) == config["isolated"], "Child isolation differs")
    if config["isolated"]:
        require(Path(cli.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), "Child imported checkout product")
    fired = False
    def boundary(name, **values):
        nonlocal fired
        if name != "before_state_transaction":
            return
        require(not fired and values["ctx"].project_id == config["head"]["project_id"], "Unexpected second publication boundary")
        fired = True
        save(directory / "ready.json", dict(pid=os.getpid(), nonce=config["nonce"],
            phase=name, operation_id=config["operation"], expected_head=config["head"],
            catalog=asdict(values["catalog"])))
        end = time.monotonic() + 75
        while not (directory / "release").exists():
            require(time.monotonic() < end, "Publication overlap barrier expired")
            time.sleep(.01)
    implementation._boundary = boundary
    code = cli.main(config["arguments"])
    save(directory / "drained.json", dict(pid=os.getpid(), nonce=config["nonce"], exit=code))
    return code


def wait_marker(child, directory, expected, *, timeout=30):
    end = time.monotonic() + timeout
    while True:
        require(child.poll() is None, "Publisher exited before its owned barrier")
        require(time.monotonic() < end, "Publisher barrier timed out")
        try:
            value = json.loads((directory / "ready.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            value = None
        except PermissionError:
            if os.name != "nt":
                raise
            value = None
        if value is not None:
            require(type(value) is dict and value.get("pid") == child.pid
                and all(value.get(key) == item for key, item in expected.items()), "Publisher marker binding differs")
            require(child.poll() is None, "Publisher exited while supplying its marker")
            return value
        time.sleep(.01)


def finish(child, directory, config):
    child.wait(timeout=30)
    drained = json.loads((directory / "drained.json").read_text(encoding="utf-8"))
    require(drained == dict(pid=child.pid, nonce=config["nonce"], exit=child.returncode), "Publisher did not drain normally")
    raw, error = (directory / "stdout").read_bytes(), (directory / "stderr").read_bytes()
    require(len(raw) <= 128 * 1024 and len(error) <= 32 * 1024, "Publisher output exceeded fixture bounds")
    value = json.loads(raw)
    require(child.returncode in (0, 2) and ("result" in value) == (child.returncode == 0), "Publisher exit/envelope differs")
    return dict(exit=child.returncode, result=value.get("result"),
                error_code=value.get("error", {}).get("code"))


@contextmanager
def publisher(prefix, helper, cwd, directory, config):
    directory.mkdir(mode=0o700)
    save(directory / "inputs.json", config)
    launch = "import runpy,sys; sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')"
    with (directory / "stdout").open("wb") as out, (directory / "stderr").open("wb") as error:
        child = subprocess.Popen([*prefix, "-c", launch, str(helper), "worker", str(directory / "inputs.json")],
            cwd=cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=error,
            start_new_session=os.name != "nt")
        try:
            yield child
        finally:
            # A failed assertion releases only this owned fixture. An unfinished
            # child is still ours/unreaped before terminating its process tree.
            (directory / "release").touch()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"],
                        capture_output=True, timeout=15, check=True)
                else:
                    os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=15)


def verify(python, scanner, scanner_sha256, workspace, *, isolated=True, checkout=None, cases=CASES):
    require(sys.platform == "win32" or (sys.platform == "linux" and platform.machine().lower() in {"amd64", "x86_64"}),
            "Actual Windows or Linux/amd64 host required")
    require(cases and all(case in CASES for case in cases) and len(set(cases)) == len(cases), "Unknown overlap case")
    require(digest(Path(scanner).read_bytes()) == scanner_sha256, "Scanner differs from exact input bytes")
    workspace = Path(workspace).resolve()
    workspace.mkdir(mode=0o700)
    raw_helper = Path(__file__).read_bytes()
    helper = workspace / "overlap.py"
    helper.write_bytes(raw_helper)
    cwd = workspace if isolated else Path(checkout).resolve()
    prefix = [str(python), *(["-I"] if isolated else [])]
    records = []
    for mode, winner in cases:
        directory = workspace / (mode + "-" + str(winner))
        directory.mkdir(mode=0o700)
        source, state, registry = directory / "source", directory / "state/state.sqlite3", directory / "registry.sqlite3"
        source.mkdir(mode=0o700)
        module = source / "Module.bsl"
        module.write_bytes(IMAGE)
        common = ["--registry", str(registry)]
        def cli(command, *args, expected=None):
            result = subprocess.run([*prefix, "-m", "rentgen_core", command, *map(str, args)],
                cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
            require(len(result.stdout) <= 128 * 1024 and len(result.stderr) <= 32 * 1024, "Fixture CLI output exceeds bounds")
            value = json.loads(result.stdout)
            require(result.returncode == (2 if expected else 0), "Fixture CLI exit differs: " + command)
            if expected:
                require(value["error"]["code"] == expected, "Fixture CLI refusal differs: " + command)
                return None
            return value["result"]
        if sys.platform == "linux":
            profile = directory / "identity/profile.json"
            cli("identity-init", "--identity-profile", profile)
            common += ["--identity-profile", str(profile)]
        cli("registry-init", *common)
        project = cli("project-register", *common, "--source-root", source, "--state-root", state.parent,
                      "--name", "Owned overlapping publishers")["project_id"]
        selected = [*common, "--project", project]
        head = cli("project-head", *selected)
        head_path = directory / "original-head.json"
        save(head_path, head)
        scanner_args = ["--scanner", str(scanner)]
        if sys.platform == "linux":
            scanner_args += ["--scanner-sha256", scanner_sha256]
        operations = [str(uuid4()), str(uuid4())]
        if mode != "different-operations-same-content":
            operations[1] = operations[0]
        configs = [dict(nonce=str(uuid4()), operation=op, head=head, isolated=isolated,
            arguments=["capture", *selected, "--operation-id", op, "--expected-head-json", str(head_path), *scanner_args]) for op in operations]
        workers = [directory / "publisher-0", directory / "publisher-1"]
        markers = []
        def marker(child, index):
            return wait_marker(child, workers[index], dict(phase="before_state_transaction", nonce=configs[index]["nonce"],
                operation_id=operations[index], expected_head=head))
        initial = state_view(state)
        require(initial["counts"] == dict.fromkeys(TABLES, 0) and initial["head"] == [None, 0], "Fixture was not empty")
        with publisher(prefix, helper, cwd, workers[0], configs[0]) as first:
            markers.append(marker(first, 0))
            images = [IMAGE, IMAGE.replace(b"Return 1", b"Return 2") if mode == "same-operation-different-content" else IMAGE]
            module.write_bytes(images[1])
            with publisher(prefix, helper, cwd, workers[1], configs[1]) as second:
                markers.append(marker(second, 1))
                children = [first, second]
                require(first.pid != second.pid and all(child.poll() is None for child in children), "Publishers did not overlap")
                catalogs = [value["catalog"] for value in markers]
                roots = [state.parent / value["generation_relpath"] for value in catalogs]
                require(roots[0] != roots[1] and set((state.parent / "generations").iterdir()) == set(roots), "Attempts are not distinct")
                originals = [inventory(root) for root in roots]
                for root, catalog, image in zip(roots, catalogs, images):
                    require((root / "sources/base/Module.bsl").read_bytes() == image, "Captured source differs from its process input")
                    require(digest((root / "manifest.json").read_bytes()) == catalog["snapshot"]["manifest_hash"], "Candidate manifest differs")
                same = catalogs[0]["snapshot"] == catalogs[1]["snapshot"]
                require(same == (mode != "same-operation-different-content"), "Captured content identity differs")
                require(state_view(state) == initial, "A paused publisher made its attempt visible")
                loser = 1 - winner
                (workers[winner] / "release").touch()
                won = finish(children[winner], workers[winner], configs[winner])
                require(won["exit"] == 0 and won["result"]["snapshot"] == catalogs[winner]["snapshot"], "Selected winner did not publish")
                published = state_view(state)
                require(published["counts"] == dict.fromkeys(TABLES, 1)
                    and published["head"] == [won["result"]["snapshot"]["snapshot_id"], 1]
                    and published["locators"] == [catalogs[winner]["generation_relpath"]]
                    and published["operations"] == [operations[winner]], "Winner did not publish one exact atomic unit")
                require(children[loser].poll() is None, "Losing publisher escaped its barrier")
                (workers[loser] / "release").touch()
                lost = finish(children[loser], workers[loser], configs[loser])
                if mode == "same-operation-same-content":
                    require(lost == won, "Concurrent exact operation did not replay the winning receipt")
                else:
                    code = "HEAD_CONFLICT" if mode == "different-operations-same-content" else "OPERATION_CONFLICT"
                    require(lost == dict(exit=2, result=None, error_code=code), "Losing publisher did not refuse exact conflict")
                after_loser = state_view(state)
                require(after_loser == published, "Losing publisher mutated the committed unit")
        require([inventory(root) for root in roots] == originals, "Publication changed retained attempt bytes")
        verified = cli("generation-verify", *selected, "--generation-relpath", catalogs[winner]["generation_relpath"])
        require(verified["catalog"] == catalogs[winner] and verified["physical_state"] == "verified_at_read"
                and verified["removal_permitted"] is False, "Winning generation could not be verified")
        orphan = cli("generation-attribution", *selected, "--generation-relpath", catalogs[loser]["generation_relpath"])
        require(orphan["status"] == "unreferenced_at_read" and orphan["removal_permitted"] is False, "Losing attempt gained catalog authority")
        cli("generation-verify", *selected, "--generation-relpath", catalogs[loser]["generation_relpath"], expected="GENERATION_UNREFERENCED")
        if operations[loser] != operations[winner]:
            cli("publication-receipt", *selected, "--operation-id", operations[loser], expected="PUBLICATION_NOT_FOUND")
        module.write_bytes(IMAGE.replace(b"Return 1", b"Return 3"))
        later_head = directory / "later-head.json"
        save(later_head, won["result"]["head"])
        later = cli("capture", *selected, "--operation-id", str(uuid4()), "--expected-head-json", later_head, *scanner_args)
        require(later["head"]["revision"] == 2 and later["snapshot"] != won["result"]["snapshot"], "Later publication did not advance head")
        source.rename(directory / "removed-live-source")
        before_replay = state_view(state)
        replay = cli("capture", *selected, "--operation-id", operations[winner], "--expected-head-json", head_path)
        require(replay == won["result"] and cli("project-head", *selected) == later["head"], "Replay lost the exact winning receipt")
        after_replay = state_view(state)
        require(after_replay == before_replay and before_replay["counts"] == dict.fromkeys(TABLES, 2), "Replay changed publication state")
        require([inventory(root) for root in roots] == originals and len(list((state.parent / "generations").iterdir())) == 3,
                "Replay changed or allocated an attempt")
        records.append(dict(mode=mode, winner=winner, expected_head=head, markers=markers,
            winner_result=won, loser_result=lost, initial=initial, published=published,
            after_loser=after_loser, final_state=before_replay, after_replay=after_replay, replay=replay,
            winner_verification=verified, loser_attribution=orphan, later=later,
            outcomes=dict(two_live_publishers=True, distinct_attempts=True, no_precommit_visibility=True,
                one_atomic_unit=True, exact_conflict_or_replay=True, normal_process_drain=True,
                retained_attempts_unchanged=True, winner_verified=True, loser_unreferenced=True,
                later_head_replay=True, replay_without_source_or_configured_scanner=True, replay_state_unchanged=True)))
    return dict(schema=1, platform=sys.platform, transport="two_process_cli", isolated=isolated,
        probe_sha256=digest(raw_helper), scanner_sha256=scanner_sha256, cases=records,
        scope="owned native phase-barrier fixture; no simultaneous COMMIT, cleanup lease, power-loss or 1C/EDT claim")


if __name__ == "__main__":
    require(len(sys.argv) == 3 and sys.argv[1] == "worker", "Expected owned overlap worker mode")
    raise SystemExit(worker(sys.argv[2]))
