import ast
import os
from pathlib import Path
from typing import Dict, List, Tuple

def analyze_file(file_path: Path) -> Tuple[int, int]:
    """Returns (total_functions, typed_functions)"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content)
    except Exception:
        return 0, 0

    total = 0
    typed = 0

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            total += 1
            if node.returns is not None:
                typed += 1
    
    return total, typed

def main():
    root = Path("src/modules")
    results = []

    for file_path in root.rglob("*.py"):
        if file_path.name == "__init__.py":
            continue
            
        total, typed = analyze_file(file_path)
        if total > 0:
            coverage = (typed / total) * 100
            results.append({
                "file": str(file_path),
                "total": total,
                "typed": typed,
                "coverage": coverage
            })

    # Sort by coverage (ascending) and then by total functions (descending)
    results.sort(key=lambda x: (x["coverage"], -x["total"]))

    print(f"{'File':<60} | {'Coverage':<10} | {'Typed/Total':<15}")
    print("-" * 90)
    
    for res in results[:20]:  # Show bottom 20
        print(f"{res['file']:<60} | {res['coverage']:>6.1f}%    | {res['typed']}/{res['total']}")

if __name__ == "__main__":
    main()
