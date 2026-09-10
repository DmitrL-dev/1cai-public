"""Run trusted server test modules on separate, owned baseline/candidate bases."""
from base64 import b64decode
import re
import shutil
import subprocess
import time
from uuid import uuid4

from ._windows_source_tree import read_retained
from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .native_platform import CONTEXTS, MAX_LOG
from .platform_check import _pin_inputs
from .yaxunit_report import parse_report


def _ibcmd(executable, run, base, authorize, deadline, name):
    args = [
        str(executable),
        "extension",
        "update",
        "--db-path=" + str(base),
        "--data=" + str(run / (name + "-data")),
        "--name=YAXUNIT",
        "--safe-mode=no",
        "--unsafe-action-protection=no",
    ]
    paths = [run / (name + ".stdout"), run / (name + ".stderr")]
    authorize()
    with paths[0].open("xb") as stdout, paths[1].open("xb") as stderr:
        child = subprocess.Popen(
            args,
            stdout=stdout,
            stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        started = time.monotonic()
        try:
            while child.poll() is None:
                authorize()
                if time.monotonic() >= min(deadline, started + 90):
                    raise CoreError(
                        "PLATFORM_TIMEOUT", "Extension setup exceeded deadline"
                    )
                if any(p.stat().st_size > MAX_LOG for p in paths):
                    raise CoreError("PLATFORM_OUTPUT_LIMIT", "ibcmd output limit")
                try:
                    child.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if child.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=15,
                )
                child.wait(timeout=15)
    authorize()
    hashes = [sha256(read_retained(p, MAX_LOG)) for p in paths]
    if child.returncode != 0:
        raise CoreError(
            "PLATFORM_COMMAND_FAILED",
            "Could not configure owned test extension",
            details={"stage": name, "exit_code": child.returncode},
        )
    return {
        "name": name,
        "exit_code": 0,
        "stdout_sha256": hashes[0],
        "stderr_sha256": hashes[1],
    }


def _engine_with_tests(engine, target, modules):
    shutil.copytree(engine, target)
    root = target / "Configuration.xml"
    config = root.read_bytes()
    marker = b"</ChildObjects>"
    if config.count(marker) != 1:
        raise CoreError("TEST_ENGINE_INVALID", "Unexpected native extension structure")
    template = (target / "CommonModules/ЮТТесты.xml").read_text("utf-8-sig")
    for module in modules:
        name = module["name"]
        metadata = target / f"CommonModules/{name}.xml"
        if metadata.exists() or (target / "CommonModules" / name).exists():
            raise CoreError("TEST_MODULE_CONFLICT", "Test module collides with engine")
        xml, count = re.subn(
            r'<CommonModule uuid="[^"]+">',
            f'<CommonModule uuid="{uuid4()}">',
            template,
            count=1,
        )
        if count != 1 or xml.count("<Name>ЮТТесты</Name>") != 1:
            raise CoreError("TEST_ENGINE_INVALID", "Native module template mismatch")
        xml = xml.replace("<Name>ЮТТесты</Name>", f"<Name>{name}</Name>")
        for flag in ("ClientManagedApplication", "ClientOrdinaryApplication"):
            xml = xml.replace(f"<{flag}>true</{flag}>", f"<{flag}>false</{flag}>")
        metadata.write_text(xml, "utf-8")
        bsl = target / f"CommonModules/{name}/Ext/Module.bsl"
        bsl.parent.mkdir(parents=True)
        bsl.write_bytes(b64decode(module["base64"], validate=True))
        config = config.replace(
            marker, f"<CommonModule>{name}</CommonModule>\n".encode() + marker
        )
    root.write_bytes(config)
    inventory = []
    for path in sorted(target.rglob("*")):
        if path.is_file():
            raw = read_retained(path, 64 * 1024**2)
            inventory.append(
                {
                    "path": path.relative_to(target).as_posix(),
                    "size": len(raw),
                    "sha256": sha256(raw),
                }
            )
            if (
                len(inventory) > 20000
                or sum(row["size"] for row in inventory) > 256 * 1024**2
            ):
                raise CoreError("TEST_ENGINE_LIMIT", "Expanded engine exceeds limit")
    return inventory


