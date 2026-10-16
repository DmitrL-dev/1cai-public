"""Exact commit-tree blob binding with real Git and strict evidence decoding."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess

import pytest

from rentgen_core._git_policy import GitRepositoryTrust
from rentgen_core.errors import CoreError
from rentgen_core.git_observer import GitObservation, observe_git
import rentgen_core.git_snapshot_evidence as evidence_impl
from rentgen_core.git_snapshot_evidence import (
    EVIDENCE_SCHEMA,
    GitSnapshotEvidence,
    GitTreeBinding,
    read_evidence,
    read_git_tree,
    save_evidence,
)
from rentgen_core.observer import _json
from test_git_watcher import git

MODULE = "Процедура Тест()\r\nКонецПроцедуры\r\n".encode("utf-8")
COMMON = b"// common\r\n"
TOOL = b"#!/bin/sh\nexit 0\n"
PROJECT = "6e461c4d-e19c-4e37-85b3-3aa0961580b7"
SNAPSHOT = "a" * 64


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init", "--initial-branch=main")
    git(root, "config", "user.name", "Tree binding test")
    git(root, "config", "user.email", "tree@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    (root / "src").mkdir()
    (root / "Module.bsl").write_bytes(MODULE)
    (root / "src" / "Common.bsl").write_bytes(COMMON)
    (root / "tool.sh").write_bytes(TOOL)
    (root / "tool.sh").chmod(0o755)  # Windows keeps core.filemode=false.
    git(root, "add", ".")
    git(root, "update-index", "--chmod=+x", "tool.sh")
    git(root, "commit", "-m", "baseline")
    return root.resolve()


def head(root):
    return git(root, "rev-parse", "HEAD")


def files(root, *paths):
    return [(path, (root / path).read_bytes()) for path in paths]


def bind_git_tree(tree, pairs, roots):
    """Snapshot-shaped inventory: ordered paths plus one bounded byte reader."""
    reads, content = [], dict(pairs)

    def read(path):
        reads.append(path)
        return content[path]

    binding = evidence_impl.bind_git_tree(tree, [path for path, _ in pairs], read, roots)
    assert not any(path == ".git" or path.startswith(".git/") for path in reads)
    return binding


def mismatch(callable_, *args):
    with pytest.raises(CoreError) as error:
        callable_(*args)
    assert error.value.code == "GIT_TREE_MISMATCH"
    return error.value.details["reason"]


def test_snapshot_bytes_bind_exact_commit_tree(repository):
    tree = read_git_tree(repository, head(repository))
    assert tree.tree == git(repository, "rev-parse", "HEAD^{tree}")
    assert tree.entries[b"tool.sh"][0] == "100755"
    inventory = files(repository, "Module.bsl", "src/Common.bsl", "tool.sh")
    metadata = [(".git", b"gitdir: elsewhere\n"), (".git/HEAD", b"ref: refs/heads/main\n")]
    binding = bind_git_tree(tree, inventory + metadata, ["."])
    assert binding == GitTreeBinding(1, "sha1", tree.tree, 3, 2, 0)


def test_layer_roots_map_paths_and_count_unproven_tree_entries(repository):
    tree = read_git_tree(repository, head(repository))
    layer = bind_git_tree(tree, files(repository, "src/Common.bsl"), ["src"])
    assert (layer.files, layer.tree_entries_outside_snapshot) == (1, 0)
    partial = bind_git_tree(tree, files(repository, "Module.bsl"), ["."])
    assert (partial.files, partial.tree_entries_outside_snapshot) == (1, 2)


def test_wrong_tree_fails_closed(repository):
    old = read_git_tree(repository, head(repository))
    (repository / "Module.bsl").write_bytes(MODULE + b"// next\r\n")
    git(repository, "commit", "-am", "next")
    new = read_git_tree(repository, head(repository))
    assert new.tree != old.tree
    current = files(repository, "Module.bsl", "src/Common.bsl", "tool.sh")
    assert mismatch(bind_git_tree, old, current, ["."]) == "content"
    stale = [("Module.bsl", MODULE), *files(repository, "src/Common.bsl", "tool.sh")]
    assert mismatch(bind_git_tree, new, stale, ["."]) == "content"


def test_swapped_blobs_fail_closed(repository):
    tree = read_git_tree(repository, head(repository))
    swapped = [("Module.bsl", COMMON), ("src/Common.bsl", MODULE)]
    assert mismatch(bind_git_tree, tree, swapped, ["."]) == "content"


@pytest.mark.parametrize("name", ["Untracked.bsl", "ignored.bsl"])
def test_missing_inventory_file_fails_closed(repository, name):
    (repository / ".git" / "info").mkdir(exist_ok=True)
    (repository / ".git" / "info" / "exclude").write_text("ignored.bsl\n", "utf-8")
    (repository / name).write_bytes(b"not committed\r\n")
    observe_git(repository)  # Untracked or ignored files keep HEAD observation clean.
    tree = read_git_tree(repository, head(repository))
    inventory = files(repository, "Module.bsl", name)
    assert mismatch(bind_git_tree, tree, inventory, ["."]) == "missing"


def test_duplicate_inventory_path_fails_closed(repository):
    tree = read_git_tree(repository, head(repository))
    inventory = files(repository, "Module.bsl", "Module.bsl")
    assert mismatch(bind_git_tree, tree, inventory, ["."]) == "duplicate"


@pytest.mark.parametrize("mode", ["120000", "160000"])
def test_symlink_and_gitlink_entries_are_not_regular_files(repository, mode):
    if mode == "120000":
        target = b"Module.bsl"
        oid = subprocess.run(
            ["git", "-C", str(repository), "hash-object", "-w", "--stdin"],
            input=target, check=True, capture_output=True,
        ).stdout.decode("ascii").strip()
    else:
        target, oid = b"", head(repository)
    git(repository, "update-index", "--add", "--cacheinfo", f"{mode},{oid},entry.bsl")
    git(repository, "commit", "-m", "special entry")
    tree = read_git_tree(repository, head(repository))
    assert mismatch(bind_git_tree, tree, [("entry.bsl", target)], ["."]) == (
        "not_regular_file"
    )


def test_line_ending_conversion_is_refused_not_normalized(repository):
    git(repository, "config", "core.autocrlf", "true")
    (repository / "Converted.bsl").write_bytes(b"line\r\n")
    git(repository, "add", "Converted.bsl")
    git(repository, "commit", "-m", "converted")
    observe_git(repository)  # Git itself reports the converted file as clean.
    tree = read_git_tree(repository, head(repository))
    inventory = files(repository, "Converted.bsl")
    assert mismatch(bind_git_tree, tree, inventory, ["."]) == "content"


def test_sha256_repository_binds_with_sha256_blob_ids(tmp_path):
    root = tmp_path / "sha256"
    root.mkdir()
    try:
        git(root, "init", "--object-format=sha256", "--initial-branch=main")
    except subprocess.CalledProcessError:
        pytest.skip("Installed Git cannot create SHA-256 repositories")
    git(root, "config", "user.name", "Tree binding test")
    git(root, "config", "user.email", "tree@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    (root / "Module.bsl").write_bytes(MODULE)
    git(root, "add", ".")
    git(root, "commit", "-m", "baseline")
    tree = read_git_tree(root.resolve(), head(root))
    assert len(tree.tree) == 64 and tree.object_format == "sha256"
    binding = bind_git_tree(tree, files(root, "Module.bsl"), ["."])
    assert binding == GitTreeBinding(1, "sha256", tree.tree, 1, 0, 0)
    assert mismatch(bind_git_tree, tree, [("Module.bsl", COMMON)], ["."]) == "content"


def test_tree_of_replaced_commit_stays_original(repository):
    original = head(repository)
    expected = git(repository, "rev-parse", "HEAD^{tree}")
    (repository / "Module.bsl").write_bytes(b"replacement\r\n")
    git(repository, "commit", "-am", "replacement")
    replacement = head(repository)
    git(repository, "reset", "--hard", original)
    git(repository, "replace", original, replacement)
    assert read_git_tree(repository, original).tree == expected


@pytest.mark.parametrize("commit", ["HEAD", "A" * 40, "a" * 39, None])
def test_invalid_commit_identity_is_refused_before_any_child(repository, monkeypatch, commit):
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("Git launched"))
    with pytest.raises(CoreError) as error:
        read_git_tree(repository, commit)
    assert error.value.code == "GIT_TREE_PROBE_FAILED"


def test_unknown_or_non_commit_object_and_oversized_listing_fail(repository, monkeypatch):
    for value in ("f" * 40, git(repository, "rev-parse", "HEAD^{tree}")):
        with pytest.raises(CoreError) as error:
            read_git_tree(repository, value)
        assert error.value.code == "GIT_TREE_PROBE_FAILED"
    monkeypatch.setattr(evidence_impl, "MAX_TREE_LISTING_BYTES", 16)
    with pytest.raises(CoreError) as error:
        read_git_tree(repository, head(repository))
    assert error.value.code == "GIT_TREE_PROBE_FAILED"


def test_tree_reads_use_trust_and_pinned_executable(repository, monkeypatch):
    executable = Path(shutil.which("git")).resolve()
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    trust = GitRepositoryTrust(repository, executable, digest)
    commit = head(repository)
    calls, run = [], subprocess.Popen

    def capture(command, **kwargs):
        calls.append((command, kwargs["env"]))
        return run(command, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", capture)
    tree = read_git_tree(repository, commit, trust=trust)
    assert tree == read_git_tree(repository, commit)
    trusted = calls[:2]
    assert [command[10] for command, _ in trusted] == ["rev-parse", "ls-tree"]
    assert all(
        command[0] == str(executable)
        and command[4:8] == ["-c", "safe.directory=", "-c", "safe.directory=" + str(repository)]
        and env["GIT_NO_REPLACE_OBJECTS"] == "1"
        for command, env in trusted
    )


def evidence(commit, binding):
    return GitSnapshotEvidence(
        PROJECT, GitObservation(str(Path(__file__).resolve().parent), commit, "refs/heads/main"), SNAPSHOT,
        "b" * 64, binding,
    )


def database():
    db = sqlite3.connect(":memory:")
    db.execute(EVIDENCE_SCHEMA)
    return db


BINDING = GitTreeBinding(1, "sha1", "c" * 40, 3, 2, 0)


def stored(db, commit, document):
    db.execute(
        "INSERT INTO git_snapshot_evidence(commit_id,evidence) VALUES(?,?)",
        (commit, json.dumps(document)),
    )


def test_tree_bound_receipt_round_trips_and_replays():
    db, value = database(), evidence("d" * 40, BINDING)
    save_evidence(db, value, _json(value))
    assert json.loads(db.execute("SELECT evidence FROM git_snapshot_evidence").fetchone()[0])[
        "tree_binding"
    ] == asdict(BINDING)
    assert read_evidence(db, "d" * 40) == value
    save_evidence(db, value, _json(value))
    with pytest.raises(CoreError) as error:
        other = replace(BINDING, tree="e" * 40)
        save_evidence(db, evidence("d" * 40, other), _json(evidence("d" * 40, other)))
    assert error.value.code == "FINDINGS_REPLAY_CONFLICT"


def test_legacy_receipt_stays_readable_but_is_never_written_or_upgraded():
    db, legacy = database(), evidence("d" * 40, None)
    document = json.loads(_json(legacy))
    del document["tree_binding"]
    stored(db, "d" * 40, document)
    assert read_evidence(db, "d" * 40) == legacy
    save_evidence(db, legacy, _json(legacy))  # identical historical replay
    bound = evidence("d" * 40, BINDING)
    with pytest.raises(CoreError) as error:
        save_evidence(db, bound, _json(bound))
    assert error.value.code == "FINDINGS_REPLAY_CONFLICT"
    fresh = evidence("e" * 40, None)
    with pytest.raises(CoreError) as error:
        save_evidence(db, fresh, _json(fresh))
    assert error.value.code == "GIT_SNAPSHOT_EVIDENCE_INVALID"
    assert db.execute("SELECT count(*) FROM git_snapshot_evidence").fetchone() == (1,)


@pytest.mark.parametrize(
    "change",
    [
        {"schema": 2},
        {"schema": True},
        {"object_format": "sha256"},
        {"tree": "c" * 64},
        {"tree": "C" * 40},
        {"files": -1},
        {"files": True},
        {"git_metadata_files": 1.0},
        {"extra": 1},
        None,
    ],
)
def test_unknown_or_malformed_tree_binding_is_refused(change):
    db = database()
    document = json.loads(_json(evidence("d" * 40, BINDING)))
    if change is None:
        document["tree_binding"] = None
    else:
        document["tree_binding"].update(change)
    stored(db, "d" * 40, document)
    with pytest.raises(CoreError) as error:
        read_evidence(db, "d" * 40)
    assert error.value.code == "GIT_SNAPSHOT_EVIDENCE_INVALID"


def test_tree_width_must_match_commit_format():
    with pytest.raises(CoreError) as error:
        evidence("d" * 64, BINDING)
    assert error.value.code == "GIT_SNAPSHOT_EVIDENCE_INVALID"
