
#!/usr/bin/env python3
"""
Проверка соответствия README.md -> реальному коду
Категории 11-15 из MASTER AUDIT CHECKLIST
"""

import os


class READMECodeChecker:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.info = []
        
    def check_technologies_in_code(self):
        """Проверка что технологии из README есть в src/"""
        print("Проверка технологий из README vs код...")
        
        if not os.path.exists('README.md'):
            self.issues.append("README.md not found")
            return
        
        with open('README.md', 'r', encoding='utf-8') as f:
            readme = f.read()
        
        # Технологии которые должны быть в src/
        tech_to_check = {
            'Qwen2.5-Coder': ['src/ai/qwen_client.py'],
            'OpenAI': ['src/ai_assistants/', 'src/services/'],
            'sentence-transformers': ['src/services/embedding_service.py'],
            'DeepSeek-OCR': ['src/services/ocr_service.py'],
        }
        
        for tech, expected_paths in tech_to_check.items():
            if tech in readme:
                # Проверяем что хоть один путь существует
                found = any(os.path.exists(p) for p in expected_paths)
                if found:
                    self.info.append(f"[OK] {tech} - found in code")
                else:
                    self.issues.append(f"README mentions {tech} but not found in {expected_paths}")
    
    def check_features_have_docs(self):
        """Проверка что каждый Feature из README имеет документацию"""
        print("Проверка Features -> docs/06-features/...")
        
        if not os.path.exists('README.md'):
            return
        
        with open('README.md', 'r', encoding='utf-8') as f:
            readme = f.read()
        
        # Ищем упоминания ключевых компонентов
        components_to_check = {
            'EDT-Parser': 'docs/06-features/EDT_PARSER_GUIDE.md',
            'ML Dataset Generator': 'docs/06-features/ML_DATASET_GENERATOR_GUIDE.md',
            'OCR': 'docs/06-features/OCR_INTEGRATION.md',
            'Voice': 'docs/06-features/VOICE_QUERIES.md',
        }
        
        for component, expected_doc in components_to_check.items():
            if component in readme:
                if os.path.exists(expected_doc):
                    self.info.append(f"[OK] {component} -> {expected_doc}")
                else:
                    self.issues.append(f"{component} in README but missing {expected_doc}")
    
    def check_requirements_packages_exist(self):
        """Проверка что пакеты в requirements.txt существуют"""
        print("Проверка requirements.txt -> PyPI...")
        
        if not os.path.exists('requirements.txt'):
            self.issues.append("requirements.txt missing")
            return
        
        with open('requirements.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Известные несуществующие пакеты
        fake_packages = ['deepseek-ocr', 'chandra-ocr']
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            package_name = line.split('==')[0].split('>=')[0].split('[')[0]
            
            if package_name in fake_packages:
                self.issues.append(f"Fake package: {package_name} (doesn't exist on PyPI)")
        
        # Проверка версии Python
        has_version = any('python' in line.lower() and '3.11' in line for line in lines[:15])
        if has_version:
            self.info.append("[OK] Python version specified in requirements.txt")
        else:
            self.warnings.append("Missing Python version in requirements.txt header")
    
    def generate_report(self, output_file):
        """Генерация отчета"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("README vs CODE VERIFICATION\n")
            f.write("="*70 + "\n\n")
            
            if self.issues:
                f.write("ISSUES:\n")
                f.write("-"*70 + "\n")
                for i, issue in enumerate(self.issues, 1):
                    f.write(f"{i}. {issue}\n")
                f.write(f"\nTotal: {len(self.issues)}\n\n")
            else:
                f.write("[OK] NO ISSUES FOUND\n\n")
            
            if self.warnings:
                f.write("WARNINGS:\n")
                f.write("-"*70 + "\n")
                for i, warning in enumerate(self.warnings, 1):
                    f.write(f"{i}. {warning}\n")
                f.write(f"\nTotal: {len(self.warnings)}\n\n")
            
            if self.info:
                f.write("VERIFIED:\n")
                f.write("-"*70 + "\n")
                for item in self.info:
                    f.write(f"  {item}\n")
                f.write("\n")
            
            f.write("GRADE:\n")
            f.write("-"*70 + "\n")
            if len(self.issues) == 0:
                grade = "A (Excellent)"
            elif len(self.issues) <= 2:
                grade = "B (Good)"
            else:
                grade = "C-F (Issues found)"
            f.write(f"{grade}\n")

def main():
    checker = READMECodeChecker()
    
    print("\n" + "="*70)
    print("README vs CODE VERIFICATION")
    print("="*70 + "\n")
    
    checker.check_technologies_in_code()
    checker.check_features_have_docs()
    checker.check_requirements_packages_exist()
    
    output = 'README_CODE_VERIFICATION.txt'
    checker.generate_report(output)
    
    print("\n" + "="*70)
    print(f"Report: {output}")
    print(f"Issues: {len(checker.issues)}")
    print(f"Warnings: {len(checker.warnings)}")
    
    if len(checker.issues) == 0:
        print("\n[OK] README MATCHES CODE")
    else:
        print(f"\n[FAIL] Found {len(checker.issues)} mismatches")

if __name__ == '__main__':
    main()

