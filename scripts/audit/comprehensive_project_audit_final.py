
#!/usr/bin/env python3
"""
КОМПЛЕКСНЫЙ АУДИТ ВСЕГО ПРОЕКТА
Максимальная тщательность - проверяем ВСЕ
Версия 2.0 - с учетом всех уроков
"""

import os
import re
from collections import defaultdict
from pathlib import Path


class ComprehensiveAuditor:
    def __init__(self):
        self.critical_issues = []
        self.warnings = []
        self.info = []
        self.stats = defaultdict(int)
        
    def check_1_essential_files(self):
        """1. Проверка критичных файлов проекта"""
        print("[1/15] Критичные файлы проекта...")
        
        essential = {
            'README.md': 'Main documentation',
            'LICENSE': 'License file',
            'CONTRIBUTING.md': 'Contributing guide',
            'CHANGELOG.md': 'Version history',
            '.gitignore': 'Git ignore rules',
            'requirements.txt': 'Python dependencies',
            'env.example': 'Environment variables example',
            'docker-compose.yml': 'Docker compose config',
        }
        
        for file, desc in essential.items():
            if os.path.exists(file):
                self.stats[f'essential_{file}'] = 1
                self.info.append(f"✓ {desc}: {file}")
            else:
                self.critical_issues.append(f"MISSING {desc}: {file}")
    
    def check_2_documentation_structure(self):
        """2. Проверка структуры документации"""
        print("[2/15] Структура документации...")
        
        required_docs = {
            'docs/01-getting-started/README.md': 'Getting started index',
            'docs/01-getting-started/installation.md': 'Installation guide',
            'docs/01-getting-started/quickstart.md': 'Quick start',
            'docs/02-architecture/ARCHITECTURE_OVERVIEW.md': 'Architecture overview',
            'FAQ.md': 'FAQ',
            'TROUBLESHOOTING.md': 'Troubleshooting',
            'SECURITY.md': 'Security policy',
        }
        
        for file, desc in required_docs.items():
            if os.path.exists(file):
                self.stats[f'docs_{desc.replace(" ", "_")}'] = 1
            else:
                self.critical_issues.append(f"MISSING {desc}: {file}")
    
    def check_3_source_code_structure(self):
        """3. Проверка структуры исходного кода"""
        print("[3/15] Структура исходного кода...")
        
        required_dirs = {
            'src/': 'Main source code',
            'src/api/': 'API routes',
            'src/ai/': 'AI services',
            'src/telegram/': 'Telegram bot',
            'tests/': 'Tests',
        }
        
        for dir, desc in required_dirs.items():
            if os.path.exists(dir):
                self.stats[f'src_{desc.replace(" ", "_")}'] = 1
            else:
                self.warnings.append(f"Missing {desc}: {dir}")
    
    def check_4_dependencies(self):
        """4. Проверка зависимостей"""
        print("[4/15] Python зависимости...")
        
        req_files = [
            'requirements.txt',
            'requirements-telegram.txt',
            'requirements-dev.txt',
        ]
        
        for req_file in req_files:
            if os.path.exists(req_file):
                with open(req_file, 'r', encoding='utf-8') as f:
                    lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
                    self.stats[f'deps_in_{req_file}'] = len(lines)
            else:
                if req_file == 'requirements.txt':
                    self.critical_issues.append(f"MISSING critical: {req_file}")
                else:
                    self.warnings.append(f"Missing optional: {req_file}")
    
    def check_5_docker_configuration(self):
        """5. Проверка Docker конфигурации"""
        print("[5/15] Docker конфигурация...")
        
        docker_files = [
            'docker-compose.yml',
            'docker-compose.stage1.yml',
            'docker-compose.mvp.yml',
        ]
        
        for dc_file in docker_files:
            if os.path.exists(dc_file):
                try:
                    with open(dc_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if 'services:' not in content:
                        self.critical_issues.append(f"{dc_file}: Missing 'services:' - INVALID")
                    else:
                        services = re.findall(r'^  (\w+):', content, re.MULTILINE)
                        self.stats[f'services_in_{dc_file}'] = len(services)
                        
                except Exception as e:
                    self.critical_issues.append(f"{dc_file}: Cannot parse - {e}")
            else:
                if dc_file == 'docker-compose.yml':
                    self.critical_issues.append(f"MISSING critical: {dc_file}")
    
    def check_6_env_configuration(self):
        """6. Проверка конфигурации окружения"""
        print("[6/15] Environment configuration...")
        
        if not os.path.exists('env.example'):
            self.critical_issues.append("MISSING env.example - users cannot configure!")
            return
        
        with open('env.example', 'r', encoding='utf-8') as f:
            env_content = f.read()
        
        critical_vars = [
            'TELEGRAM_BOT_TOKEN',
            'POSTGRES_PASSWORD',
            'DATABASE_URL',
        ]
        
        for var in critical_vars:
            if var in env_content:
                self.stats[f'env_var_{var}'] = 1
            else:
                self.warnings.append(f"env.example: Missing {var}")
        
        env_vars = re.findall(r'^([A-Z_]+)=', env_content, re.MULTILINE)
        self.stats['total_env_vars'] = len(env_vars)
    
    def check_7_gitignore_safety(self):
        """7. Проверка безопасности .gitignore"""
        print("[7/15] .gitignore безопасность...")
        
        if not os.path.exists('.gitignore'):
            self.critical_issues.append("MISSING .gitignore - secrets may be exposed!")
            return
        
        with open('.gitignore', 'r', encoding='utf-8') as f:
            gitignore = f.read()
        
        required_patterns = [
            '.env',
            '*.log',
            '__pycache__',
            '*.pyc',
            '*.key',
            '*.pem',
        ]
        
        for pattern in required_patterns:
            if pattern in gitignore:
                self.stats[f'gitignore_{pattern}'] = 1
            else:
                self.warnings.append(f".gitignore: Missing {pattern}")
    
    def check_8_secrets_not_committed(self):
        """8. Проверка что секреты не закоммичены"""
        print("[8/15] Проверка секретов в git...")
        
        result = os.popen('git ls-files .env 2>&1').read()
        if '.env' in result and 'env.example' not in result:
            self.critical_issues.append("SECURITY: .env file is tracked in git!")
        else:
            self.info.append("✓ .env не в git (безопасно)")
    
    def check_9_database_configs(self):
        """9. Проверка конфигураций БД"""
        print("[9/15] Database configurations...")
        
        if os.path.exists('db/init'):
            init_files = list(Path('db/init').glob('*.sql'))
            self.stats['db_init_scripts'] = len(init_files)
        
        if os.path.exists('db/migrations'):
            migrations = list(Path('db/migrations').glob('*.sql'))
            self.stats['db_migrations'] = len(migrations)
    
    def check_10_api_endpoints(self):
        """10. Проверка API endpoints"""
        print("[10/15] API endpoints...")
        
        api_dir = 'src/api'
        if os.path.exists(api_dir):
            api_files = list(Path(api_dir).glob('*.py'))
            self.stats['api_files'] = len(api_files)
    
    def check_11_tests_exist(self):
        """11. Проверка наличия тестов"""
        print("[11/15] Тесты...")
        
        if os.path.exists('tests/'):
            test_files = list(Path('tests').rglob('test_*.py'))
            self.stats['test_files'] = len(test_files)
            
            if len(test_files) == 0:
                self.warnings.append("tests/ exists but no test_*.py files found")
        else:
            self.warnings.append("Missing tests/ directory")
    
    def check_12_ci_cd(self):
        """12. Проверка CI/CD конфигурации"""
        print("[12/15] CI/CD конфигурация...")
        
        if os.path.exists('.github/workflows/'):
            workflows = list(Path('.github/workflows/').glob('*.yml'))
            self.stats['github_workflows'] = len(workflows)
            self.info.append(f"✓ GitHub Actions: {len(workflows)} workflows")
        else:
            self.warnings.append("No CI/CD configuration found")
    
    def check_13_dockerfile_exists(self):
        """13. Проверка Dockerfiles"""
        print("[13/15] Dockerfiles...")
        
        dockerfiles = list(Path('.').glob('Dockerfile*'))
        dockerfiles.extend(list(Path('./docker').glob('Dockerfile*')) if os.path.exists('docker') else [])
        
        self.stats['dockerfiles'] = len(dockerfiles)
        
        if len(dockerfiles) > 0:
            self.info.append(f"✓ Found {len(dockerfiles)} Dockerfiles")
    
    def check_14_readme_quality(self):
        """14. Проверка качества README"""
        print("[14/15] Качество README.md...")
        
        if not os.path.exists('README.md'):
            self.critical_issues.append("CRITICAL: README.md missing!")
            return
        
        with open('README.md', 'r', encoding='utf-8') as f:
            readme = f.read()
        
        required_sections = {
            'Installation': ['install', 'установ', 'quick start', 'быстрый старт'],
            'Usage': ['usage', 'использование', 'how to', 'как использовать'],
            'Features': ['features', 'возможности', 'функции'],
            'Documentation': ['documentation', 'документация', 'docs'],
            'License': ['license', 'лицензия'],
        }
        
        readme_lower = readme.lower()
        
        for section, keywords in required_sections.items():
            found = any(kw in readme_lower for kw in keywords)
            if found:
                self.stats[f'readme_section_{section}'] = 1
            else:
                self.warnings.append(f"README.md: Possibly missing {section} section")
        
        code_blocks = len(re.findall(r'```', readme)) // 2
        self.stats['readme_code_blocks'] = code_blocks
    
    def check_15_link_validity(self):
        """15. Финальная проверка ссылок"""
        print("[15/15] Финальная проверка ссылок...")
        
        critical_files = ['README.md', 'QUICK_START.md', 'FAQ.md', 'TROUBLESHOOTING.md']
        
        total_links = 0
        broken_links = 0
        
        for file in critical_files:
            if not os.path.exists(file):
                continue
            
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            links = re.findall(r'\]\(([^)]+)\)', content)
            
            for link in links:
                total_links += 1
                if link.startswith('http') or link.startswith('#'):
                    continue
                
                link_path = link.split('#')[0]
                if link_path and not os.path.exists(link_path):
                    broken_links += 1
        
        self.stats['critical_files_total_links'] = total_links
        self.stats['critical_files_broken_links'] = broken_links
        
        if broken_links > 0:
            self.warnings.append(f"Found {broken_links} potentially broken links in critical files")
    
    def generate_report(self, output_file):
        """Генерация итогового отчета"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("КОМПЛЕКСНЫЙ АУДИТ ПРОЕКТА v2.0\n")
            f.write("Дата: 7 ноября 2025\n")
            f.write("="*70 + "\n\n")
            
            if self.critical_issues:
                f.write("КРИТИЧНЫЕ ПРОБЛЕМЫ:\n")
                f.write("-"*70 + "\n")
                for i, issue in enumerate(self.critical_issues, 1):
                    f.write(f"{i}. {issue}\n")
                f.write(f"\nИтого критичных: {len(self.critical_issues)}\n\n")
            else:
                f.write("✓ КРИТИЧНЫХ ПРОБЛЕМ НЕТ\n\n")
            
            if self.warnings:
                f.write("ПРЕДУПРЕЖДЕНИЯ:\n")
                f.write("-"*70 + "\n")
                for i, warning in enumerate(self.warnings, 1):
                    f.write(f"{i}. {warning}\n")
                f.write(f"\nИтого предупреждений: {len(self.warnings)}\n\n")
            
            if self.info:
                f.write("ЧТО ХОРОШО:\n")
                f.write("-"*70 + "\n")
                for info in self.info[:20]:
                    f.write(f"  {info}\n")
                if len(self.info) > 20:
                    f.write(f"  ... и еще {len(self.info) - 20}\n")
                f.write("\n")
            
            f.write("СТАТИСТИКА ПРОЕКТА:\n")
            f.write("-"*70 + "\n")
            for key, value in sorted(self.stats.items()):
                f.write(f"  {key}: {value}\n")
            f.write("\n")
            
            f.write("ИТОГОВАЯ ОЦЕНКА:\n")
            f.write("-"*70 + "\n")
            
            critical = len(self.critical_issues)
            warnings = len(self.warnings)
            
            if critical == 0 and warnings == 0:
                grade = "A+ (Perfect)"
                verdict = "Проект в идеальном состоянии"
            elif critical == 0 and warnings <= 3:
                grade = "A (Excellent)"
                verdict = "Отличное качество, минимальные замечания"
            elif critical == 0 and warnings <= 10:
                grade = "A- (Very Good)"
                verdict = "Очень хорошо, есть что улучшить"
            elif critical <= 2 and warnings <= 15:
                grade = "B+ (Good)"
                verdict = "Хорошее качество, требуется внимание"
            elif critical <= 5:
                grade = "B (Satisfactory)"
                verdict = "Удовлетворительно, нужны исправления"
            else:
                grade = "C-F (Needs Work)"
                verdict = "Требует серьезной доработки"
            
            f.write(f"Grade: {grade}\n")
            f.write(f"Вердикт: {verdict}\n\n")
            f.write(f"Критичных проблем: {critical}\n")
            f.write(f"Предупреждений: {warnings}\n")
            f.write(f"Сильных сторон: {len(self.info)}\n")

def main():
    auditor = ComprehensiveAuditor()
    
    print("\n" + "="*70)
    print("КОМПЛЕКСНЫЙ АУДИТ ВСЕГО ПРОЕКТА v2.0")
    print("С учетом всех уроков и промахов")
    print("="*70 + "\n")
    
    auditor.check_1_essential_files()
    auditor.check_2_documentation_structure()
    auditor.check_3_source_code_structure()
    auditor.check_4_dependencies()
    auditor.check_5_docker_configuration()
    auditor.check_6_env_configuration()
    auditor.check_7_gitignore_safety()
    auditor.check_8_secrets_not_committed()
    auditor.check_9_database_configs()
    auditor.check_10_api_endpoints()
    auditor.check_11_tests_exist()
    auditor.check_12_ci_cd()
    auditor.check_13_dockerfile_exists()
    auditor.check_14_readme_quality()
    auditor.check_15_link_validity()
    
    output = 'COMPREHENSIVE_AUDIT_FINAL.txt'
    auditor.generate_report(output)
    
    print("\n" + "="*70)
    print(f"Отчет: {output}")
    print(f"\nКритичных проблем: {len(auditor.critical_issues)}")
    print(f"Предупреждений: {len(auditor.warnings)}")
    
    if len(auditor.critical_issues) == 0:
        print("\n[OK] КРИТИЧНЫХ ПРОБЛЕМ НЕТ")
    else:
        print(f"\n[FAIL] Найдено {len(auditor.critical_issues)} критичных проблем")

if __name__ == '__main__':
    main()

