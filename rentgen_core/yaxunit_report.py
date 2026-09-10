"""Strict, bounded YAxUnit JUnit evidence; parsing alone does not prove execution."""
import hashlib
import re
import xml.etree.ElementTree as ET


class _Tree(ET.TreeBuilder):
    def __init__(self):
        super().__init__()
        self.nodes = self.depth = 0

    def start(self, tag, attrs):
        self.nodes += 1
        self.depth += 1
        if self.nodes > 20000 or self.depth > 32:
            raise ValueError("JUnit node/depth limit")
        return super().start(tag, attrs)

    def end(self, tag):
        self.depth -= 1
        return super().end(tag)

    def doctype(self, *_):
        raise ValueError("JUnit DTD and entities are forbidden")


def parse_report(raw, exit_raw, expected):
    """Require the exact (classname, name, context) inventory selected by caller."""
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= 2 * 1024**2:
        raise ValueError("JUnit byte limit")
    if not isinstance(exit_raw, bytes) or not 1 <= len(exit_raw) <= 32:
        raise ValueError("Missing or excessive test exit code")
    exit_code = exit_raw.decode("utf-8-sig").strip()
    if exit_code not in {"0", "1"}:
        raise ValueError("Unknown test exit code")
    if not isinstance(expected, (list, tuple)) or not 1 <= len(expected) <= 1000:
        raise ValueError("A bounded nonempty expected test inventory is required")
    if any(
        not isinstance(key, tuple)
        or len(key) != 3
        or any(not isinstance(s, str) or not 1 <= len(s) <= 512 for s in key)
        for key in expected
    ):
        raise ValueError("Invalid expected test identity")
    wanted = set(expected)
    if len(wanted) != len(expected):
        raise ValueError("Duplicate expected test")
    try:
        parser = ET.XMLParser(target=_Tree())
        parser.feed(raw)
        root = parser.close()
    except ET.ParseError as exc:
        raise ValueError("Invalid JUnit XML") from exc
    if root.tag != "testsuites" or any(
        c.tag not in {"testsuite", "properties"} for c in root
    ):
        raise ValueError("Unknown JUnit root structure")
    for container in root.iter():
        if container.tag == "properties" and any(
            child.tag != "property" or len(child) for child in container
        ):
            raise ValueError("Unknown JUnit properties structure")
    observed, cases = set(), []
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in root.findall("testsuite"):
        counts = dict.fromkeys(totals, 0)
        if any(
            c.tag not in {"testcase", "properties", "system-out", "system-err"}
            for c in suite
        ):
            raise ValueError("Unknown JUnit suite structure")
        for case in suite.findall("testcase"):
            key = tuple(case.get(name) for name in ("classname", "name", "context"))
            if key not in wanted or key in observed:
                raise ValueError("Unexpected or duplicate executed test")
            observed.add(key)
            allowed = {
                "failure",
                "error",
                "skipped",
                "system-out",
                "system-err",
                "properties",
            }
            if any(c.tag not in allowed for c in case):
                raise ValueError("Unknown JUnit test structure")
            outcomes = {c.tag for c in case if c.tag in {"failure", "error", "skipped"}}
            if len(outcomes) > 1:
                raise ValueError("Ambiguous test outcome")
            outcome = next(iter(outcomes), "passed")
            counts["tests"] += 1
            if outcome != "passed":
                counts[
                    {"failure": "failures", "error": "errors", "skipped": "skipped"}[
                        outcome
                    ]
                ] += 1
            cases.append(
                {
                    "classname": key[0],
                    "name": key[1],
                    "context": key[2],
                    "outcome": outcome,
                }
            )
        for name, counted in counts.items():
            value = suite.get(name, "")
            if not re.fullmatch(r"[0-9]{1,6}", value) or int(value) != counted:
                raise ValueError("JUnit counters disagree with executed cases")
            totals[name] += counted
    if observed != wanted:
        raise ValueError("Expected tests were not all reported")
    for name, counted in totals.items():
        if name in root.attrib:
            value = root.get(name)
            if not re.fullmatch(r"[0-9]{1,6}", value) or int(value) != counted:
                raise ValueError("JUnit root totals disagree with executed cases")
    failed = totals["failures"] + totals["errors"]
    if (
        failed
        and exit_code != "1"
        or not failed
        and not totals["skipped"]
        and exit_code != "0"
    ):
        raise ValueError("JUnit and framework exit code disagree")
    return {
        "status": "failed"
        if failed
        else "incomplete"
        if totals["skipped"]
        else "passed",
        "counts": {**totals, "passed": totals["tests"] - failed - totals["skipped"]},
        "cases": cases,
        "junit_sha256": hashlib.sha256(raw).hexdigest(),
        "exit_file_sha256": hashlib.sha256(exit_raw).hexdigest(),
        "framework_exit_code": int(exit_code),
        "evidence": "parsed_unattested",
    }
