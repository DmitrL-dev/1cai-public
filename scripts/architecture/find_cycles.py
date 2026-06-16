
import ast
from pathlib import Path
from collections import defaultdict

class CycleFinder:
    def __init__(self, src_dir: Path = Path("src")):
        self.src_dir = src_dir
        self.dependencies = defaultdict(set)

    def _get_module_name(self, filepath: Path) -> str:
        try:
            rel_path = filepath.relative_to(self.src_dir)
            parts = rel_path.parts
            if len(parts) > 0:
                return parts[0]
        except:
            pass
        return "unknown"

    def _get_imported_module(self, node) -> str:
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("src."):
                parts = node.module.split(".")
                if len(parts) > 1:
                    return parts[1]
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("src."):
                    parts = alias.name.split(".")
                    if len(parts) > 1:
                        return parts[1]
        return None

    def build_graph(self):
        print("Building dependency graph...")
        
        class DependencyVisitor(ast.NodeVisitor):
            def __init__(self, finder):
                self.finder = finder
                self.current_module = None
                self.in_type_checking = False
                self.in_function = False

            def visit_FunctionDef(self, node):
                old_in_function = self.in_function
                self.in_function = True
                self.generic_visit(node)
                self.in_function = old_in_function

            def visit_AsyncFunctionDef(self, node):
                old_in_function = self.in_function
                self.in_function = True
                self.generic_visit(node)
                self.in_function = old_in_function

            def visit_Import(self, node):
                if not self.in_type_checking and not self.in_function:
                    imported = self.finder._get_imported_module(node)
                    if imported and imported != self.current_module:
                        self.finder.dependencies[self.current_module].add(imported)
                self.generic_visit(node)

            def visit_ImportFrom(self, node):
                if not self.in_type_checking and not self.in_function:
                    imported = self.finder._get_imported_module(node)
                    if imported and imported != self.current_module:
                        self.finder.dependencies[self.current_module].add(imported)
                self.generic_visit(node)

            def visit_If(self, node):
                # Check if this is a TYPE_CHECKING block
                is_type_checking = False
                try:
                    if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                        is_type_checking = True
                    elif isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING":
                        is_type_checking = True
                except:
                    pass

                if is_type_checking:
                    old_in_type_checking = self.in_type_checking
                    self.in_type_checking = True
                    # Only visit body with type checking flag, but we actually want to SKIP dependencies there
                    # So we just visit to continue traversing but our visit_Import* methods will check the flag
                    for child in node.body:
                        self.visit(child)
                    self.in_type_checking = old_in_type_checking
                    
                    # Visit else block normally
                    for child in node.orelse:
                        self.visit(child)
                else:
                    self.generic_visit(node)

        visitor = DependencyVisitor(self)

        for py_file in self.src_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                
                module_name = self._get_module_name(py_file)
                visitor.current_module = module_name
                visitor.visit(tree)
                
            except Exception as e:
                print(f"Error parsing {py_file}: {e}")

    def find_cycles(self):
        print("Finding cycles...")
        cycles = []
        visited = set()
        recursion_stack = []

        def dfs(node, path):
            if node in path:
                cycle_start = path.index(node)
                cycle = path[cycle_start:]
                # Normalize cycle to avoid duplicates (e.g., A->B->A is same as B->A->B)
                # We store as tuple to be hashable
                if cycle not in cycles:
                    cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            path.append(node)

            for dep in self.dependencies.get(node, []):
                dfs(dep, path.copy())

        for node in list(self.dependencies.keys()):
            dfs(node, [])

        # Deduplicate cycles based on set of nodes
        unique_cycles = []
        seen_sets = []
        
        for cycle in cycles:
            cycle_set = set(cycle)
            if cycle_set not in seen_sets:
                seen_sets.append(cycle_set)
                unique_cycles.append(cycle)

        return unique_cycles

    def print_cycles(self):
        self.build_graph()
        cycles = self.find_cycles()
        
        if not cycles:
            print("\n✅ No cyclic dependencies found!")
            return

        print(f"\n⚠️ Found {len(cycles)} unique cyclic dependency chains:")
        for i, cycle in enumerate(cycles, 1):
            chain = " -> ".join(cycle) + " -> " + cycle[0]
            print(f"{i}. {chain}")

if __name__ == "__main__":
    finder = CycleFinder()
    finder.print_cycles()
