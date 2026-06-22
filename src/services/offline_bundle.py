"""Offline bundle manifest and integrity verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.productization_readiness import (
    DELIVERABLES,
    REVIEW_FILES,
    ROOT,
    TEST_FILES,
    productization_readiness,
)

DEFAULT_OUTPUT_PATH = ROOT / "data" / "offline_bundles" / "latest_manifest.json"
DEFAULT_ARCHIVE_DIR = ROOT / "data" / "offline_bundles"
SIGNING_KEY_ENV = "ONECAI_BUNDLE_SIGNING_KEY"
LEGACY_SIGNING_KEY_ENV = "1CAI_BUNDLE_SIGNING_KEY"
SUPPORTED_PROFILES = {"pilot", "production", "airgap"}


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
    target = path or (root / "data" / "offline_bundles" / "latest_manifest.json")
    candidate = target if target.is_absolute() else root / target
    candidate = candidate.resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"Output path escapes repository root: {target}") from exc
    return candidate


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _archive_name(profile: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"1cai-{profile}-{stamp}.zip"


def _display_bool(value: bool) -> str:
    return "yes" if value else "no"


def _canonical(payload: dict[str, Any]) -> bytes:
    copy = json.loads(json.dumps(payload, ensure_ascii=False))
    copy.pop("signature", None)
    copy.pop("manifest_sha256", None)
    encoded = json.dumps(
        copy, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return encoded.encode("utf-8")


def _manifest_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _sign(payload: dict[str, Any], signing_key: str) -> dict[str, Any]:
    signature = hmac.new(
        signing_key.encode("utf-8"), _canonical(payload), hashlib.sha256
    ).hexdigest()
    return {
        "signed": True,
        "algorithm": "hmac-sha256",
        "key_hint": hashlib.sha256(signing_key.encode("utf-8")).hexdigest()[:12],
        "value": signature,
    }


def _signing_key(explicit: str | None = None) -> str | None:
    return explicit or os.getenv(SIGNING_KEY_ENV) or os.getenv(LEGACY_SIGNING_KEY_ENV)


def _signature_required(manifest: dict[str, Any]) -> bool:
    installer_profile = (
        manifest.get("installer_profile")
        if isinstance(manifest.get("installer_profile"), dict)
        else {}
    )
    return bool(installer_profile.get("requires_signed_manifest"))


def _passport_decision(manifest: dict[str, Any]) -> dict[str, str]:
    signature = (
        manifest.get("signature") if isinstance(manifest.get("signature"), dict) else {}
    )
    readiness = (
        manifest.get("readiness") if isinstance(manifest.get("readiness"), dict) else {}
    )
    summary = (
        manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    )
    requires_signature = _signature_required(manifest)
    if int(summary.get("missing") or 0):
        return {
            "status": "blocked",
            "headline": "Offline bundle has missing files and must not be delivered.",
        }
    if requires_signature and not signature.get("signed"):
        return {
            "status": "blocked",
            "headline": "Production or airgap delivery requires a signed manifest before handoff.",
        }
    if str(readiness.get("status") or "") == "fail":
        return {
            "status": "risk",
            "headline": "Bundle is complete, but productization readiness has blocking findings.",
        }
    if str(readiness.get("status") or "") == "warn":
        return {
            "status": "warn",
            "headline": "Bundle is deliverable for pilot use with visible productization caveats.",
        }
    return {
        "status": "ready",
        "headline": "Bundle is ready for closed-contour verification and buyer handoff.",
    }


def _verification_steps(
    manifest: dict[str, Any], *, archive_filename: str
) -> list[dict[str, Any]]:
    signature = (
        manifest.get("signature") if isinstance(manifest.get("signature"), dict) else {}
    )
    signed = bool(signature.get("signed"))
    return [
        {
            "step": 1,
            "owner": "Operations",
            "title": "Verify archive payload hashes",
            "command": f"C:\\Python311\\python.exe -m src.services.offline_bundle --verify-archive {archive_filename}",
            "pass_condition": "status is pass; warn is acceptable only for an explicitly unsigned pilot archive",
        },
        {
            "step": 2,
            "owner": "Security",
            "title": "Check signature policy",
            "command": "set ONECAI_BUNDLE_SIGNING_KEY=<customer-secret> before verification"
            if signed
            else "Approve unsigned pilot scope or rebuild with --sign",
            "pass_condition": "production and airgap profiles have signature.signed=true and matching key_hint",
        },
        {
            "step": 3,
            "owner": "Release board",
            "title": "Attach evidence pack",
            "command": "Export Evidence Bundle ZIP and compare SHA-256 manifest before approval",
            "pass_condition": "Evidence Bundle manifest, caveats and Productization passport are attached to the approval packet",
        },
    ]


def _acceptance_gates(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    signature = (
        manifest.get("signature") if isinstance(manifest.get("signature"), dict) else {}
    )
    summary = (
        manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    )
    readiness = (
        manifest.get("readiness") if isinstance(manifest.get("readiness"), dict) else {}
    )
    requires_signature = _signature_required(manifest)
    signed = bool(signature.get("signed"))
    signature_status = "pass" if signed else ("fail" if requires_signature else "warn")
    return [
        {
            "id": "payload-integrity",
            "owner": "Operations",
            "status": "pass" if int(summary.get("missing") or 0) == 0 else "fail",
            "evidence": f"{summary.get('files', 0)} files, {summary.get('missing', 0)} missing, sha256 manifest {manifest.get('manifest_sha256')}",
            "acceptance": "All payload files exist in the archive and match manifest hashes.",
        },
        {
            "id": "signature-policy",
            "owner": "Security",
            "status": signature_status,
            "evidence": f"signed={_display_bool(signed)}, required={_display_bool(requires_signature)}, algorithm={signature.get('algorithm') or 'none'}",
            "acceptance": "Pilot can be unsigned if accepted; production and airgap require a verified HMAC signature.",
        },
        {
            "id": "productization-readiness",
            "owner": "Product owner",
            "status": str(readiness.get("status") or "warn"),
            "evidence": f"decision={readiness.get('release_decision') or summary.get('readiness_decision')}; score={readiness.get('score', 'n/a')}",
            "acceptance": "High findings are closed or explicitly accepted before production rollout.",
        },
        {
            "id": "closed-contour-install",
            "owner": "IT / Operations",
            "status": "warn",
            "evidence": "Archive is self-contained; target infrastructure validation remains customer-local.",
            "acceptance": "Install mode, backup, rollback and network restrictions are validated in the target contour.",
        },
        {
            "id": "buyer-proof-handoff",
            "owner": "Sponsor / vendor lead",
            "status": "pass",
            "evidence": "Delivery passport, manifest, VERIFY.txt and payload are included in one archive.",
            "acceptance": "Security, architect and director receive role-specific handoff notes before pilot start.",
        },
    ]


def build_delivery_passport(
    manifest: dict[str, Any], *, archive_filename: str = "<archive.zip>"
) -> dict[str, Any]:
    """Build a buyer-safe delivery passport for an offline bundle archive."""

    summary = (
        manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    )
    signature = (
        manifest.get("signature") if isinstance(manifest.get("signature"), dict) else {}
    )
    installer_profile = (
        manifest.get("installer_profile")
        if isinstance(manifest.get("installer_profile"), dict)
        else {}
    )
    return {
        "schema_version": "1.0",
        "product": manifest.get("product") or "1cAI Enterprise 1C SDLC Platform",
        "profile": manifest.get("profile") or "pilot",
        "generated_at": _now(),
        "decision": _passport_decision(manifest),
        "package": {
            "archive_filename": archive_filename,
            "manifest_sha256": manifest.get("manifest_sha256"),
            "files": int(summary.get("files") or 0),
            "missing": int(summary.get("missing") or 0),
            "total_bytes": int(summary.get("total_bytes") or 0),
            "signed": bool(signature.get("signed")),
            "signature_algorithm": signature.get("algorithm") or "none",
            "signature_key_hint": signature.get("key_hint"),
        },
        "install_profile": installer_profile,
        "verification_steps": _verification_steps(
            manifest, archive_filename=archive_filename
        ),
        "acceptance_gates": _acceptance_gates(manifest),
        "handoff_by_role": [
            {
                "role": "Developer / QA",
                "opens": "payload/, manifest.json, Evidence Bundle",
                "needs": "Run tests and compare changed artifacts against the manifest before approval.",
            },
            {
                "role": "Architect / Security",
                "opens": "DELIVERY_PASSPORT.md, VERIFY.txt, Productization report",
                "needs": "Confirm local contour, signature policy, SBOM and rights/RLS review gates.",
            },
            {
                "role": "Director / Sponsor",
                "opens": "DELIVERY_PASSPORT.md and Evidence Bundle summary",
                "needs": "See that the product is a local asset with repeatable verification, not a mandatory AI subscription.",
            },
        ],
        "caveats": [
            "The passport proves archive integrity and handoff gates; it is not an OS-native signed installer.",
            "Customer-specific infrastructure, IdP handshakes and production backup drills still require local validation.",
        ],
    }


def delivery_passport_markdown(passport: dict[str, Any]) -> str:
    """Render an offline delivery passport as Markdown."""

    decision = (
        passport.get("decision") if isinstance(passport.get("decision"), dict) else {}
    )
    package = (
        passport.get("package") if isinstance(passport.get("package"), dict) else {}
    )
    install_profile = (
        passport.get("install_profile")
        if isinstance(passport.get("install_profile"), dict)
        else {}
    )
    lines = [
        "# 1cAI Offline Delivery Passport",
        "",
        f"- Product: {passport.get('product')}",
        f"- Profile: `{passport.get('profile')}`",
        f"- Decision: `{decision.get('status')}` - {decision.get('headline')}",
        f"- Archive: `{package.get('archive_filename')}`",
        f"- Manifest SHA-256: `{package.get('manifest_sha256')}`",
        f"- Files: {package.get('files')} / missing: {package.get('missing')} / signed: {_display_bool(bool(package.get('signed')))}",
        f"- Target: {install_profile.get('target', 'n/a')}",
        "",
        "## Verification Steps",
        "",
    ]
    for item in passport.get("verification_steps", []):
        lines.append(
            f"{item['step']}. **{item['owner']}** - {item['title']}: `{item['command']}`"
        )
        lines.append(f"   Pass: {item['pass_condition']}")
    lines.extend(["", "## Acceptance Gates", ""])
    for item in passport.get("acceptance_gates", []):
        lines.append(
            f"- **{item['status']}** `{item['id']}` / {item['owner']}: {item['acceptance']} Evidence: {item['evidence']}"
        )
    lines.extend(["", "## Role Handoff", ""])
    for item in passport.get("handoff_by_role", []):
        lines.append(f"- **{item['role']}** opens `{item['opens']}`: {item['needs']}")
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in passport.get("caveats", []))
    return "\n".join(lines)


def _default_paths() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in DELIVERABLES:
        pairs.append((str(item["path"]), str(item.get("category") or "deliverable")))
    for rel_path in REVIEW_FILES:
        pairs.append((rel_path, "review"))
    for rel_path in TEST_FILES:
        pairs.append((rel_path, "test"))
    pairs.extend(
        [
            ("policy/1cai-default-policy.json", "policy"),
            ("env.example", "ops"),
            ("Dockerfile", "ops"),
            ("docker-compose.yml", "ops"),
        ]
    )
    seen = set()
    unique = []
    for rel_path, category in pairs:
        normalized = rel_path.replace("\\", "/")
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append((normalized, category))
    return unique


def _atomic_write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def build_offline_bundle_manifest(
    *,
    profile: str = "pilot",
    include_paths: list[str] | None = None,
    include_defaults: bool = True,
    output_path: Path | None = None,
    signing_key: str | None = None,
    sign: bool | None = None,
    write: bool = True,
    root: Path | None = None,
) -> dict[str, Any]:
    """Build a reproducible offline bundle manifest with file hashes."""

    base = root or ROOT
    bundle_profile = _clean(profile or "pilot", limit=40).lower()
    if bundle_profile not in SUPPORTED_PROFILES:
        raise ValueError(f"Unsupported offline bundle profile: {profile}")

    requested = [(path, "custom") for path in (include_paths or [])]
    path_specs = (_default_paths() if include_defaults else []) + requested
    artifacts = []
    missing = []
    seen = set()
    for rel_path, category in path_specs:
        safe_rel = _safe_rel_path(rel_path, root=base)
        if safe_rel in seen:
            continue
        seen.add(safe_rel)
        abs_path = base / safe_rel
        if not abs_path.exists() or not abs_path.is_file():
            missing.append(
                {"path": safe_rel, "category": category, "reason": "missing"}
            )
            continue
        artifacts.append(
            {
                "path": safe_rel,
                "category": category,
                "size_bytes": abs_path.stat().st_size,
                "sha256": _sha256_file(abs_path),
            }
        )

    category_counts = Counter(item["category"] for item in artifacts)
    readiness = productization_readiness(root=base)
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "product": "1cAI Enterprise 1C SDLC Platform",
        "profile": bundle_profile,
        "generated_at": _now(),
        "root": str(base),
        "installer_profile": _installer_profile(bundle_profile),
        "summary": {
            "files": len(artifacts),
            "missing": len(missing),
            "total_bytes": sum(item["size_bytes"] for item in artifacts),
            "by_category": dict(sorted(category_counts.items())),
            "readiness_status": readiness["status"],
            "readiness_decision": readiness["release_decision"],
        },
        "artifacts": sorted(artifacts, key=lambda item: item["path"]),
        "missing": missing,
        "readiness": {
            "status": readiness["status"],
            "release_decision": readiness["release_decision"],
            "score": readiness["score"],
            "findings": readiness["findings"],
        },
        "verification": {
            "command": "python -m src.services.offline_bundle --verify data/offline_bundles/latest_manifest.json",
            "hash_algorithm": "sha256",
        },
    }
    manifest["manifest_sha256"] = _manifest_digest(manifest)
    if sign is False:
        key = None
    elif signing_key is not None:
        key = signing_key
    else:
        key = _signing_key()
    manifest["signature"] = (
        _sign(manifest, key)
        if key
        else {"signed": False, "algorithm": "none", "value": None}
    )

    if write:
        _atomic_write_json(manifest, _safe_output_path(output_path, root=base))
    return manifest


def load_offline_bundle_manifest(
    *, manifest_path: Path | None = None
) -> dict[str, Any]:
    """Load a bundle manifest from disk."""

    target = manifest_path or DEFAULT_OUTPUT_PATH
    if not target.exists():
        raise FileNotFoundError(f"Offline bundle manifest not found: {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Offline bundle manifest must be a JSON object")
    return payload


def verify_offline_bundle_manifest(
    *,
    manifest: dict[str, Any] | None = None,
    manifest_path: Path | None = None,
    signing_key: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Verify file hashes and optional manifest signature."""

    payload = manifest or load_offline_bundle_manifest(manifest_path=manifest_path)
    base = root or Path(str(payload.get("root") or ROOT))
    findings = []
    checked = 0
    for missing in payload.get("missing", []):
        if isinstance(missing, dict):
            findings.append(
                {
                    "severity": "high",
                    "code": "bundle-manifest-has-missing-file",
                    "path": missing.get("path"),
                    "reason": missing.get("reason") or "missing",
                }
            )
    for artifact in payload.get("artifacts", []):
        rel_path = _safe_rel_path(str(artifact.get("path") or ""), root=base)
        target = base / rel_path
        if not target.exists() or not target.is_file():
            findings.append(
                {"severity": "high", "code": "bundle-file-missing", "path": rel_path}
            )
            continue
        checked += 1
        actual = _sha256_file(target)
        if actual != artifact.get("sha256"):
            findings.append(
                {
                    "severity": "high",
                    "code": "bundle-file-hash-mismatch",
                    "path": rel_path,
                    "expected": artifact.get("sha256"),
                    "actual": actual,
                }
            )

    expected_digest = payload.get("manifest_sha256")
    actual_digest = _manifest_digest(payload)
    if expected_digest != actual_digest:
        findings.append(
            {
                "severity": "high",
                "code": "manifest-digest-mismatch",
                "expected": expected_digest,
                "actual": actual_digest,
            }
        )

    signature = (
        payload.get("signature") if isinstance(payload.get("signature"), dict) else {}
    )
    key = _signing_key(signing_key)
    if signature.get("signed"):
        if not key:
            findings.append(
                {
                    "severity": "medium",
                    "code": "signature-key-missing",
                    "message": "Signed manifest requires signing key for verification.",
                }
            )
        else:
            expected = _sign(payload, key)["value"]
            if expected != signature.get("value"):
                findings.append(
                    {
                        "severity": "high",
                        "code": "signature-mismatch",
                        "message": "Manifest signature does not match.",
                    }
                )
    else:
        findings.append(
            {
                "severity": "medium",
                "code": "manifest-unsigned",
                "message": "Manifest is not signed.",
            }
        )

    severities = Counter(item["severity"] for item in findings)
    status = "fail" if severities.get("high") else ("warn" if findings else "pass")
    return {
        "status": status,
        "checked_files": checked,
        "summary": {
            "findings": len(findings),
            "high": severities.get("high", 0),
            "medium": severities.get("medium", 0),
            "low": severities.get("low", 0),
            "manifest_path": str(manifest_path or DEFAULT_OUTPUT_PATH),
        },
        "signature": signature,
        "findings": findings,
    }


