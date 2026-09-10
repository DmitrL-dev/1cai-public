"""Export verified core delivery artifacts and a hash-locked offline MCP kit."""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile
from kit_inputs import lock_entries


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def metadata(path):
    with zipfile.ZipFile(path) as archive:
        names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(names) != 1:
            raise ValueError("Expected one wheel metadata record")
        return BytesParser().parsebytes(archive.read(names[0]))


def export(accepted, clean, wheelhouse, go_license, output):
    if output.exists() or output.with_suffix(output.suffix + ".zip").exists():
        raise FileExistsError("A fresh output directory and archive are required")
    accepted_files = {p.name: p for p in (accepted / "dist").iterdir()}
    clean_files = {p.name: p for p in (clean / "dist").iterdir()}
    if set(accepted_files) != set(clean_files) or any(
        digest(p) != digest(clean_files[n]) for n, p in accepted_files.items()
    ):
        raise ValueError(
            "Clean artifacts differ from the installed acceptance artifacts"
        )
    wheels = [p for p in clean_files.values() if p.suffix == ".whl"]
    sources = [p for p in clean_files.values() if p.name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(sources) != 1 or len(clean_files) != 2:
        raise ValueError("Expected exactly one core wheel and one sdist")
    wheel = wheels[0]
    core = metadata(wheel)
    version = core["Version"]
    if core["Name"] != "rentgen-core" or not re.fullmatch(r"[0-9A-Za-z._-]+", version):
        raise ValueError("Unexpected core package identity")
    lock = clean / "checkout/requirements/locks/product-py311-windows.txt"
    audited = lock_entries(lock)
    selected_lock = clean / "checkout/requirements/locks/mcp-py311-windows.txt"
    selected = lock_entries(selected_lock)
    if any(
        key not in audited or not hashes <= audited[key]
        for key, hashes in selected.items()
    ):
        raise ValueError("MCP lock is not a subset of the committed runtime lock")
    dependencies = []
    for path in sorted(wheelhouse.glob("*.whl")):
        info = metadata(path)
        name = re.sub(r"[-_.]+", "-", info["Name"]).lower()
        identity = (name, info["Version"], digest(path))
        if (name, info["Version"]) not in selected or identity[2] not in selected[
            (name, info["Version"])
        ]:
            raise ValueError(f"Wheel was not accepted: {path.name}")
        dependencies.append((path, identity, info))
    if {(identity[0], identity[1]) for _, identity, _ in dependencies} != set(
        selected
    ) or len(dependencies) != len(selected):
        raise ValueError("Accepted dependency wheels are missing")
    scanner = accepted / "bsl-scan.exe"
    if not scanner.is_file() or not go_license.is_file():
        raise ValueError("Delivered scanner and Go license are required")
    if digest(scanner) != digest(clean / "bsl-scan.exe"):
        raise ValueError("Rebuilt scanner differs")
    output.mkdir()
    (output / "wheels").mkdir()
    (output / "LICENSES").mkdir()
    for path in clean_files.values():
        shutil.copyfile(path, output / path.name)
    shutil.copyfile(scanner, output / "bsl-scan.exe")
    shutil.copyfile(clean / "checkout/LICENSE", output / "LICENSE")
    shutil.copyfile(go_license, output / "LICENSES/Go-BSD-3-Clause.txt")
    shutil.copyfile(lock, output / "audited-product-runtime.lock")
    shutil.copyfile(
        clean / "build-input-hashes.json", output / "build-input-hashes.json"
    )
    lines = [f"rentgen-core[mcp]=={version} --hash=sha256:{digest(wheel)}"]
    notices = []
    for path, (name, dependency_version, sha), info in dependencies:
        shutil.copyfile(path, output / "wheels" / path.name)
        lines.append(f"{name}=={dependency_version} --hash=sha256:{sha}")
        notices.append(
            {
                "name": name,
                "version": dependency_version,
                "wheel": "wheels/" + path.name,
                "license_metadata": info.get("License-Expression")
                or info.get("License"),
                "notice": "Original wheel, including its license files, is preserved.",
            }
        )
    (output / "mcp-requirements.lock").write_text(
        "# Windows x64 / CPython 3.11; verified subset of audited-product-runtime.lock\n"
        + "\n".join(lines)
        + "\n",
        encoding="utf-8",
    )
    (output / "THIRD-PARTY.json").write_text(
        json.dumps(notices, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "README.md").write_text(
        f"""# Рентген core {version}: комплект без сетевой установки

Требуется Windows x64 и установленный CPython 3.11. Комплект содержит ядро,
исходный архив, Go scanner и {len(dependencies)} wheels зависимостей MCP с закреплёнными хэшами. Лицензия
собственного кода — MIT; лицензии зависимостей сохранены в исходных wheels.
Python, редактор, модели, Java/BSL-LS и платформа 1С устанавливаются отдельно.

После распаковки откройте PowerShell в этой папке и создайте новое окружение:

```powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install --no-index --only-binary=:all: --require-hashes --find-links . --find-links .\\wheels -r .\\mcp-requirements.lock
.\\.venv\\Scripts\\python.exe -m pip check
.\\.venv\\Scripts\\rentgen.exe --help
.\\.venv\\Scripts\\rentgen-mcp.exe --help
```

Для базового CLI без SDK можно установить только wheel с --no-index --no-deps.
Полный audited-product-runtime.lock приложен как источник проверки хешей;
устанавливать его целиком из этого комплекта не нужно. Для установки используется
именно mcp-requirements.lock с зависимостями MCP.

Новый проект создаётся в schema4. Для прежней schema3 требуется явная команда
state-upgrade-workflows с backup и operation ID; установка wheel не мигрирует
проект автоматически. Команды и границы описаны в docs/product внутри sdist.
Scanner: .\\bsl-scan.exe. MCP-клиент запускает .\\.venv\\Scripts\\rentgen-mcp.exe
с явными --registry и, при необходимости нового захвата, --scanner.

Черновики, чтение сохранённых исходников и 21 MCP-команда доступны в пакете.
В dev8 доступны сравнение снимков, observer выгрузки и нативная проверка
предложения отдельно установленной платформой 1С. Их границы описаны в sdist.
Применение изменений, бизнес-тесты и обновление конфигураций требуют дальнейшей приёмки. Этот комплект
ядра не является заявлением о полной готовности Рентгена.
""",
        encoding="utf-8",
    )
    files = {
        p.relative_to(output).as_posix(): {
            "sha256": digest(p),
            "size_bytes": p.stat().st_size,
        }
        for p in sorted(output.rglob("*"))
        if p.is_file()
    }
    manifest = {
        "version": version,
        "platform": "Windows x64 / CPython 3.11",
        "files": files,
    }
    (output / "SHA256SUMS.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    archive_path = output.with_suffix(output.suffix + ".zip")
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(
                    output.name + "/" + path.relative_to(output).as_posix(),
                    (1980, 1, 1, 0, 0, 0),
                )
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
    return {
        "directory": str(output),
        "archive": str(archive_path),
        "archive_sha256": digest(archive_path),
        "wheel_sha256": digest(wheel),
        "sdist_sha256": digest(sources[0]),
        "dependency_wheels": len(dependencies),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("accepted", "clean", "wheelhouse", "go-license", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            export(
                args.accepted.resolve(strict=True),
                args.clean.resolve(strict=True),
                args.wheelhouse.resolve(strict=True),
                args.go_license.resolve(strict=True),
                args.output.absolute(),
            ),
            ensure_ascii=False,
        )
    )
