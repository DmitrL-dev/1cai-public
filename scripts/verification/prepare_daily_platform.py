"""Create an isolated native XML fixture for the editor's daily repair scenario."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

MODULE = "CommonModules/RentgenPlatformProbe/Ext/Module.bsl"
SOURCE = """// Записывает подготовленный объект документа.
//
// Параметры:
//  ДокументОбъект - ДокументОбъект - объект для записи.
//
Процедура СохранитьДокумент(ДокументОбъект) Экспорт
    Попытка
        ДокументОбъект.Записать();
    Исключение
    КонецПопытки;
КонецПроцедуры
"""


def prepare(python, scanner, fixture, diagnostics_root, platform, output):
    python, scanner, fixture, diagnostics_root, platform = (
        p.resolve(strict=True)
        for p in (python, scanner, fixture, diagnostics_root, platform)
    )
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    shutil.copytree(fixture, source)
    if not (source / MODULE).is_file() or not (source / "Configuration.xml").is_file():
        raise ValueError("Use first-roundtrip from verify_native_platform.py")
    original = b"\xef\xbb\xbf" + SOURCE.replace("\n", "\r\n").encode("utf-8")
    (source / MODULE).write_bytes(original)
    # This scenario compiles the proposal; it does not execute application code.
    (source / "Ext/ManagedApplicationModule.bsl").write_text(
        "// No startup actions in this fixture.\n", "utf-8"
    )
    registry = output / "registry.sqlite3"
    project = None

    def cli(command, *extra):
        args = [
            str(python),
            "-I",
            "-m",
            "rentgen_core",
            command,
            "--registry",
            str(registry),
        ]
        if project:
            args += ["--project", project]
        result = subprocess.run(
            args + list(map(str, extra)),
            capture_output=True,
            encoding="utf-8",
            timeout=60,
        )
        value = json.loads(result.stdout)
        if result.returncode or "result" not in value:
            raise RuntimeError(value)
        return value["result"]

    cli("registry-init")
    project = cli(
        "project-register",
        "--source-root",
        source,
        "--state-root",
        output / "state",
        "--name",
        "Daily editor native fixture",
    )["project_id"]
    layers = output / "layers.json"
    layers.write_text(
        json.dumps(
            [
                {
                    "layer_id": "base",
                    "ordinal": 0,
                    "kind": "base",
                    "root_relative_path": ".",
                    "source_format": "designer_xml",
                }
            ]
        ),
        "utf-8",
    )
    cli("layers-set", "--expected-revision", 1, "--layers-json", layers)
    cli("capture", "--scanner", scanner)
    profile = {
        "schema": 1,
        "core_version": "0.1.0.dev8",
        "python": str(python),
        "registry": str(registry),
        "project_id": project,
        "diagnostics_local_app_data": str(diagnostics_root),
    }
    (output / "profile.json").write_text(json.dumps(profile, indent=2), "utf-8")
    scenario = {
        "module": MODULE,
        "platform": str(platform),
        "model": "qwen3.5:9b",
        "head": cli("project-head"),
        "instruction": "Исправь пустой обработчик исключения в СохранитьДокумент: ошибка записи должна передаваться вызывающему коду. Сохрани процедуру, параметр, комментарии и саму запись документа; не отключай диагностики.",
    }
    (output / "daily-scenario.json").write_text(
        json.dumps(scenario, ensure_ascii=False, indent=2), "utf-8"
    )
    (output / "workspace").mkdir()
    return {"profile": str(output), "project_id": project}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "python",
        "scanner",
        "fixture",
        "diagnostics-root",
        "platform",
        "output",
    ):
        parser.add_argument("--" + name, required=True, type=Path)
    print(json.dumps(prepare(**vars(parser.parse_args()))))
