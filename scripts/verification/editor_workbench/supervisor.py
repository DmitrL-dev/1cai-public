"""Own a real editor process tree with the installed Core Windows Job owner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=("install", "first", "restart"))
    args = parser.parse_args()
    if sys.platform != "win32":
        raise RuntimeError("Real Windows editor required")
    from rentgen_core.native_process import OwnedProcess

    launch = json.loads(args.launch.read_text("utf-8"))
    base = args.launch.resolve(strict=True).parent
    editor = Path(launch["editor"])
    with editor.open("rb") as stream:
        editor_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    if not editor.resolve(strict=True).is_relative_to(base) or editor_sha != launch["editor_exe_sha256"]:
        raise RuntimeError("Editor executable binding differs")
    profile = base / "profile"
    original = {key.upper(): value for key, value in os.environ.items()}
    system = Path(original["SYSTEMROOT"])
    # Editor, extension and Java receive no GitHub/Azure/SSH/model credentials.
    env = {k: v for k, v in original.items() if k.upper() in {
        "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC", "PATHEXT",
        "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "SESSIONNAME",
    }}
    env.update(PATH=os.pathsep.join((str(Path(sys.executable).parent), str(system / "System32"), str(system))),
               TEMP=str(base / "temp"), TMP=str(base / "temp"),
               USERPROFILE=str(base / "user-profile"), APPDATA=str(base / "app-data"),
               LOCALAPPDATA=str(profile / "local-app-data"), PYTHONUTF8="1",
               RENTGEN_EDITOR_PROFILE=str(profile))
    for name in ("temp", "user-profile", "app-data"):
        (base / name).mkdir(exist_ok=True)
    command = [str(editor)]
    if args.mode == "install":
        env["ELECTRON_RUN_AS_NODE"] = "1"
        command += [str(editor.parent / "resources/app/out/cli.js"), "--user-data-dir", str(base / "editor-user"),
                    "--extensions-dir", str(base / "extensions"), "--install-extension", launch["vsix"]]
    else:
        env.update(RENTGEN_WORKBENCH_PHASE=args.mode, RENTGEN_WORKBENCH_LAUNCH=str(args.launch.resolve(strict=True)))
        command += ["--user-data-dir", str(base / "editor-user"), "--extensions-dir", str(base / "extensions"),
                    "--extensionDevelopmentPath=" + launch["harness"],
                    "--extensionTestsPath=" + str(Path(launch["harness"]) / "host.cjs"),
                    "--disable-workspace-trust", "--skip-welcome", "--skip-release-notes", "--disable-gpu",
                    "--new-window", str(profile / "workspace")]
    os.environ.clear()
    os.environ.update(env)
    report = {"schema": 1, "mode": args.mode, "accepted": False, "cleanup_complete": False,
              "credential_environment": "explicit_allowlist", "runtime": "actual_windows_process_tree"}
    try:
        with (base / "evidence" / ("editor-" + args.mode + ".log")).open("xb") as log:
            child = None
            try:
                with OwnedProcess(subprocess.list2cmdline(command), editor, log, log, cwd=base) as child:
                    report["editor_process_id"] = child.pid
                    report["exit_code"] = child.wait(timeout=360 if args.mode != "install" else 120)
                    report["active_before_owned_cleanup"] = child.job.active()
                report["cleanup_complete"] = True
            finally:
                if child is not None and child.job.handle is not None:
                    child.close()
                    report["cleanup_complete"] = True
        if report["exit_code"] != 0:
            raise RuntimeError("Editor process returned nonzero")
        report["accepted"] = True
    except Exception as error:
        report["error"] = type(error).__name__
        raise
    finally:
        (base / "evidence" / ("supervisor-" + args.mode + ".json")).write_text(json.dumps(report, indent=2) + "\n", "utf-8")


if __name__ == "__main__":
    main()
