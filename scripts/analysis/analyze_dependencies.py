
#!/usr/bin/env python3
"""
Анализ зависимостей между объектами конфигурации 1С.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

from scripts.analysis.tree_sitter_adapter import ensure_parser, extract_calls

CATALOG_PATTERNS = [
    r"Справочники\.(\w+)",
    r"Справочник\.(\w+)",
    r"CatalogRef\.(\w+)",
    r"Catalog\.(\w+)",
]
DOCUMENT_PATTERNS = [
    r"Документы\.(\w+)",
    r"Документ\.(\w+)",
    r"DocumentRef\.(\w+)",
    r"Document\.(\w+)",
]
REGISTER_PATTERNS = [
    r"РегистрыСведений\.(\w+)",
    r"РегистрыНакопления\.(\w+)",
    r"InformationRegister\.(\w+)",
    r"AccumulationRegister\.(\w+)",
]


def load_parse_results(parse_path: Path) -> Dict[str, Any]:
    if not parse_path.exists():
        raise FileNotFoundError(
            f"Файл {parse_path} не найден. Запустите парсинг EDT перед анализом зависимостей."
        )

    try:
        with parse_path.open("r", encoding="utf-8") as fp:
            return json.load(fp)
    except json.JSONDecodeError as err:
        raise ValueError(f"Повреждён JSON ({parse_path}): {err}") from err


def _extract(patterns: Iterable[str], code: str) -> Set[str]:
    refs: Set[str] = set()
    for pattern in patterns:
        refs.update(re.findall(pattern, code, re.IGNORECASE))
    return refs


def analyze_module_dependencies(module: Dict[str, Any], module_name: str) -> Dict[str, Any]:
    code_parts: List[str] = []
    if "code" in module:
        code_parts.append(module["code"])
    for func in module.get("functions", []):
        body = func.get("body")
        if body:
            code_parts.append(body)
    for proc in module.get("procedures", []):
        body = proc.get("body")
        if body:
            code_parts.append(body)

    full_code = "\n".join(code_parts)
    calls = extract_calls(full_code) if ensure_parser() else {}

    return {
        "module_name": module_name,
        "catalogs": list(_extract(CATALOG_PATTERNS, full_code)),
        "documents": list(_extract(DOCUMENT_PATTERNS, full_code)),
        "registers": list(_extract(REGISTER_PATTERNS, full_code)),
        "calls": calls,
    }


def analyze_object_dependencies(obj: Dict[str, Any], obj_name: str, obj_type: str) -> Dict[str, Any]:
    dependencies = {
        "object_name": obj_name,
        "object_type": obj_type,
        "metadata_refs": {"catalogs": [], "documents": []},
        "code_refs": {
            "catalogs": [],
            "documents": [],
            "registers": [],
            "calls": {},
        },
    }

    metadata = obj.get("metadata")
    if metadata:
        for attr in metadata.get("attributes", []) or []:
            for type_name in attr.get("type", {}).get("types", []) or []:
                if "CatalogRef." in type_name or "Справочник." in type_name:
                    dependencies["metadata_refs"]["catalogs"].append(
                        type_name.split(".")[-1]
                    )
                elif "DocumentRef." in type_name or "Документ." in type_name:
                    dependencies["metadata_refs"]["documents"].append(
                        type_name.split(".")[-1]
                    )
        for section in metadata.get("tabular_sections", []) or []:
            for col in section.get("columns", []) or []:
                for type_name in col.get("type", {}).get("types", []) or []:
                    if "CatalogRef." in type_name or "Справочник." in type_name:
                        dependencies["metadata_refs"]["catalogs"].append(
                            type_name.split(".")[-1]
                        )
                    elif "DocumentRef." in type_name or "Документ." in type_name:
                        dependencies["metadata_refs"]["documents"].append(
                            type_name.split(".")[-1]
                        )

    code_parts: List[str] = []
    for module_key in ["manager_module", "object_module"]:
        module = obj.get(module_key)
        if not module:
            continue
        if "code" in module:
            code_parts.append(module["code"])
        for func in module.get("functions", []) or []:
            body = func.get("body")
            if body:
                code_parts.append(body)
        for proc in module.get("procedures", []) or []:
            body = proc.get("body")
            if body:
                code_parts.append(body)

    if code_parts:
        full_code = "\n".join(code_parts)
        parser_available = ensure_parser()
        dependencies["code_refs"]["catalogs"] = list(_extract(CATALOG_PATTERNS, full_code))
        dependencies["code_refs"]["documents"] = list(_extract(DOCUMENT_PATTERNS, full_code))
        dependencies["code_refs"]["registers"] = list(_extract(REGISTER_PATTERNS, full_code))
        if parser_available:
            dependencies["code_refs"]["calls"] = extract_calls(full_code)
        else:
            dependencies["code_refs"]["calls"] = {}

    return dependencies


def build_dependency_graph(
    data: Dict[str, Any],
    limit_modules: int | None,
    limit_objects: int | None,
) -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print("ПОСТРОЕНИЕ ГРАФА ЗАВИСИМОСТЕЙ")
    print("=" * 80)

    graph = {"nodes": [], "edges": []}
    all_deps: List[Dict[str, Any]] = []

    modules = data.get("common_modules", [])
    if limit_modules:
        modules = modules[:limit_modules]

    print("\nАнализ общих модулей...")
    for module in modules:
        if not module or not isinstance(module, dict):
            continue
        module_name = module.get("name", "")
        deps = analyze_module_dependencies(module, module_name)
        all_deps.append(deps)
        graph["nodes"].append({"name": module_name, "type": "CommonModule"})
        for catalog in deps["catalogs"]:
            graph["edges"].append({"source": module_name, "target": catalog, "type": "catalog"})
        for document in deps["documents"]:
            graph["edges"].append({"source": module_name, "target": document, "type": "document"})
        if deps.get("calls"):
            for callee, count in deps["calls"].items():
                graph["edges"].append(
                    {"source": module_name, "target": callee, "type": "call", "weight": count}
                )

    objects = []
    for catalog in data.get("catalogs", []):
        objects.append((catalog, "Catalog"))
    for doc in data.get("documents", []):
        objects.append((doc, "Document"))

    if limit_objects:
        objects = objects[:limit_objects]

    for obj, obj_type in objects:
        if not obj or not isinstance(obj, dict):
            continue
        deps = analyze_object_dependencies(obj, obj.get("name", ""), obj_type)
        graph["nodes"].append({"name": obj.get("name", ""), "type": obj_type})
        all_deps.append(deps)

        for catalog in deps["code_refs"]["catalogs"]:
            graph["edges"].append({"source": obj.get("name", ""), "target": catalog, "type": "catalog"})
        for document in deps["code_refs"]["documents"]:
            graph["edges"].append({"source": obj.get("name", ""), "target": document, "type": "document"})
        for register in deps["code_refs"]["registers"]:
            graph["edges"].append({"source": obj.get("name", ""), "target": register, "type": "register"})
        calls = deps["code_refs"].get("calls") or {}
        for callee, count in calls.items():
            graph["edges"].append(
                {"source": obj.get("name", ""), "target": callee, "type": "call", "weight": count}
            )

    return {"graph": graph, "dependencies": all_deps}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Анализ зависимостей объектов конфигурации 1С")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("./output/edt_parser/full_parse_with_metadata.json"),
        help="Путь к результатам парсинга EDT",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./output/analysis/dependency_analysis.json"),
        help="Файл для сохранения графа и зависимостей",
    )
    parser.add_argument(
        "--limit-modules",
        type=int,
        default=None,
        help="Ограничить количество анализируемых общих модулей",
    )
    parser.add_argument(
        "--limit-objects",
        type=int,
        default=None,
        help="Ограничить количество анализируемых объектов (справочники + документы)",
    )
    parser.add_argument(
        "--config-name",
        default="Configuration",
        help="Имя конфигурации для заголовков",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("=" * 80)
    print(f"АНАЛИЗ ЗАВИСИМОСТЕЙ ДЛЯ {args.config_name.upper()}")
    print("=" * 80)

    try:
        data = load_parse_results(args.input)
    except (FileNotFoundError, ValueError) as err:
        print(f"Ошибка: {err}")
        return 1

    graph_data = build_dependency_graph(data, args.limit_modules, args.limit_objects)

    result = {
        "schema_version": "1.0.0",
        "config_name": args.config_name,
        "graph": graph_data["graph"],
        "dependencies": graph_data["dependencies"],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("АНАЛИЗ ЗАВИСИМОСТЕЙ ЗАВЕРШЁН")
    print("=" * 80)
    print(f"\nРезультаты сохранены: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())




