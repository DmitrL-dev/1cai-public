"""Closed candidate plan and byte-bound local evidence contracts; no publication API.

This module validates claims and provenance. It cannot authenticate an experiment
from arbitrary JSON. Full requirement admission deliberately has no adapter yet.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[2]
MAX_JSON = 1024 * 1024
MAX_FILE = 256 * 1024**2
MAX_FILES = 1024
MAX_TOTAL = 1024 * 1024**2
IDS_SHA256 = "ced75ca7e87ea10d5b2be2bb89b8701c84b2dcda275f0b0d17d2c74d4fb11596"
TUPLE_KEYS = ("component", "os", "arch", "runtime", "operation")
LIFECYCLE = ("dependencies", "offline-install", "update", "uninstall",
             "state-migration", "cancel", "recovery")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fields(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), "Invalid " + label + " fields")
    return value


def text(value, label, limit=128):
    require(type(value) is str and 0 < len(value) <= limit
            and all(32 <= ord(c) < 127 for c in value), "Invalid " + label)
    return value


def integer(value, label, maximum, minimum=0):
    require(type(value) is int and minimum <= value <= maximum, "Invalid " + label)
    return value


def digest(value, length=64):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{%d}" % length, value),
            "Invalid exact digest")
    return value


def sequence(value, label, maximum):
    require(type(value) is list and len(value) <= maximum, "Invalid " + label)
    return value


def relative(value):
    text(value, "relative file", 240)
    require(re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", value)
            and all(p not in {".", ".."} for p in value.split("/"))
            and len(value.split("/")) <= 8, "Unsafe relative file")
    return value


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns)


def _directory_stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode)


def _ordinary(info, directory=False):
    require(not stat.S_ISLNK(info.st_mode)
            and not (getattr(info, "st_file_attributes", 0) & 0x400),
            "Symlink/reparse input refused")
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode),
            "Input must be an ordinary " + ("directory" if directory else "file"))


def checked_bytes(path, maximum=MAX_JSON, keep=True):
    """Read one bounded ordinary file, rejecting link ancestors and changed identity.

    No archive extraction or input execution. Hashes bind bytes even where the OS
    lacks O_NOFOLLOW. This is an audit of a quiescent local evidence directory,
    not a lease against a malicious same-user filesystem writer.
    """
    path = Path(os.path.abspath(path))
    ancestors = []
    for parent in reversed(path.parents):
        info = parent.lstat()
        _ordinary(info, directory=True)
        ancestors.append((parent, _directory_stamp(info)))
    before = path.lstat()
    _ordinary(before)
    require(0 < before.st_size <= maximum, "File exceeds size limit or is empty")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    hasher, chunks, size = hashlib.sha256(), [], 0
    with os.fdopen(fd, "rb") as stream:
        require(_stamp(os.fstat(stream.fileno())) == _stamp(before), "File identity changed")
        while chunk := stream.read(min(1024 * 1024, maximum + 1 - size)):
            size += len(chunk)
            require(size <= maximum, "File grew beyond size limit")
            hasher.update(chunk)
            if keep:
                chunks.append(chunk)
        require(_stamp(os.fstat(stream.fileno())) == _stamp(before), "File changed while reading")
    require(_stamp(path.lstat()) == _stamp(before), "File path changed while reading")
    for parent, stamp in ancestors:
        after = parent.lstat()
        _ordinary(after, directory=True)
        require(_directory_stamp(after) == stamp, "Input ancestor changed while reading")
    return {"sha256": hasher.hexdigest(), "size_bytes": size}, b"".join(chunks)


def strict_json(raw):
    require(type(raw) is bytes and len(raw) <= MAX_JSON, "JSON exceeds limit")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON field")
            result[key] = value
        return result
    def constant(_):
        raise ValueError("Non-finite JSON number")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=constant, parse_float=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Invalid bounded JSON") from exc
    nodes = 0
    def bounded(item, depth):
        nonlocal nodes
        nodes += 1
        require(depth <= 24 and nodes <= 30000, "JSON nesting/node limit")
        if type(item) is dict:
            for key, child in item.items():
                require(len(key) <= 240, "JSON key exceeds limit")
                bounded(child, depth + 1)
        elif type(item) is list:
            for child in item:
                bounded(child, depth + 1)
        elif type(item) is str:
            require(len(item) <= 4096, "JSON string exceeds limit")
    bounded(value, 0)
    return value


def load_policy():
    binding, raw = checked_bytes(ROOT / "scripts/release/release_policy.json")
    policy = fields(strict_json(raw), ("schema", "requirements", "ide_scenarios",
                    "mandatory_deliveries", "final_targets", "lifecycle", "not_applicable", "product_adapters"), "policy")
    require(policy["schema"] == "rentgen-release-policy/1"
            and policy["product_adapters"] == "not-implemented", "Unknown policy admission")
    ids = sequence(policy["requirements"], "requirements policy", 127)
    require(len(ids) == len(set(ids)) == 127 and
            hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest() == IDS_SHA256,
            "Canonical requirement catalog differs")
    _, registry = checked_bytes(ROOT / "docs/product/FULL-FINAL-PLAN.md")
    actual = re.findall(rb"^\| `([^`]+)` \|", registry, re.M)
    require(len(actual) == 127 and set(actual) == {i.encode() for i in ids},
            "Catalog differs from full final registry")
    require(policy["ide_scenarios"] == [f"IDE-SC-{i:02d}" for i in range(1, 25)]
            and set(policy["ide_scenarios"]) <= set(ids), "IDE24 catalog differs")
    require(policy["lifecycle"] == list(LIFECYCLE) and policy["not_applicable"] == [],
            "Unknown lifecycle or N/A policy")
    deliveries = sequence(policy["mandatory_deliveries"], "delivery policy", 32)
    require(len(deliveries) >= 5, "Mandatory delivery policy missing")
    keys = []
    for item in deliveries:
        fields(item, (*TUPLE_KEYS, "asset_kind"), "delivery policy")
        keys.append(tuple_key(item))
        text(item["asset_kind"], "asset kind")
    require(len(keys) == len(set(keys)), "Duplicate delivery policy")
    require(policy["final_targets"] == [os_name + "/" + role
            for os_name in ("windows", "linux", "macos")
            for role in ("ide-client", "executor")], "Mandatory final target missing")
    return policy, binding


def tuple_key(item):
    return "/".join(text(item[key], "delivery tuple") for key in TUPLE_KEYS)


def blob(value):
    fields(value, ("path", "sha256", "size_bytes"), "blob reference")
    relative(value["path"])
    digest(value["sha256"])
    integer(value["size_bytes"], "blob size", MAX_FILE, 1)
    return value


def git(repo, *args, maximum=MAX_JSON):
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    environment.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1", GIT_NO_LAZY_FETCH="1",
                       GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    # Only fixed read-only commands are called; no hooks, remotes, checkout or index refresh.
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(repo), *args],
                            env=environment, capture_output=True, timeout=15)
    require(result.returncode == 0 and len(result.stdout) <= maximum,
            "Git source/record binding failed")
    return result.stdout


def bind_git(plan, repo):
    for key in ("source_commit", "source_tree", "record_commit"):
        digest(plan[key], 40)
    source, record = plan["source_commit"], plan["record_commit"]
    require(git(repo, "rev-parse", source + "^{commit}").decode().strip() == source
            and git(repo, "rev-parse", record + "^{commit}").decode().strip() == record,
            "Source/record must be exact commits")
    require(git(repo, "rev-parse", source + "^{tree}").decode().strip() == plan["source_tree"],
            "Source tree differs")
    git(repo, "merge-base", "--is-ancestor", source, record)
    git(repo, "merge-base", "--is-ancestor", record, "HEAD")
    def source_file(path):
        size = int(git(repo, "cat-file", "-s", source + ":" + path))
        require(0 < size <= MAX_JSON, "Source metadata exceeds limit")
        return git(repo, "show", source + ":" + path)
    try:
        core = tomllib.loads(source_file("pyproject.toml").decode())["project"]["version"]
        companion = strict_json(source_file("integrations/vscode-rentgen/package.json"))["version"]
    except (ValueError, KeyError, TypeError, RecursionError) as exc:
        raise ValueError("Invalid bounded source component metadata") from exc
    require(core == plan["components"]["core"]["version"]
            and companion == plan["components"]["companion"]["version"],
            "Component versions differ from source bytes")


def validate_plan(plan):
    fields(plan, ("schema", "channel", "source_commit", "source_tree", "record_commit",
                  "components", "component_pair", "assets", "dependencies", "deliveries",
                  "requirements"), "plan")
    require(plan["schema"] == "rentgen-release-plan/2", "Unknown plan schema")
    channel = plan["channel"]
    require(channel in {"development", "release-candidate", "stable"}, "Unknown channel")
    fields(plan["components"], ("core", "companion"), "components")
    fields(plan["component_pair"], ("core", "companion"), "component pair")
    for component, value in plan["components"].items():
        fields(value, ("version", "tag"), "component")
        version = text(value["version"], "component version", 64)
        plain = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
        suffix = {"development": (r"\.dev[1-9][0-9]*" if component == "core" else ""),
                  "release-candidate": (r"rc[1-9][0-9]*" if component == "core" else r"-rc\.[1-9][0-9]*"),
                  "stable": ""}[channel]
        require(re.fullmatch(plain + suffix, version), "Version differs from explicit channel")
        tag_version = version.replace(".dev", "-dev") if component == "core" else version
        if component == "core" and channel == "release-candidate":
            tag_version = version.replace("rc", "-rc")
        require(value["tag"] == component + "-v" + tag_version, "Non-canonical component tag")
        require(plan["component_pair"][component] == version, "Component pair differs")
    assets = {}
    for item in sequence(plan["assets"], "assets", 32):
        fields(item, ("id", "kind", "component", "os", "arch", "blob"), "asset")
        identity = text(item["id"], "asset id")
        require(identity not in assets and item["component"] in plan["components"], "Duplicate/unknown asset")
        for key in ("kind", "os", "arch"):
            text(item[key], "asset " + key)
        blob(item["blob"])
        assets[identity] = item
    dependencies = {}
    for item in sequence(plan["dependencies"], "dependencies", 256):
        fields(item, ("id", "version", "distribution_sha256", "license", "license_file"), "dependency")
        identity = text(item["id"], "dependency id")
        require(identity not in dependencies, "Duplicate dependency")
        text(item["version"], "pinned dependency version")
        digest(item["distribution_sha256"])
        text(item["license"], "license identifier", 256)
        blob(item["license_file"])
        dependencies[identity] = item
    return assets, dependencies


def inventory(root):
    root = Path(os.path.abspath(root))
    _ordinary(root.lstat(), directory=True)
    found, total, entries_seen = set(), 0, 0
    def walk(folder, depth):
        nonlocal total, entries_seen
        require(depth <= 8, "Evidence directory depth exceeds limit")
        with os.scandir(folder) as entries:
            for entry in entries:
                entries_seen += 1
                require(entries_seen <= MAX_FILES, "Evidence entry count exceeds limit")
                info = entry.stat(follow_symlinks=False)
                require(not stat.S_ISLNK(info.st_mode)
                        and not (getattr(info, "st_file_attributes", 0) & 0x400), "Symlink/reparse evidence refused")
                name = relative(Path(entry.path).relative_to(root).as_posix())
                if stat.S_ISDIR(info.st_mode):
                    walk(Path(entry.path), depth + 1)
                else:
                    _ordinary(info)
                    require(0 < info.st_size <= MAX_FILE, "Evidence file size exceeds limit")
                    found.add(name)
                    total += info.st_size
                    require(len(found) <= MAX_FILES and total <= MAX_TOTAL, "Evidence inventory exceeds limit")
    walk(root, 0)
    return found


class Evidence:
    def __init__(self, root, plan):
        self.root, self.plan, self.bindings, self.refs = Path(root), plan, {}, {}

    def read(self, reference, json_file=False):
        blob(reference)
        name = reference["path"]
        if name in self.refs:
            require(self.refs[name] == reference, "Conflicting file references")
            require(not json_file, "Receipt reused for multiple cells")
            return None
        binding, raw = checked_bytes(self.root / name, MAX_JSON if json_file else MAX_FILE,
                                     keep=json_file)
        require(binding == {k: reference[k] for k in ("sha256", "size_bytes")},
                "Evidence SHA/size differs: " + name)
        self.refs[name], self.bindings[name] = dict(reference), binding
        return strict_json(raw) if json_file else None

    def receipt(self, reference, scope, assets, dependencies):
        item = self.read(reference, json_file=True)
        fields(item, ("schema", "kind", "origin", "source_commit", "source_tree", "component_pair",
                       "scope", "assets", "dependencies", "result", "execution", "attachments"), "receipt")
        require(item["schema"] == "rentgen-release-evidence/1"
                and item["kind"] in {"lifecycle-execution", "github-main-ci", "full-product-criterion"},
                "Unknown typed receipt kind")
        require(item["origin"] in {"fixture", "execution"}, "Unknown receipt origin")
        require(item["source_commit"] == self.plan["source_commit"]
                and item["source_tree"] == self.plan["source_tree"]
                and item["component_pair"] == self.plan["component_pair"], "Receipt source/tree/pair differs")
        require(item["scope"] == scope, "Receipt scenario scope differs")
        require(item["assets"] == sorted(assets) and item["dependencies"] == sorted(dependencies),
                "Receipt asset/dependency binding differs")
        counts = fields(item["result"], ("executed", "passed", "failed", "errors", "skipped"), "result counts")
        for key, value in counts.items():
            integer(value, "result " + key, 1000000)
        require(counts["executed"] == sum(counts[k] for k in ("passed", "failed", "errors", "skipped")),
                "Receipt counts do not reconcile")
        successful = counts["passed"] > 0 and counts["executed"] == counts["passed"]
        execution = item["execution"]
        if item["kind"] == "github-main-ci":
            fields(execution, ("repository", "workflow", "run_id", "run_attempt", "artifact_id",
                               "event", "branch", "status", "conclusion", "artifact"), "CI execution")
            require(execution["repository"] == "DmitrL-dev/1cai-public"
                    and execution["event"] == "push" and execution["branch"] == "main"
                    and execution["status"] == "completed", "CI repository/event/branch/status differs")
            require(execution["workflow"] in {".github/workflows/core-ci.yml", ".github/workflows/portable-ci.yml",
                                               ".github/workflows/gui-browser-ci.yml", ".github/workflows/diagnostic-ci.yml"},
                    "Unknown CI workflow scope")
            for key in ("run_id", "run_attempt", "artifact_id"):
                integer(execution[key], "CI " + key, 2**63 - 1, 1)
            require(execution["conclusion"] in {"success", "failure", "cancelled"}, "Unknown CI conclusion")
            self.read(execution["artifact"])
            successful = successful and execution["conclusion"] == "success"
        else:
            fields(execution, ("command", "exit_code"), "local execution")
            argv = sequence(execution["command"], "execution argv", 64)
            require(bool(argv), "Empty execution argv")
            for argument in argv:
                text(argument, "execution argv", 512)
            integer(execution["exit_code"], "execution exit", 255)
            successful = successful and execution["exit_code"] == 0
        attachments = sequence(item["attachments"], "receipt attachments", 16)
        require(bool(attachments), "Receipt raw evidence missing")
        for attachment in attachments:
            self.read(attachment)
        # Full-product JSON is a bound claim, not an implemented admission adapter.
        return successful, item["origin"], item["kind"]
