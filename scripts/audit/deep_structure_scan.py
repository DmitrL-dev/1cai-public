import os
import time
from pathlib import Path
from datetime import datetime

# Configuration
ROOT_DIR = Path(r"c:\1cAI")
IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "htmlcov",
    "site-packages",
    "dist",
    "build",
}
IGNORE_EXTENSIONS = {".pyc", ".pyd", ".pyo"}

# Patterns to flag
SUSPICIOUS_PATTERNS = [
    "verify_",
    "check_",
    "test_manual",
    "demo_",
    "tmp",
    "temp",
    "backup",
    "old",
    "copy",
    "unused",
    "deprecated",
]
SUSPICIOUS_EXTENSIONS = {".log", ".tmp", ".bak", ".old", ".json", ".txt", ".md"}
# Allowed json/md/txt in specific places, but flagged in root or src if they look like reports


def is_ignored(path: Path) -> bool:
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
    return False


def scan_project(root: Path):
    print(f"Scanning {root}...")
    start_time = time.time()

    all_files = []
    flagged_files = []
    empty_dirs = []

    for path in root.rglob("*"):
        if is_ignored(path):
            continue

        if path.is_dir():
            try:
                if not any(path.iterdir()):
                    empty_dirs.append(path)
            except OSError:
                pass
            continue

        if path.suffix in IGNORE_EXTENSIONS:
            continue

        all_files.append(path)

        # Analysis logic
        is_suspicious = False
        reason = []

        # 1. Suspicious Name Patterns
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern in path.name.lower():
                is_suspicious = True
                reason.append(f"Pattern '{pattern}'")

        # 2. Root Clutter
        if path.parent == root:
            if path.suffix in SUSPICIOUS_EXTENSIONS and path.name not in [
                "README.md",
                "LICENSE",
                "requirements.txt",
                "Makefile",
                "setup.py",
                ".gitignore",
                ".env.example",
            ]:
                is_suspicious = True
                reason.append("Root Clutter")

        # 3. Reports in Source
        if (
            "src" in path.parts
            and path.suffix in [".json", ".txt", ".md"]
            and path.name != "README.md"
            and "locales" not in path.parts
        ):
            # Heuristic: src usually contains code, not json reports (except config/locales)
            if "report" in path.name.lower() or "audit" in path.name.lower():
                is_suspicious = True
                reason.append("Report in Source")

        if is_suspicious:
            flagged_files.append(
                {"path": str(path.relative_to(root)), "size": path.stat().st_size, "reason": ", ".join(reason)}
            )

    print(f"\n=== Scan Complete in {time.time() - start_time:.2f}s ===")
    print(f"Total Files Scanned: {len(all_files)}")
    print(f"Empty Directories: {len(empty_dirs)}")
    print(f"Flagged Candidates: {len(flagged_files)}\n")

    print("--- Empty Directories ---")
    for d in empty_dirs[:20]:
        print(f"[EMPTY] {d.relative_to(root)}")
    if len(empty_dirs) > 20:
        print(f"... and {len(empty_dirs)-20} more")

    print("\n--- Flagged Files (Potential Clutter) ---")
    # Group by directory for better readability
    flagged_files.sort(key=lambda x: x["path"])

    current_dir = ""
    for f in flagged_files:
        d = os.path.dirname(f["path"])
        if d != current_dir:
            print(f"\n[DIR] {d if d else '(Root)'}")
            current_dir = d
        print(f"  - {os.path.basename(f['path'])} ({f['size']} bytes) [{f['reason']}]")


if __name__ == "__main__":
    scan_project(ROOT_DIR)
