#!/usr/bin/env python3
"""
Fix parsing errors (E0001) - indentation issues.
"""

import json
import subprocess
from pathlib import Path
from collections import defaultdict

PYLINT_RESULTS = Path("c:/1cAI/pylint_results_after_fixes.json")
SRC_DIR = Path("c:/1cAI/src")

def get_parsing_errors():
    """Get all parsing errors from pylint results."""
    with open(PYLINT_RESULTS, 'r', encoding='utf-8-sig') as f:
        results = json.load(f)
    
    parsing_errors = []
    for issue in results:
        if issue.get('message-id') == 'E0001':
            parsing_errors.append({
                'file': issue.get('path'),
                'line': issue.get('line'),
                'message': issue.get('message'),
            })
    
    return parsing_errors

def fix_file_with_autopep8(filepath):
    """Try to fix file with autopep8 aggressive mode."""
    try:
        subprocess.run(
            ['autopep8', '--in-place', '--aggressive', '--aggressive', str(filepath)],
            check=True,
            capture_output=True
        )
        return True
    except Exception as e:
        print(f"  ❌ autopep8 failed: {e}")
        return False

def main():
    """Main entry point."""
    print("=" * 70)
    print("🔧 FIXING PARSING ERRORS (E0001)")
    print("=" * 70)
    print()
    
    # Get parsing errors
    errors = get_parsing_errors()
    print(f"Found {len(errors)} parsing errors")
    print()
    
    # Group by file
    files_with_errors = defaultdict(list)
    for error in errors:
        files_with_errors[error['file']].append(error)
    
    print(f"Affected files: {len(files_with_errors)}")
    print()
    
    # Fix each file
    fixed_count = 0
    for filepath, file_errors in sorted(files_with_errors.items(), key=lambda x: -len(x[1])):
        print(f"📄 {Path(filepath).name} ({len(file_errors)} errors)")
        
        full_path = SRC_DIR / filepath if not Path(filepath).is_absolute() else Path(filepath)
        
        if fix_file_with_autopep8(full_path):
            print(f"  ✅ Fixed with autopep8")
            fixed_count += 1
        else:
            print(f"  ⚠️ Manual fix required")
            # Show first error
            if file_errors:
                print(f"     Line {file_errors[0]['line']}: {file_errors[0]['message'][:60]}")
    
    print()
    print("=" * 70)
    print(f"✅ Attempted to fix {fixed_count}/{len(files_with_errors)} files")
    print("=" * 70)
    print()
    print("🔍 Re-run pylint to verify fixes")

if __name__ == "__main__":
    main()
