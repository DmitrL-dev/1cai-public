import ast
import os
import re
from typing import Dict, List, Any, Tuple
import json

def has_cyrillic(text: str) -> bool:
    return bool(re.search('[а-яА-Я]', text))

def is_google_style(docstring: str) -> bool:
    if not docstring:
        return False
    return "Args:" in docstring or "Returns:" in docstring or "Raises:" in docstring or "Attributes:" in docstring

class DocAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.stats = {
            "modules": 0,
            "classes": 0,
            "functions": 0,
            "methods": 0,
            "docstrings_found": 0,
            "docstrings_missing": 0,
            "russian_docstrings": 0,
            "english_docstrings": 0,
            "google_style": 0,
            "items": []
        }
        self.current_file = ""

    def visit_Module(self, node):
        self.stats["modules"] += 1
        docstring = ast.get_docstring(node)
        self._analyze_docstring(docstring, "module", self.current_file)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.stats["classes"] += 1
        docstring = ast.get_docstring(node)
        self._analyze_docstring(docstring, "class", f"{self.current_file}::{node.name}")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._handle_function(node)

    def _handle_function(self, node):
        # Determine if it's a method or function (heuristic)
        is_method = False
        if hasattr(node, 'parent') and isinstance(node.parent, ast.ClassDef):
             is_method = True
        
        # Simple check: if indentation level suggests it's inside a class, count as method
        # But AST visitor doesn't give indentation easily. 
        # We'll just count all as functions for now, distinguishing based on context is harder without parent pointers.
        # Actually, we can just count them all as "functions/methods".
        
        self.stats["functions"] += 1
        docstring = ast.get_docstring(node)
        self._analyze_docstring(docstring, "function", f"{self.current_file}::{node.name}")
        self.generic_visit(node)

    def _analyze_docstring(self, docstring: str, item_type: str, name: str):
        item_info = {
            "name": name,
            "type": item_type,
            "has_docstring": bool(docstring),
            "language": "unknown",
            "style": "unknown"
        }

        if docstring:
            self.stats["docstrings_found"] += 1
            if has_cyrillic(docstring):
                self.stats["russian_docstrings"] += 1
                item_info["language"] = "russian"
            else:
                self.stats["english_docstrings"] += 1
                item_info["language"] = "english"
            
            if is_google_style(docstring):
                self.stats["google_style"] += 1
                item_info["style"] = "google"
            else:
                item_info["style"] = "other"
        else:
            self.stats["docstrings_missing"] += 1
        
        self.stats["items"].append(item_info)

def analyze_directory(root_dir: str) -> Dict[str, Any]:
    analyzer = DocAnalyzer()
    
    readme_stats = {
        "total_modules": 0,
        "modules_with_readme": 0,
        "missing_readmes": []
    }

    # Walk src/modules to check for READMEs
    modules_dir = os.path.join(root_dir, "src", "modules")
    if os.path.exists(modules_dir):
        for item in os.listdir(modules_dir):
            item_path = os.path.join(modules_dir, item)
            if os.path.isdir(item_path):
                readme_stats["total_modules"] += 1
                if os.path.exists(os.path.join(item_path, "README.md")):
                    readme_stats["modules_with_readme"] += 1
                else:
                    readme_stats["missing_readmes"].append(item)

    # Walk all python files
    for root, _, files in os.walk(os.path.join(root_dir, "src")):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, root_dir)
                analyzer.current_file = rel_path
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read())
                    analyzer.visit(tree)
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")

    return {
        "code_stats": analyzer.stats,
        "readme_stats": readme_stats
    }

if __name__ == "__main__":
    results = analyze_directory(os.getcwd())
    
    print(json.dumps(results, indent=2, ensure_ascii=False))
    
    stats = results["code_stats"]
    readmes = results["readme_stats"]
    
    print("\n" + "="*50)
    print("DOCUMENTATION ANALYSIS REPORT")
    print("="*50)
    print(f"Total Python Items (Modules/Classes/Funcs): {stats['modules'] + stats['classes'] + stats['functions']}")
    print(f"Docstrings Found: {stats['docstrings_found']}")
    print(f"Docstrings Missing: {stats['docstrings_missing']}")
    print(f"Coverage: {stats['docstrings_found'] / (stats['docstrings_found'] + stats['docstrings_missing']) * 100:.1f}%")
    print("-" * 30)
    print(f"Russian Docstrings: {stats['russian_docstrings']}")
    print(f"English Docstrings: {stats['english_docstrings']}")
    print(f"Google Style: {stats['google_style']}")
    print("-" * 30)
    print(f"Modules with README: {readmes['modules_with_readme']}/{readmes['total_modules']}")
    if readmes['missing_readmes']:
        print("Modules missing README:")
        for m in readmes['missing_readmes']:
            print(f"  - {m}")
