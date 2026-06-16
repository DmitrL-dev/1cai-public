#!/usr/bin/env python3
"""
Smart Error Pattern Analyzer
Analyzes pylint errors and categorizes them for automated fixing.
"""

import json
from pathlib import Path
from collections import defaultdict

PYLINT_RESULTS = Path("c:/1cAI/pylint_results_after_fixes.json")
OUTPUT_MATRIX = Path("c:/1cAI/ERROR_FIX_MATRIX.txt")

def analyze_errors():
    """Analyze all errors and categorize by pattern."""
    
    # Read results
    with open(PYLINT_RESULTS, 'r', encoding='utf-8-sig') as f:
        results = json.load(f)
    
    # Categorize errors
    categories = {
        'parsing_indentation': [],
        'parsing_syntax': [],
        'import_errors': [],
        'import_not_found': [],
        'function_call_errors': [],
        'unused_arguments': [],
        'unused_imports': [],
        'unused_variables': [],
        'missing_docstrings': [],
        'lazy_logging': [],
        'unnecessary_elif': [],
        'line_too_long': [],
        'trailing_whitespace': [],
        'other': [],
    }
    
    for issue in results:
        msg_id = issue.get('message-id', '')
        msg = issue.get('message', '')
        issue_type = issue.get('type', '')
        
        # Categorize
        if msg_id == 'E0001':
            if 'indent' in msg.lower():
                categories['parsing_indentation'].append(issue)
            else:
                categories['parsing_syntax'].append(issue)
        elif msg_id == 'E0611':
            categories['import_errors'].append(issue)
        elif msg_id == 'E0401':
            categories['import_not_found'].append(issue)
        elif msg_id == 'E1121':
            categories['function_call_errors'].append(issue)
        elif msg_id == 'W0613':
            categories['unused_arguments'].append(issue)
        elif msg_id == 'W0611':
            categories['unused_imports'].append(issue)
        elif msg_id == 'W0612':
            categories['unused_variables'].append(issue)
        elif msg_id == 'C0116':
            categories['missing_docstrings'].append(issue)
        elif msg_id == 'W1203':
            categories['lazy_logging'].append(issue)
        elif msg_id == 'R1705':
            categories['unnecessary_elif'].append(issue)
        elif msg_id == 'C0301':
            categories['line_too_long'].append(issue)
        elif msg_id == 'C0303':
            categories['trailing_whitespace'].append(issue)
        else:
            categories['other'].append(issue)
    
    # Generate fix matrix
    with open(OUTPUT_MATRIX, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("ERROR FIX MATRIX - Systematic Approach\n")
        f.write("=" * 80 + "\n\n")
        
        total = sum(len(v) for v in categories.values())
        f.write(f"Total Issues: {total}\n\n")
        
        # Priority 1: Auto-fixable (Easy)
        f.write("PRIORITY 1: AUTO-FIXABLE (Easy)\n")
        f.write("-" * 80 + "\n")
        auto_fixable = [
            ('trailing_whitespace', 'Trailing whitespace', 'sed/regex'),
            ('line_too_long', 'Line too long', 'black formatter'),
            ('unused_imports', 'Unused imports', 'autoflake'),
            ('lazy_logging', 'Lazy logging', 'regex replacement'),
        ]
        auto_count = 0
        for key, name, tool in auto_fixable:
            count = len(categories[key])
            auto_count += count
            f.write(f"  [{count:3d}] {name:30s} - Tool: {tool}\n")
        f.write(f"\nSubtotal: {auto_count} issues (can be fixed in 10-15 minutes)\n\n")
        
        # Priority 2: Semi-automated (Medium)
        f.write("PRIORITY 2: SEMI-AUTOMATED (Medium)\n")
        f.write("-" * 80 + "\n")
        semi_auto = [
            ('unused_arguments', 'Unused arguments', 'prefix with _'),
            ('unused_variables', 'Unused variables', 'prefix with _ or remove'),
            ('unnecessary_elif', 'Unnecessary elif', 'remove elif'),
            ('missing_docstrings', 'Missing docstrings', 'AI-generate'),
        ]
        semi_count = 0
        for key, name, approach in semi_auto:
            count = len(categories[key])
            semi_count += count
            f.write(f"  [{count:3d}] {name:30s} - Approach: {approach}\n")
        f.write(f"\nSubtotal: {semi_count} issues (can be fixed in 30-60 minutes)\n\n")
        
        # Priority 3: Manual (Hard)
        f.write("PRIORITY 3: MANUAL FIXES (Hard)\n")
        f.write("-" * 80 + "\n")
        manual = [
            ('parsing_indentation', 'Parsing: indentation', 'manual review'),
            ('parsing_syntax', 'Parsing: syntax', 'manual review'),
            ('import_errors', 'Import errors', 'fix import paths'),
            ('import_not_found', 'Import not found', 'add dependencies'),
            ('function_call_errors', 'Function call errors', 'fix signatures'),
        ]
        manual_count = 0
        for key, name, approach in manual:
            count = len(categories[key])
            manual_count += count
            f.write(f"  [{count:3d}] {name:30s} - Approach: {approach}\n")
        f.write(f"\nSubtotal: {manual_count} issues (requires 2-4 hours)\n\n")
        
        # Priority 4: Other
        other_count = len(categories['other'])
        f.write(f"PRIORITY 4: OTHER\n")
        f.write("-" * 80 + "\n")
        f.write(f"  [{other_count:3d}] Other issues - requires analysis\n\n")
        
        # Summary
        f.write("=" * 80 + "\n")
        f.write("EXECUTION PLAN\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Phase 1: Auto-fixable       {auto_count:4d} issues - 15 min\n")
        f.write(f"Phase 2: Semi-automated     {semi_count:4d} issues - 60 min\n")
        f.write(f"Phase 3: Manual fixes       {manual_count:4d} issues - 240 min\n")
        f.write(f"Phase 4: Other              {other_count:4d} issues - TBD\n")
        f.write(f"\nTotal:                      {total:4d} issues\n")
        f.write(f"Estimated time:             ~5-6 hours\n\n")
        
        # Top files needing fixes
        f.write("=" * 80 + "\n")
        f.write("TOP 20 FILES NEEDING FIXES\n")
        f.write("=" * 80 + "\n\n")
        
        file_counts = defaultdict(int)
        for category_issues in categories.values():
            for issue in category_issues:
                filepath = issue.get('path', 'unknown')
                file_counts[filepath] += 1
        
        for filepath, count in sorted(file_counts.items(), key=lambda x: -x[1])[:20]:
            filename = Path(filepath).name
            f.write(f"  [{count:3d}] {filename}\n")
        
        f.write("\n" + "=" * 80 + "\n")
    
    print(f"✅ Analysis complete!")
    print(f"📊 Total issues: {total}")
    print(f"📋 Fix matrix saved to: {OUTPUT_MATRIX}")
    print()
    print(f"Breakdown:")
    print(f"  Auto-fixable:    {auto_count:4d} issues (~15 min)")
    print(f"  Semi-automated:  {semi_count:4d} issues (~60 min)")
    print(f"  Manual:          {manual_count:4d} issues (~240 min)")
    print(f"  Other:           {other_count:4d} issues")
    print()
    print(f"📖 Review {OUTPUT_MATRIX} for detailed plan")

if __name__ == "__main__":
    analyze_errors()
