
#!/usr/bin/env python3
"""
Запуск YAxUnit тестов через 1С:Предприятие.

Этот скрипт создает JSON конфигурацию для YAxUnit и запускает тесты
через 1cv8c с параметром RunUnitTests.

Требования:
- 1С:Предприятие 8.3.10 или старше
- YAxUnit расширение загружено в информационную базу
- Информационная база настроена и доступна
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Пути по умолчанию
DEFAULT_TEST_DIR = Path("tests/bsl")
DEFAULT_OUTPUT_DIR = Path("output/bsl-tests")
DEFAULT_CONFIG_FILE = DEFAULT_OUTPUT_DIR / "yaxunit-config.json"
DEFAULT_REPORT_FILE = DEFAULT_OUTPUT_DIR / "reports" / "report.xml"
DEFAULT_LOG_FILE = DEFAULT_OUTPUT_DIR / "logs" / "tests.log"


def create_yaxunit_config(
    test_files: Optional[List[str]] = None,
    modules: Optional[List[str]] = None,
    report_path: Optional[Path] = None,
    log_file: Optional[Path] = None,
    report_format: str = "jUnit",
    close_after_tests: bool = True,
    log_level: str = "info",
) -> Dict:
    """
    Создает JSON конфигурацию для YAxUnit.
    
    Args:
        test_files: Список файлов с тестами (опционально)
        modules: Список имен модулей для запуска (опционально)
        report_path: Путь к файлу отчета
        log_file: Путь к файлу лога
        report_format: Формат отчета (jUnit, JSON, allure)
        close_after_tests: Закрывать 1С после тестов
        log_level: Уровень логирования (debug, info, warning, error)
    
    Returns:
        Словарь с конфигурацией YAxUnit
    """
    config: Dict = {
        "reportFormat": report_format,
        "closeAfterTests": close_after_tests,
        "showReport": False,  # Не показывать UI в CI
        "logging": {
            "enable": True,
            "console": True,
            "level": log_level,
        },
    }
    
    # Фильтр тестов
    filter_config: Dict = {}
    
    if modules:
        filter_config["modules"] = modules
    
    if test_files:
        # Преобразуем имена файлов в имена модулей
        # Например: test_parsers.bsl -> Тесты_Парсеры
        test_names = []
        for test_file in test_files:
            # Убираем расширение и преобразуем в имя модуля
            module_name = Path(test_file).stem
            # Преобразуем snake_case в PascalCase для BSL
            parts = module_name.split("_")
            module_name_bsl = "".join(word.capitalize() for word in parts)
            test_names.append(module_name_bsl)
        
        if test_names:
            filter_config["modules"] = test_names
    
    if filter_config:
        config["filter"] = filter_config
    
    # Путь к отчету
    if report_path:
        config["reportPath"] = str(report_path.absolute())
    
    # Путь к логу
    if log_file:
        config["logging"]["file"] = str(log_file.absolute())
    
    # Файл с кодом завершения
    exit_code_file = report_path.parent / "exit-code.txt" if report_path else None
    if exit_code_file:
        config["exitCode"] = str(exit_code_file.absolute())
    
    return config


def save_config(config: Dict, config_path: Path) -> None:
    """Сохраняет конфигурацию в JSON файл."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def run_1c_tests(
    config_path: Path,
    ib_path: Optional[str] = None,
    ib_name: Optional[str] = None,
    ib_user: str = "Admin",
    ib_password: Optional[str] = None,
    v8_path: Optional[str] = None,
) -> int:
    """
    Запускает тесты через 1cv8c.
    
    Args:
        config_path: Путь к JSON конфигурации YAxUnit
        ib_path: Путь к файловой информационной базе
        ib_name: Имя информационной базы на сервере
        ib_user: Имя пользователя
        ib_password: Пароль пользователя
        v8_path: Путь к 1cv8c.exe
    
    Returns:
        Код возврата (0 - успех, иначе ошибка)
    """
    # Определяем путь к 1cv8c
    if v8_path:
        v8_exe = Path(v8_path)
    else:
        # Попытка найти 1cv8c в стандартных местах
        if sys.platform == "win32":
            possible_paths = [
                Path("C:/Program Files/1cv8") / "8.3.*" / "bin" / "1cv8c.exe",
                Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "1cv8" / "8.3.*" / "bin" / "1cv8c.exe",
            ]
        else:
            possible_paths = [
                Path("/opt/1cv8/x86_64/8.3.*/1cv8c"),
                Path("/usr/bin/1cv8c"),
            ]
        
        v8_exe = None
        for pattern in possible_paths:
            if "*" in str(pattern):
                # Ищем последнюю версию
                parent = pattern.parent.parent
                if parent.exists():
                    versions = sorted([d for d in parent.iterdir() if d.is_dir()], reverse=True)
                    if versions:
                        v8_exe = versions[0] / pattern.name.replace("*", "")
                        if v8_exe.exists():
                            break
            elif pattern.exists():
                v8_exe = pattern
                break
        
        if not v8_exe or not v8_exe.exists():
            print(f"[ERROR] 1cv8c не найден. Укажите путь через --v8-path")
            return 127
    
    # Формируем команду
    cmd = [str(v8_exe), "ENTERPRISE"]
    
    # Параметры подключения к ИБ
    if ib_path:
        cmd.extend(["/IBPath", ib_path])
    elif ib_name:
        cmd.extend(["/IBName", ib_name])
    else:
        print("[ERROR] Необходимо указать --ib-path или --ib-name")
        return 1
    
    # Параметры авторизации
    cmd.extend(["/N", ib_user])
    if ib_password:
        cmd.extend(["/P", ib_password])
    
    # Параметр запуска тестов
    cmd.extend(["/C", f"RunUnitTests={config_path.absolute()}"])
    
    # Параметры для CI/CD
    cmd.extend([
        "/DisableStartupDialogs",
        "/DisableStartupMessages",
        "/DisableUnrecoverableErrorMessage",
    ])
    
    print(f"[run_yaxunit_tests] Запуск: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        return result.returncode
    except FileNotFoundError:
        print(f"[ERROR] Не удалось запустить {v8_exe}")
        return 127
    except Exception as e:
        print(f"[ERROR] Ошибка при запуске тестов: {e}")
        return 1


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description="Запуск YAxUnit тестов через 1С:Предприятие"
    )
    
    parser.add_argument(
        "--test-dir",
        type=Path,
        default=DEFAULT_TEST_DIR,
        help=f"Директория с тестами (default: {DEFAULT_TEST_DIR})",
    )
    
    parser.add_argument(
        "--test-files",
        nargs="+",
        help="Конкретные файлы тестов для запуска",
    )
    
    parser.add_argument(
        "--modules",
        nargs="+",
        help="Имена модулей для запуска",
    )
    
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Директория для отчетов и логов (default: {DEFAULT_OUTPUT_DIR})",
    )
    
    parser.add_argument(
        "--config-file",
        type=Path,
        help="Путь к файлу конфигурации (по умолчанию создается автоматически)",
    )
    
    parser.add_argument(
        "--report-format",
        choices=["jUnit", "JSON", "allure"],
        default="jUnit",
        help="Формат отчета (default: jUnit)",
    )
    
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Уровень логирования (default: info)",
    )
    
    # Параметры подключения к 1С
    parser.add_argument(
        "--ib-path",
        help="Путь к файловой информационной базе",
    )
    
    parser.add_argument(
        "--ib-name",
        help="Имя информационной базы на сервере",
    )
    
    parser.add_argument(
        "--ib-user",
        default="Admin",
        help="Имя пользователя (default: Admin)",
    )
    
    parser.add_argument(
        "--ib-password",
        help="Пароль пользователя",
    )
    
    parser.add_argument(
        "--v8-path",
        help="Путь к 1cv8c.exe",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только создать конфигурацию, не запускать тесты",
    )
    
    return parser.parse_args()


