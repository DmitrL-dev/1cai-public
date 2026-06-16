#!/usr/bin/env python3
"""
Compare pylint results before and after fixes.
"""

import json
from pathlib import Path

BEFORE = Path("c:/1cAI/pylint_results_v2.json")
AFTER = Path("c:/1cAI/pylint_results_after_fixes.json")
OUTPUT = Path("c:/1cAI/PYLINT_COMPARISON.txt")

def compare_results():
    """Compare before and after results."""
    
    # Read results
    with open(BEFORE, 'r', encoding='utf-8-sig') as f:
        before = json.load(f)
    
    with open(AFTER, 'r', encoding='utf-8-sig') as f:
        after = json.load(f)
    
    before_count = len(before)
    after_count = len(after)
    fixed_count = before_count - after_count
    
    # Group by type
    before_types = {}
    after_types = {}
    
    for issue in before:
        issue_type = issue.get('type', 'unknown')
        before_types[issue_type] = before_types.get(issue_type, 0) + 1
    
    for issue in after:
        issue_type = issue.get('type', 'unknown')
        after_types[issue_type] = after_types.get(issue_type, 0) + 1
    
    # Write comparison
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("PYLINT RESULTS COMPARISON\n")
        f.write("=" * 70 + "\n\n")
        
        f.write(f"Before:  {before_count} issues\n")
        f.write(f"After:   {after_count} issues\n")
        f.write(f"Fixed:   {fixed_count} issues ({(fixed_count/before_count*100):.1f}%)\n\n")
        
        f.write("By Type:\n")
        f.write("-" * 70 + "\n")
        all_types = set(before_types.keys()) | set(after_types.keys())
        for issue_type in sorted(all_types):
            before_val = before_types.get(issue_type, 0)
            after_val = after_types.get(issue_type, 0)
            diff = before_val - after_val
            f.write(f"{issue_type:15s}: {before_val:4d} → {after_val:4d} ({diff:+4d})\n")
        
        f.write("\n" + "=" * 70 + "\n")
    
    print(f"✅ Comparison saved to: {OUTPUT}")
    print(f"📊 Fixed: {fixed_count}/{before_count} issues ({(fixed_count/before_count*100):.1f}%)")
    print(f"📊 Remaining: {after_count} issues")

if __name__ == "__main__":
    compare_results()
