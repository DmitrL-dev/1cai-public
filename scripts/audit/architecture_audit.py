
#!/usr/bin/env python3
"""
Архитектурный аудит проекта 1С AI Stack.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

DEFAULT_IGNORE = {"__pycache__", ".git", "node_modules", "1c_configurations"}


class ArchitectureAuditor:
    def __init__(self, project_root: Path, ignore: Set[str], limit_modules: int | None) -> None:
        self.project_root = project_root
        self.ignore_dirs = ignore
        self.limit_modules = limit_modules
        self.imports_graph: Dict[str, Set[str]] = defaultdict(set)
        self.modules: Dict[str, Dict[str, any]] = {}
        self.layers: Dict[str, List[str]] = defaultdict(list)

    def audit_architecture(self) -> Dict[str, any]:
        self.scan_modules()
        self.build_import_graph()
        cycles = self.find_circular_dependencies()
        concerns = self.check_separation_of_concerns()

        return {
            "total_modules": len(self.modules),
            "import_connections": sum(len(v) for v in self.imports_graph.values()),
            "circular_dependencies": len(cycles),
            "cycles_details": cycles[:10],
            "layers": {k: len(v) for k, v in self.layers.items()},
            "concerns": concerns,
        }

    def scan_modules(self) -> None:
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = Path(root) / file
                rel_path = file_path.relative_to(self.project_root)
                module_name = str(rel_path)
                layer = self.detect_layer(rel_path)
                self.modules[module_name] = {"path": file_path, "layer": layer, "imports": []}
                self.layers[layer].append(module_name)

    def detect_layer(self, rel_path: Path) -> str:
        parts = rel_path.parts
        if not parts:
            return "root"
        first = parts[0].lower()
        if first == "src" and len(parts) > 1:
            second = parts[1].lower()
            mapping = {
                "api": "api_layer",
                "services": "service_layer",
                "db": "data_layer",
                "ai": "ai_layer",
            }
            return mapping.get(second, "business_layer")
        if first in {"scripts", "tests", "frontend", "frontend-portal"}:
            return first
        return first

    def build_import_graph(self) -> None:
        for module_name, info in self.modules.items():
            try:
                with info["path"].open("r", encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=str(info["path"]))
            except (OSError, SyntaxError):
                continue
            imports = self.extract_imports(tree)
            info["imports"] = imports
            for imp in imports:
                if imp in self.modules:
                    self.imports_graph[module_name].add(imp)

    @staticmethod
    def extract_imports(tree: ast.AST) -> List[str]:
        imports: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names if alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        return imports

    def find_circular_dependencies(self) -> List[List[str]]:
        cycles: List[List[str]] = []
        visited: Set[str] = set()

        def dfs(node: str, path: List[str]) -> None:
            if node in path:
                cycle = path[path.index(node) :]
                if len(cycle) > 1 and cycle not in cycles:
                    cycles.append(cycle)
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            for neighbor in self.imports_graph.get(node, []):
                dfs(neighbor, path.copy())
            path.pop()

        module_names = list(self.modules.keys())
        if self.limit_modules:
            module_names = module_names[: self.limit_modules]
        for module in module_names:
            dfs(module, [])
        return cycles

    def check_separation_of_concerns(self) -> Dict[str, List[str]]:
        issues: Dict[str, List[str]] = defaultdict(list)
        rules = {
            "api_layer": {"services", "db", "tests"},
            "service_layer": {"db", "frontend"},
        }
        for module, info in self.modules.items():
            allowed = rules.get(info["layer"], set())
            if not allowed:
                continue
            for imp in info["imports"]:
                imported_layer = self.modules.get(imp, {}).get("layer")
                if imported_layer and any(layer in imported_layer for layer in allowed):
                    issues[info["layer"]].append(module)
                    break
        return dict(issues)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Архитектурный аудит проекта")
    parser.add_argument("--root", type=Path, default=Path("."), help="Корень проекта")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./output/audit/architecture_audit.json"),
        help="Файл для сохранения отчёта",
    )
    parser.add_argument(
        "--ignore",
        nargs="*",
        default=list(DEFAULT_IGNORE),
        help="Каталоги для игнорирования",
    )
    parser.add_argument(
        "--limit-modules",
        type=int,
        default=None,
        help="Ограничить количество модулей при поиске циклов",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    if not root.exists():
        print(f"Ошибка: каталог {root} не найден")
        return 1

    auditor = ArchitectureAuditor(root, set(args.ignore), args.limit_modules)
    report = auditor.audit_architecture()
    report["schema_version"] = "1.0.0"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)

    print("=" * 80)
    print(f"АРХИТЕКТУРНЫЙ АУДИТ ЗАВЕРШЁН. Отчёт: {args.output}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())




