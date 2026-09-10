"""Create an owned infobase and verify native XML/BSL round trips with 1C."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from uuid import uuid4


MODULE = "RentgenPlatformProbe"
GOOD = "Function Calculate() Export\n    Return 40 + 2;\nEndFunction\n"
BROKEN = "Function Calculate() Export\n    Return 40 + ;\nEndFunction\n"
REPAIRED = "Function Calculate() Export\n    Return 40 + 3;\nEndFunction\n"
NS = "http://v8.1c.ru/8.3/MDClasses"
APPLICATION = f"""Procedure OnStart()
    Result = {MODULE}.Calculate();
    Output = New TextDocument;
    Output.SetText(String(Result));
    Output.Write(LaunchParameter, TextEncoding.UTF8);
    Exit(False);
EndProcedure
"""


def normalized_bsl(path):
    return path.read_text("utf-8-sig").replace("\r\n", "\n")


def object_uuid(path, kind):
    root = ET.parse(path).getroot()
    return root.find(f"{{{NS}}}{kind}").attrib["uuid"]


class PlatformRun:
    def __init__(self, executable, output, timeout):
        if os.name != "nt":
            raise RuntimeError("Native platform verification requires Windows")
        self.executable = executable.resolve(strict=True)
        if self.executable.name.lower() != "1cv8.exe":
            raise ValueError("Use the full 1cv8.exe client")
        if not 5 <= timeout <= 300:
            raise ValueError("Timeout must be 5..300 seconds per command")
        self.output = output.resolve()
        # Reserve exclusively: never attach to or replace a user's existing base.
        self.output.mkdir(parents=True, exist_ok=False)
        self.base = self.output / "infobase"
        self.timeout = timeout
        self.steps = []

    def command(self, name, args, *, expect_error=False):
        log = self.output / (name + ".log")
        arguments = [
            str(self.executable),
            *map(str, args),
            "/DisableStartupDialogs",
            "/DisableStartupMessages",
            "/Out",
            str(log),
        ]
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        started = time.monotonic()
        timed_out = False
        with (self.output / (name + ".stdout.log")).open("xb") as stdout, (
            self.output / (name + ".stderr.log")
        ).open("xb") as stderr:
            # 1C parses doubled embedded quotes; Windows CRT list2cmdline would
            # insert backslashes and corrupt a quoted connection-string value.
            command_line = " ".join(
                '"' + arg.replace('"', '""') + '"'
                if any(char.isspace() or char == '"' for char in arg)
                else arg
                for arg in arguments
            )
            child = subprocess.Popen(
                command_line,
                executable=str(self.executable),
                startupinfo=startup,
                stdout=stdout,
                stderr=stderr,
            )
            try:
                child.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                # Also clean up on Ctrl+C; only this invocation's child is owned.
                if child.poll() is None:
                    subprocess.run(
                        ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                        capture_output=True,
                        timeout=15,
                        check=False,
                    )
                    child.wait(timeout=15)
        raw = log.read_bytes() if log.exists() else b""
        try:
            log_text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            log_text = raw.decode("cp1251")
        step = {
            "name": name,
            "arguments": arguments[1:],
            "exit_code": child.returncode,
            "timed_out": timed_out,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "log": log_text,
            "log_sha256": hashlib.sha256(raw).hexdigest(),
        }
        self.steps.append(step)
        (self.output / "steps.json").write_text(
            json.dumps(self.steps, ensure_ascii=False, indent=2), "utf-8"
        )
        print(
            json.dumps(
                {"step": name, "exit_code": child.returncode, "timed_out": timed_out}
            ),
            flush=True,
        )
        if timed_out or not log.exists():
            raise RuntimeError(f"{name}: timeout or missing platform log")
        if expect_error:
            if (
                child.returncode != 101
                or MODULE not in log_text
                or "(2," not in log_text
            ):
                raise RuntimeError(
                    f"{name}: expected compiler rejection naming {MODULE}"
                )
        elif child.returncode != 0:
            raise RuntimeError(
                f"{name}: platform returned {child.returncode}; inspect {log}"
            )
        return step

    def designer(self, name, *args, expect_error=False):
        return self.command(
            name, ["DESIGNER", "/F", self.base, *args], expect_error=expect_error
        )

    def dump(self, name):
        folder = self.output / name
        folder.mkdir()
        self.designer(name, "/DumpConfigToFiles", folder)
        return folder

    def execute(self, name, expected):
        result = self.output / (name + ".txt")
        if result.exists():
            raise FileExistsError(result)
        self.command(name, ["ENTERPRISE", "/F", self.base, "/C", result])
        actual = result.read_text("utf-8-sig").strip()
        if actual != str(expected):
            raise RuntimeError(
                f"{name}: expected runtime value {expected}, got {actual!r}"
            )
        return int(actual)


def verify(executable, output, timeout=60):
    run = PlatformRun(executable, output, timeout)
    # Quote the File value for 1C's connection parser, then quote the entire
    # argument for 1C's command-line parser in command(). No shell is involved.
    if any(char in str(run.base) for char in (";", '"', "\r", "\n")):
        raise ValueError("Output path contains a connection-string delimiter")
    run.command("create", ["CREATEINFOBASE", f'File="{run.base}";Locale=ru_RU;'])
    if not (run.base / "1Cv8.1CD").is_file():
        raise RuntimeError("1C did not create the owned infobase")
    baseline = run.dump("baseline")
    native = (baseline / "Configuration.xml").read_bytes()
    configuration_id = object_uuid(baseline / "Configuration.xml", "Configuration")
    candidate = run.output / "candidate"
    shutil.copytree(baseline, candidate)
    # Preserve every namespace and QName value in the native root document.
    marker = b"</ChildObjects>"
    if native.count(marker) != 1:
        raise RuntimeError("Unsupported native root: expected one ChildObjects list")
    (candidate / "Configuration.xml").write_bytes(
        native.replace(
            marker, f"<CommonModule>{MODULE}</CommonModule>\n\t\t".encode() + marker
        )
    )
    module_id = str(uuid4())
    namespace_header = (
        native.decode("utf-8-sig").split("<MetaDataObject", 1)[1].split(">", 1)[0]
    )
    module_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject{namespace_header}>
  <CommonModule uuid="{module_id}">
    <Properties>
      <Name>{MODULE}</Name><Synonym/><Comment/>
      <Global>false</Global><ClientManagedApplication>false</ClientManagedApplication>
      <Server>true</Server><ExternalConnection>true</ExternalConnection>
      <ClientOrdinaryApplication>false</ClientOrdinaryApplication><ServerCall>true</ServerCall>
      <Privileged>false</Privileged><ReturnValuesReuse>DontUse</ReturnValuesReuse>
    </Properties>
  </CommonModule>
</MetaDataObject>
"""
    module_path = Path("CommonModules") / MODULE / "Ext/Module.bsl"
    (candidate / module_path).parent.mkdir(parents=True)
    (candidate / f"CommonModules/{MODULE}.xml").write_text(module_xml, "utf-8")
    (candidate / module_path).write_text(GOOD, "utf-8")
    application_path = Path("Ext/ManagedApplicationModule.bsl")
    (candidate / application_path).parent.mkdir(exist_ok=True)
    (candidate / application_path).write_text(APPLICATION, "utf-8")
    run.designer("load-good", "/LoadConfigFromFiles", candidate)
    run.designer(
        "check-good", "/CheckConfig", "-Server", "-ExternalConnection", "-ThinClient"
    )
    run.designer("update-good", "/UpdateDBCfg")
    initial_value = run.execute("execute-good", 42)
    first = run.dump("first-roundtrip")
    if object_uuid(first / f"CommonModules/{MODULE}.xml", "CommonModule") != module_id:
        raise RuntimeError("Common module UUID changed")
    if normalized_bsl(first / module_path) != GOOD:
        raise RuntimeError("Initial BSL round trip changed content")

    broken = run.output / "broken"
    shutil.copytree(first, broken)
    (broken / module_path).write_text(BROKEN, "utf-8")
    run.designer("load-broken", "/LoadConfigFromFiles", broken)
    run.designer(
        "check-broken",
        "/CheckConfig",
        "-Server",
        "-ExternalConnection",
        expect_error=True,
    )
    unchanged_value = run.execute("execute-after-rejection", 42)

    repaired = run.output / "repaired"
    shutil.copytree(first, repaired)
    (repaired / module_path).write_text(REPAIRED, "utf-8")
    run.designer("load-repaired", "/LoadConfigFromFiles", repaired)
    run.designer(
        "check-repaired",
        "/CheckConfig",
        "-Server",
        "-ExternalConnection",
        "-ThinClient",
    )
    run.designer("update-repaired", "/UpdateDBCfg")
    repaired_value = run.execute("execute-repaired", 43)
    final = run.dump("final-roundtrip")
    if object_uuid(final / "Configuration.xml", "Configuration") != configuration_id:
        raise RuntimeError("Configuration UUID changed")
    if object_uuid(final / f"CommonModules/{MODULE}.xml", "CommonModule") != module_id:
        raise RuntimeError("Repaired module UUID changed")
    if normalized_bsl(final / module_path) != REPAIRED:
        raise RuntimeError("Repaired BSL round trip changed content")
    if normalized_bsl(final / application_path) != APPLICATION:
        raise RuntimeError("Application module changed")
    if (baseline / "Configuration.xml").read_bytes() != native:
        raise RuntimeError("Baseline export was modified")
    report = {
        "schema": 1,
        "accepted": True,
        "platform_executable": str(run.executable),
        "platform_executable_sha256": hashlib.sha256(
            run.executable.read_bytes()
        ).hexdigest(),
        "configuration_uuid": configuration_id,
        "module_uuid": module_id,
        "native_uuid_preserved": True,
        "compiler_rejects_broken_bsl": True,
        "repaired_bsl_roundtrip": True,
        "baseline_preserved": True,
        "runtime_values": {
            "initial": initial_value,
            "after_rejection": unchanged_value,
            "repaired": repaired_value,
        },
        "steps": run.steps,
        "model_calls": 0,
        "not_verified": [
            "forms",
            "vendor updates",
            "rollback",
            "ibcmd",
        ],
    }
    (run.output / "acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), "utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New directory; never an existing infobase",
    )
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    verify(args.platform, args.output, args.timeout)
    print(json.dumps({"accepted": True}), flush=True)
