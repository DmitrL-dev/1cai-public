"""Run the actual pinned Cline extension in an isolated VS Code test host."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def wait_owned(process, log, timeout=300):
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Keep the Popen handle and act only on this still-owned live process.
        # Windows termination of the parent alone would orphan the extension host.
        if process.poll() is None:
            stopped = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=log,
                stderr=log,
                timeout=15,
                check=False,
            )
            # A Windows venv launcher may exit when its child is killed, before
            # taskkill reaches the launcher itself (exit 255, already stopped).
            # Ignore that race only after observing our owned handle as exited.
            if stopped.returncode and process.poll() is None:
                stopped.check_returncode()
            process.wait(timeout=15)
        return 124


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--request-capture", type=Path)
    args = parser.parse_args()
    profile = args.profile.resolve(strict=True)
    config = json.loads((profile / "profile.json").read_text("utf-8"))
    env = os.environ.copy()
    env.update(
        {
            "CLINE_DATA_DIR": str(profile / "cline/data"),
            "CLINE_DIR": str(profile / "cline"),
            "RENTGEN_EDITOR_ACCEPTANCE": str(profile),
            "RENTGEN_EDITOR_PROFILE": str(profile),
            "CLINE_BUNDLE_OVERRIDE": "legacy",
        }
    )
    env.pop("ELECTRON_RUN_AS_NODE", None)
    env.pop("RENTGEN_EDITOR_PROMPT_FILE", None)
    env.pop("RENTGEN_EDITOR_REQUEST_CAPTURE", None)
    if args.request_capture:
        capture = args.request_capture.resolve()
        if not args.prompt_file or capture.parent != profile or capture.exists():
            parser.error(
                "Capture requires a prompt and a new marker directly in this profile"
            )
        env["RENTGEN_EDITOR_REQUEST_CAPTURE"] = str(capture)
    if args.prompt_file:
        env["RENTGEN_EDITOR_PROMPT_FILE"] = str(args.prompt_file.resolve(strict=True))
    host = Path(__file__).with_name("open_editor_host").resolve()
    command = [
        config["editor"],
        "--user-data-dir",
        str(profile / "editor"),
        "--extensions-dir",
        str(profile / "extensions"),
        "--extensionDevelopmentPath=" + str(host),
        "--extensionTestsPath=" + str(host / "host.cjs"),
        "--skip-welcome",
        "--skip-release-notes",
        "--disable-workspace-trust",
        str(profile / "rentgen.code-workspace"),
    ]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    with (profile / "host.log").open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            command, env=env, stdout=log, stderr=log, startupinfo=startup
        )
        (profile / "host-process.json").write_text(
            json.dumps({"pid": process.pid, "args": command}), encoding="utf-8"
        )
        print("Editor acceptance PID", process.pid, flush=True)
        # The caller observes this handle; no timeout triggers another model run.
        code = wait_owned(process, log, timeout=60 if args.request_capture else 300)
        print("Editor exit", code, flush=True)
        raise SystemExit(code)


if __name__ == "__main__":
    main()
