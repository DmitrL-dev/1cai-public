"""Verify stored data across an owned EDT fixture migration on real 1C/YAxUnit."""
import argparse
import base64
from contextlib import ExitStack
import json
from pathlib import Path
import shutil
import time
import xml.etree.ElementTree as ET

from rentgen_core._windows_source_tree import read_retained, pinned_retained
from rentgen_core.edt_inventory import exported_inventory
from rentgen_core.manifests import canonical_bytes, sha256
from rentgen_core.native_platform import NativePlatform, CONTEXTS
from rentgen_core.native_resources import DiskBudget, project_slot
from rentgen_core.platform_check import _pin_inputs
from rentgen_core.yaxunit_report import parse_report
from rentgen_core.yaxunit_runner import _engine_with_tests, _ibcmd
from verify_edt_metadata_fixture import verify_structure

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "packaging/fixtures/edt-metadata-v1"
DATA = ROOT / "packaging/fixtures/metadata-migration-v1/RentgenMigrationData.bsl"
CFE_SHA = "805a2277c997a3c24be0b0d080696479e91e4a15ed7e27aaf3991a7346522d70"
OLD_UUID = "eb298009-8fc5-4a2f-8812-902daeed99df"
BAD_UUID = "eb298009-8fc5-4a2f-8812-902daeed99aa"


def require(value, message):
    if not value:
        raise ValueError(message)


def modules():
    values = {"RentgenMigrationData": read_retained(DATA, 64 * 1024)}
    for suffix, statement in (
        ("Создание", "СоздатьДанные()"),
        ("Старое", 'ПроверитьДанные("Article")'),
        ("Новое", 'ПроверитьДанные("SKU")'),
    ):
        values["ЮТРентгенМиграция" + suffix] = (
            "Процедура ИсполняемыеСценарии() Экспорт\n"
            '    ЮТТесты.ДобавитьТест("Данные").НастройкаИсполнения("ВТранзакции", Ложь);\n'
            "КонецПроцедуры\n\nПроцедура Данные() Экспорт\n"
            "    RentgenMigrationData." + statement + ";\nКонецПроцедуры\n"
        ).encode("utf-8")
    return values


def prepare_engine_language(source, target, inventory):
    """Adapt the extension's borrowed language; base configuration bytes stay exact."""
    target.mkdir(exist_ok=False)
    for row in inventory:
        name = row["path"]
        raw = read_retained(source / name, 64 * 1024**2)
        if name == "Languages/Русский.xml":
            marker = "<Name>Русский</Name>".encode()
            require(raw.count(marker) == 1, "Unexpected engine language")
            raw = raw.replace(marker, b"<Name>Russian</Name>")
            name = "Languages/Russian.xml"
        elif name == "Configuration.xml":
            marker = "<Language>Русский</Language>".encode()
            require(raw.count(marker) == 1, "Unexpected engine language reference")
            raw = raw.replace(marker, b"<Language>Russian</Language>")
        elif name == "ConfigDumpInfo.xml":
            marker = 'name="Language.Русский"'.encode()
            require(raw.count(marker) == 1, "Unexpected engine language inventory")
            raw = raw.replace(marker, b'name="Language.Russian"')
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)


def normalize_bsl(data):
    return data.decode("utf-8-sig").replace("\r\n", "\n")


