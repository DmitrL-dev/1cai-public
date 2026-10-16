"""Bounded read-only qualification of a retained YAxUnit run; never executes.

The evaluator compares already bounded retained bytes with the stored report.
A consistent dossier is ``local_unattested`` evidence: it does not prove that
the platform executed anything and grants no apply authority.
"""
from contextlib import ExitStack
from dataclasses import asdict, dataclass
import hashlib
from pathlib import PurePosixPath, PureWindowsPath
import re
import stat
import time

from .errors import CoreError
from .manifests import canonical_bytes, sha256

PHASES = ("baseline", "candidate")
TREES = ("baseline", "candidate", "engine-with-tests")
SCRATCH = (
    "baseline-extension-properties-data",
    "candidate-extension-properties-data",
)
CHECKS = (
    "report_identity",
    "profile_definition",
    "input_inventories",
    "native_roundtrip",
    "step_sequence",
    "runner_settings",
    "junit_exit",
    "engine_source",
    "scratch_cleanup",
)
LIMITATIONS = (
    "Retained bytes are local_unattested and do not prove native execution",
    "This read started no 1C, test, build or apply operation",
    "A consistent dossier is not native, full-product or release acceptance",
)
HASH = re.compile(r"[0-9a-f]{64}")
MAX_LOG = 128 * 1024
MAX_TARGET = 2 * 1024**2
FILE_LIMITS = {".junit.xml": 2 * 1024**2, ".exit": 32, "-settings.json": 32768}
REPORT_KEYS = frozenset(
    {
        "schema",
        "run_id",
        "source_ref",
        "proposal_content_id",
        "profile_id",
        "platform_executable_sha256",
        "candidate_sha256",
        "baseline_input_sha256",
        "candidate_input_sha256",
        "tests",
        "scratch_cleanup",
        "apply",
        "evidence",
        "runtime_dependencies",
        "report_sha256",
    }
)
BINDING_KEYS = (
    "source_ref",
    "proposal_content_id",
    "profile_id",
    "platform_executable_sha256",
)
TESTS_KEYS = frozenset(
    {
        "baseline",
        "candidate",
        "status",
        "engine_source_sha256",
        "steps",
        "isolated_infobases",
    }
)
EXECUTED_KEYS = frozenset(
    {
        "status",
        "counts",
        "cases",
        "junit_sha256",
        "exit_file_sha256",
        "framework_exit_code",
        "evidence",
        "native_module_sha256",
        "module_text_verified",
        "client_exit_code",
        "settings_sha256",
    }
)
PLATFORM_STEP_KEYS = frozenset(
    {
        "name",
        "exit_code",
        "log",
        "log_sha256",
        "stdout_sha256",
        "stderr_sha256",
        "elapsed_ms",
    }
)
IBCMD_STEP_KEYS = frozenset({"name", "exit_code", "stdout_sha256", "stderr_sha256"})
UNREADABLE = "unreadable"
OVERSIZED = "oversized"


class _Mismatch(Exception):
    pass


class _Missing(Exception):
    pass


def _need(ok, detail):
    if not ok:
        raise _Mismatch(detail)


def phase_steps(phase, *, executed, engine_dump):
    """The closed native step order written by the runner for one phase."""
    names = [phase + "-" + step for step in ("create", "load", "dump", "compile")]
    if executed:
        names += [phase + "-apply", phase + "-engine-load", phase + "-engine-apply"]
        if engine_dump:
            names.append("engine-dump")
        names += [
            phase + "-tests-load",
            phase + "-tests-apply",
            phase + "-extension-properties",
            phase + "-execute",
        ]
    return names


def _ibcmd(name):
    return name.endswith("-extension-properties")


def _suffixes(name):
    return (".stdout", ".stderr") if _ibcmd(name) else (".log", ".stdout", ".stderr")


def step_universe():
    names = set()
    for phase in PHASES:
        names.update(phase_steps(phase, executed=True, engine_dump=True))
    return tuple(sorted(names))


def evidence_names():
    """Closed top-level file universe; no path is ever taken from report JSON."""
    names = [name + suffix for name in step_universe() for suffix in _suffixes(name)]
    for phase in PHASES:
        names += [phase + ".junit.xml", phase + ".exit", phase + "-settings.json"]
    return tuple(sorted(names))


