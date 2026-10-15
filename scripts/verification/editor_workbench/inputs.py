"""Fixed public runtime inputs and exact checkout/VSIX binding; no user URLs."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

PINS = {
    "editor": {
        "version": "1.135.06055", "api_version": "1.135.0",
        "url": "https://github.com/VSCodium/vscodium/releases/download/1.135.06055/VSCodium-win32-x64-1.135.06055.zip",
        "size_bytes": 250898961,
        "sha256": "0bec978f201238624bc9ad43966f5e201ed8afacc37d77035a822252d9c9c200",
        "license": "MIT", "license_url": "https://github.com/VSCodium/vscodium/blob/1.135.06055/LICENSE",
    },
    "java": {
        "version": "Temurin-21.0.12.1+1-LTS",
        "url": "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip",
        "size_bytes": 205073461,
        "sha256": "f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e",
        "license": "GPL-2.0 WITH Classpath-exception-2.0",
        "license_url": "https://github.com/adoptium/temurin21-binaries/releases/tag/jdk-21.0.12.1%2B1",
    },
    "bsl": {
        "version": "1.0.5",
        "url": "https://github.com/1c-syntax/bsl-language-server/releases/download/v1.0.5/bsl-language-server-1.0.5-exec.jar",
        "size_bytes": 131962428,
        "sha256": "de97f571e6474c5c151cf859294f589ee01152de3b4826b43e1a80b69ee2602a",
        "license": "LGPL-3.0-or-later",
        "license_url": "https://github.com/1c-syntax/bsl-language-server/blob/v1.0.5/LICENSE",
    },
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    require(len(data) <= 2 * 1024**2, "Receipt exceeds 2 MiB")
    with Path(path).open("xb") as stream:
        stream.write(data)


class _HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        require(target.scheme == "https" and target.hostname in {
            "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com",
        } and target.username is None and target.password is None, "Unapproved runtime redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(name, destination):
    """Three bounded public downloads at most; never forward authentication."""
    pin = PINS[name]
    require(not destination.exists(), "Download destination must be new")
    opener = urllib.request.build_opener(_HTTPSRedirect())
    attempts = []
    for attempt in range(1, 4):
        path = destination.with_name(destination.name + f".attempt-{attempt}")
        record = {"attempt": attempt, "verified": False}
        attempts.append(record)
        started = time.monotonic()
        try:
            request = urllib.request.Request(pin["url"], headers={"User-Agent": "Rentgen-editor-acceptance"})
            with opener.open(request, timeout=30) as source, path.open("xb") as target:
                require(urllib.parse.urlsplit(source.url).scheme == "https", "Runtime origin is not HTTPS")
                total = 0
                while chunk := source.read(1024 * 1024):
                    total += len(chunk)
                    require(total <= pin["size_bytes"], "Runtime download exceeds pinned size")
                    require(time.monotonic() - started <= 180, "Runtime download deadline")
                    target.write(chunk)
            require(total == pin["size_bytes"] and digest(path) == pin["sha256"], "Runtime size or SHA256 differs")
            path.rename(destination)
            record["verified"] = True
            return {"name": name, **pin, "attempts": attempts}
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            record["error_type"] = type(error).__name__
            record["http_status"] = getattr(error, "code", None)
            transient = isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError)
            if isinstance(error, urllib.error.HTTPError):
                transient = error.code in {408, 429, 500, 502, 503, 504}
            if not transient or attempt == 3:
                raise RuntimeError(f"Pinned {name} download failed on attempt {attempt}: {type(error).__name__}") from None
            time.sleep(2 if attempt == 1 else 5)
    raise RuntimeError("No verified runtime download")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bind_checkout(checkout, expected, trigger_head, vsix):
    require(all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (expected, trigger_head)), "Exact source SHAs required")
    actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], timeout=15).decode().strip()
    require(actual == expected, "Checkout source differs from event")
    paths = ["rentgen_core", "rentgen_graph", "rentgen_diagnostics", "integrations/vscode-rentgen",
             "integrations/open-editor", "scripts/verification/editor_workbench",
             "scripts/verification/kit_inputs.py", "scripts/verification/verify_service_scm_delivery.py", "pyproject.toml"]
    tree = subprocess.check_output(["git", "-C", str(checkout), "ls-tree", "-rz", actual, "--", *paths], timeout=15)
    inventory = {}
    for record in tree.split(b"\0"):
        if not record:
            continue
        header, name = record.split(b"\t", 1)
        mode, kind, blob = header.decode().split()
        name = name.decode("utf-8")
        path = checkout / name
        require(kind == "blob" and mode in ("100644", "100755") and not path.is_symlink(), "Non-regular bound source")
        raw = path.read_bytes()
        require(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == blob, "Source bytes differ from Git: " + name)
        inventory[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
    require(inventory, "Empty source inventory")
    builder = load(checkout / "integrations/vscode-rentgen/build.py", "editor_workbench_vsix_builder")
    expected_vsix = builder.build_bytes()
    require(vsix.read_bytes() == expected_vsix, "VSIX does not reproduce bound checkout")
    package = json.loads((checkout / "integrations/vscode-rentgen/package.json").read_text("utf-8"))
    return {"schema": 1, "source_commit": actual, "trigger_head": trigger_head,
            "scope": "actual checkout; pull_request may be GitHub test merge",
            "recorded_at": datetime.now(timezone.utc).isoformat(), "files": inventory,
            "vsix_sha256": digest(vsix), "vsix_size_bytes": vsix.stat().st_size,
            "companion_id": package["publisher"] + "." + package["name"],
            "companion_version": package["version"]}