def main() -> int:
    """Главная функция."""
    args = parse_args()
    
    # Создаем директории
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "reports").mkdir(exist_ok=True)
    (output_dir / "logs").mkdir(exist_ok=True)
    
    # Пути к файлам
    config_file = args.config_file or (output_dir / "yaxunit-config.json")
    report_file = output_dir / "reports" / "report.xml"
    log_file = output_dir / "logs" / "tests.log"
    
    # Создаем конфигурацию
    config = create_yaxunit_config(
        test_files=args.test_files,
        modules=args.modules,
        report_path=report_file,
        log_file=log_file,
        report_format=args.report_format,
        log_level=args.log_level,
    )
    
    # Сохраняем конфигурацию
    save_config(config, config_file)
    print(f"[run_yaxunit_tests] Конфигурация сохранена: {config_file}")
    
    if args.dry_run:
        print("[run_yaxunit_tests] Dry-run режим: тесты не запускаются")
        return 0
    
    # Запускаем тесты
    if not args.ib_path and not args.ib_name:
        print("[WARNING] Не указана информационная база. Используйте --ib-path или --ib-name")
        print("[INFO] Для локальной разработки создайте тестовую ИБ и укажите путь")
        return 0
    
    exit_code = run_1c_tests(
        config_path=config_file,
        ib_path=args.ib_path,
        ib_name=args.ib_name,
        ib_user=args.ib_user,
        ib_password=args.ib_password,
        v8_path=args.v8_path,
    )
    
    if exit_code == 0:
        print(f"[run_yaxunit_tests] Тесты успешно завершены")
        print(f"[run_yaxunit_tests] Отчет: {report_file}")
    else:
        print(f"[run_yaxunit_tests] Тесты завершились с ошибкой (код: {exit_code})")
        if log_file.exists():
            print(f"[run_yaxunit_tests] Лог: {log_file}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