def verify(args):
    source_run = args.input_run.resolve(strict=True)
    sources = [source_run / name for name in ("input", "baseline-xml", "candidate-xml")]
    root = args.output.resolve()
    require(
        not any(root.is_relative_to(source.resolve()) for source in sources),
        "Output must be outside retained input directories",
    )
    inventories = [exported_inventory(p, authorize=lambda: None) for p in sources]
    manifest = json.loads((FIXTURE / "manifest.json").read_bytes())["files"]
    expected = {
        p.removeprefix("created/"): value
        for p, value in manifest.items()
        if p.startswith("created/")
    }
    require(
        {r["path"]: r["sha256"] for r in inventories[0]} == expected,
        "Only the exact owned edt-metadata-v1 source is accepted",
    )
    require(
        all({r["path"] for r in rows} == set(expected) for rows in inventories),
        "Unexpected fixture export files",
    )
    for phase, source in zip(("created", "created", "renamed"), sources):
        verify_structure(FIXTURE / phase, source, phase)
    platform, ibcmd, cfe = [
        p.resolve(strict=True) for p in (args.platform, args.ibcmd, args.cfe)
    ]
    require(
        sha256(read_retained(ibcmd, 64 * 1024**2)) == args.ibcmd_sha256,
        "ibcmd SHA256 mismatch",
    )
    root.mkdir(parents=True, exist_ok=False)
    run = root / "metadata-runs/migration"
    run.mkdir(parents=True)
    reports, steps = {}, []
    deadline = time.monotonic() + 900
    test_modules = modules()

    with ExitStack() as pins, project_slot(root) as job:
        native = NativePlatform(platform, args.platform_sha256, job=job)
        pins.enter_context(pinned_retained(platform, 64 * 1024**2))
        require(
            sha256(pins.enter_context(pinned_retained(ibcmd, 64 * 1024**2)))
            == args.ibcmd_sha256,
            "Pinned ibcmd SHA256 mismatch",
        )
        require(
            sha256(pins.enter_context(pinned_retained(cfe, 64 * 1024**2))) == CFE_SHA,
            "Expected YAxUnit 25.12 CFE",
        )
        for source, inventory in zip(sources, inventories):
            pins.enter_context(_pin_inputs(source, inventory))
        budget = DiskBudget(root, run)

        def check():
            budget.check()
            require(time.monotonic() < deadline, "Migration test deadline exceeded")

        def invoke(name, arguments):
            step = native.invoke(run, name, arguments, check, deadline)
            steps.append(step)
            (root / "steps.json").write_bytes(canonical_bytes(steps))
            require(step["exit_code"] == 0, "Native step failed: " + name)
            print(json.dumps({"native_step": name, "exit_code": 0}), flush=True)
            return step

        base = run / "infobase"
        common = ["DESIGNER", "/F", base]
        invoke("create", ["CREATEINFOBASE", f'File="{base}";Locale=ru_RU;'])

        def load(name, source):
            invoke(name + "-load", [*common, "/LoadConfigFromFiles", source])
            invoke(name + "-update", [*common, "/UpdateDBCfg"])
            invoke(name + "-compile", [*common, "/CheckConfig", *CONTEXTS])

        load("initial", sources[0])
        invoke("engine-load", [*common, "/LoadCfg", cfe, "-Extension", "YAXUNIT"])
        exported = run / "engine-export"
        exported.mkdir()
        invoke(
            "engine-export",
            [*common, "/DumpConfigToFiles", exported, "-Extension", "YAXUNIT"],
        )
        engine = run / "engine-with-tests"
        adapted = run / "engine-language"
        prepare_engine_language(
            exported, adapted, exported_inventory(exported, authorize=check)
        )
        module_inputs = [
            {"name": name, "base64": base64.b64encode(raw).decode("ascii")}
            for name, raw in test_modules.items()
        ]
        engine_inventory = _engine_with_tests(adapted, engine, module_inputs)
        pins.enter_context(_pin_inputs(engine, engine_inventory))
        invoke(
            "tests-load",
            [*common, "/LoadConfigFromFiles", engine, "-Extension", "YAXUNIT"],
        )
        invoke("tests-update", [*common, "/UpdateDBCfg", "-Extension", "YAXUNIT"])
        steps.append(
            _ibcmd(ibcmd, run, base, check, deadline, "extension-properties", job)
        )
        restored_engine = run / "verified-engine"
        restored_engine.mkdir()
        invoke(
            "tests-dump",
            [*common, "/DumpConfigToFiles", restored_engine, "-Extension", "YAXUNIT"],
        )
        module_records = {}
        for name, raw in test_modules.items():
            native_raw = read_retained(
                restored_engine / f"CommonModules/{name}/Ext/Module.bsl", 64 * 1024
            )
            require(
                normalize_bsl(raw) == normalize_bsl(native_raw),
                "Native test code differs: " + name,
            )
            ids = []
            for folder in (engine, restored_engine):
                node = ET.parse(folder / f"CommonModules/{name}.xml").find(
                    "{http://v8.1c.ru/8.3/MDClasses}CommonModule"
                )
                ids.append(node.attrib["uuid"])
            require(ids[0] == ids[1], "Native test module identity differs")
            module_records[name] = {
                "source_sha256": sha256(raw),
                "native_sha256": sha256(native_raw),
                "uuid": ids[0],
            }

        def execute(label, suffix, expected_status="passed"):
            suite = "ЮТРентгенМиграция" + suffix
            junit, exit_file = run / (label + ".xml"), run / (label + ".exit")
            settings = run / (label + "-settings.json")
            raw = canonical_bytes(
                {
                    "filter": {"modules": [suite]},
                    "reportFormat": "jUnit",
                    "reportPath": str(junit),
                    "exitCode": str(exit_file),
                    "closeAfterTests": True,
                    "showReport": False,
                }
            )
            settings.write_bytes(raw)
            invoke(
                label + "-execute",
                ["ENTERPRISE", "/F", base, "/C", "RunUnitTests=" + str(settings)],
            )
            result = parse_report(
                read_retained(junit, 2 * 1024**2),
                read_retained(exit_file, 32),
                [(suite + ".Данные", "Данные", "Сервер")],
            )
            require(
                result["status"] == expected_status and result["counts"]["errors"] == 0,
                "Unexpected data test outcome: " + label,
            )
            if expected_status == "failed":
                require(
                    result["counts"]["failures"] == 1,
                    "Expected assertion failure for lost data",
                )
            reports[label] = {
                **result,
                "settings_sha256": sha256(raw),
                "client_exit_code": 0,
            }
            (root / "reports.json").write_bytes(canonical_bytes(reports))
            print(
                json.dumps({"data_phase": label, "status": result["status"]}),
                flush=True,
            )

        execute("seed", "Создание")
        execute("reopen-original", "Старое")
        for label, source, suite in (
            ("normalized", sources[1], "Старое"),
            ("renamed", sources[2], "Новое"),
            ("restored", sources[0], "Старое"),
        ):
            load(label, source)
            execute(label, suite)
            restored = run / (label + "-roundtrip")
            restored.mkdir()
            invoke(label + "-dump", [*common, "/DumpConfigToFiles", restored])
            verify_structure(
                source, restored, "renamed" if suite == "Новое" else "created"
            )
        bad = run / "wrong-uuid-source"
        shutil.copytree(sources[2], bad)
        for path in bad.rglob("*.xml"):
            path.write_bytes(
                path.read_bytes().replace(OLD_UUID.encode(), BAD_UUID.encode())
            )
        bad_inventory = exported_inventory(bad, authorize=check)
        with _pin_inputs(bad, bad_inventory):
            load("wrong-uuid", bad)
            execute("wrong-uuid", "Новое", "failed")
        require(job.active() == 0, "Native descendants remain")
        budget.check(force=True)
    evidence = {
        "schema": 1,
        "source": "real 1C/YAxUnit on a new owned file infobase",
        "platform_sha256": args.platform_sha256,
        "ibcmd_sha256": args.ibcmd_sha256,
        "engine_cfe_sha256": CFE_SHA,
        "source_inventories": dict(
            zip(("original", "normalized", "renamed"), inventories)
        ),
        "test_modules": module_records,
        "test_framework_adjustment": "Borrowed Language.Русский in YAxUnit renamed to Russian, retaining its UUID and ru language code; base sources unchanged",
        "unmodified_preview_execution": True,
        "reports": reports,
        "records": 3,
        "value_cases": ["unicode", "empty", "length_32"],
        "full_record_reference_preserved": True,
        "schema_restore_preserves_data": True,
        "wrong_uuid_compiles_but_loses_data": True,
        "product_apply_undo": False,
        "arbitrary_configuration_qualification": False,
    }
    (root / "acceptance.json").write_bytes(canonical_bytes(evidence))
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input-run", "platform", "ibcmd", "cfe", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("platform-sha256", "ibcmd-sha256"):
        parser.add_argument("--" + name, required=True)
    result = verify(parser.parse_args())
    print(
        json.dumps(
            {
                "accepted": True,
                "records": result["records"],
                "phases": {
                    name: value["status"] for name, value in result["reports"].items()
                },
            }
        ),
        flush=True,
    )