def run_yaxunit(
    platform, ibcmd, engine_cfe, modules, before, after, target, run, authorize
):
    deadline = time.monotonic() + 900
    steps, results = [], {}
    expected = [
        (f"{module['name']}.{test}", test, "Сервер")
        for module in modules
        for test in module["tests"]
    ]
    engine_source = run / "engine-with-tests"
    engine_inventory = None

    def invoke(name, args, compiler=False):
        step = platform.invoke(run, name, args, authorize, deadline)
        steps.append(step)
        if step["exit_code"] not in ({0, 101} if compiler else {0}):
            raise CoreError(
                "PLATFORM_COMMAND_FAILED",
                "Test platform command failed",
                details={"stage": name, "exit_code": step["exit_code"]},
            )
        return step

    for phase, source in (("baseline", before), ("candidate", after)):
        authorize()
        base = run / (phase + "-infobase")
        invoke(phase + "-create", ["CREATEINFOBASE", f'File="{base}";Locale=ru_RU;'])
        if not (base / "1Cv8.1CD").is_file():
            raise CoreError("PLATFORM_BASE_MISSING", "Own test base not created")
        designer = ["DESIGNER", "/F", base]
        invoke(phase + "-load", [*designer, "/LoadConfigFromFiles", source])
        restored = run / (phase + "-roundtrip")
        restored.mkdir()
        invoke(phase + "-dump", [*designer, "/DumpConfigToFiles", restored])
        raw = read_retained(restored / target, 2 * 1024**2)

        def normalize(value):
            return value.decode("utf-8-sig").replace("\r\n", "\n")

        if normalize(raw) != normalize(read_retained(source / target, 2 * 1024**2)):
            raise CoreError(
                "PLATFORM_TARGET_MISMATCH", "Native module differs from test input"
            )
        compiler = invoke(
            phase + "-compile", [*designer, "/CheckConfig", *CONTEXTS], compiler=True
        )
        if compiler["exit_code"] == 101:
            results[phase] = {
                "status": "not_run",
                "reason": "compiler_diagnostics",
                "native_module_sha256": sha256(raw),
            }
            continue
        invoke(phase + "-apply", [*designer, "/UpdateDBCfg"])
        invoke(
            phase + "-engine-load",
            [*designer, "/LoadCfg", engine_cfe, "-Extension", "YAXUNIT"],
        )
        invoke(
            phase + "-engine-apply",
            [*designer, "/UpdateDBCfg", "-Extension", "YAXUNIT"],
        )
        if engine_inventory is None:
            exported = run / "engine-export"
            exported.mkdir()
            invoke(
                "engine-dump",
                [*designer, "/DumpConfigToFiles", exported, "-Extension", "YAXUNIT"],
            )
            engine_inventory = _engine_with_tests(exported, engine_source, modules)
        with _pin_inputs(engine_source, engine_inventory):
            invoke(
                phase + "-tests-load",
                [
                    *designer,
                    "/LoadConfigFromFiles",
                    engine_source,
                    "-Extension",
                    "YAXUNIT",
                ],
            )
        invoke(
            phase + "-tests-apply", [*designer, "/UpdateDBCfg", "-Extension", "YAXUNIT"]
        )
        steps.append(
            _ibcmd(
                ibcmd, run, base, authorize, deadline, phase + "-extension-properties"
            )
        )
        junit, exit_file = run / (phase + ".junit.xml"), run / (phase + ".exit")
        config = run / (phase + "-settings.json")
        config_bytes = canonical_bytes(
            {
                "filter": {"modules": [m["name"] for m in modules]},
                "reportFormat": "jUnit",
                "reportPath": str(junit),
                "exitCode": str(exit_file),
                "closeAfterTests": True,
                "showReport": False,
            }
        )
        with config.open("xb") as stream:
            stream.write(config_bytes)
        from ._windows_source_tree import pinned_retained

        with pinned_retained(config, 32768):
            step = invoke(
                phase + "-execute",
                ["ENTERPRISE", "/F", base, "/C", "RunUnitTests=" + str(config)],
            )
        try:
            result = parse_report(
                read_retained(junit, 2 * 1024**2),
                read_retained(exit_file, 32),
                expected,
            )
        except (ValueError, OSError, CoreError) as exc:
            raise CoreError(
                "TEST_REPORT_INVALID",
                "Test inventory, JUnit or exit code not verified",
                details={"phase": phase},
            ) from exc
        results[phase] = {
            **result,
            "native_module_sha256": sha256(raw),
            "module_text_verified": True,
            "client_exit_code": step["exit_code"],
            "settings_sha256": sha256(config_bytes),
        }
    authorize()
    return {
        "baseline": results["baseline"],
        "candidate": results["candidate"],
        "status": results["candidate"]["status"],
        "engine_source_sha256": sha256(canonical_bytes(engine_inventory))
        if engine_inventory
        else None,
        "steps": steps,
        "isolated_infobases": True,
    }
