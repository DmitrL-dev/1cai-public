#!/usr/bin/env python3
"""
AI-Powered Automatic Code Fixer
Uses AST analysis and intelligent pattern matching to fix parsing errors.
"""

import ast
import re
import json
from pathlib import Path

PYLINT_RESULTS = Path("c:/1cAI/pylint_results_after_fixes.json")
SRC_DIR = Path("c:/1cAI/src")

stats = {
    'files_processed': 0,
    'files_fixed': 0,
    'files_failed': 0,
}

def fix_indentation_errors(content: str) -> str:
    """Fix common indentation errors."""
    lines = content.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines):
        # Fix: empty try/except/if/for/while blocks
        if line.strip().endswith(':'):
            # Check if next line is empty or has wrong indentation
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if not next_line.strip() or not next_line.startswith(' '):
                    # Add pass statement
                    indent = len(line) - len(line.lstrip())
                    fixed_lines.append(line)
                    fixed_lines.append(' ' * (indent + 4) + 'pass')
                    continue
        
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

def fix_common_syntax_errors(content: str) -> str:
    """Fix common syntax errors."""
    
    # Fix: missing colons
    content = re.sub(r'(if|elif|else|try|except|finally|for|while|def|class)\s+([^:]+)$', 
                     r'\1 \2:', content, flags=re.MULTILINE)
    
    # Fix: trailing commas in wrong places
    content = re.sub(r',\s*\)', ')', content)
    content = re.sub(r',\s*\]', ']', content)
    content = re.sub(r',\s*\}', '}', content)
    
    # Fix: missing parentheses in print statements (Python 2 → 3)
    content = re.sub(r'^(\s*)print\s+([^(].*?)$', r'\1print(\2)', content, flags=re.MULTILINE)
    
    return content

def fix_import_errors(content: str) -> str:
    """Fix common import errors."""
    
    # Fix: duplicate src/ in imports
    content = re.sub(r'from src\.src\.', 'from src.', content)
    content = re.sub(r'import src\.src\.', 'import src.', content)
    
    return content

def smart_fix_file(filepath: Path) -> bool:
    """Apply intelligent fixes to a file."""
    try:
        # Read file
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # Apply fixes in order
        content = fix_import_errors(content)
        content = fix_common_syntax_errors(content)
        content = fix_indentation_errors(content)
        
        # Try to parse as Python to verify
        try:
            ast.parse(content)
            # Success! File is now valid Python
            if content != original:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                return True
            return False
        except SyntaxError as e:
            # Still has errors, try more aggressive fixes
            content = aggressive_fix(content, e)
            
            # Try again
            try:
                ast.parse(content)
                if content != original:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    return True
            except:
                pass
            
            return False
    
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def aggressive_fix(content: str, error: SyntaxError) -> str:
    """Apply aggressive fixes based on syntax error."""
    lines = content.split('\n')
    
    if error.lineno:
        line_idx = error.lineno - 1
        
        # Fix specific error types
        if 'expected an indented block' in str(error):
            # Add pass statement
            if line_idx + 1 < len(lines):
                indent = len(lines[line_idx]) - len(lines[line_idx].lstrip())
                lines.insert(line_idx + 1, ' ' * (indent + 4) + 'pass')
        
        elif 'invalid syntax' in str(error):
            # Try to fix the problematic line
            line = lines[line_idx]
            
            # Common fixes
            if line.strip() and not line.strip().endswith(':') and line.strip().startswith(('if', 'elif', 'else', 'try', 'except', 'for', 'while', 'def', 'class')):
                lines[line_idx] = line + ':'
    
    return '\n'.join(lines)

def main():
    """Main entry point."""
    print("=" * 70)
    print("AI-POWERED AUTOMATIC CODE FIXER")
    print("=" * 70)
    print()
    
    # Get parsing errors
    with open(PYLINT_RESULTS, 'r', encoding='utf-8-sig') as f:
        results = json.load(f)
    
    parsing_errors = [r for r in results if r.get('message-id') == 'E0001']
    
    # Get unique files
    files_with_errors = set()
    for error in parsing_errors:
        filepath = error.get('path', '')
        if filepath.startswith('src/') or filepath.startswith('src\\'):
            filepath = filepath[4:]
        files_with_errors.add(filepath)
    
    print(f"Found {len(files_with_errors)} files with parsing errors")
    print()
    
    # Fix each file
    for filepath in sorted(files_with_errors):
        full_path = SRC_DIR / filepath
        
        if not full_path.exists():
            continue
        
        print(f"Fixing: {filepath}")
        
        if smart_fix_file(full_path):
            print(f"  ✅ Fixed")
            stats['files_fixed'] += 1
        else:
            print(f"  ❌ Could not fix automatically")
            stats['files_failed'] += 1
        
        stats['files_processed'] += 1
    
    print()
    print("=" * 70)
    print("STATISTICS")
    print("=" * 70)
    print(f"Files processed: {stats['files_processed']}")
    print(f"Files fixed:     {stats['files_fixed']}")
    print(f"Files failed:    {stats['files_failed']}")
    print(f"Success rate:    {stats['files_fixed'] / stats['files_processed'] * 100:.1f}%")
    print("=" * 70)

if __name__ == "__main__":
    main()
