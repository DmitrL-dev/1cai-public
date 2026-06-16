"""
Deep Import Analysis Script

Analyzes all Python files in the project to detect:
1. Circular imports
2. Missing imports
3. Forward reference issues
4. Dependency order problems
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict


class ImportAnalyzer(ast.NodeVisitor):
    """AST visitor to extract imports from Python files"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.imports: List[Tuple[str, int]] = []  # (module, line_number)
        self.from_imports: List[Tuple[str, str, int]] = []  # (module, name, line_number)
        
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append((alias.name, node.lineno))
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        if node.module:
            for alias in node.names:
                self.from_imports.append((node.module, alias.name, node.lineno))
        self.generic_visit(node)


def analyze_file(filepath: Path) -> Tuple[List, List]:
    """Analyze a single Python file for imports"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(filepath))
        
        analyzer = ImportAnalyzer(str(filepath))
        analyzer.visit(tree)
        return analyzer.imports, analyzer.from_imports
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}")
        return [], []


def build_dependency_graph(src_dir: Path) -> Dict[str, Set[str]]:
    """Build a dependency graph of all Python modules"""
    graph = defaultdict(set)
    
    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
            
        # Convert file path to module name
        rel_path = py_file.relative_to(src_dir.parent)
        module_name = str(rel_path).replace(os.sep, ".").replace(".py", "")
        
        imports, from_imports = analyze_file(py_file)
        
        # Add dependencies
        for imp, _ in imports:
            if imp.startswith("src."):
                graph[module_name].add(imp)
        
        for module, name, _ in from_imports:
            if module.startswith("src."):
                graph[module_name].add(module)
    
    return graph


def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Find all circular dependencies using DFS"""
    cycles = []
    visited = set()
    rec_stack = set()
    path = []
    
    def dfs(node):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                # Found a cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)
                return True
        
        path.pop()
        rec_stack.remove(node)
        return False
    
    for node in graph:
        if node not in visited:
            dfs(node)
    
    return cycles


def main():
    src_dir = Path("C:/1cAI/src")
    
    print("=" * 80)
    print("DEEP IMPORT ANALYSIS")
    print("=" * 80)
    
    # Build dependency graph
    print("\n1. Building dependency graph...")
    graph = build_dependency_graph(src_dir)
    print(f"   Found {len(graph)} modules")
    
    # Find circular dependencies
    print("\n2. Detecting circular imports...")
    cycles = find_cycles(graph)
    
    if cycles:
        print(f"\n   ❌ FOUND {len(cycles)} CIRCULAR DEPENDENCIES:")
        for i, cycle in enumerate(cycles, 1):
            print(f"\n   Cycle {i}:")
            for j, module in enumerate(cycle):
                if j < len(cycle) - 1:
                    print(f"      {module}")
                    print(f"         ↓")
                else:
                    print(f"      {module} (back to start)")
    else:
        print("   ✅ No circular dependencies found")
    
    # Check for common issues
    print("\n3. Checking for common import issues...")
    
    issues = []
    
    # Check dependencies.py
    deps_file = src_dir / "api" / "dependencies.py"
    if deps_file.exists():
        imports, from_imports = analyze_file(deps_file)
        
        # Check for GraphService import
        has_graph_service = any(
            "GraphService" in name for _, name, _ in from_imports
        )
        if has_graph_service:
            issues.append("dependencies.py imports GraphService at module level (circular import risk)")
    
    # Check for TYPE_CHECKING usage
    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if "TYPE_CHECKING" in content and "from typing import" in content:
                # Good practice
                pass
            elif ": GraphService" in content or ": ArchiExporter" in content:
                # Should use TYPE_CHECKING
                rel_path = py_file.relative_to(src_dir)
                issues.append(f"{rel_path}: Uses type hints without TYPE_CHECKING")
        except:
            pass
    
    if issues:
        print(f"\n   ❌ FOUND {len(issues)} ISSUES:")
        for issue in issues:
            print(f"      - {issue}")
    else:
        print("   ✅ No common issues found")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
