"""
Phase 3: Documentation Audit - Analysis Script
Analyzes documentation completeness and missing docstrings
"""

import json
from pathlib import Path
from typing import Dict
import ast


def analyze_documentation():
    """Analyze project documentation state"""
    
    results = {
        "markdown_files": 0,
        "python_files": 0,
        "missing_docstrings": {
            "modules": 0,
            "classes": 0,
            "functions": 0,
            "total": 0
        },
        "files_with_issues": []
    }
    
    src_dir = Path("src")
    
    # Count markdown files
    results["markdown_files"] = len(list(Path(".").rglob("*.md")))
    
    # Analyze Python files
    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
            
        results["python_files"] += 1
        
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            tree = ast.parse(content)
            file_issues = analyze_file(tree, py_file)
            
            if file_issues["total"] > 0:
                results["files_with_issues"].append({
                    "file": str(py_file),
                    "issues": file_issues
                })
                
                results["missing_docstrings"]["modules"] += file_issues["module"]
                results["missing_docstrings"]["classes"] += file_issues["classes"]
                results["missing_docstrings"]["functions"] += file_issues["functions"]
                results["missing_docstrings"]["total"] += file_issues["total"]
                
        except Exception as e:
            print(f"Error analyzing {py_file}: {e}")
    
    return results


def analyze_file(tree: ast.AST, filepath: Path) -> Dict[str, int]:
    """Analyze single Python file for missing docstrings"""
    
    issues = {
        "module": 0,
        "classes": 0,
        "functions": 0,
        "total": 0
    }
    
    # Check module docstring
    if not ast.get_docstring(tree):
        issues["module"] = 1
        issues["total"] += 1
    
    # Check classes and functions
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if not ast.get_docstring(node):
                issues["classes"] += 1
                issues["total"] += 1
        
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip private functions (start with _)
            if not node.name.startswith("_"):
                if not ast.get_docstring(node):
                    issues["functions"] += 1
                    issues["total"] += 1
    
    return issues


def print_summary(results: Dict):
    """Print analysis summary"""
    
    print("=" * 80)
    print("PHASE 3: DOCUMENTATION AUDIT - ANALYSIS RESULTS")
    print("=" * 80)
    print()
    
    print(f"📄 Markdown files: {results['markdown_files']:,}")
    print(f"🐍 Python files analyzed: {results['python_files']:,}")
    print()
    
    print("Missing Docstrings:")
    print(f"  Modules:   {results['missing_docstrings']['modules']:,}")
    print(f"  Classes:   {results['missing_docstrings']['classes']:,}")
    print(f"  Functions: {results['missing_docstrings']['functions']:,}")
    print(f"  TOTAL:     {results['missing_docstrings']['total']:,}")
    print()
    
    print(f"Files with issues: {len(results['files_with_issues']):,}")
    print()
    
    # Top 10 files with most issues
    if results['files_with_issues']:
        sorted_files = sorted(
            results['files_with_issues'],
            key=lambda x: x['issues']['total'],
            reverse=True
        )[:10]
        
        print("Top 10 files with most missing docstrings:")
        for item in sorted_files:
            print(f"  {item['file']}: {item['issues']['total']} missing")
    
    print()
    print("=" * 80)
    
    # Save detailed results
    with open("phase3_documentation_analysis.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    print("✅ Detailed results saved to: phase3_documentation_analysis.json")
    print("=" * 80)


if __name__ == "__main__":
    print("Starting documentation analysis...")
    print()
    
    results = analyze_documentation()
    print_summary(results)