def build_offline_bundle_archive(
    *,
    profile: str = "pilot",
    include_paths: list[str] | None = None,
    include_defaults: bool = True,
    output_path: Path | None = None,
    signing_key: str | None = None,
    sign: bool | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Create a portable ZIP archive containing payload files and manifest."""

    base = root or ROOT
    manifest = build_offline_bundle_manifest(
        profile=profile,
        include_paths=include_paths,
        include_defaults=include_defaults,
        signing_key=signing_key,
        sign=sign,
        write=False,
        root=base,
    )
    if manifest.get("missing"):
        raise ValueError(
            f"Cannot build offline archive with missing files: {len(manifest['missing'])}"
        )

    archive_path = _safe_output_path(
        output_path or (DEFAULT_ARCHIVE_DIR / _archive_name(manifest["profile"])),
        root=base,
    )
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    passport = build_delivery_passport(manifest, archive_filename=archive_path.name)
    passport_markdown = delivery_passport_markdown(passport)
    verify_text = "\n".join(
        [
            "1cAI offline bundle",
            "",
            "Verify manifest and payload before installation:",
            "C:\\Python311\\python.exe -m src.services.offline_bundle --verify-archive <archive.zip>",
            "",
            "Read DELIVERY_PASSPORT.md before customer handoff; it contains role-specific gates and acceptance checks.",
            "",
            "For signed manifests, set ONECAI_BUNDLE_SIGNING_KEY before verification.",
            "",
        ]
    )
    with zipfile.ZipFile(
        archive_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        archive.writestr(
            "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2)
        )
        archive.writestr(
            "DELIVERY_PASSPORT.json", json.dumps(passport, ensure_ascii=False, indent=2)
        )
        archive.writestr("DELIVERY_PASSPORT.md", passport_markdown)
        archive.writestr("VERIFY.txt", verify_text)
        for artifact in manifest["artifacts"]:
            rel_path = _safe_rel_path(artifact["path"], root=base)
            archive.write(base / rel_path, f"payload/{rel_path}")

    return {
        "status": "created",
        "archive_path": str(archive_path),
        "archive_sha256": _sha256_file(archive_path),
        "size_bytes": archive_path.stat().st_size,
        "archive_files": [
            "manifest.json",
            "DELIVERY_PASSPORT.json",
            "DELIVERY_PASSPORT.md",
            "VERIFY.txt",
        ]
        + [f"payload/{artifact['path']}" for artifact in manifest["artifacts"]],
        "manifest": manifest,
        "delivery_passport": passport,
        "delivery_passport_markdown": passport_markdown,
    }


def verify_offline_bundle_archive(
    *,
    archive_path: Path,
    signing_key: str | None = None,
) -> dict[str, Any]:
    """Verify a ZIP offline bundle without extracting it."""

    if not archive_path.exists() or not archive_path.is_file():
        raise FileNotFoundError(f"Offline bundle archive not found: {archive_path}")

    findings: list[dict[str, Any]] = []
    checked = 0
    passport: dict[str, Any] | None = None
    with zipfile.ZipFile(archive_path, "r") as archive:
        names = set(archive.namelist())
        if "manifest.json" not in names:
            return {
                "status": "fail",
                "checked_files": 0,
                "archive_path": str(archive_path),
                "findings": [
                    {
                        "severity": "high",
                        "code": "archive-manifest-missing",
                        "message": "Archive has no manifest.json.",
                    }
                ],
                "summary": {"findings": 1, "high": 1, "medium": 0, "low": 0},
            }
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("Archive manifest must be a JSON object")
        if "DELIVERY_PASSPORT.json" in names:
            passport = json.loads(
                archive.read("DELIVERY_PASSPORT.json").decode("utf-8")
            )
            if not isinstance(passport, dict):
                findings.append(
                    {
                        "severity": "high",
                        "code": "archive-passport-invalid",
                        "message": "DELIVERY_PASSPORT.json must be a JSON object.",
                    }
                )
                passport = None
            else:
                package = (
                    passport.get("package")
                    if isinstance(passport.get("package"), dict)
                    else {}
                )
                if package.get("manifest_sha256") != manifest.get("manifest_sha256"):
                    findings.append(
                        {
                            "severity": "high",
                            "code": "archive-passport-manifest-mismatch",
                            "expected": manifest.get("manifest_sha256"),
                            "actual": package.get("manifest_sha256"),
                        }
                    )
        else:
            findings.append(
                {
                    "severity": "medium",
                    "code": "archive-passport-missing",
                    "message": "Archive has no DELIVERY_PASSPORT.json buyer handoff file.",
                }
            )
        if "DELIVERY_PASSPORT.md" not in names:
            findings.append(
                {
                    "severity": "medium",
                    "code": "archive-passport-markdown-missing",
                    "message": "Archive has no DELIVERY_PASSPORT.md buyer handoff file.",
                }
            )

        for missing in manifest.get("missing", []):
            if isinstance(missing, dict):
                findings.append(
                    {
                        "severity": "high",
                        "code": "archive-manifest-has-missing-file",
                        "path": missing.get("path"),
                        "reason": missing.get("reason") or "missing",
                    }
                )
        for artifact in manifest.get("artifacts", []):
            rel_path = str(artifact.get("path") or "").replace("\\", "/")
            member = f"payload/{rel_path}"
            if member not in names:
                findings.append(
                    {
                        "severity": "high",
                        "code": "archive-payload-missing",
                        "path": rel_path,
                    }
                )
                continue
            checked += 1
            actual = _sha256_bytes(archive.read(member))
            if actual != artifact.get("sha256"):
                findings.append(
                    {
                        "severity": "high",
                        "code": "archive-payload-hash-mismatch",
                        "path": rel_path,
                        "expected": artifact.get("sha256"),
                        "actual": actual,
                    }
                )

    expected_digest = manifest.get("manifest_sha256")
    actual_digest = _manifest_digest(manifest)
    if expected_digest != actual_digest:
        findings.append(
            {
                "severity": "high",
                "code": "manifest-digest-mismatch",
                "expected": expected_digest,
                "actual": actual_digest,
            }
        )

    signature = (
        manifest.get("signature") if isinstance(manifest.get("signature"), dict) else {}
    )
    key = _signing_key(signing_key)
    if signature.get("signed"):
        if not key:
            findings.append(
                {
                    "severity": "medium",
                    "code": "signature-key-missing",
                    "message": "Signed archive manifest requires signing key for verification.",
                }
            )
        else:
            expected = _sign(manifest, key)["value"]
            if expected != signature.get("value"):
                findings.append(
                    {
                        "severity": "high",
                        "code": "signature-mismatch",
                        "message": "Archive manifest signature does not match.",
                    }
                )
    else:
        findings.append(
            {
                "severity": "medium",
                "code": "manifest-unsigned",
                "message": "Archive manifest is not signed.",
            }
        )

    severities = Counter(item["severity"] for item in findings)
    status = "fail" if severities.get("high") else ("warn" if findings else "pass")
    return {
        "status": status,
        "archive_path": str(archive_path),
        "archive_sha256": _sha256_file(archive_path),
        "checked_files": checked,
        "signature": signature,
        "delivery_passport": passport,
        "summary": {
            "findings": len(findings),
            "high": severities.get("high", 0),
            "medium": severities.get("medium", 0),
            "low": severities.get("low", 0),
        },
        "findings": findings,
    }


def _installer_profile(profile: str) -> dict[str, Any]:
    profiles = {
        "pilot": {
            "offline": True,
            "target": "single-node pilot or internal demo",
            "requires_signed_manifest": False,
            "services": ["api", "portal", "local-data"],
        },
        "production": {
            "offline": True,
            "target": "customer-controlled production contour",
            "requires_signed_manifest": True,
            "services": ["api", "portal", "local-data", "audit-export", "backup"],
        },
        "airgap": {
            "offline": True,
            "target": "air-gapped enterprise contour",
            "requires_signed_manifest": True,
            "services": [
                "api",
                "portal",
                "local-data",
                "audit-export",
                "backup",
                "local-model",
            ],
        },
    }
    return profiles[profile]


def _main() -> int:  # pragma: no cover - CLI convenience
    import argparse

    parser = argparse.ArgumentParser(
        description="Build or verify 1cAI offline bundle manifests."
    )
    parser.add_argument(
        "--profile", default="pilot", choices=sorted(SUPPORTED_PROFILES)
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--sign", action="store_true")
    parser.add_argument("--verify")
    parser.add_argument("--archive", action="store_true")
    parser.add_argument("--verify-archive")
    args = parser.parse_args()

    if args.verify_archive:
        result = verify_offline_bundle_archive(archive_path=Path(args.verify_archive))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] != "fail" else 1

    if args.verify:
        result = verify_offline_bundle_manifest(manifest_path=Path(args.verify))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] != "fail" else 1

    if args.archive:
        result = build_offline_bundle_archive(
            profile=args.profile, output_path=Path(args.output), sign=args.sign
        )
        print(
            json.dumps(
                {
                    "path": result["archive_path"],
                    "sha256": result["archive_sha256"],
                    "files": result["manifest"]["summary"]["files"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    manifest = build_offline_bundle_manifest(
        profile=args.profile, output_path=Path(args.output), sign=args.sign
    )
    print(
        json.dumps(
            {
                "path": args.output,
                "summary": manifest["summary"],
                "signed": manifest["signature"]["signed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
