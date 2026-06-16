
#!/usr/bin/env python3
"""
Комплексный аудит всего проекта (Deep Audit)
Этапы 4-9: Глубокий комплексный аудит с использованием AST

Проверяет:
- Зависимости (requirements)
- Тесты
- Документацию
- Конфигурацию
- Безопасность (AST-based)
- Технический долг
- Type Hints (AST-based)
- Неиспользуемые импорты (AST-based)
- Циклические зависимости
"""

import ast
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

# Добавляем корневую директорию в путь для импорта скриптов
sys.path.append(os.getcwd())

try:
    from scripts.architecture.find_cycles import CycleFinder
except ImportError:
    CycleFinder = None


class DeepProjectAuditor:
    """Глубокий аудитор проекта на основе AST"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.findings = defaultdict(list)
        self.stats = defaultdict(int)
    
    def run_full_audit(self) -> Dict:
        """Полный аудит проекта"""
        print("=" * 80)
        print("ГЛУБОКИЙ КОМПЛЕКСНЫЙ АУДИТ ПРОЕКТА (AST-BASED)")
        print("=" * 80)
        print()
        
        results = {}
        
        # Этап 4: Зависимости
        print("[ЭТАП 4] Анализ зависимостей...")
        results['dependencies'] = self.audit_dependencies()
        
        # Этап 5: Тесты
        print("\n[ЭТАП 5] Проверка тестов...")
        results['tests'] = self.audit_tests()
        
        # Этап 6: Документация
        print("\n[ЭТАП 6] Аудит документации...")
        results['documentation'] = self.audit_documentation()
        
        # Этап 7: Конфигурация
        print("\n[ЭТАП 7] Анализ конфигурации...")
        results['configuration'] = self.audit_configuration()
        
        # Этап 8: Безопасность (AST)
        print("\n[ЭТАП 8] Проверка безопасности (AST)...")
        results['security'] = self.audit_security()
        
        # Этап 9: Технический долг
        print("\n[ЭТАП 9] Поиск технического долга...")
        results['technical_debt'] = self.audit_technical_debt()

        # Этап 10: Type Hints (AST)
        print("\n[ЭТАП 10] Анализ Type Hints (AST)...")
        results['type_hints'] = self.audit_type_hints()

        # Этап 11: Неиспользуемые импорты (AST)
        print("\n[ЭТАП 11] Поиск неиспользуемых импортов (AST)...")
        results['unused_imports'] = self.audit_unused_imports()

        # Этап 12: Циклические зависимости
        print("\n[ЭТАП 12] Поиск циклических зависимостей...")
        results['cycles'] = self.audit_cycles()
        
        return results
    
    def _get_python_files(self) -> List[Path]:
        """Получить список всех Python файлов, исключая venv и кэш"""
        py_files = []
        for root, dirs, files in os.walk(self.project_root):
            if 'venv' in root or '__pycache__' in root or '.git' in root or 'node_modules' in root:
                continue
            for file in files:
                if file.endswith('.py'):
                    py_files.append(Path(root) / file)
        return py_files

    def audit_dependencies(self) -> Dict:
        """Аудит зависимостей"""
        results = {
            'requirements_files': [],
            'total_dependencies': 0,
            'unique_packages': set()
        }
        
        for file in self.project_root.glob('requirements*.txt'):
            with open(file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            deps = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    pkg_name = re.split(r'[=<>~!]', line)[0].strip()
                    deps.append(line)
                    results['unique_packages'].add(pkg_name)
            
            results['requirements_files'].append({
                'file': file.name,
                'dependencies': len(deps),
                'examples': deps[:5]
            })
            results['total_dependencies'] += len(deps)
        
        print(f"  Requirements файлов: {len(results['requirements_files'])}")
        print(f"  Всего зависимостей: {results['total_dependencies']}")
        print(f"  Уникальных пакетов: {len(results['unique_packages'])}")
        
        results['unique_packages'] = list(results['unique_packages'])
        return results
    
    def audit_tests(self) -> Dict:
        """Аудит тестов"""
        test_files = list(self.project_root.glob('**/test_*.py'))
        test_dirs = list(self.project_root.glob('**/tests'))
        
        total_test_functions = 0
        
        for test_file in test_files:
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name.startswith('test_'):
                            total_test_functions += 1
            except:
                pass
        
        results = {
            'test_files': len(test_files),
            'test_directories': len(test_dirs),
            'test_functions': total_test_functions,
        }
        
        print(f"  Тестовых файлов: {len(test_files)}")
        print(f"  Тестовых директорий: {len(test_dirs)}")
        print(f"  Тестовых функций: {total_test_functions}")
        
        return results
    
    def audit_documentation(self) -> Dict:
        """Аудит документации"""
        readme_files = list(self.project_root.glob('**/README.md'))
        
        md_files = []
        for root, dirs, files in os.walk(self.project_root):
            if 'node_modules' in root or '__pycache__' in root:
                continue
            for file in files:
                if file.endswith('.md'):
                    md_files.append(Path(root) / file)
        
        total_doc_size = 0
        for md_file in md_files:
            try:
                total_doc_size += md_file.stat().st_size
            except:
                pass
        
        results = {
            'readme_files': len(readme_files),
            'total_md_files': len(md_files),
            'total_doc_size_mb': total_doc_size / 1024 / 1024
        }
        
        print(f"  README файлов: {len(readme_files)}")
        print(f"  Всего .md файлов: {len(md_files)}")
        print(f"  Размер документации: {total_doc_size / 1024 / 1024:.2f} MB")
        
        return results
    
    def audit_configuration(self) -> Dict:
        """Аудит конфигурационных файлов"""
        results = {
            'docker_compose_files': [],
            'dockerfiles': [],
            'config_files': []
        }
        
        for file in self.project_root.glob('docker-compose*.yml'):
            results['docker_compose_files'].append(file.name)
        
        for file in self.project_root.glob('**/Dockerfile*'):
            if 'node_modules' not in str(file):
                results['dockerfiles'].append(str(file.relative_to(self.project_root)))
        
        for file in self.project_root.glob('*.ini'):
            results['config_files'].append(file.name)
        
        print(f"  Docker compose файлов: {len(results['docker_compose_files'])}")
        print(f"  Dockerfiles: {len(results['dockerfiles'])}")
        print(f"  Config файлов (.ini): {len(results['config_files'])}")
        
        return results
    
    def audit_security(self) -> Dict:
        """Аудит безопасности с использованием AST"""
        results = {
            'potential_secrets': [],
            'sql_injection_risks': [],
            'hardcoded_ips': []
        }
        
        sensitive_keywords = {'password', 'secret', 'api_key', 'token', 'access_key'}
        
        for py_file in self._get_python_files():
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)
                
                # AST Analysis
                for node in ast.walk(tree):
                    # 1. Hardcoded Secrets in Assignments
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                if any(k in target.id.lower() for k in sensitive_keywords):
                                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                        # Исключаем пустые строки и плейсхолдеры
                                        val = node.value.value
                                        if len(val) > 5 and not val.startswith('{') and ' ' not in val:
                                            results['potential_secrets'].append({
                                                'file': str(py_file.relative_to(self.project_root)),
                                                'variable': target.id,
                                                'line': node.lineno
                                            })
                    
                    # 2. SQL Injection Risks (execute calls with binop/format)
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Attribute) and node.func.attr == 'execute':
                            if node.args:
                                arg = node.args[0]
                                # Проверяем конкатенацию (+) или форматирование (%)
                                if isinstance(arg, ast.BinOp) or (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == 'format'):
                                    results['sql_injection_risks'].append({
                                        'file': str(py_file.relative_to(self.project_root)),
                                        'line': node.lineno
                                    })

                # 3. Hardcoded IPs (Regex still best for this, but applied to string constants only could be better, but regex is fine)
                ip_matches = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', content)
                if ip_matches:
                    filtered_ips = [ip for ip in ip_matches if ip not in ['127.0.0.1', '0.0.0.0']]
                    if filtered_ips:
                        results['hardcoded_ips'].append({
                            'file': str(py_file.relative_to(self.project_root)),
                            'ips': list(set(filtered_ips))
                        })

            except Exception as e:
                # print(f"Error analyzing {py_file}: {e}")
                pass
        
        print(f"  Потенциальных секретов (AST): {len(results['potential_secrets'])}")
        print(f"  SQL injection рисков (AST): {len(results['sql_injection_risks'])}")
        print(f"  Hardcoded IPs: {len(results['hardcoded_ips'])}")
        
        return results
    
    def audit_technical_debt(self) -> Dict:
        """Аудит технического долга (комментарии)"""
        results = {
            'todo_count': 0,
            'fixme_count': 0,
            'hack_count': 0,
            'xxx_count': 0,
            'deprecated_count': 0,
        }
        
        for py_file in self._get_python_files():
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                results['todo_count'] += len(re.findall(r'#\s*TODO', content, re.IGNORECASE))
                results['fixme_count'] += len(re.findall(r'#\s*FIXME', content, re.IGNORECASE))
                results['hack_count'] += len(re.findall(r'#\s*HACK', content, re.IGNORECASE))
                results['xxx_count'] += len(re.findall(r'#\s*XXX', content, re.IGNORECASE))
                results['deprecated_count'] += len(re.findall(r'@deprecated|# deprecated', content, re.IGNORECASE))
            except:
                pass
        
        total_debt = sum(results.values())
        print(f"  TODO: {results['todo_count']}")
        print(f"  FIXME: {results['fixme_count']}")
        print(f"  HACK: {results['hack_count']}")
        print(f"  ИТОГО маркеров: {total_debt}")
        
        return results

    def audit_type_hints(self) -> Dict:
        """Анализ покрытия Type Hints с использованием AST"""
        stats = {
            'total_functions': 0,
            'fully_typed': 0,
            'partially_typed': 0,
            'untyped': 0
        }
        
        for py_file in self._get_python_files():
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        stats['total_functions'] += 1
                        has_args = False
                        all_args_typed = True
                        has_return = node.returns is not None
                        
                        # Check arguments
                        for arg in node.args.args:
                            if arg.arg == 'self' or arg.arg == 'cls':
                                continue
                            has_args = True
                            if arg.annotation is None:
                                all_args_typed = False
                        
                        if not has_args:
                            # If no args, check return type
                            if has_return:
                                stats['fully_typed'] += 1
                            else:
                                stats['untyped'] += 1
                        else:
                            if all_args_typed and has_return:
                                stats['fully_typed'] += 1
                            elif all_args_typed or has_return:
                                stats['partially_typed'] += 1
                            else:
                                stats['untyped'] += 1
            except:
                pass
        
        coverage = (stats['fully_typed'] / stats['total_functions'] * 100) if stats['total_functions'] > 0 else 0
        print(f"  Всего функций: {stats['total_functions']}")
        print(f"  Полностью типизированы: {stats['fully_typed']} ({coverage:.1f}%)")
        print(f"  Частично типизированы: {stats['partially_typed']}")
        print(f"  Без типов: {stats['untyped']}")
        
        return stats

    def audit_unused_imports(self) -> Dict:
        """Поиск неиспользуемых импортов с использованием AST"""
        unused_count = 0
        unused_details = []
        
        for py_file in self._get_python_files():
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())
                
                imports = set()
                used_names = set()
                
                # Collect imports and usages
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            name = alias.asname if alias.asname else alias.name
                            imports.add(name.split('.')[0]) # Top level check mostly
                    elif isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            name = alias.asname if alias.asname else alias.name
                            imports.add(name)
                    elif isinstance(node, ast.Name):
                        if isinstance(node.ctx, ast.Load):
                            used_names.add(node.id)
                
                # Check for unused
                # This is a simplified check. It doesn't handle __all__, etc. perfectly but good for audit.
                for imp in imports:
                    if imp not in used_names:
                        # Ignore common unused imports like typing in some cases or if it's a re-export file
                        if imp not in ['TYPE_CHECKING', 'Optional', 'List', 'Dict', 'Any']: 
                             # Check if file is __init__.py (often re-exports)
                            if py_file.name != '__init__.py':
                                unused_count += 1
                                unused_details.append(f"{py_file.name}: {imp}")
            except:
                pass
        
        print(f"  Потенциально неиспользуемых импортов: {unused_count}")
        if unused_count > 0:
            print(f"  Примеры: {', '.join(unused_details[:5])}...")
            
        return {'count': unused_count, 'examples': unused_details[:10]}

    def audit_cycles(self) -> Dict:
        """Поиск циклических зависимостей"""
        if CycleFinder:
            finder = CycleFinder(self.project_root / "src")
            # Suppress stdout for build_graph
            # sys.stdout = open(os.devnull, 'w')
            finder.build_graph()
            cycles = finder.find_cycles()
            # sys.stdout = sys.__stdout__
            
            print(f"  Найдено циклов: {len(cycles)}")
            return {'count': len(cycles), 'cycles': cycles}
        else:
            print("  CycleFinder не найден (scripts.architecture.find_cycles). Пропуск.")
            return {'error': 'CycleFinder not found'}


def main():
    """Главная функция"""
    project_root = Path(".")
    
    auditor = DeepProjectAuditor(project_root)
    results = auditor.run_full_audit()
    
    # Сохранение
    output_dir = Path("./output/audit")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "deep_audit.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    print("\n" + "=" * 80)
    print("ГЛУБОКИЙ АУДИТ ЗАВЕРШЕН")
    print("=" * 80)
    print(f"\nРезультаты: {output_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
