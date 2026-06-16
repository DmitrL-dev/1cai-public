
#!/usr/bin/env python3
"""
CLI для построения Unified Change Graph из кода 1С.

Использование:
    python scripts/cli/build_1c_code_graph.py --input /path/to/bsl/files --output graph.json
    python scripts/cli/build_1c_code_graph.py --input module.bsl --module-path "ОбщийМодуль.Имя"
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ai.code_graph import InMemoryCodeGraphBackend
from src.ai.code_graph_1c_builder import OneCCodeGraphBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def build_from_file(
    file_path: str,
    module_path: str,
    output_path: Optional[str] = None,
) -> None:
    """Построить граф из одного BSL файла."""
    backend = InMemoryCodeGraphBackend()
    builder = OneCCodeGraphBuilder(backend)

    file = Path(file_path)
    if not file.exists():
        logger.error("File does not exist: %s", file_path)
        sys.exit(1)

    module_code = file.read_text(encoding="utf-8")
    stats = await builder.build_from_module(
        module_path,
        module_code,
        module_metadata={"file_path": str(file)},
    )

    logger.info("Graph built: %d nodes, %d edges", stats["nodes_created"], stats["edges_created"])

    if output_path:
        graph_export = await builder.export_graph(output_path)
        logger.info("Graph exported to: %s", output_path)
    else:
        graph_export = await builder.export_graph()
        print(json.dumps(graph_export, ensure_ascii=False, indent=2))


async def build_from_directory(
    directory_path: str,
    output_path: Optional[str] = None,
    pattern: str = "*.bsl",
    recursive: bool = True,
) -> None:
    """Построить граф из директории с BSL файлами."""
    backend = InMemoryCodeGraphBackend()
    builder = OneCCodeGraphBuilder(backend)

    stats = await builder.build_from_directory(
        directory_path,
        pattern=pattern,
        recursive=recursive,
    )

    logger.info(
        "Graph built: %d modules, %d nodes, %d edges",
        stats["total_modules"],
        stats["total_nodes"],
        stats["total_edges"],
    )

    if output_path:
        graph_export = await builder.export_graph(output_path)
        logger.info("Graph exported to: %s", output_path)
    else:
        graph_export = await builder.export_graph()
        print(json.dumps(graph_export, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Build Unified Change Graph from 1C BSL code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Input: path to BSL file or directory",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output: path to JSON file (if not specified, prints to stdout)",
    )
    parser.add_argument(
        "--module-path",
        help="Module path (required if --input is a file, e.g., 'ОбщийМодуль.Имя')",
    )
    parser.add_argument(
        "--pattern",
        default="*.bsl",
        help="File pattern for directory search (default: '*.bsl')",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Don't search recursively in directories",
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    if input_path.is_file():
        if not args.module_path:
            logger.error("--module-path is required when --input is a file")
            sys.exit(1)
        asyncio.run(build_from_file(args.input, args.module_path, args.output))
    elif input_path.is_dir():
        asyncio.run(
            build_from_directory(
                args.input,
                args.output,
                pattern=args.pattern,
                recursive=not args.no_recursive,
            )
        )
    else:
        logger.error("Input path does not exist: %s", args.input)
        sys.exit(1)


if __name__ == "__main__":
    main()

