#!/usr/bin/env python3
"""
Pylint Results Analyzer
Analyzes pylint JSON output and generates summary report.
"""

import json
from pathlib import Path
from collections import defaultdict

# Input/Output files
PYLINT_RESULTS = Path("c:/1cAI/pylint_results_v2.json")
OUTPUT_SUMMARY = Path("c:/1cAI/PYLINT_SUMMARY.txt")

def analyze_pylint_results():
    """Analyze pylint results and generate summary."""
    
    # Read pylint results (handle UTF-8 BOM)
    with open(PYLINT_RESULTS, 'r', encoding='utf-8-sig') as f:
        results = json.load(f)
    
    # Statistics
    stats = {
        'total_issues': len(results),
        'by_type': defaultdict(int),
        'by_category': defaultdict(int),
        'by_file': defaultdict(int),
        'top_messages': defaultdict(int),
    }
    
    # Analyze each issue
    for issue in results:
        msg_type = issue.get('type', 'unknown')
        category = issue.get('message-id', 'unknown')
        filename = issue.get('path', 'unknown')
        message = issue.get('message', 'unknown')
        
        stats['by_type'][msg_type] += 1
        stats['by_category'][category] += 1
        stats['by_file'][filename] += 1
        stats['top_messages'][message[:80]] += 1
    
    # Generate summary report
    with open(OUTPUT_SUMMARY, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("PYLINT CODE QUALITY ANALYSIS\n")
        f.write("=" * 70 + "\n\n")
        
        f.write(f"Total Issues: {stats['total_issues']}\n\n")
        
        # By Type
        f.write("Issues by Type:\n")
        f.write("-" * 70 + "\n")
        for issue_type, count in sorted(stats['by_type'].items(), key=lambda x: -x[1]):
            f.write(f"  {issue_type:20s}: {count:5d}\n")
        f.write("\n")
        
        # By Category (Top 20)
        f.write("Top 20 Issue Categories:\n")
        f.write("-" * 70 + "\n")
        for category, count in sorted(stats['by_category'].items(), key=lambda x: -x[1])[:20]:
            f.write(f"  {category:30s}: {count:5d}\n")
        f.write("\n")
        
        # Top 10 Files with Most Issues
        f.write("Top 10 Files with Most Issues:\n")
        f.write("-" * 70 + "\n")
        for filename, count in sorted(stats['by_file'].items(), key=lambda x: -x[1])[:10]:
            short_name = Path(filename).name
            f.write(f"  {short_name:50s}: {count:5d}\n")
        f.write("\n")
        
        # Top 10 Messages
        f.write("Top 10 Most Common Messages:\n")
        f.write("-" * 70 + "\n")
        for message, count in sorted(stats['top_messages'].items(), key=lambda x: -x[1])[:10]:
            f.write(f"  [{count:4d}] {message}\n")
        f.write("\n")
        
        f.write("=" * 70 + "\n")
        f.write(f"Summary saved to: {OUTPUT_SUMMARY}\n")
        f.write("=" * 70 + "\n")
    
    print(f"✅ Analysis complete! Summary saved to: {OUTPUT_SUMMARY}")
    print(f"📊 Total issues: {stats['total_issues']}")
    print(f"📁 Files analyzed: {len(stats['by_file'])}")

if __name__ == "__main__":
    analyze_pylint_results()
