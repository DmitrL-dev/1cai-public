
#!/usr/bin/env python3
"""
Анализ архитектуры конфигурации 1С.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scripts.analysis.tree_sitter_adapter import ensure_parser, extract_calls


def load_parse_results(parse_path: Path) -> Dict[str, Any]:
    """Загрузить результаты парсинга EDT."""
    if not parse_path.exists():
        raise FileNotFoundError(
            f"Файл {parse_path} не найден. Запустите парсер EDT перед анализом."
        )

    try:
        with parse_path.open("r", encoding="utf-8") as fp:
            return json.load(fp)
    except json.JSONDecodeError as err:
        raise ValueError(f"Повреждён JSON ({parse_path}): {err}") from err


def analyze_module_distribution(data: Dict[str, Any]) -> Dict[str, Any]:
    """Анализ распределения модулей по типам."""
    print("\n" + "=" * 80)
    print("1. РАСПРЕДЕЛЕНИЕ МОДУЛЕЙ ПО ТИПАМ")
    print("=" * 80)

    stats = {
        "common_modules": len(data.get("common_modules", [])),
        "catalogs": len(data.get("catalogs", [])),
        "documents": len(data.get("documents", [])),
        "catalog_managers": 0,
        "catalog_objects": 0,
        "document_managers": 0,
        "document_objects": 0,
    }

    for catalog in data.get("catalogs", []):
        manager_module = catalog.get("manager_module")
        if manager_module:
            stats["catalog_managers"] += 1
        object_module = catalog.get("object_module")
        if object_module:
            stats["catalog_objects"] += 1

    for doc in data.get("documents", []):
        manager_module = doc.get("manager_module")
        if manager_module:
            stats["document_managers"] += 1
        object_module = doc.get("object_module")
        if object_module:
            stats["document_objects"] += 1

    total_modules = (
        stats["common_modules"]
        + stats["catalog_managers"]
        + stats["catalog_objects"]
        + stats["document_managers"]
        + stats["document_objects"]
    )

    print(f"\nОбщих модулей: {stats['common_modules']:,}")
    print(f"\nСправочников: {stats['catalogs']:,}")
    print(f"  - С модулем менеджера: {stats['catalog_managers']:,}")
    print(f"  - С модулем объекта: {stats['catalog_objects']:,}")
    print(f"\nДокументов: {stats['documents']:,}")
    print(f"  - С модулем менеджера: {stats['document_managers']:,}")
    print(f"  - С модулем объекта: {stats['document_objects']:,}")
    print(f"\nВСЕГО МОДУЛЕЙ С КОДОМ: {total_modules:,}")

    return stats


def _collect_code_chunks(modules: List[Dict[str, Any]]) -> List[str]:
    chunks: List[str] = []
    for module in modules:
        if not module:
            continue
        if code := module.get("code"):
            chunks.append(code)
        for func in module.get("functions", []) or []:
            if not func:
                continue
            body = func.get("body")
            if body:
                chunks.append(body)
        for proc in module.get("procedures", []) or []:
            if not proc:
                continue
            body = proc.get("body")
            if body:
                chunks.append(body)
    return chunks


def analyze_code_volume(data: Dict[str, Any]) -> Dict[str, Any]:
    """Анализ объёма кода."""
    print("\n" + "=" * 80)
    print("2. ОБЪЕМ КОДА")
    print("=" * 80)

    volumes = {
        "common_modules": {"total": 0, "avg": 0, "max": 0, "max_name": ""},
        "catalogs": {"total": 0, "avg": 0, "max": 0, "max_name": ""},
        "documents": {"total": 0, "avg": 0, "max": 0, "max_name": ""},
    }

    for module in data.get("common_modules", []):
        size = module.get("code_length", 0)
        volumes["common_modules"]["total"] += size
        if size > volumes["common_modules"]["max"]:
            volumes["common_modules"]["max"] = size
            volumes["common_modules"]["max_name"] = module.get("name", "")

    if data.get("common_modules"):
        volumes["common_modules"]["avg"] = (
            volumes["common_modules"]["total"] / len(data["common_modules"])
        )

    for catalog in data.get("catalogs", []):
        size = 0
        if catalog.get("manager_module"):
            size += catalog["manager_module"].get("code_length", 0)
        if catalog.get("object_module"):
            size += catalog["object_module"].get("code_length", 0)
        volumes["catalogs"]["total"] += size
        if size > volumes["catalogs"]["max"]:
            volumes["catalogs"]["max"] = size
            volumes["catalogs"]["max_name"] = catalog.get("name", "")

    if data.get("catalogs"):
        volumes["catalogs"]["avg"] = volumes["catalogs"]["total"] / len(data["catalogs"])

    for doc in data.get("documents", []):
        size = 0
        if doc.get("manager_module"):
            size += doc["manager_module"].get("code_length", 0)
        if doc.get("object_module"):
            size += doc["object_module"].get("code_length", 0)
        volumes["documents"]["total"] += size
        if size > volumes["documents"]["max"]:
            volumes["documents"]["max"] = size
            volumes["documents"]["max_name"] = doc.get("name", "")

    if data.get("documents"):
        volumes["documents"]["avg"] = volumes["documents"]["total"] / len(data["documents"])

    total_code = (
        volumes["common_modules"]["total"]
        + volumes["catalogs"]["total"]
        + volumes["documents"]["total"]
    )

    parser_available = ensure_parser()
    total_calls = 0
    unique_calls = set()
    if parser_available:
        call_stats: Counter[str] = Counter()

        def _process_chunk(text: str) -> None:
            if not text:
                return
            calls = extract_calls(text)
            call_stats.update(calls)

        for module in data.get("common_modules", []):
            if isinstance(module, dict):
                for chunk in _collect_code_chunks([module]):
                    _process_chunk(chunk)

        for catalog in data.get("catalogs", []):
            if not isinstance(catalog, dict):
                continue
            for chunk in _collect_code_chunks(
                [
                    catalog.get("manager_module", {}) or {},
                    catalog.get("object_module", {}) or {},
                ]
            ):
                _process_chunk(chunk)

        for doc in data.get("documents", []):
            if not isinstance(doc, dict):
                continue
            for chunk in _collect_code_chunks(
                [
                    doc.get("manager_module", {}) or {},
                    doc.get("object_module", {}) or {},
                ]
            ):
                _process_chunk(chunk)

        total_calls = sum(call_stats.values())
        unique_calls = set(call_stats.keys())

    print("\nОбщие модули:")
    print(f"  Всего символов: {volumes['common_modules']['total']:,}")
    print(f"  Средний размер: {volumes['common_modules']['avg']:,.0f} символов")
    print(
        "  Самый большой: "
        f"{volumes['common_modules']['max_name']} "
        f"({volumes['common_modules']['max']:,} символов)"
    )

    print("\nСправочники:")
    print(f"  Всего символов: {volumes['catalogs']['total']:,}")
    print(f"  Средний размер: {volumes['catalogs']['avg']:,.0f} символов")
    print(
        "  Самый большой: "
        f"{volumes['catalogs']['max_name']} "
        f"({volumes['catalogs']['max']:,} символов)"
    )

    print("\nДокументы:")
    print(f"  Всего символов: {volumes['documents']['total']:,}")
    print(f"  Средний размер: {volumes['documents']['avg']:,.0f} символов")
    print(
        "  Самый большой: "
        f"{volumes['documents']['max_name']} "
        f"({volumes['documents']['max']:,} символов)"
    )

    print(f"\nВСЕГО СИМВОЛОВ КОДА: {total_code:,}")
    print(f"Примерно страниц текста: {total_code / 4000:,.0f}")
    print(f"Примерно книг по 300 страниц: {total_code / 4000 / 300:,.0f}")
    if parser_available:
        print(f"Всего вызовов функций/процедур: {total_calls:,} (уникальных: {len(unique_calls):,})")
    else:
        print("Вызовы функций/процедур: пропущены (tree-sitter-bsl не настроен)")

    volumes["call_stats"] = {
        "collected": bool(parser_available),
        "total_calls": total_calls,
        "unique_calls": len(unique_calls),
    }
    return volumes


def _collect_module_metrics(module: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """Подсчитать функции, процедуры, экспорт и параметры в конкретном модуле."""
    functions = module.get("functions", [])
    procedures = module.get("procedures", [])

    fn_real = len(functions)
    pr_real = len(procedures)
    exp_real = sum(1 for func in functions if func.get("is_export"))
    params_real = sum(len(func.get("parameters", [])) for func in functions)
    params_real += sum(len(proc.get("parameters", [])) for proc in procedures)

    fn_total = max(fn_real, module.get("functions_count", 0))
    pr_total = max(pr_real, module.get("procedures_count", 0))
    exp_total = max(exp_real, module.get("export_functions_count", 0))
    params_total = max(params_real, module.get("parameters_count", 0))

    return fn_total, pr_total, exp_total, params_total


def analyze_complexity(data: Dict[str, Any]) -> Dict[str, Any]:
    """Анализ сложности кода."""
    print("\n" + "=" * 80)
    print("3. СЛОЖНОСТЬ КОДА")
    print("=" * 80)

    total_functions = 0
    total_procedures = 0
    total_params = 0
    export_functions = 0

    for module in data.get("common_modules", []):
        fn, pr, exp, params = _collect_module_metrics(module)
        total_functions += fn
        total_procedures += pr
        export_functions += exp
        total_params += params

    for catalog in data.get("catalogs", []):
        for module_key in ["manager_module", "object_module"]:
            module = catalog.get(module_key)
            if not module:
                continue
            fn, pr, exp, params = _collect_module_metrics(module)
            total_functions += fn
            total_procedures += pr
            export_functions += exp
            total_params += params

    for doc in data.get("documents", []):
        for module_key in ["manager_module", "object_module"]:
            module = doc.get(module_key)
            if not module:
                continue
            fn, pr, exp, params = _collect_module_metrics(module)
            total_functions += fn
            total_procedures += pr
            export_functions += exp
            total_params += params

    total_methods = total_functions + total_procedures
    avg_params = total_params / total_methods if total_methods > 0 else 0

    print(f"\nВсего методов: {total_methods:,}")
    print(f"  Функций: {total_functions:,}")
    print(f"  Процедур: {total_procedures:,}")
    export_percent = (export_functions / total_functions * 100) if total_functions else 0
    print(f"\nЭкспортных функций: {export_functions:,} ({export_percent:.1f}%)")
    print(f"\nСредне параметров на метод: {avg_params:.2f}")

    return {
        "total_methods": total_methods,
        "functions": total_functions,
        "procedures": total_procedures,
        "export_functions": export_functions,
        "avg_params": avg_params,
    }


def analyze_metadata_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    """Анализ структуры метаданных."""
    print("\n" + "=" * 80)
    print("4. СТРУКТУРА МЕТАДАННЫХ")
    print("=" * 80)

    catalog_stats = {
        "total": len(data.get("catalogs", [])),
        "with_metadata": 0,
        "hierarchical": 0,
        "total_attributes": 0,
        "total_tabular_sections": 0,
        "avg_attributes": 0,
        "avg_tabular_sections": 0,
    }

    for catalog in data.get("catalogs", []):
        metadata = catalog.get("metadata")
        if not metadata:
            continue
        catalog_stats["with_metadata"] += 1
        if metadata.get("hierarchical"):
            catalog_stats["hierarchical"] += 1
        catalog_stats["total_attributes"] += len(metadata.get("attributes", []))
        catalog_stats["total_tabular_sections"] += len(metadata.get("tabular_sections", []))

    if catalog_stats["with_metadata"]:
        catalog_stats["avg_attributes"] = (
            catalog_stats["total_attributes"] / catalog_stats["with_metadata"]
        )
        catalog_stats["avg_tabular_sections"] = (
            catalog_stats["total_tabular_sections"] / catalog_stats["with_metadata"]
        )

    doc_stats = {
        "total": len(data.get("documents", [])),
        "with_metadata": 0,
        "with_posting": 0,
        "total_attributes": 0,
        "total_tabular_sections": 0,
        "avg_attributes": 0,
        "avg_tabular_sections": 0,
    }

    for doc in data.get("documents", []):
        metadata = doc.get("metadata")
        if not metadata:
            continue
        doc_stats["with_metadata"] += 1
        if metadata.get("posting"):
            doc_stats["with_posting"] += 1
        doc_stats["total_attributes"] += len(metadata.get("attributes", []))
        doc_stats["total_tabular_sections"] += len(metadata.get("tabular_sections", []))

    if doc_stats["with_metadata"]:
        doc_stats["avg_attributes"] = (
            doc_stats["total_attributes"] / doc_stats["with_metadata"]
        )
        doc_stats["avg_tabular_sections"] = (
            doc_stats["total_tabular_sections"] / doc_stats["with_metadata"]
        )

    print("\nСПРАВОЧНИКИ:")
    print(f"  Всего: {catalog_stats['total']:,}")
    print(f"  С метаданными: {catalog_stats['with_metadata']:,}")
    print(f"  Иерархических: {catalog_stats['hierarchical']:,}")
    print(f"  Всего реквизитов: {catalog_stats['total_attributes']:,}")
    print(f"  Средне реквизитов: {catalog_stats['avg_attributes']:.1f}")
    print(f"  Всего табл. частей: {catalog_stats['total_tabular_sections']:,}")
    print(f"  Средне табл. частей: {catalog_stats['avg_tabular_sections']:.2f}")

    print("\nДОКУМЕНТЫ:")
    print(f"  Всего: {doc_stats['total']:,}")
    print(f"  С метаданными: {doc_stats['with_metadata']:,}")
    print(f"  С проведением: {doc_stats['with_posting']:,}")
    print(f"  Всего реквизитов: {doc_stats['total_attributes']:,}")
    print(f"  Средне реквизитов: {doc_stats['avg_attributes']:.1f}")
    print(f"  Всего табл. частей: {doc_stats['total_tabular_sections']:,}")
    print(f"  Средне табл. частей: {doc_stats['avg_tabular_sections']:.2f}")

    return {"catalogs": catalog_stats, "documents": doc_stats}


def analyze_top_modules(data: Dict[str, Any]) -> Dict[str, Any]:
    """Топ модулей по размерам и числу методов."""
    print("\n" + "=" * 80)
    print("5. ТОП МОДУЛЕЙ")
    print("=" * 80)

    modules_info = []
    for module in data.get("common_modules", []):
        modules_info.append(
            {
                "name": module.get("name", ""),
                "type": "CommonModule",
                "code_length": module.get("code_length", 0),
                "functions": module.get("functions_count", len(module.get("functions", []))),
                "procedures": module.get(
                    "procedures_count", len(module.get("procedures", []))
                ),
            }
        )

    modules_info.sort(key=lambda item: item["code_length"], reverse=True)
    top_by_size = modules_info[:10]
    print("\nТОП-10 по размеру кода:")
    for idx, mod in enumerate(top_by_size, 1):
        print(f"  {idx:2d}. {mod['name']:<50} {mod['code_length']:>8,} символов")

    modules_info.sort(key=lambda item: item["functions"] + item["procedures"], reverse=True)
    top_by_methods = modules_info[:10]
    print("\nТОП-10 по количеству методов:")
    for idx, mod in enumerate(top_by_methods, 1):
        total_methods = mod["functions"] + mod["procedures"]
        print(f"  {idx:2d}. {mod['name']:<50} {total_methods:>4} методов")

    modules_info.sort(key=lambda item: item["functions"], reverse=True)
    top_by_funcs = modules_info[:10]
    print("\nТОП-10 по количеству функций:")
    for idx, mod in enumerate(top_by_funcs, 1):
        print(f"  {idx:2d}. {mod['name']:<50} {mod['functions']:>4} функций")

    return {
        "top_by_size": top_by_size,
        "top_by_methods": top_by_methods,
        "top_by_functions": top_by_funcs,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Анализ архитектуры конфигурации 1С")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("./output/edt_parser/full_parse_with_metadata.json"),
        help="Путь к результатам парсинга EDT",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./output/analysis/architecture_analysis.json"),
        help="Путь для сохранения результатов анализа",
    )
    parser.add_argument(
        "--config-name",
        default="Configuration",
        help="Имя конфигурации для логов и отчёта",
    )
    return parser.parse_args()


def main() -> int:
    """Главная функция"""
    args = parse_args()

    print("=" * 80)
    print(f"АНАЛИЗ АРХИТЕКТУРЫ КОНФИГУРАЦИИ {args.config_name.upper()}")
    print("=" * 80)

    try:
        data = load_parse_results(args.input)
    except (FileNotFoundError, ValueError) as err:
        print(f"Ошибка: {err}")
        return 1

    results = {
        "schema_version": "1.0.0",
        "config_name": args.config_name,
        "distribution": analyze_module_distribution(data),
        "volume": analyze_code_volume(data),
        "complexity": analyze_complexity(data),
        "metadata": analyze_metadata_structure(data),
        "top_modules": analyze_top_modules(data),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("АНАЛИЗ ЗАВЕРШЕН")
    print("=" * 80)
    print(f"\nРезультаты сохранены: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())




