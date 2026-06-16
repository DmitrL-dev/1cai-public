"""
Code Sync Service
Scans the repository and updates Wiki pages to reflect the codebase structure and documentation.
"""

import ast
import os
import uuid
from pathlib import Path
from typing import List, Optional, Set

from src.database import get_db_connection
from src.services.wiki.models import WikiPageCreate, WikiPageUpdate
from src.services.wiki.service import WikiService
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    "venv",
    "node_modules",
    ".idea",
    ".vscode",
    "tests",
    "migrations",
}
IGNORED_FILES = {"__init__.py"}


class ImportVisitor(ast.NodeVisitor):
    """Extracts imports from AST"""

    def __init__(self):
        self.imports: Set[str] = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.add(node.module)
        self.generic_visit(node)


class CodeSyncService:
    def __init__(self, root_path: str, wiki_service: WikiService):
        self.root_path = Path(root_path)
        self.wiki_service = wiki_service
        self.namespace_cache = {}  # path -> namespace_id

    async def sync_all(self):
        """
        Full synchronization of the codebase into Wiki.
        """
        logger.info(f"Starting CodeSync from {self.root_path}")

        # 1. Ensure 'Codebase' root namespace exists
        root_ns_id = await self._get_or_create_namespace("Codebase", "codebase")
        self.namespace_cache["."] = root_ns_id

        # 2. Walk the tree
        for root, dirs, files in os.walk(self.root_path):
            # Filter ignored
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

            rel_path = Path(root).relative_to(self.root_path)
            if str(rel_path) == ".":
                current_ns_id = root_ns_id
            else:
                # Create namespace for this directory
                parent_path = rel_path.parent
                parent_ns_id = self.namespace_cache.get(str(parent_path), root_ns_id)
                current_ns_id = await self._get_or_create_namespace(
                    rel_path.name, str(rel_path), parent_ns_id
                )
                self.namespace_cache[str(rel_path)] = current_ns_id

            # Process Python files
            for file in files:
                if file.endswith(".py") and file not in IGNORED_FILES:
                    await self._process_python_file(Path(root) / file, current_ns_id)

        logger.info("CodeSync completed")

    async def _process_python_file(self, file_path: Path, namespace_id: str):
        """
        Parse Python file and update Wiki page.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)

            # Extract Info
            rel_path = file_path.relative_to(self.root_path)
            module_name = file_path.stem
            slug = str(rel_path).replace(os.sep, "-").replace(".", "-").lower()

            docstring = ast.get_docstring(tree) or "No module documentation."

            # Extract Imports
            import_visitor = ImportVisitor()
            import_visitor.visit(tree)
            imports = sorted(list(import_visitor.imports))

            # Generate Markdown Content
            md_content = f"# {module_name}\n\n"
            md_content += f"**Path**: `{rel_path}`\n\n"
            md_content += f"## Description\n{docstring}\n\n"

            # Architecture Diagrams (Mermaid)
            classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]

            # 1. Dependency Graph
            if imports:
                md_content += "## Dependencies\n\n"
                md_content += self._generate_dependency_graph(module_name, imports)
                md_content += "\n\n"

            # 2. Class Diagram
            if classes:
                md_content += "## Architecture (Classes)\n\n"
                md_content += self._generate_class_diagram(classes)
                md_content += "\n\n"

            # Detailed Class Docs
            if classes:
                md_content += "## Class Details\n"
                for cls in classes:
                    cls_doc = ast.get_docstring(cls) or "No description."
                    md_content += f"### `class {cls.name}`\n{cls_doc}\n\n"

                    # Methods
                    methods = [
                        m
                        for m in cls.body
                        if isinstance(m, ast.FunctionDef) and not m.name.startswith("_")
                    ]
                    if methods:
                        md_content += "**Methods:**\n"
                        for method in methods:
                            md_content += f"- `{method.name}`: {ast.get_docstring(method) or ''}\n"
                        md_content += "\n"

            # Functions
            funcs = [
                n
                for n in tree.body
                if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
            ]
            if funcs:
                md_content += "## Functions\n"
                for func in funcs:
                    func_doc = ast.get_docstring(func) or "No description."
                    md_content += f"### `def {func.name}`\n{func_doc}\n\n"

            md_content += f"\n---\n*Auto-generated by CodeSync on {os.getenv('COMPUTERNAME', 'Server')}*"

            # Upsert Page
            await self._upsert_page(slug, module_name, md_content, namespace_id)

        except Exception as e:
            logger.error("Failed to process %s: {e}", file_path)

    def _generate_dependency_graph(self, module_name: str, imports: List[str]) -> str:
        """Generates a Mermaid graph TD showing imports"""
        mermaid = "```mermaid\ngraph TD\n"
        mermaid += f"    {module_name}['{module_name}']\n"

        for imp in imports:
            # Simplify import name for graph (e.g., src.services.wiki -> wiki)
            simple_name = imp.split(".")[-1]
            mermaid += f"    {module_name} --> {simple_name}\n"

        mermaid += "```"
        return mermaid

    def _generate_class_diagram(self, classes: List[ast.ClassDef]) -> str:
        """Generates a Mermaid classDiagram"""
        mermaid = "```mermaid\nclassDiagram\n"

        for cls in classes:
            mermaid += f"    class {cls.name} {{\n"

            # Methods
            methods = [m for m in cls.body if isinstance(m, ast.FunctionDef)]
            for method in methods:
                visibility = "-" if method.name.startswith("_") else "+"
                mermaid += f"        {visibility}{method.name}()\n"

            mermaid += "    }\n"

            # Inheritance
            for base in cls.bases:
                if isinstance(base, ast.Name):
                    mermaid += f"    {base.id} <|-- {cls.name}\n"

        mermaid += "```"
        return mermaid

    async def _get_or_create_namespace(
        self, name: str, path: str, parent_id: Optional[str] = None
    ) -> str:
        """
        Stub for namespace management.
        """
        # Deterministic ID based on path
        ns_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"namespace:{path}"))

        async with get_db_connection() as conn:
            # Check exist
            row = await conn.fetchrow(
                "SELECT id FROM wiki_namespaces WHERE id = $1", ns_uuid
            )
            if not row:
                await conn.execute(
                    """
                    INSERT INTO wiki_namespaces (id, name, path, parent_id)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (id) DO NOTHING
                """,
                    ns_uuid,
                    name,
                    path,
                    parent_id,
                )

        return ns_uuid

    async def _upsert_page(
        self, slug: str, title: str, content: str, namespace_id: str
    ):
        """
        Create or Update page if content changed.
        """
        existing = await self.wiki_service.get_page(slug)

        if existing:
            if "Auto-generated" in (existing.html_content or ""):
                await self.wiki_service.update_page(
                    slug,
                    WikiPageUpdate(
                        content=content,
                        version=existing.version,
                        commit_message="Auto-sync update",
                    ),
                    author_id="system-sync",
                )
        else:
            await self.wiki_service.create_page(
                WikiPageCreate(
                    slug=slug,
                    title=title,
                    content=content,
                    namespace=namespace_id,
                    commit_message="Auto-sync create",
                ),
                author_id="system-sync",
            )
