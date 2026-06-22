"""Offline dependency/SBOM inventory for productization."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SBOM_PATH = ROOT / "data" / "offline_bundles" / "sbom.json"

REQUIREMENT_FILES = [
    "requirements.txt",
    "code/requirements.txt",
    "code/py_server/requirements.txt",
    "code/py_server/requirements-test.txt",
    "code/py_server/requirements-cache.txt",
    "src/requirements.txt",
]

PACKAGE_FILES = [
    "package.json",
    "portal/package.json",
    "demo/demo-ai-assistants-1c/package.json",
]

PACKAGE_LOCK_FILES = [
    "package-lock.json",
    "portal/package-lock.json",
]

DOCKERFILES = [
    "Dockerfile",
    "Dockerfile.backend",
    "Dockerfile.dev",
    "Dockerfile.gateway",
    "Dockerfile.metrics",
    "docker-compose.yml",
]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any, *, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _safe_rel_path(path: str, *, root: Path) -> str:
    rel = _clean(path, limit=500)
    if not rel:
        raise ValueError("Path must not be empty")
    candidate = (root / rel).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"Path escapes repository root: {path}") from exc
    return str(candidate.relative_to(root_resolved)).replace("\\", "/")


def _safe_output_path(path: Path | None, *, root: Path) -> Path:
    target = path or (root / "data" / "offline_bundles" / "sbom.json")
    candidate = target if target.is_absolute() else root / target
    candidate = candidate.resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"Output path escapes repository root: {target}") from exc
    return candidate


def _component_id(component: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "type": component.get("type"),
            "name": component.get("name"),
            "version": component.get("version"),
            "source_file": component.get("source_file"),
            "scope": component.get("scope"),
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return "cmp_" + hashlib.sha1(payload).hexdigest()[:16]


def _atomic_write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def generate_sbom(
    *,
    root: Path | None = None,
    include_paths: list[str] | None = None,
    include_defaults: bool = True,
    output_path: Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Generate a lightweight offline SBOM from local dependency manifests."""

    base = root or ROOT
    paths = (_default_paths() if include_defaults else []) + [
        (_safe_rel_path(path, root=base), _infer_type(path))
        for path in (include_paths or [])
    ]
    components: list[dict[str, Any]] = []
    sources = []
    missing = []
    seen_sources = set()
    for rel_path, source_type in paths:
        if rel_path in seen_sources:
            continue
        seen_sources.add(rel_path)
        target = base / rel_path
        if not target.exists() or not target.is_file():
            missing.append({"path": rel_path, "type": source_type})
            continue
        sources.append(
            {"path": rel_path, "type": source_type, "size_bytes": target.stat().st_size}
        )
        if source_type == "python":
            components.extend(_parse_requirements(target, rel_path))
        elif source_type == "npm":
            components.extend(_parse_package_json(target, rel_path))
        elif source_type == "npm-lock":
            components.extend(_parse_package_lock(target, rel_path))
        elif source_type == "docker":
            components.extend(_parse_dockerfile(target, rel_path))

    deduped = _dedupe_components(components)
    by_type = Counter(item["type"] for item in deduped)
    by_scope = Counter(item.get("scope") or "unknown" for item in deduped)
    sbom = {
        "bomFormat": "CycloneDX-lite",
        "specVersion": "1.0-local",
        "serialNumber": "urn:uuid:"
        + hashlib.sha1(
            json.dumps(deduped, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "generated_at": _now(),
        "product": "1cAI Enterprise 1C SDLC Platform",
        "summary": {
            "components": len(deduped),
            "sources": len(sources),
            "missing_sources": len(missing),
            "by_type": dict(sorted(by_type.items())),
            "by_scope": dict(sorted(by_scope.items())),
        },
        "sources": sources,
        "missing_sources": missing,
        "components": deduped,
    }
    if write:
        _atomic_write_json(sbom, _safe_output_path(output_path, root=base))
    return sbom


def sbom_markdown_report(
    *,
    root: Path | None = None,
    include_paths: list[str] | None = None,
    include_defaults: bool = True,
) -> dict[str, Any]:
    """Return an SBOM summary as Markdown."""

    sbom = generate_sbom(
        root=root,
        include_paths=include_paths,
        include_defaults=include_defaults,
        write=False,
    )
    lines = [
        "# 1cAI SBOM Inventory",
        "",
        f"- Components: {sbom['summary']['components']}",
        f"- Sources: {sbom['summary']['sources']}",
        f"- Missing sources: {sbom['summary']['missing_sources']}",
        "",
        "## Component Types",
    ]
    lines.extend(
        f"- {name}: {count}" for name, count in sbom["summary"]["by_type"].items()
    )
    lines.extend(["", "## Scopes"])
    lines.extend(
        f"- {name}: {count}" for name, count in sbom["summary"]["by_scope"].items()
    )
    return {"format": "markdown", "content": "\n".join(lines), "sbom": sbom}


def _default_paths() -> list[tuple[str, str]]:
    pairs = []
    pairs.extend((path, "python") for path in REQUIREMENT_FILES)
    pairs.extend((path, "npm") for path in PACKAGE_FILES)
    pairs.extend((path, "npm-lock") for path in PACKAGE_LOCK_FILES)
    pairs.extend((path, "docker") for path in DOCKERFILES)
    return pairs


def _infer_type(path: str) -> str:
    name = Path(path).name.lower()
    if name.startswith("requirements") and name.endswith(".txt"):
        return "python"
    if name == "package.json":
        return "npm"
    if name == "package-lock.json":
        return "npm-lock"
    if name.startswith("dockerfile"):
        return "docker"
    return "custom"


def _parse_requirements(path: Path, rel_path: str) -> list[dict[str, Any]]:
    components = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or raw.startswith("-"):
            continue
        cleaned = raw.split("#", 1)[0].strip()
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*([<>=!~]{1,3}\s*[^;]+)?", cleaned)
        if not match:
            continue
        name = match.group(1)
        version = _clean(
            (match.group(2) or "")
            .replace("=", "")
            .replace("~", "")
            .replace("!", "")
            .replace("<", "")
            .replace(">", ""),
            limit=120,
        )
        components.append(_component("library", name, version, rel_path, "python", raw))
    return components


def _parse_package_json(path: Path, rel_path: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    components = []
    for scope in (
        "dependencies",
        "devDependencies",
        "optionalDependencies",
        "peerDependencies",
    ):
        deps = payload.get(scope)
        if not isinstance(deps, dict):
            continue
        for name, version in deps.items():
            components.append(
                _component(
                    "library",
                    str(name),
                    str(version),
                    rel_path,
                    scope,
                    f"{name}@{version}",
                )
            )
    return components


def _parse_package_lock(path: Path, rel_path: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    components = []
    packages = payload.get("packages")
    if isinstance(packages, dict):
        for package_path, data in packages.items():
            if not package_path or not isinstance(data, dict):
                continue
            name = data.get("name") or str(package_path).split("node_modules/")[-1]
            version = data.get("version") or ""
            scope = "devDependencies" if data.get("dev") else "dependencies"
            components.append(
                _component(
                    "library",
                    str(name),
                    str(version),
                    rel_path,
                    scope,
                    str(package_path),
                )
            )
    return components


def _parse_dockerfile(path: Path, rel_path: str) -> list[dict[str, Any]]:
    components = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw = line.strip()
        if not raw.upper().startswith("FROM "):
            continue
        image = raw.split()[1]
        image = image.split("@", 1)[0]
        name, _, version = image.partition(":")
        components.append(
            _component("container", name, version or "latest", rel_path, "runtime", raw)
        )
    return components


def _component(
    component_type: str, name: str, version: str, source_file: str, scope: str, raw: str
) -> dict[str, Any]:
    component = {
        "type": component_type,
        "name": _clean(name, limit=240),
        "version": _clean(version, limit=160),
        "source_file": source_file,
        "scope": scope,
        "raw": _clean(raw, limit=500),
    }
    component["id"] = _component_id(component)
    return component


def _dedupe_components(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = {}
    for component in components:
        key = (
            component.get("type"),
            str(component.get("name") or "").casefold(),
            component.get("version"),
            component.get("source_file"),
            component.get("scope"),
        )
        seen[key] = component
    return sorted(
        seen.values(),
        key=lambda item: (
            item.get("type", ""),
            item.get("name", ""),
            item.get("source_file", ""),
        ),
    )
