
"""
Automated Fix Script for Code Review Issues
Автоматическое исправление найденных проблем
"""

import os
import re


def fix_get_db_pool_implementations():
    """Fix missing get_db_pool() implementations"""
    
    files_to_fix = [
        'src/api/admin_dashboard_api.py',
        'src/api/billing_webhooks.py'
    ]
    
    replacement = '''
def get_db_pool():
    """Dependency injection для DB pool"""
    from src.database import get_pool
    return get_pool()
'''
    
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace "pass" or "# TODO" in get_db_pool
            pattern = r'def get_db_pool\(\):[^\n]*\n\s*(pass|# TODO:[^\n]*)'
            if re.search(pattern, content):
                content = re.sub(pattern, replacement.strip(), content)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"✓ Fixed get_db_pool() in {file_path}")

def move_imports_to_top():
    """Move conditional imports to module level"""
    
    # Example: src/api/test_generation.py
    file_path = 'src/api/test_generation.py'
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Find conditional imports
        imports_to_move = []
        fixed_lines = []
        
        for i, line in enumerate(lines):
            if 'from src.api.test_generation_ts import' in line:
                # Mark for removal and add to imports
                imports_to_move.append(line.strip())
                fixed_lines.append(f"# Moved to top: {line}")
            else:
                fixed_lines.append(line)
        
        if imports_to_move:
            # Add imports after other imports
            insert_index = 0
            for i, line in enumerate(fixed_lines):
                if line.startswith('import ') or line.startswith('from '):
                    insert_index = i + 1
            
            for imp in imports_to_move:
                fixed_lines.insert(insert_index, imp + '\n')
                insert_index += 1
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(fixed_lines)
            
            print(f"✓ Moved imports to top in {file_path}")

def fix_production_check():
    """Fix production environment detection"""
    
    file_path = 'src/main.py'
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace weak production check
        old_pattern = r'is_production\s*=\s*settings\.openai_api_key\s*!=\s*"test"'
        new_code = 'is_production = settings.environment == "production"'
        
        if re.search(old_pattern, content):
            content = re.sub(old_pattern, new_code, content)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✓ Fixed production check in {file_path}")

def add_missing_type_hints():
    """Add type hints to functions missing them"""
    
    # This is complex - would need AST parsing
    # For now, just report
    print("ℹ Manual task: Add type hints to functions")

def extract_magic_numbers():
    """Extract magic numbers to constants"""
    
    # Example patterns to find
    patterns = [
        r'sleep\((\d+\.?\d*)\)',
        r'range\((\d+)\)',
        r'timeout[=\s]+(\d+)',
    ]
    
    print("ℹ Manual task: Extract magic numbers to constants")

def standardize_error_messages():
    """Standardize error messages to single language"""
    
    print("ℹ Manual task: Choose English or Russian for all error messages")

def main():
    """Run all fixes"""
    
    print("="*60)
    print("  AUTOMATED CODE FIXES")
    print("="*60)
    print()
    
    print("[1/6] Fixing get_db_pool implementations...")
    fix_get_db_pool_implementations()
    print()
    
    print("[2/6] Moving imports to module level...")
    move_imports_to_top()
    print()
    
    print("[3/6] Fixing production environment check...")
    fix_production_check()
    print()
    
    print("[4/6] Type hints...")
    add_missing_type_hints()
    print()
    
    print("[5/6] Magic numbers...")
    extract_magic_numbers()
    print()
    
    print("[6/6] Error message standardization...")
    standardize_error_messages()
    print()
    
    print("="*60)
    print("  FIXES COMPLETE")
    print("="*60)
    print()
    print("✓ Automated fixes applied")
    print("ℹ Manual tasks identified")
    print()
    print("Next: Review changes and run tests")
    print()

if __name__ == '__main__':
    main()


