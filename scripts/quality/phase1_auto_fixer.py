#!/usr/bin/env python3
"""
Phase 1: Auto-fixable Issues Fixer
Fixes line length and lazy logging issues.
"""

import re
import subprocess
from pathlib import Path
import json

PYLINT_RESULTS = Path("c:/1cAI/pylint_results_after_fixes.json")
SRC_DIR = Path("c:/1cAI/src")

stats = {
    'line_length_fixed': 0,
    'lazy_logging_fixed': 0,
    'files_processed': 0,
}

def get_issues_by_type(msg_id):
    """Get all issues of a specific type."""
    with open(PYLINT_RESULTS, 'r', encoding='utf-8-sig') as f:
        results = json.load(f)
    
    issues = []
    for issue in results:
        if issue.get('message-id') == msg_id:
            issues.append(issue)
    
    return issues

def fix_line_length():
    """Fix line length issues with black."""
    print("🔧 Fixing line length issues with black...")
    
    try:
        # Run black with line length 88
        result = subprocess.run(
            ['black', str(SRC_DIR), '--line-length', '88', '--skip-string-normalization'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Count reformatted files
            reformatted = result.stderr.count('reformatted')
            stats['line_length_fixed'] = reformatted
            print(f"  ✅ Black reformatted {reformatted} files")
            return True
        else:
            print(f"  ⚠️ Black completed with warnings")
            return True
    except FileNotFoundError:
        print("  ❌ Black not installed")
        return False
    except Exception as e:
        print(f"  ❌ Black failed: {e}")
        return False

def fix_lazy_logging_in_file(filepath):
    """Fix lazy logging in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # Pattern 1: logger.info(f"text {var}")
        # Replace with: logger.info("text %s", var)
        def replace_fstring(match):
            level = match.group(1)
            text = match.group(2)
            
            # Extract variables from f-string
            vars_pattern = r'\{([^}]+)\}'
            variables = re.findall(vars_pattern, text)
            
            # Replace {var} with %s
            new_text = re.sub(vars_pattern, '%s', text)
            
            # Build new logger call
            if variables:
                vars_str = ', '.join(variables)
                return f'logger.{level}("{new_text}", {vars_str})'
            else:
                return f'logger.{level}("{new_text}")'
        
        # Apply replacement
        pattern = r'logger\.(debug|info|warning|error|critical)\(f["\']([^"\']+)["\']\)'
        content = re.sub(pattern, replace_fstring, content)
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
    
    except Exception as e:
        print(f"  ❌ Error processing {filepath.name}: {e}")
        return False

def fix_lazy_logging():
    """Fix lazy logging issues."""
    print("🔧 Fixing lazy logging issues...")
    
    # Get all lazy logging issues
    issues = get_issues_by_type('W1203')
    
    if not issues:
        print("  ℹ️ No lazy logging issues found")
        return
    
    # Group by file
    files_with_issues = {}
    for issue in issues:
        filepath = issue.get('path', '')
        if filepath not in files_with_issues:
            files_with_issues[filepath] = []
        files_with_issues[filepath].append(issue)
    
    print(f"  Found {len(issues)} issues in {len(files_with_issues)} files")
    
    # Fix each file
    fixed_count = 0
    for filepath in files_with_issues.keys():
        # Handle path correctly - remove duplicate src/ if present
        if filepath.startswith('src/') or filepath.startswith('src\\'):
            filepath = filepath[4:]  # Remove 'src/' prefix
        
        full_path = SRC_DIR / filepath
        
        if not full_path.exists():
            print(f"  ⚠️ File not found: {full_path}")
            continue
        
        if fix_lazy_logging_in_file(full_path):
            fixed_count += 1
    
    stats['lazy_logging_fixed'] = fixed_count
    print(f"  ✅ Fixed lazy logging in {fixed_count} files")

def main():
    """Main entry point."""
    print("=" * 70)
    print("🔧 PHASE 1: AUTO-FIXABLE ISSUES")
    print("=" * 70)
    print()
    
    # Fix line length
    fix_line_length()
    print()
    
    # Fix lazy logging
    fix_lazy_logging()
    print()
    
    # Statistics
    print("=" * 70)
    print("📊 STATISTICS")
    print("=" * 70)
    print(f"Line length fixed:   {stats['line_length_fixed']} files")
    print(f"Lazy logging fixed:  {stats['lazy_logging_fixed']} files")
    print("=" * 70)
    print()
    print("✅ Phase 1 complete!")
    print("🔍 Re-run pylint to verify fixes")

if __name__ == "__main__":
    main()
