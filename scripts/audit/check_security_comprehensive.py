
#!/usr/bin/env python3
"""
SECURITY AUDIT SCRIPT
Проверка безопасности проекта по всем критичным векторам
"""

import os
import re
from pathlib import Path


class SecurityAuditor:
    def __init__(self):
        self.critical = []
        self.high = []
        self.medium = []
        self.info = []
        
    def check_hardcoded_secrets(self):
        """1. Поиск хардкодных секретов"""
        print("[1/8] Поиск хардкодных секретов...")
        
        secret_patterns = [
            (r'sk-[a-zA-Z0-9]{48}', 'OpenAI API Key'),
            (r'ghp_[a-zA-Z0-9]{36}', 'GitHub Token'),
            (r'OPENAI_API_KEY\s*=\s*["\'][^"\']+["\']', 'Hardcoded OpenAI key'),
            (r'REDIS_PASSWORD\s*=\s*["\'][^"\']+["\']', 'Hardcoded Redis password'),
            (r'POSTGRES_PASSWORD\s*=\s*["\'][^"\']+["\']', 'Hardcoded Postgres password'),
        ]
        
        python_files = list(Path('src').rglob('*.py')) if os.path.exists('src') else []
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for pattern, desc in secret_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        # Проверяем что это не в комментарии/примере
                        for match in matches:
                            if 'example' not in match.lower() and 'your_' not in match.lower():
                                self.critical.append(
                                    f"HARDCODED SECRET: {desc} in {py_file}"
                                )
            except:
                pass
        
        if not self.critical:
            self.info.append("✓ No hardcoded secrets found")
    
    def check_cors_configuration(self):
        """2. Проверка CORS конфигурации"""
        print("[2/8] Проверка CORS...")
        
        python_files = list(Path('src').rglob('*.py')) if os.path.exists('src') else []
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Ищем опасные CORS конфигурации
                if 'allow_origins=["*"]' in content or "allow_origins=['*']" in content:
                    self.high.append(
                        f"CORS WILDCARD: {py_file} - allows any origin (CSRF risk)"
                    )
            except:
                pass
        
        if not self.high:
            self.info.append("✓ No CORS wildcard found")
    
    def check_rate_limiting(self):
        """3. Проверка rate limiting на критичных endpoints"""
        print("[3/8] Проверка rate limiting...")
        
        api_files = list(Path('src/api').rglob('*.py')) if os.path.exists('src/api') else []
        
        for api_file in api_files:
            try:
                with open(api_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Ищем критичные endpoints без rate limiting
                critical_endpoints = [
                    '@router.post("/generate")',
                    '@router.post("/create")',
                    '@app.post("/generate")',
                ]
                
                for endpoint in critical_endpoints:
                    if endpoint in content:
                        # Проверяем есть ли limiter
                        if '@limiter.limit' not in content and 'RateLimiter' not in content:
                            self.high.append(
                                f"NO RATE LIMIT: {api_file} has {endpoint} without rate limiting"
                            )
            except:
                pass
    
    def check_sql_injection(self):
        """4. Проверка SQL injection уязвимостей"""
        print("[4/8] Проверка SQL injection...")
        
        python_files = list(Path('src').rglob('*.py')) if os.path.exists('src') else []
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Ищем опасные паттерны
                if re.search(r'execute\s*\(\s*f["\']', content):
                    self.critical.append(
                        f"SQL INJECTION RISK: {py_file} uses f-string in execute()"
                    )
                # Проверяем % formatting - но не параметризованные запросы
                # execute("... %s", (param,)) - БЕЗОПАСНО
                # execute("... %s" % param) - ОПАСНО
                if re.search(r'execute\s*\([^)]*%.*%[^)]*\)', content):
                    # Дополнительная проверка что это не параметризация
                    matches = re.findall(r'execute\s*\([^)]+\)', content)
                    for match in matches:
                        if '%' in match and '(' not in match[match.find('%'):]:
                            self.high.append(
                                f"SQL INJECTION RISK: {py_file} uses % formatting in execute()"
                            )
                            break
            except:
                pass
        
        if not self.critical and len([h for h in self.high if 'SQL' in h]) == 0:
            self.info.append("✓ No SQL injection patterns found")
    
    def check_env_in_gitignore(self):
        """5. Проверка .gitignore"""
        print("[5/8] Проверка .gitignore...")
        
        if not os.path.exists('.gitignore'):
            self.critical.append("MISSING .gitignore - secrets may be exposed!")
            return
        
        with open('.gitignore', 'r', encoding='utf-8') as f:
            gitignore = f.read()
        
        required = ['.env', '*.key', '.pem']
        for pattern in required:
            if pattern not in gitignore:
                self.high.append(f".gitignore missing: {pattern}")
        
        if not any('.env' not in h for h in self.high):
            self.info.append("✓ .gitignore protects secrets")
    
    def check_requirements_validity(self):
        """6. Проверка валидности requirements.txt"""
        print("[6/8] Проверка requirements.txt...")
        
        if not os.path.exists('requirements.txt'):
            self.critical.append("MISSING requirements.txt")
            return
        
        with open('requirements.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Проверяем Python version
        has_python_version = any('python' in line.lower() and '3.11' in line for line in lines[:10])
        if not has_python_version:
            self.medium.append("requirements.txt: Missing Python version requirement")
        
        # Проверяем подозрительные пакеты
        suspicious = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                # Проверяем на несуществующие пакеты (только если это реальная установка)
                if line.startswith('deepseek-ocr'):
                    suspicious.append("deepseek-ocr (package doesn't exist!)")
                if line.startswith('chandra-ocr'):
                    suspicious.append("chandra-ocr (package doesn't exist!)")
        
        if suspicious:
            self.critical.append(
                f"requirements.txt: Non-existent packages: {', '.join(suspicious)}"
            )
        else:
            self.info.append("✓ No obviously fake packages in requirements.txt")
    
    def check_private_data_in_files(self):
        """7. Проверка приватных данных в файлах"""
        print("[7/8] Проверка приватных данных...")
        
        md_files = list(Path('.').glob('*.md'))
        
        private_patterns = [
            (r'C:\\Users\\[^\\]+', 'Windows user path'),
            (r'/Users/[^/]+/', 'Mac user path'),
            (r'/home/[^/]+/', 'Linux user path'),
            (r'Desktop\\', 'Desktop path'),
        ]
        
        for md_file in md_files:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for pattern, desc in private_patterns:
                    if re.search(pattern, content):
                        self.critical.append(
                            f"PRIVATE DATA: {md_file} contains {desc}"
                        )
            except:
                pass
    
    def check_timeout_in_requests(self):
        """8. Проверка timeout в HTTP запросах"""
        print("[8/8] Проверка timeout в requests...")
        
        python_files = list(Path('src').rglob('*.py')) if os.path.exists('src') else []
        
        timeout_issues = 0
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Ищем requests/httpx без timeout
                patterns = [
                    r'requests\.(get|post|put|delete)\([^)]*\)',
                    r'httpx\.(get|post|put|delete)\([^)]*\)',
                    r'aiohttp\..*\.(get|post|put|delete)\([^)]*\)',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, content)
                    for match_text in matches:
                        if 'timeout' not in match_text:
                            timeout_issues += 1
                            if timeout_issues <= 5:  # Показываем первые 5
                                self.medium.append(
                                    f"NO TIMEOUT: {py_file} - external call without timeout"
                                )
            except:
                pass
    
    def generate_report(self, output_file):
        """Генерация отчета"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("SECURITY AUDIT REPORT\n")
            f.write("="*70 + "\n\n")
            
            if self.critical:
                f.write("🔴 CRITICAL ISSUES:\n")
                f.write("-"*70 + "\n")
                for i, issue in enumerate(self.critical, 1):
                    f.write(f"{i}. {issue}\n")
                f.write(f"\nTotal: {len(self.critical)}\n\n")
            
            if self.high:
                f.write("[HIGH] PRIORITY:\n")
                f.write("-"*70 + "\n")
                for i, issue in enumerate(self.high, 1):
                    f.write(f"{i}. {issue}\n")
                f.write(f"\nTotal: {len(self.high)}\n\n")
            
            if self.medium:
                f.write("[MEDIUM] PRIORITY:\n")
                f.write("-"*70 + "\n")
                for i, issue in enumerate(self.medium[:10], 1):
                    f.write(f"{i}. {issue}\n")
                if len(self.medium) > 10:
                    f.write(f"... and {len(self.medium) - 10} more\n")
                f.write(f"\nTotal: {len(self.medium)}\n\n")
            
            if self.info:
                f.write("[GOOD] ITEMS:\n")
                f.write("-"*70 + "\n")
                for item in self.info:
                    f.write(f"  {item}\n")
                f.write("\n")
            
            # Оценка
            f.write("SECURITY GRADE:\n")
            f.write("-"*70 + "\n")
            
            critical = len(self.critical)
            high = len(self.high)
            medium = len(self.medium)
            
            if critical == 0 and high == 0 and medium <= 5:
                grade = "A (Secure)"
            elif critical == 0 and high <= 2 and medium <= 15:
                grade = "B+ (Good, minor issues)"
            elif critical <= 1 and high <= 5:
                grade = "B (Acceptable)"
            else:
                grade = "C-F (Security issues found)"
            
            f.write(f"Grade: {grade}\n")
            f.write(f"Critical: {critical}\n")
            f.write(f"High: {high}\n")
            f.write(f"Medium: {medium}\n")

def main():
    auditor = SecurityAuditor()
    
    print("\n" + "="*70)
    print("SECURITY AUDIT")
    print("="*70 + "\n")
    
    auditor.check_hardcoded_secrets()
    auditor.check_cors_configuration()
    auditor.check_rate_limiting()
    auditor.check_sql_injection()
    auditor.check_env_in_gitignore()
    auditor.check_requirements_validity()
    auditor.check_private_data_in_files()
    auditor.check_timeout_in_requests()
    
    output = 'SECURITY_AUDIT_REPORT.txt'
    auditor.generate_report(output)
    
    print("\n" + "="*70)
    print(f"Report: {output}")
    print(f"\nCritical: {len(auditor.critical)}")
    print(f"High: {len(auditor.high)}")
    print(f"Medium: {len(auditor.medium)}")
    
    if len(auditor.critical) == 0 and len(auditor.high) == 0:
        print("\n[OK] NO CRITICAL SECURITY ISSUES")
    else:
        print(f"\n[FAIL] Found {len(auditor.critical) + len(auditor.high)} security issues")

if __name__ == '__main__':
    main()

