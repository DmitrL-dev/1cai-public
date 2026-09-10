"""Install the pinned BSL runtime from local files; no downloads or execution.

Run with the installed core dev4/dev5/dev6/dev7/dev8 Python and -I. The private pinning interface is
intentionally tied to that release. Existing installations are verified, never
overwritten. An interrupted staging directory is preserved for inspection.
"""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4


def contract():
    import rentgen_core
    from rentgen_diagnostics._runtime_pins import RuntimePins
    from rentgen_diagnostics.bsl_language_server import _runtime_descriptor

    if (
        sys.platform != "win32"
        or sys.version_info[:2] != (3, 11)
        or importlib.metadata.version("rentgen-core")
        not in {"0.1.0.dev4", "0.1.0.dev5", "0.1.0.dev6", "0.1.0.dev7", "0.1.0.dev8"}
        or not Path(rentgen_core.__file__)
        .resolve()
        .is_relative_to(Path(sys.prefix).resolve())
    ):
        raise ValueError(
            "Use installed Windows Python 3.11/core dev4/dev5/dev6/dev7/dev8 with -I"
        )
    descriptor, expected = _runtime_descriptor()
    return descriptor, expected, RuntimePins


def install(*, java_home, jar, local_app_data):
    descriptor, expected, pins_type = contract()
    base, java_home, jar = (
        Path(p).absolute() for p in (local_app_data, java_home, jar)
    )
    parent = base / "Rentgen/runtimes"
    target = parent / descriptor["profile_id"]
    if (
        target.is_relative_to(java_home)
        or java_home.is_relative_to(target)
        or jar.is_relative_to(target)
    ):
        raise ValueError("Source runtime and installation must be separate")
    jar_pin = {
        "expected_size": descriptor["bsl"]["jar_size_bytes"],
        "expected_sha256": descriptor["bsl"]["jar_sha256"],
    }

    def verify(directory):
        pins = pins_type()
        try:
            pins.tree(directory / "jdk", expected)
            pins.file(directory / "bsl-language-server.jar", **jar_pin)
            pins.verify()
        finally:
            pins.close()

    parents = pins_type()
    stage = None
    try:
        # Validate and retain each ancestor before writing under it. Do not
        # resolve away reparse points; RuntimePins must be able to reject them.
        parents.directory(base)
        for directory in (base / "Rentgen", parent):
            directory.mkdir(exist_ok=True)
            parents.directory(directory)
        if target.exists():
            verify(target)
            return {
                "status": "already_present",
                "runtime": str(target),
                "profile_id": descriptor["profile_id"],
            }
        source = pins_type()
        try:
            source.tree(java_home, expected)
            source.file(jar, **jar_pin)
            stage = parent / (".install-" + str(uuid4()))
            stage.mkdir(exist_ok=False)
            (stage / "jdk").mkdir()
            for relative in sorted(expected):
                destination = stage / "jdk" / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(java_home / relative, destination)
            shutil.copyfile(jar, stage / "bsl-language-server.jar")
            source.verify()
        finally:
            source.close()
        verify(stage)
        # Retained ancestor handles also prevent child directory rename on
        # Windows. End the copy ownership interval before publication, resolve
        # both paths again, then re-pin the installed tree before reporting it.
        parents.verify()
        parents.close()
        # Windows rename refuses an existing destination. Both absolute paths
        # must stay under the pinned, explicitly selected installation parent.
        if (
            stage.resolve() != stage
            or target.resolve() != target
            or stage.parent != parent
            or target.parent != parent
        ):
            raise ValueError("Installation paths changed before publication")
        stage.rename(target)
        verify(target)
        return {
            "status": "installed",
            "runtime": str(target),
            "profile_id": descriptor["profile_id"],
            "jdk_files": len(expected),
            "jar_sha256": descriptor["bsl"]["jar_sha256"],
        }
    except Exception as error:
        if stage is not None:
            error.add_note("Inspect the owned installation attempt: " + str(stage))
        raise
    finally:
        parents.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument(
        "--local-app-data", type=Path, default=os.environ.get("LOCALAPPDATA")
    )
    args = parser.parse_args()
    if args.local_app_data is None or not args.local_app_data.is_absolute():
        parser.error("An existing absolute LOCALAPPDATA directory is required")
    print(json.dumps(install(**vars(args)), ensure_ascii=True))


if __name__ == "__main__":
    main()