def evidence_limit(name):
    for suffix, maximum in FILE_LIMITS.items():
        if name.endswith(suffix):
            return maximum
    return MAX_LOG


def target_path(value):
    """Validate the retained module path syntax before any read uses it."""
    if type(value) is not str or not 0 < len(value) <= 1024:
        return None
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or str(path) != value
        or any(part in ("", ".", "..") for part in path.parts)
        or any(c in value for c in '\\:*?"<>|')
        or any(ord(c) < 32 for c in value)
        or not value.lower().endswith(".bsl")
    ):
        return None
    return value


def _text(raw):
    try:
        return raw.decode("utf-8-sig").replace("\r\n", "\n")
    except UnicodeDecodeError as exc:
        raise _Mismatch("ROUNDTRIP_ENCODING") from exc


def _log_text(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return raw.decode("cp1251")
        except UnicodeDecodeError as exc:
            raise _Mismatch("LOG_ENCODING") from exc


def _evidence(files, name):
    raw = files.get(name)
    if raw is None:
        raise _Missing(name.upper().replace(".", "_").replace("-", "_") + "_ABSENT")
    _need(type(raw) is bytes, "EVIDENCE_" + str(raw).upper())
    return raw


def _inventory(tree, *, windows_order=False):
    files = tree["files"]
    key = (lambda item: PureWindowsPath(item["path"])) if windows_order else None
    rows = [
        {"path": item["path"], "size": item["size"], "sha256": item["sha256"]}
        for item in files
    ]
    rows.sort(key=key or (lambda item: item["path"]))
    return rows


def _ancestors(paths):
    result = set()
    for path in paths:
        parent = PurePosixPath(path).parent
        while str(parent) != ".":
            result.add(str(parent))
            parent = parent.parent
    return result


def _tree(bundle, name, *, exact_directories=True):
    tree = bundle["trees"].get(name)
    if tree is None:
        raise _Missing(name.upper().replace("-", "_") + "_TREE_ABSENT")
    _need(tree != UNREADABLE, name.upper().replace("-", "_") + "_TREE_UNSAFE")
    # Core materializes only file parents; a native engine export may hold
    # empty directories, which never enter the claimed file inventory digest.
    _need(
        not exact_directories
        or set(tree["directories"]) == _ancestors(i["path"] for i in tree["files"]),
        "UNEXPECTED_DIRECTORY",
    )
    return tree


class _Context:
    def __init__(self, bundle):
        self.bundle = bundle
        self.record = bundle["record"]
        self.request = self.record["request"]
        self.report = self.record["report"]
        self.tests = self.report["tests"]
        self.files = bundle["files"]
        self.profile = bundle.get("profile")
        self.target = target_path(self.report["source_ref"]["relative_path"])

    def executed(self, phase):
        return self.tests[phase]["status"] != "not_run"

    def expected_cases(self):
        if self.profile is None or self.profile == UNREADABLE:
            raise _Missing("PROFILE_REQUIRED")
        return [
            (module["name"] + "." + test, test, "Сервер")
            for module in self.profile["definition"]["modules"]
            for test in module["tests"]
        ]

    def module_names(self):
        self.expected_cases()
        return [module["name"] for module in self.profile["definition"]["modules"]]


def _report_identity(c):
    report, request = c.report, c.request
    _need(type(report) is dict and set(report) == REPORT_KEYS, "REPORT_SHAPE")
    _need(type(report["schema"]) is int and report["schema"] == 1, "REPORT_SCHEMA")
    _need(report["run_id"] == c.bundle["run_id"], "RUN_ID")
    unsigned = {k: v for k, v in report.items() if k != "report_sha256"}
    _need(report["report_sha256"] == sha256(canonical_bytes(unsigned)), "REPORT_DIGEST")
    _need(type(request) is dict, "REQUEST_ABSENT")
    binding = request["input"]
    _need(
        type(binding) is dict
        and set(binding) == set(BINDING_KEYS)
        and all(
            canonical_bytes(report[key]) == canonical_bytes(binding[key])
            for key in BINDING_KEYS
        ),
        "BINDING",
    )
    project = c.bundle["project_id"]
    _need(
        request["project_id"] == project
        and report["source_ref"]["snapshot"]["project_id"] == project,
        "PROJECT",
    )
    _need(c.target is not None, "TARGET_PATH")
    _need(
        all(
            type(report[key]) is str and HASH.fullmatch(report[key])
            for key in (
                "proposal_content_id",
                "profile_id",
                "platform_executable_sha256",
                "candidate_sha256",
                "baseline_input_sha256",
                "candidate_input_sha256",
            )
        ),
        "REPORT_DIGEST_FIELDS",
    )
    _need(
        report["apply"] == {"status": "unavailable"}
        and report["evidence"] == "local_unattested"
        and report["runtime_dependencies"] == "not_fully_pinned",
        "AUTHORITY",
    )
    tests = c.tests
    _need(
        type(tests) is dict
        and set(tests) == TESTS_KEYS
        and tests["isolated_infobases"] is True
        and tests["status"] == tests["candidate"]["status"],
        "TESTS_SHAPE",
    )
    for phase in PHASES:
        result = tests[phase]
        if result["status"] == "not_run":
            _need(
                set(result) == {"status", "reason", "native_module_sha256"}
                and result["reason"] == "compiler_diagnostics",
                "NOT_RUN_SHAPE",
            )
        else:
            _need(
                set(result) == EXECUTED_KEYS
                and result["status"] in {"passed", "failed", "incomplete"}
                and result["module_text_verified"] is True
                and result["evidence"] == "parsed_unattested",
                "PHASE_SHAPE",
            )


def _profile_definition(c):
    from .test_profiles import ENGINE_SHA256, _validate

    profile = c.profile
    if profile is None:
        raise _Missing("PROFILE_ABSENT")
    _need(profile != UNREADABLE, "PROFILE_INVALID")
    definition = profile["definition"]
    try:
        _validate(definition)
    except CoreError as exc:
        raise _Mismatch("PROFILE_INVALID") from exc
    binding = c.request["input"]
    _need(
        profile["profile_id"]
        == binding["profile_id"]
        == sha256(canonical_bytes(definition))
        and profile["project_id"] == c.bundle["project_id"],
        "PROFILE_IDENTITY",
    )
    _need(
        definition["platform"]["sha256"] == binding["platform_executable_sha256"],
        "PLATFORM_BINDING",
    )
    engine = c.bundle.get("engine_sha256")
    if engine is None:
        raise _Missing("ENGINE_ABSENT")
    _need(engine == ENGINE_SHA256 == definition["engine_sha256"], "ENGINE_DIGEST")


def _input_inventories(c):
    rows = {}
    for phase in PHASES:
        tree = _tree(c.bundle, phase)
        inventory = _inventory(tree)
        _need(
            sha256(canonical_bytes(inventory)) == c.report[phase + "_input_sha256"],
            phase.upper() + "_INPUT_DIGEST",
        )
        rows[phase] = {item["path"]: item for item in inventory}
    before, after = rows["baseline"], rows["candidate"]
    _need(set(before) == set(after), "INPUT_PATHS")
    _need(c.target in before, "TARGET_ABSENT")
    changed = sorted(path for path in before if before[path] != after[path])
    _need(changed in ([c.target], []), "CHANGED_SET")
    _need(after[c.target]["sha256"] == c.report["candidate_sha256"], "CANDIDATE_DIGEST")
    targets = c.bundle["targets"]
    for phase in PHASES:
        raw = targets.get(phase)
        if raw is None:
            raise _Missing(phase.upper() + "_TARGET_ABSENT")
        _need(type(raw) is bytes, phase.upper() + "_TARGET_" + str(raw).upper())
        _need(sha256(raw) == rows[phase][c.target]["sha256"], "TARGET_READBACK")


def _native_roundtrip(c):
    targets = c.bundle["targets"]
    for phase in PHASES:
        raw = targets.get(phase + "-roundtrip")
        if raw is None:
            raise _Missing(phase.upper() + "_ROUNDTRIP_ABSENT")
        _need(type(raw) is bytes, phase.upper() + "_ROUNDTRIP_" + str(raw).upper())
        _need(
            sha256(raw) == c.tests[phase]["native_module_sha256"],
            phase.upper() + "_ROUNDTRIP_DIGEST",
        )
        source = targets.get(phase)
        if source is None:
            raise _Missing(phase.upper() + "_TARGET_ABSENT")
        _need(type(source) is bytes, phase.upper() + "_TARGET_" + str(source).upper())
        _need(_text(raw) == _text(source), phase.upper() + "_ROUNDTRIP_TEXT")


def _step_sequence(c):
    steps = c.tests["steps"]
    _need(type(steps) is list, "STEPS_SHAPE")
    base, cand = c.executed("baseline"), c.executed("candidate")
    expected = phase_steps("baseline", executed=base, engine_dump=base)
    expected += phase_steps("candidate", executed=cand, engine_dump=cand and not base)
    _need(
        all(type(step) is dict for step in steps)
        and [step.get("name") for step in steps] == expected,
        "STEP_ORDER",
    )
    for step in steps:
        name, code = step["name"], step["exit_code"]
        _need(
            set(step) == (IBCMD_STEP_KEYS if _ibcmd(name) else PLATFORM_STEP_KEYS),
            "STEP_SHAPE",
        )
        _need(type(code) is int, "STEP_EXIT")
        if name.endswith("-compile"):
            phase = name.split("-", 1)[0]
            _need(code == (0 if c.executed(phase) else 101), "COMPILE_EXIT")
        else:
            _need(code == 0, "STEP_EXIT")
        if not _ibcmd(name):
            _need(
                type(step["elapsed_ms"]) is int and step["elapsed_ms"] >= 0,
                "STEP_ELAPSED",
            )
        for suffix in _suffixes(name):
            raw = _evidence(c.files, name + suffix)
            _need(
                sha256(raw) == step[suffix[1:] + "_sha256"],
                "STEP_" + suffix[1:].upper() + "_DIGEST",
            )
            if suffix == ".log":
                _need(type(step["log"]) is str and _log_text(raw) == step["log"], "STEP_LOG_TEXT")
    unexpected = [
        name + suffix
        for name in step_universe()
        if name not in expected
        for suffix in _suffixes(name)
        if c.files.get(name + suffix) is not None
    ]
    _need(not unexpected, "UNEXPECTED_STEP_EVIDENCE")


def _runner_settings(c):
    root = PureWindowsPath(c.bundle["run_root"])
    for phase in PHASES:
        name = phase + "-settings.json"
        if not c.executed(phase):
            _need(c.files.get(name) is None, "UNEXPECTED_PHASE_SETTINGS")
            continue
        raw = _evidence(c.files, name)
        expected = canonical_bytes(
            {
                "filter": {"modules": c.module_names()},
                "reportFormat": "jUnit",
                "reportPath": str(root / (phase + ".junit.xml")),
                "exitCode": str(root / (phase + ".exit")),
                "closeAfterTests": True,
                "showReport": False,
            }
        )
        _need(raw == expected, phase.upper() + "_SETTINGS_CONTENT")
        _need(sha256(raw) == c.tests[phase]["settings_sha256"], phase.upper() + "_SETTINGS_DIGEST")


def _junit_exit(c):
    from .yaxunit_report import parse_report

    for phase in PHASES:
        names = (phase + ".junit.xml", phase + ".exit")
        if not c.executed(phase):
            _need(all(c.files.get(n) is None for n in names), "UNEXPECTED_PHASE_REPORT")
            continue
        junit, exit_raw = (_evidence(c.files, n) for n in names)
        try:
            parsed = parse_report(junit, exit_raw, c.expected_cases())
        except ValueError as exc:
            raise _Mismatch(phase.upper() + "_JUNIT_INVALID") from exc
        result = c.tests[phase]
        for key in (
            "status",
            "counts",
            "cases",
            "junit_sha256",
            "exit_file_sha256",
            "framework_exit_code",
            "evidence",
        ):
            # canonical JSON keeps bool and integer distinct (True == 1 in Python).
            _need(
                canonical_bytes(parsed[key]) == canonical_bytes(result[key]),
                phase.upper() + "_JUNIT_" + key.upper(),
            )
        execute = [s for s in c.tests["steps"] if s.get("name") == phase + "-execute"]
        _need(
            type(result["client_exit_code"]) is int
            and result["client_exit_code"] == 0
            and len(execute) == 1
            and execute[0]["exit_code"] == 0,
            phase.upper() + "_CLIENT_EXIT",
        )


def _engine_source(c):
    claimed = c.tests["engine_source_sha256"]
    if not any(c.executed(phase) for phase in PHASES):
        _need(
            claimed is None and c.bundle["trees"].get("engine-with-tests") is None,
            "ENGINE_SOURCE_UNEXPECTED",
        )
        return
    tree = _tree(c.bundle, "engine-with-tests", exact_directories=False)
    inventory = _inventory(tree, windows_order=True)
    _need(
        type(claimed) is str and sha256(canonical_bytes(inventory)) == claimed,
        "ENGINE_SOURCE_DIGEST",
    )
    c.expected_cases()
    rows = {item["path"]: item for item in inventory}
    for module in c.profile["definition"]["modules"]:
        item = rows.get("CommonModules/" + module["name"] + "/Ext/Module.bsl")
        _need(item is not None and item["sha256"] == module["sha256"], "ENGINE_TEST_MODULE")


def _scratch_cleanup(c):
    cleanup = c.report["scratch_cleanup"]
    _need(type(cleanup) is dict, "CLEANUP_SHAPE")
    released = cleanup.get("released_logical_bytes")
    _need(type(released) is int and released >= 0, "CLEANUP_SHAPE")
    present = c.bundle["scratch_present"]
    if cleanup.get("status") == "completed":
        _need(set(cleanup) == {"status", "released_logical_bytes"}, "CLEANUP_SHAPE")
        _need(not any(present.get(name) for name in SCRATCH), "SCRATCH_PRESENT")
    else:
        _need(
            cleanup.get("status") == "retained"
            and set(cleanup) == {"status", "released_logical_bytes", "reason"}
            and type(cleanup["reason"]) is str,
            "CLEANUP_SHAPE",
        )


_FUNCTIONS = {
    "report_identity": _report_identity,
    "profile_definition": _profile_definition,
    "input_inventories": _input_inventories,
    "native_roundtrip": _native_roundtrip,
    "step_sequence": _step_sequence,
    "runner_settings": _runner_settings,
    "junit_exit": _junit_exit,
    "engine_source": _engine_source,
    "scratch_cleanup": _scratch_cleanup,
}


def _check(function, context):
    try:
        function(context)
    except _Missing as exc:
        return "missing", str(exc)
    except _Mismatch as exc:
        return "mismatch", str(exc)
    except (KeyError, TypeError, AttributeError, IndexError, ValueError):
        return "mismatch", "MALFORMED"
    return "verified", None


def evaluate(bundle):
    """Pure strict comparison over bounded retained bytes; returns a dossier."""
    record = bundle["record"]
    status = record["status"]
    request = record.get("request")
    profile = bundle.get("profile")
    dossier = {
        "schema": 1,
        "kind": "yaxunit-retained-run-qualification",
        "run_id": bundle["run_id"],
        "project_id": bundle["project_id"],
        "run_status": status,
        "failure_code": record["failure"]["code"] if status == "failed" else None,
        "binding": request["input"] if type(request) is dict else None,
        "profile": (
            {"profile_id": profile["profile_id"], "enabled": profile["enabled"]}
            if type(profile) is dict
            else None
        ),
        "candidate_sha256": None,
        "report_sha256": None,
        "test_result": None,
        "evidence": "local_unattested",
        "execution": "not_performed",
        "apply": {"status": "unavailable"},
        "limitations": list(LIMITATIONS),
    }
    if status != "completed":
        rows = [
            {"id": name, "status": "not_applicable", "detail": "RUN_NOT_COMPLETED"}
            for name in CHECKS
        ]
        dossier.update(checks=rows, qualification="incomplete")
    else:
        try:
            context = _Context(bundle)
        except (KeyError, TypeError, AttributeError):
            context = None
        rows = []
        for name in CHECKS:
            state, detail = (
                ("mismatch", "MALFORMED")
                if context is None
                else _check(_FUNCTIONS[name], context)
            )
            rows.append({"id": name, "status": state, "detail": detail})
        states = {row["status"] for row in rows}
        dossier.update(
            checks=rows,
            qualification="inconsistent"
            if "mismatch" in states
            else "incomplete"
            if "missing" in states
            else "consistent",
        )
        report = record["report"]
        if rows[0]["status"] == "verified":
            tests = report["tests"]
            dossier.update(
                candidate_sha256=report["candidate_sha256"],
                report_sha256=report["report_sha256"],
                test_result={
                    "status": tests["status"],
                    "baseline": tests["baseline"]["status"],
                    "candidate": tests["candidate"]["status"],
                },
            )
    dossier["dossier_sha256"] = sha256(canonical_bytes(dossier))
    return dossier


@dataclass(frozen=True)
class QualificationLimits:
    """Trusted typed accounting bounds; never built from request fields."""

    tree_entries: int = 60_000
    tree_bytes: int = 768 * 1024**2
    evidence_bytes: int = 32 * 1024**2
    handles: int = 65_536
    deadline_seconds: int = 300

    def __post_init__(self):
        maxima = (200_000, 4 * 1024**3, 128 * 1024**2, 131_072, 1800)
        if any(
            type(value) is not int or not 1 <= value <= maximum
            for value, maximum in zip(asdict(self).values(), maxima)
        ):
            raise CoreError(
                "INVALID_QUERY_OPTIONS", "Typed bounded qualification limits required"
            )


class _Budget:
    def __init__(self, limits, authorize):
        self.limits, self.authorize = limits, authorize
        self.deadline = time.monotonic() + limits.deadline_seconds
        self.used = dict.fromkeys(
            ("tree_entries", "tree_bytes", "evidence_bytes", "handles"), 0
        )

    def charge(self, kind, amount):
        if time.monotonic() >= self.deadline:
            raise CoreError(
                "TEST_RUN_QUALIFY_TIMEOUT", "Retained run qualification deadline exceeded"
            )
        self.used[kind] += amount
        if self.used[kind] > getattr(self.limits, kind):
            raise CoreError(
                "TEST_RUN_QUALIFY_LIMIT",
                "Retained evidence exceeds qualification limits",
                details={"limit": kind},
            )


UNSAFE_CODES = frozenset({"SOURCE_PATH_UNSAFE", "SNAPSHOT_CORRUPT", "SOURCE_ROOT_UNAVAILABLE"})


def _present(path, *, directory):
    """No-follow existence; a reparse object or wrong type is never absence."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if (
        getattr(info, "st_file_attributes", 0) & 0x400
        or stat.S_ISDIR(info.st_mode) != directory
        or not directory
        and not stat.S_ISREG(info.st_mode)
    ):
        raise CoreError("SOURCE_PATH_UNSAFE", "Retained evidence object is unsafe")
    return True


def _walk(ops, pins, root, budget, stamps):
    from ._windows_source_tree import _retained_stamp

    files, directories = [], []

    def visit(path, expected=None, depth=0):
        if depth > 64:
            raise CoreError("TEST_RUN_QUALIFY_LIMIT", "Retained tree depth limit")
        budget.charge("handles", 1)
        handle = ops.open(path, directory=expected is None or expected.directory)
        pins.callback(ops.close, handle)
        before = _retained_stamp(ops, handle)
        if ops.final_path(handle) != path or (
            expected is not None
            and (
                before.identity != expected.identity
                or before.directory != expected.directory
            )
        ):
            raise CoreError("SOURCE_PATH_UNSAFE", "Retained object identity changed")
        if before.directory:
            if path != root:
                directories.append(path.relative_to(root).as_posix())
            children = []
            for name, child in ops.enumerate(handle):
                budget.charge("tree_entries", 1)
                children.append((name, child))
            budget.authorize()
            for name, child in sorted(children):
                visit(path / name, child, depth + 1)
        else:
            budget.charge("tree_bytes", before.size)
            digest, size = hashlib.sha256(), 0
            for chunk in ops.chunks(handle):
                size += len(chunk)
                if size > before.size:
                    raise CoreError("SNAPSHOT_CORRUPT", "Retained file grew while reading")
                digest.update(chunk)
            if size != before.size:
                raise CoreError("SNAPSHOT_CORRUPT", "Retained file changed while reading")
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size": size,
                    "sha256": digest.hexdigest(),
                }
            )
            stamps.append((handle, before))

    visit(root)
    return {"files": files, "directories": sorted(directories)}


def _read(pins, path, maximum, budget):
    """Pinned bounded read; absent is None, unsafe/oversized become markers."""
    from ._windows_source_tree import pinned_retained

    try:
        if not _present(path, directory=False):
            return None
        size = path.lstat().st_size
        if size > maximum:
            return OVERSIZED
        budget.charge("evidence_bytes", size)
        budget.charge("handles", len(path.parents) + 1)
        return pins.enter_context(pinned_retained(path, maximum))
    except CoreError as exc:
        if exc.code not in UNSAFE_CODES:
            raise
        return UNREADABLE


def _collect(ctx, operation_id, record, run, pins, budget):
    from ._windows_source_tree import WindowsHandleOps, pinned_directory, read_retained
    from . import test_profiles

    ops, stamps = WindowsHandleOps(), []
    pins.enter_context(pinned_directory(run))
    request = record["request"]
    profile = engine = None
    profile_id = request["input"].get("profile_id") if request else None
    if type(profile_id) is str and HASH.fullmatch(profile_id):
        folder = test_profiles.profile_path(ctx, profile_id)
        try:
            if _present(folder, directory=True):
                profile = test_profiles._load(ctx, profile_id)
                engine = sha256(read_retained(folder / "engine.cfe", 8 * 1024**2))
        except CoreError as exc:
            if exc.code not in UNSAFE_CODES | {"TEST_PROFILE_INVALID"}:
                raise
            profile, engine = UNREADABLE, None
    trees = {}
    for name in TREES:
        path = run / name
        try:
            trees[name] = (
                _walk(ops, pins, path, budget, stamps)
                if _present(path, directory=True)
                else None
            )
        except CoreError as exc:
            if exc.code not in UNSAFE_CODES:
                raise
            trees[name] = UNREADABLE
    files = {}
    for name in evidence_names():
        value = _read(pins, run / name, evidence_limit(name), budget)
        if value is not None:
            files[name] = value
    targets = {}
    report = record.get("report")
    target = None
    if type(report) is dict and type(report.get("source_ref")) is dict:
        target = target_path(report["source_ref"].get("relative_path"))
    if target is not None:
        for phase in PHASES:
            for folder in (phase, phase + "-roundtrip"):
                targets[folder] = _read(pins, run / folder / target, MAX_TARGET, budget)
    scratch = {}
    for name in SCRATCH:
        try:
            scratch[name] = _present(run / name, directory=True)
        except CoreError:
            scratch[name] = True
    budget.authorize()
    return {
        "run_id": operation_id,
        "project_id": ctx.project_id,
        "run_root": str(run),
        "record": record,
        "profile": profile,
        "engine_sha256": engine,
        "trees": trees,
        "files": files,
        "targets": targets,
        "scratch_present": scratch,
    }, ops, stamps


def qualify_test_run(ctx, operation_id, *, limits=None):
    """Authorized retained-evidence read; never repeats, applies or opens live inputs."""
    from ._windows_source_tree import _retained_stamp
    from .platform_runs import _get, run_path
    from .snapshots import validate_operation_id
    from .test_profiles import PERMISSIONS, authorized

    limits = QualificationLimits() if limits is None else limits
    if type(limits) is not QualificationLimits:
        raise CoreError(
            "INVALID_QUERY_OPTIONS", "Typed bounded qualification limits required"
        )

    def authorize():
        with ctx.state.transaction(ctx.principal) as tx:
            tx.require_all(PERMISSIONS)

    with authorized(ctx):
        validate_operation_id(operation_id)
        record = _get(ctx, operation_id, namespace="test-runs")
        run = run_path(ctx, operation_id, namespace="test-runs")
        budget = _Budget(limits, authorize)
        try:
            with ExitStack() as pins:
                bundle, ops, stamps = _collect(
                    ctx, operation_id, record, run, pins, budget
                )
                dossier = evaluate(bundle)
                if any(_retained_stamp(ops, handle) != stamp for handle, stamp in stamps):
                    raise CoreError("SNAPSHOT_CORRUPT", "Retained tree changed")
                authorize()
        except CoreError as exc:
            if exc.code in UNSAFE_CODES:
                raise CoreError(
                    "TEST_RUN_EVIDENCE_CHANGED",
                    "Retained evidence changed during qualification",
                ) from exc
            raise
        return dossier
