"""
Анализ архитектуры проекта - всё в одном скрипте.
Запуск: python scripts/architecture/analyze_all.py
"""

import ast
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set


class ArchitectureAnalyzer:
    """Полный анализ архитектуры проекта."""
    
    def __init__(self, src_dir: Path = Path("src")):
        """Инициализация."""
        self.src_dir = src_dir
        self.results = {
            "modules": {},
            "dependencies": {},
            "complexity": {},
            "issues": [],
            "recommendations": []
        }
    
    def analyze_all(self):
        """Запускает все анализы."""
        print("=" * 80)
        print("АНАЛИЗ АРХИТЕКТУРЫ ПРОЕКТА")
        print("=" * 80)
        print()
        
        print("1. Анализ структуры модулей...")
        self.analyze_module_structure()
        
        print("\n2. Анализ зависимостей...")
        self.analyze_dependencies()
        
        print("\n3. Анализ сложности...")
        self.analyze_complexity()
        
        print("\n4. Выявление проблем...")
        self.identify_issues()
        
        print("\n5. Генерация рекомендаций...")
        self.generate_recommendations()
        
        self.save_results()
        self.print_summary()
    
    def analyze_module_structure(self):
        """Анализирует структуру модулей."""
        modules = {}
        
        for item in self.src_dir.iterdir():
            if item.is_dir() and not item.name.startswith('__'):
                py_files = list(item.rglob("*.py"))
                modules[item.name] = {
                    "files": len(py_files),
                    "lines": sum(self._count_lines(f) for f in py_files),
                    "subdirs": len([d for d in item.iterdir() if d.is_dir()])
                }
        
        self.results["modules"] = modules
        
        # Топ-5 самых больших модулей
        top_modules = sorted(
            modules.items(),
            key=lambda x: x[1]["files"],
            reverse=True
        )[:5]
        
        print("  Топ-5 модулей по количеству файлов:")
        for name, data in top_modules:
            print(f"    {name}: {data['files']} файлов, {data['lines']} строк")
    
    def analyze_dependencies(self):
        """Анализирует зависимости между модулями."""
        dependencies = defaultdict(set)
        
        for py_file in self.src_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                
                module_name = self._get_module_name(py_file)
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        imported = self._get_imported_module(node)
                        if imported and imported != module_name:
                            dependencies[module_name].add(imported)
            
            except Exception:
                pass
        
        # Конвертация set в list для JSON
        self.results["dependencies"] = {
            k: list(v) for k, v in dependencies.items()
        }
        
        # Поиск циклических зависимостей
        cycles = self._find_cycles(dependencies)
        if cycles:
            print(f"  ⚠️  Найдено циклических зависимостей: {len(cycles)}")
        else:
            print("  ✅ Циклических зависимостей не найдено")
    
    def analyze_complexity(self):
        """Анализирует сложность кода."""
        complexity_data = {}
        
        for py_file in self.src_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                
                # Подсчёт функций и классов
                functions = sum(1 for node in ast.walk(tree) 
                              if isinstance(node, ast.FunctionDef))
                classes = sum(1 for node in ast.walk(tree) 
                            if isinstance(node, ast.ClassDef))
                
                if functions > 0 or classes > 0:
                    module = self._get_module_name(py_file)
                    if module not in complexity_data:
                        complexity_data[module] = {
                            "functions": 0,
                            "classes": 0,
                            "files": 0
                        }
                    
                    complexity_data[module]["functions"] += functions
                    complexity_data[module]["classes"] += classes
                    complexity_data[module]["files"] += 1
            
            except Exception:
                pass
        
        self.results["complexity"] = complexity_data
        
        # Топ-5 самых сложных модулей
        top_complex = sorted(
            complexity_data.items(),
            key=lambda x: x[1]["functions"] + x[1]["classes"],
            reverse=True
        )[:5]
        
        print("  Топ-5 модулей по сложности:")
        for name, data in top_complex:
            total = data["functions"] + data["classes"]
            print(f"    {name}: {total} элементов ({data['functions']} функций, {data['classes']} классов)")
    
    def identify_issues(self):
        """Выявляет архитектурные проблемы."""
        issues = []
        
        # Проблема 1: Слишком много файлов в модуле
        for name, data in self.results["modules"].items():
            if data["files"] > 100:
                issues.append({
                    "severity": "high",
                    "module": name,
                    "issue": f"Слишком много файлов ({data['files']})",
                    "recommendation": "Разделить на подмодули"
                })
        
        # Проблема 2: Большой main.py
        main_py = self.src_dir / "main.py"
        if main_py.exists():
            lines = self._count_lines(main_py)
            if lines > 500:
                issues.append({
                    "severity": "medium",
                    "module": "main",
                    "issue": f"main.py слишком большой ({lines} строк)",
                    "recommendation": "Вынести логику в отдельные модули"
                })
        
        # Проблема 3: Дублирование модулей
        module_names = list(self.results["modules"].keys())
        similar = self._find_similar_names(module_names)
        for group in similar:
            if len(group) > 1:
                issues.append({
                    "severity": "low",
                    "module": ", ".join(group),
                    "issue": "Похожие названия модулей",
                    "recommendation": "Возможно объединить или переименовать"
                })
        
        self.results["issues"] = issues
        
        print(f"  Найдено проблем: {len(issues)}")
        for issue in issues[:5]:
            print(f"    [{issue['severity']}] {issue['module']}: {issue['issue']}")
    
    def generate_recommendations(self):
        """Генерирует рекомендации."""
        recommendations = []
        
        # На основе размера modules
        if "modules" in self.results["modules"]:
            files = self.results["modules"]["modules"]["files"]
            if files > 100:
                recommendations.append({
                    "priority": "critical",
                    "action": "Реструктуризация modules/",
                    "description": f"Разделить {files} файлов на доменные подмодули",
                    "effort": "high"
                })
        
        # На основе зависимостей
        dep_count = len(self.results["dependencies"])
        if dep_count > 50:
            recommendations.append({
                "priority": "medium",
                "action": "Упростить зависимости",
                "description": "Слишком много межмодульных зависимостей",
                "effort": "medium"
            })
        
        # Общие рекомендации
        recommendations.append({
            "priority": "high",
            "action": "Внедрить Dependency Injection",
            "description": "Улучшит тестируемость и модульность",
            "effort": "medium"
        })
        
        recommendations.append({
            "priority": "medium",
            "action": "Создать architecture tests",
            "description": "Автоматическая проверка архитектурных правил",
            "effort": "low"
        })
        
        self.results["recommendations"] = recommendations
        
        print(f"  Рекомендаций: {len(recommendations)}")
        for rec in recommendations:
            print(f"    [{rec['priority']}] {rec['action']}")
    
    def save_results(self):
        """Сохраняет результаты."""
        output_file = Path("architecture_analysis.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Результаты сохранены: {output_file}")
    
    def print_summary(self):
        """Выводит итоговую сводку."""
        print()
        print("=" * 80)
        print("ИТОГОВАЯ СВОДКА")
        print("=" * 80)
        print()
        
        print(f"Модулей: {len(self.results['modules'])}")
        print(f"Зависимостей: {len(self.results['dependencies'])}")
        print(f"Проблем: {len(self.results['issues'])}")
        print(f"Рекомендаций: {len(self.results['recommendations'])}")
        
        print()
        print("Критичные действия:")
        for rec in self.results["recommendations"]:
            if rec["priority"] == "critical":
                print(f"  🔴 {rec['action']}")
        
        print()
        print("=" * 80)
    
    # Вспомогательные методы
    
    def _count_lines(self, filepath: Path) -> int:
        """Подсчитывает строки в файле."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return len(f.readlines())
        except:
            return 0
    
    def _get_module_name(self, filepath: Path) -> str:
        """Получает имя модуля из пути."""
        try:
            rel_path = filepath.relative_to(self.src_dir)
            parts = rel_path.parts
            if len(parts) > 0:
                return parts[0]
        except:
            pass
        return "unknown"
    
    def _get_imported_module(self, node) -> str:
        """Получает имя импортируемого модуля."""
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("src."):
                parts = node.module.split(".")
                if len(parts) > 1:
                    return parts[1]
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("src."):
                    parts = alias.name.split(".")
                    if len(parts) > 1:
                        return parts[1]
        return None
    
    def _find_cycles(self, dependencies: Dict[str, Set[str]]) -> List[List[str]]:
        """Находит циклические зависимости."""
        cycles = []
        visited = set()
        
        def dfs(node, path):
            if node in path:
                cycle_start = path.index(node)
                cycle = path[cycle_start:]
                if cycle not in cycles:
                    cycles.append(cycle)
                return
            
            if node in visited:
                return
            
            visited.add(node)
            path.append(node)
            
            for dep in dependencies.get(node, []):
                dfs(dep, path.copy())
        
        for node in dependencies:
            dfs(node, [])
        
        return cycles
    
    def _find_similar_names(self, names: List[str]) -> List[List[str]]:
        """Находит похожие названия."""
        similar = []
        
        # Простая эвристика: одинаковые корни
        roots = defaultdict(list)
        for name in names:
            root = name.split("_")[0]
            roots[root].append(name)
        
        for group in roots.values():
            if len(group) > 1:
                similar.append(group)
        
        return similar


def main():
    """Главная функция."""
    analyzer = ArchitectureAnalyzer()
    analyzer.analyze_all()


if __name__ == "__main__":
    main()
