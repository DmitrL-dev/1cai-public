"""Run BSL-only editor acceptance on an explicitly selected synthetic manual fixture."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from kit_inputs import extract
from run_open_editor_host import wait_owned


def run(args):
    profile = args.profile.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    extract(args.vsix.resolve(strict=True), output / "unpacked")
    env = os.environ.copy()
    env.pop("ELECTRON_RUN_AS_NODE", None)
    env.pop("RENTGEN_BSL_ACCEPTANCE_PRIOR", None)
    env.update(
        RENTGEN_EDITOR_PROFILE=str(profile),
        RENTGEN_BSL_ACCEPTANCE_OUTPUT=str(output / "acceptance.json"),
        LOCALAPPDATA=str(args.local_app_data.resolve(strict=True)),
    )
    if args.prior:
        env["RENTGEN_BSL_ACCEPTANCE_PRIOR"] = str(args.prior.resolve(strict=True))
    script = Path(__file__).with_name("companion_host") / "bsl.cjs"
    command = [
        str(args.editor.resolve(strict=True)),
        "--user-data-dir",
        str(output / "user"),
        "--extensions-dir",
        str(output / "extensions"),
        "--extensionDevelopmentPath=" + str(output / "unpacked/extension"),
        "--extensionTestsPath=" + str(script.resolve()),
        "--disable-workspace-trust",
        "--skip-welcome",
        "--skip-release-notes",
        str(profile / "workspace"),
    ]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    with (output / "host.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command, env=env, stdout=log, stderr=log, startupinfo=startup
        )
        code = wait_owned(process, log, timeout=480)
    print(json.dumps({"exit_code": code, "report": str(output / "acceptance.json")}))
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("profile", "output", "vsix", "editor", "local-app-data"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--prior", type=Path)
    raise SystemExit(run(parser.parse_args()))
