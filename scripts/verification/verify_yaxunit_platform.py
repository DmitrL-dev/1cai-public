"""Exercise pinned YAxUnit on a new synthetic infobase: failure then repair."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from uuid import uuid4

from verify_native_platform import PlatformRun, normalized_bsl, object_uuid
from yaxunit_report import parse_report

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "packaging/test-profiles/yaxunit-25.12"
MODULE = "RentgenPlatformProbe"
SUITE = "ЮТРентгенПроверка"
TEST = "ОшибкаЗаписиПередается"
EXPECTED = [(f"{SUITE}.{TEST}", TEST, "Сервер")]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def add_module(folder, name, module_xml, bsl):
    config = folder / "Configuration.xml"
    raw = config.read_bytes()
    marker = b"</ChildObjects>"
    if raw.count(marker) != 1 or f"<CommonModule>{name}</CommonModule>".encode() in raw:
        raise ValueError("Unexpected native configuration structure")
    config.write_bytes(
        raw.replace(marker, f"<CommonModule>{name}</CommonModule>\n".encode() + marker)
    )
    (folder / "CommonModules").mkdir(exist_ok=True)
    (folder / f"CommonModules/{name}.xml").write_text(module_xml, "utf-8")
    path = folder / f"CommonModules/{name}/Ext/Module.bsl"
    path.parent.mkdir(parents=True)
    path.write_bytes(bsl)


def verify(executable, executable_sha256, ibcmd, ibcmd_sha256, cfe, output):
    executable, ibcmd, cfe = (p.resolve(strict=True) for p in (executable, ibcmd, cfe))
    inputs = json.loads((PROFILE / "inputs.json").read_text("utf-8"))
    expected_cfe = inputs["files"]["YAxUnit-25.12.cfe"]
    if digest(executable) != executable_sha256 or digest(ibcmd) != ibcmd_sha256:
        raise ValueError("Platform executable hash mismatch")
    if (
        ibcmd.name.lower() != "ibcmd.exe"
        or digest(cfe) != expected_cfe["sha256"]
        or cfe.stat().st_size != expected_cfe["bytes"]
    ):
        raise ValueError("Pinned YAxUnit or ibcmd input mismatch")
    if any(c in str(output.resolve()) for c in (";", '"', "\r", "\n")):
        raise ValueError("Output cannot contain connection-string delimiters")
    run = PlatformRun(executable, output, 120)
    run.command("create", ["CREATEINFOBASE", f'File="{run.base}";Locale=ru_RU;'])
    if not (run.base / "1Cv8.1CD").is_file():
        raise RuntimeError("No owned infobase created")
    empty = run.dump("empty-source")
    source = run.output / "bad-source"
    shutil.copytree(empty, source)
    header = (
        (empty / "Configuration.xml")
        .read_text("utf-8-sig")
        .split("<MetaDataObject", 1)[1]
        .split(">", 1)[0]
    )
    module_id = str(uuid4())
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject{header}><CommonModule uuid="{module_id}"><Properties>
<Name>{MODULE}</Name><Synonym/><Comment/><Global>false</Global>
<ClientManagedApplication>false</ClientManagedApplication><Server>true</Server>
<ExternalConnection>true</ExternalConnection><ClientOrdinaryApplication>false</ClientOrdinaryApplication>
<ServerCall>true</ServerCall><Privileged>false</Privileged><ReturnValuesReuse>DontUse</ReturnValuesReuse>
</Properties></CommonModule></MetaDataObject>"""
    original = (
        b"\xef\xbb\xbf"
        + (PROFILE / "СохранитьДокумент.bsl")
        .read_text("utf-8")
        .replace("\n", "\r\n")
        .encode()
    )
    add_module(source, MODULE, xml, original)
    (source / "Ext").mkdir(exist_ok=True)
    (source / "Ext/ManagedApplicationModule.bsl").write_text(
        "Процедура ПередНачаломРаботыСистемы(Отказ)\nКонецПроцедуры\n\nПроцедура ПриНачалеРаботыСистемы()\nКонецПроцедуры\n",
        "utf-8",
    )
    run.designer("load-source", "/LoadConfigFromFiles", source)
    run.designer("apply-source", "/UpdateDBCfg")
    retained = run.dump("retained-source")
    module_path = Path(f"CommonModules/{MODULE}/Ext/Module.bsl")
    if object_uuid(
        retained / f"CommonModules/{MODULE}.xml", "CommonModule"
    ) != module_id or normalized_bsl(retained / module_path) != original.decode(
        "utf-8-sig"
    ).replace(
        "\r\n", "\n"
    ):
        raise ValueError("Native source roundtrip mismatch")
    run.designer("load-yaxunit", "/LoadCfg", cfe, "-Extension", "YAXUNIT")
    run.designer("apply-yaxunit", "/UpdateDBCfg", "-Extension", "YAXUNIT")
    engine = run.output / "engine"
    engine.mkdir()
    run.designer("dump-yaxunit", "/DumpConfigToFiles", engine, "-Extension", "YAXUNIT")
    engine_id = object_uuid(engine / "Configuration.xml", "Configuration")
    tests = run.output / "engine-with-test"
    shutil.copytree(engine, tests)
    template = (engine / "CommonModules/ЮТТесты.xml").read_text("utf-8")
    test_id = str(uuid4())
    template, matches = re.subn(
        r'<CommonModule uuid="[^"]+">',
        f'<CommonModule uuid="{test_id}">',
        template,
        count=1,
    )
    if matches != 1 or template.count("<Name>ЮТТесты</Name>") != 1:
        raise ValueError("Unexpected native YAxUnit module template")
    template = template.replace("<Name>ЮТТесты</Name>", f"<Name>{SUITE}</Name>")
    for flag in ("ClientManagedApplication", "ClientOrdinaryApplication"):
        template = template.replace(f"<{flag}>true</{flag}>", f"<{flag}>false</{flag}>")
    test_bytes = (PROFILE / "ОшибкаЗаписи.bsl").read_bytes()
    add_module(tests, SUITE, template, test_bytes)
    run.designer("load-tests", "/LoadConfigFromFiles", tests, "-Extension", "YAXUNIT")
    run.designer("apply-tests", "/UpdateDBCfg", "-Extension", "YAXUNIT")
    command = [
        str(ibcmd),
        "extension",
        "update",
        "--db-path=" + str(run.base),
        "--data=" + str(run.output / "ibcmd-data"),
        "--name=YAXUNIT",
        "--safe-mode=no",
        "--unsafe-action-protection=no",
    ]
    with (run.output / "extension-properties.stdout").open("xb") as stdout, (
        run.output / "extension-properties.stderr"
    ).open("xb") as stderr:
        process = subprocess.Popen(
            command,
            stdout=stdout,
            stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            code = process.wait(timeout=90)
        finally:
            if process.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=15,
                )
                process.wait(timeout=15)
    if code != 0:
        raise RuntimeError("Could not set properties of owned test extension")

    def execute(label):
        settings = {
            "filter": {"modules": [SUITE]},
            "reportFormat": "jUnit",
            "reportPath": str(run.output / (label + ".xml")),
            "exitCode": str(run.output / (label + ".exit")),
            "closeAfterTests": True,
            "showReport": False,
            "logging": {
                "file": str(run.output / (label + "-framework.log")),
                "level": "info",
            },
        }
        config = run.output / (label + "-settings.json")
        config.write_text(json.dumps(settings, ensure_ascii=False), "utf-8")
        step = run.command(
            "run-" + label,
            ["ENTERPRISE", "/F", run.base, "/C", "RunUnitTests=" + str(config)],
        )
        raw_path, exit_path = run.output / (label + ".xml"), run.output / (
            label + ".exit"
        )
        if raw_path.stat().st_size > 2 * 1024**2 or exit_path.stat().st_size > 32:
            raise ValueError("Framework report limit")
        value = parse_report(raw_path.read_bytes(), exit_path.read_bytes(), EXPECTED)
        return {
            **value,
            "client_exit_code": step["exit_code"],
            "settings_sha256": digest(config),
        }

    bad = execute("bad")
    if bad["status"] != "failed" or bad["counts"]["failures"] != 1:
        raise ValueError("Known faulty behavior did not fail its test")
    fixed_source = run.output / "fixed-source"
    shutil.copytree(retained, fixed_source)
    raw = (fixed_source / module_path).read_bytes()
    marker = "    Исключение\r\n".encode()
    if raw.count(marker) != 1:
        raise ValueError("Unexpected synthetic exception handler")
    fixed = raw.replace(marker, marker + "        ВызватьИсключение;\r\n".encode())
    (fixed_source / module_path).write_bytes(fixed)
    run.designer("load-fixed", "/LoadConfigFromFiles", fixed_source)
    run.designer("apply-fixed", "/UpdateDBCfg")
    good = execute("fixed")
    if good["status"] != "passed":
        raise ValueError("Repaired behavior did not pass its test")
    final_engine = run.output / "final-engine"
    final_engine.mkdir()
    run.designer(
        "dump-final-engine", "/DumpConfigToFiles", final_engine, "-Extension", "YAXUNIT"
    )
    if (
        object_uuid(final_engine / "Configuration.xml", "Configuration") != engine_id
        or object_uuid(final_engine / f"CommonModules/{SUITE}.xml", "CommonModule")
        != test_id
        or normalized_bsl(final_engine / f"CommonModules/{SUITE}/Ext/Module.bsl")
        != test_bytes.decode("utf-8-sig").replace("\r\n", "\n")
    ):
        raise ValueError("Test extension changed during behavior comparison")
    if (
        digest(executable) != executable_sha256
        or digest(ibcmd) != ibcmd_sha256
        or digest(cfe) != expected_cfe["sha256"]
    ):
        raise ValueError("Runtime inputs changed during acceptance")
    result = {
        "accepted": True,
        "scope": "synthetic_error_propagation",
        "platform_sha256": executable_sha256,
        "ibcmd_sha256": ibcmd_sha256,
        "upstream_cfe_sha256": expected_cfe["sha256"],
        "test_module_sha256": hashlib.sha256(test_bytes).hexdigest(),
        "original_sha256": hashlib.sha256(raw).hexdigest(),
        "fixed_sha256": hashlib.sha256(fixed).hexdigest(),
        "bad": bad,
        "fixed": good,
        "test_module_and_extension_identity_preserved": True,
        "steps": run.steps,
        "profile_registration": "not_registered",
    }
    (run.output / "acceptance.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("platform", "ibcmd", "cfe", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("platform-sha256", "ibcmd-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = verify(
        args.platform,
        args.platform_sha256,
        args.ibcmd,
        args.ibcmd_sha256,
        args.cfe,
        args.output,
    )
    print(
        json.dumps(
            {
                "accepted": result["accepted"],
                "bad": result["bad"]["status"],
                "fixed": result["fixed"]["status"],
            }
        )
    )
