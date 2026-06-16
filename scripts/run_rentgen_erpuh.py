"""Run Рентген on unpacked ERP УХ configuration.

First real-world test: 28,901 BSL modules, 131,168 files, 8.81 GB.
"""

import logging
import sys
import time
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import src.parser.bsl_ast_visitor as _bsl_mod

_bsl_mod.ANTLR4_AVAILABLE = False  # Force regex-only mode for speed at scale

from src.ai.code_graph_1c_builder import OneCCodeGraphBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("rentgen-erpuh")

CONFIG_PATH = ROOT / "data" / "configs" / "unpacked"


def main():
    logger.info("=== РЕНТГЕН: ERP УХ (regex-only mode) ===")
    logger.info("Config path: %s", CONFIG_PATH)

    bsl_files = sorted(CONFIG_PATH.rglob("*.bsl"))
    bsl_count = len(bsl_files)
    logger.info("BSL files found: %d", bsl_count)

    builder = OneCCodeGraphBuilder(config_path=str(CONFIG_PATH))

    # Phase 1: Metadata
    t0 = time.perf_counter()
    builder.parse_metadata()
    t_meta = time.perf_counter() - t0
    logger.info(
        "Metadata parsed in %.1fs: %d documents, %d catalogs, %d common_modules, %d subscriptions",
        t_meta,
        len(builder.metadata.documents),
        len(builder.metadata.catalogs),
        len(builder.metadata.common_modules),
        len(builder.metadata.subscriptions),
    )

    # Phase 2: BSL modules with progress logging
    t1 = time.perf_counter()
    errors = 0
    for i, bsl_path in enumerate(bsl_files, 1):
        module_name = builder._module_name_from_path(bsl_path)
        try:
            builder._parse_bsl_file(bsl_path, module_name)
        except Exception as e:
            errors += 1
            if errors <= 5:
                logger.warning("Error parsing %s: %s", bsl_path.name, e)
        if i % 2000 == 0 or i == bsl_count:
            elapsed = time.perf_counter() - t1
            rate = i / elapsed if elapsed > 0 else 0
            eta = (bsl_count - i) / rate if rate > 0 else 0
            logger.info(
                "Progress: %d/%d (%.0f%%) | %.0f files/sec | ETA %.0fs | funcs: %d | errors: %d",
                i,
                bsl_count,
                100 * i / bsl_count,
                rate,
                eta,
                len(builder.functions),
                errors,
            )
    t_bsl = time.perf_counter() - t1

    # Stats
    total_funcs = len(builder.functions)
    funcs = sum(1 for f in builder.functions if f.is_function)
    procs = sum(1 for f in builder.functions if not f.is_function)
    exports = sum(1 for f in builder.functions if f.is_export)
    total_calls = sum(len(f.calls) for f in builder.functions)
    total_queries = sum(len(f.queries) for f in builder.functions)
    modules_set = set(f.module for f in builder.functions)

    # Complexity stats
    complexities = [f.complexity for f in builder.functions]
    avg_complexity = sum(complexities) / len(complexities) if complexities else 0
    max_complexity = max(complexities) if complexities else 0
    complex_funcs = [
        (f.name, f.module, f.complexity) for f in builder.functions if f.complexity > 20
    ]
    complex_funcs.sort(key=lambda x: x[2], reverse=True)

    # Top callers
    top_callers = sorted(builder.functions, key=lambda f: len(f.calls), reverse=True)[
        :10
    ]

    # Top query-heavy
    top_query = sorted(builder.functions, key=lambda f: len(f.queries), reverse=True)[
        :10
    ]

    logger.info("=" * 60)
    logger.info("=== РЕЗУЛЬТАТЫ РЕНТГЕНА: ERP УХ ===")
    logger.info("=" * 60)
    logger.info(
        "BSL parsing time: %.1fs (%.0f files/sec)",
        t_bsl,
        builder._modules_parsed / t_bsl if t_bsl > 0 else 0,
    )
    logger.info("Modules parsed: %d", builder._modules_parsed)
    logger.info("Unique modules with code: %d", len(modules_set))
    logger.info("Total functions: %d", funcs)
    logger.info("Total procedures: %d", procs)
    logger.info("Total subroutines: %d", total_funcs)
    logger.info("Export subroutines: %d", exports)
    logger.info("Total call edges: %d", total_calls)
    logger.info("Total queries: %d", total_queries)
    logger.info("Avg complexity: %.1f", avg_complexity)
    logger.info("Max complexity: %d", max_complexity)
    logger.info("")
    logger.info("--- TOP 10 most complex functions ---")
    for name, mod, cx in complex_funcs[:10]:
        logger.info("  %s.%s → complexity %d", mod, name, cx)
    logger.info("")
    logger.info("--- TOP 10 callers (most outgoing calls) ---")
    for f in top_callers:
        logger.info("  %s.%s → %d calls", f.module, f.name, len(f.calls))
    logger.info("")
    logger.info("--- TOP 10 query-heavy functions ---")
    for f in top_query:
        if f.queries:
            logger.info("  %s.%s → %d queries", f.module, f.name, len(f.queries))
    logger.info("")
    logger.info("Total time: %.1fs", time.perf_counter() - t0)

    # Save summary JSON
    summary = {
        "config": "ERP УХ",
        "bsl_files": bsl_count,
        "modules_parsed": builder._modules_parsed,
        "unique_modules": len(modules_set),
        "functions": funcs,
        "procedures": procs,
        "exports": exports,
        "call_edges": total_calls,
        "queries": total_queries,
        "avg_complexity": round(avg_complexity, 1),
        "max_complexity": max_complexity,
        "parse_time_sec": round(t_bsl, 1),
        "top_complex": [
            {"name": n, "module": m, "complexity": c} for n, m, c in complex_funcs[:20]
        ],
        "top_callers": [
            {"name": f.name, "module": f.module, "calls": len(f.calls)}
            for f in top_callers
        ],
    }
    import json

    out_path = ROOT / "data" / "rentgen_erpuh_results.json"
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Summary saved to: %s", out_path)


if __name__ == "__main__":
    main()
