"""Check current Core/Companion pair claims against the single READINESS source.

Every "Core devN / Companion X.Y.Z" phrase in a current document must name the
published pair declared by the READINESS heading. Release tags are checked on
the front-door pages, where they mean the current release; elsewhere a tag is a
citation of an immutable release. Historical sections (a heading containing
"истор" or "history"), dated or version-scoped documents, evidence and release
records keep their original numbers.
The check reads text only; it never edits files.
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
READINESS = Path("docs/product/READINESS.md")
HEADING = re.compile(
    r"^## Текущая опубликованная пара — Core dev(\d+) / Companion (\d+\.\d+\.\d+)$",
    re.M,
)
PAIR = re.compile(r"Core (?:0\.1\.0\.)?dev(\d+)\s*/\s*Companion (\d+\.\d+\.\d+)")
CORE_TAG = re.compile(r"core-v0\.1\.0-dev(\d+)")
COMPANION_TAG = re.compile(r"companion-v(\d+\.\d+\.\d+)")
SUFFIXES = {".md", ".html"}
HISTORY_DIRS = (
    "docs/product/evidence/",
    "releases/",
    "docs/superpowers/",
    "node_modules/",
    ".git/",
)
DATED = re.compile(r"(?:^|[-_])(?:20\d{6}|DEV\d+)(?:[-_.]|$)")
TAG_FILES = frozenset(
    {
        "README.md",
        "GETTING_STARTED.md",
        "docs/README.md",
        "docs/START_HERE.md",
        "docs/USER_GUIDE.md",
        "site/index.html",
    }
)
HISTORY_HEADING = re.compile(r"истор|history", re.I)


def published_pair(root):
    text = (root / READINESS).read_text("utf-8")
    found = HEADING.findall(text)
    if len(found) != 1:
        raise ValueError("READINESS must declare exactly one current published pair")
    core, companion = found[0]
    return "0.1.0.dev" + core, companion


def _current_files(root):
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if (
            path.suffix in SUFFIXES
            and path.is_file()
            and not path.is_symlink()
            and not relative.startswith(HISTORY_DIRS)
            and not DATED.search(path.stem)
        ):
            yield relative, path


def scan(root=ROOT):
    """Return (pair, findings); findings name file, line and the stale claim."""
    core, companion = published_pair(root)
    core_number = core.removeprefix("0.1.0.dev")
    findings = []
    for relative, path in _current_files(root):
        historical = False
        for number, line in enumerate(path.read_text("utf-8").splitlines(), 1):
            if line.startswith("#"):
                historical = bool(HISTORY_HEADING.search(line))
            if historical:
                continue
            claims = [
                ("pair", f"dev{a} / {b}")
                for a, b in PAIR.findall(line)
                if (a, b) != (core_number, companion)
            ]
            if relative in TAG_FILES:
                claims += [
                    ("core_tag", "core-v0.1.0-dev" + a)
                    for a in CORE_TAG.findall(line)
                    if a != core_number
                ]
                claims += [
                    ("companion_tag", "companion-v" + a)
                    for a in COMPANION_TAG.findall(line)
                    if a != companion
                ]
            findings += [
                {"file": relative, "line": number, "kind": kind, "claim": claim}
                for kind, claim in claims
            ]
    return {"core": core, "companion": companion}, findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    pair, findings = scan(args.root.resolve())
    print(json.dumps({"published_pair": pair, "findings": findings}, ensure_ascii=False, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
