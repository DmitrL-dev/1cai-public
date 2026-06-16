
#!/usr/bin/env python3
"""
Render PlantUML diagrams under docs/architecture to PNG (and optional SVG).

Usage:
    python scripts/docs/render_uml.py [--format png] [--format svg]

The script downloads PlantUML if missing, invokes it via Java in headless mode
and writes outputs into a `png/` (or `svg/`) subdirectory next to each `.puml`.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Sequence


def resolve_output_file(puml_path: Path, fmt: str) -> Path | None:
    out_dir = puml_path.parent / fmt
    if not out_dir.exists():
        return None
    candidates = []
    expected = out_dir / f"{puml_path.stem}.{fmt}"
    if expected.exists():
        return expected
    sanitized = puml_path.stem.replace("-", "_")
    alt = out_dir / f"{sanitized}.{fmt}"
    if alt.exists():
        return alt
    candidates.extend(sorted(out_dir.glob(f"{sanitized}*.{fmt}")))
    candidates.extend(sorted(out_dir.glob(f"{puml_path.stem}*.{fmt}")))
    if not candidates:
        candidates = sorted(out_dir.glob(f"*.{fmt}"))
    return candidates[0] if candidates else None


PLANTUML_VERSION = os.environ.get("PLANTUML_VERSION", "1.2024.7")
TOOLS_DIR = Path("tools")
PLANTUML_JAR = TOOLS_DIR / f"plantuml-{PLANTUML_VERSION}.jar"
PLANTUML_URL = f"https://github.com/plantuml/plantuml/releases/download/v{PLANTUML_VERSION}/plantuml-{PLANTUML_VERSION}.jar"


def ensure_tools_dir() -> None:
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)


def download_plantuml() -> None:
    if PLANTUML_JAR.exists():
        return
    ensure_tools_dir()
    print(f"[render_uml] Downloading PlantUML {PLANTUML_VERSION}...")
    import urllib.request

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with urllib.request.urlopen(PLANTUML_URL) as response, tmp_path.open("wb") as target:
            shutil.copyfileobj(response, target)
        tmp_path.replace(PLANTUML_JAR)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def discover_puml(root: Path) -> List[Path]:
    return sorted(root.rglob("*.puml"))


def run_plantuml(puml_files: Sequence[Path], output_suffix: str) -> None:
    if not puml_files:
        return
    cmd = [
        "java",
        "-Djava.awt.headless=true",
        "-jar",
        str(PLANTUML_JAR),
        f"-t{output_suffix}",
        "-o",
        output_suffix,
    ]
    for file_path in puml_files:
        cmd.append(str(file_path))
    print(f"[render_uml] Rendering {len(puml_files)} diagram(s) to {output_suffix}...")
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)


def hash_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Render PlantUML diagrams.")
    parser.add_argument(
        "--format",
        action="append",
        choices=("png", "svg"),
        help="Output formats to render. Defaults to png.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("docs/architecture"),
        help="Root directory that contains .puml files.",
    )
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Exit with error if no diagrams are found.",
    )
    args = parser.parse_args(argv)

    formats = args.format or ["png"]
    puml_files = discover_puml(args.root)
    if not puml_files and args.fail_on_missing:
        raise SystemExit("[render_uml] No PlantUML files found.")

    download_plantuml()

    for fmt in formats:
        run_plantuml(puml_files, fmt)

    # Create checksums for reproducibility (optional audit)
    checksum_dir = args.root / "checksums"
    checksum_dir.mkdir(exist_ok=True)
    for fmt in formats:
        checksums_path = checksum_dir / f"{fmt}.sha256"
        with checksums_path.open("w", encoding="utf-8") as handle:
            for src in puml_files:
                out = resolve_output_file(src, fmt)
                if out and out.exists():
                    handle.write(f"{hash_file(out)}  {out.as_posix()}\n")
    print("[render_uml] Completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

