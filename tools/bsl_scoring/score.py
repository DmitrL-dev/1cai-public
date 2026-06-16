"""Scoring functions for BSL module quality assessment.

Three composite scores: Complexity, Documentation, Maintainability.
All return int 0–100. Uses numpy for sigmoid normalization.
"""

import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pickle
from pathlib import Path as _Path

_MODEL_PATH = (
    _Path(__file__).parent.parent.parent / "gabriel_runs" / "code_quality_model.pkl"
)
_model_cache = None


def _load_model():
    global _model_cache
    if _model_cache is not None:
        return _model_cache
    if not _MODEL_PATH.exists():
        return None
    with open(_MODEL_PATH, "rb") as f:
        raw = pickle.load(f)
    # Pickle may wrap model in a dict with key "model"
    if isinstance(raw, dict) and "model" in raw:
        _model_cache = raw["model"]
    else:
        _model_cache = raw
    return _model_cache


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _sigmoid(x: float, center: float = 0.0, steepness: float = 1.0) -> float:
    """Sigmoid function normalized to [0, 1]."""
    return float(1.0 / (1.0 + np.exp(-steepness * (x - center))))


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    """Clamp value to [lo, hi] and return int."""
    return int(max(lo, min(hi, round(value))))


# ---------------------------------------------------------------------------
# Complexity Score (0–100, higher = MORE complex = WORSE)
# ---------------------------------------------------------------------------


def score_complexity(
    cyclomatic: int,
    max_nesting: int,
    loc: int,
    num_functions: int,
    avg_func_length: float,
    has_n_plus_one: bool,
) -> int:
    """Sigmoid-normalized composite complexity score.

    0 = trivially simple, 100 = extremely complex.
    """
    # Normalize each factor via sigmoid into [0, 1]
    # Cyclomatic: center=15 (moderate complexity), steepness tuned
    cc_norm = _sigmoid(cyclomatic, center=15, steepness=0.15)

    # Max nesting: center=3, anything above 5 is very bad
    nest_norm = _sigmoid(max_nesting, center=3, steepness=0.8)

    # LOC: center=300, large modules are complex
    loc_norm = _sigmoid(loc, center=300, steepness=0.005)

    # Functions per module: low count with high LOC = bad structure
    # Invert: many small functions = good
    if num_functions > 0:
        loc_per_func = loc / num_functions
        struct_norm = _sigmoid(loc_per_func, center=40, steepness=0.05)
    else:
        struct_norm = _sigmoid(loc, center=50, steepness=0.01)

    # Avg function length: center=30
    func_len_norm = _sigmoid(avg_func_length, center=30, steepness=0.05)

    # N+1 query penalty
    n_plus_one_penalty = 0.15 if has_n_plus_one else 0.0

    # Weighted composite
    raw = (
        0.30 * cc_norm
        + 0.20 * nest_norm
        + 0.15 * loc_norm
        + 0.15 * struct_norm
        + 0.10 * func_len_norm
        + n_plus_one_penalty
    )

    return _clamp(raw * 100)


# ---------------------------------------------------------------------------
# Documentation Score (0–100, higher = BETTER documented)
# ---------------------------------------------------------------------------


def score_documentation(
    doc_coverage: float,
    comment_density: float,
    has_module_header: bool,
    num_functions: int,
    loc: int,
) -> int:
    """Weighted composite documentation score.

    0 = no docs, 100 = fully documented.
    """
    # Doc coverage: 0–1 → 0–40 points
    doc_pts = doc_coverage * 40.0

    # Comment density: optimal ~15%, diminishing returns past 30%
    # Map 0–0.3 → 0–30 points, cap at 30
    density_pts = min(30.0, (comment_density / 0.15) * 30.0)

    # Module header: 15 points
    header_pts = 15.0 if has_module_header else 0.0

    # Small modules with few functions get a doc bonus (less need for docs)
    size_bonus = 0.0
    if loc < 50 and num_functions <= 2:
        size_bonus = 15.0
    elif loc < 100 and num_functions <= 5:
        size_bonus = 10.0

    raw = doc_pts + density_pts + header_pts + size_bonus
    return _clamp(raw)


# ---------------------------------------------------------------------------
# Maintainability Score (0–100, higher = MORE maintainable = BETTER)
# ---------------------------------------------------------------------------


def score_maintainability(
    complexity_score: int,
    documentation_score: int,
    loc: int,
    fan_in: int = 0,
    fan_out: int = 0,
    has_empty_catch: bool = False,
    has_magic_numbers: bool = False,
    export_ratio: float = 0.0,
    avg_identifier_length: float = 0.0,
) -> int:
    """SEI Maintainability Index adapted for BSL.

    0 = unmaintainable, 100 = excellent.

    Adapted from: MI = 171 - 5.2*ln(V) - 0.23*CC - 16.2*ln(LOC)
    We use our own normalized version.
    """
    # Base: invert complexity (high complexity → low maintainability)
    base = (100 - complexity_score) * 0.90  # 0–90, calibrated vs LLM ground truth

    # Documentation boost (up to +20)
    doc_boost = documentation_score * 0.15

    # LOC penalty: very large modules are harder to maintain
    loc_penalty = min(20.0, max(0.0, (loc - 150) * 0.02))

    # Fan-out penalty: too many dependencies
    fanout_penalty = min(10.0, fan_out * 0.5) if fan_out > 5 else 0.0

    # Anti-pattern penalties
    empty_catch_penalty = 5.0 if has_empty_catch else 0.0
    magic_num_penalty = 3.0 if has_magic_numbers else 0.0

    # Export ratio: high export ratio on large modules = higher coupling risk
    export_penalty = 0.0
    if export_ratio > 0.8 and loc > 200:
        export_penalty = 5.0

    # Identifier quality: very short names hurt readability
    ident_penalty = 0.0
    if 0 < avg_identifier_length < 4:
        ident_penalty = 5.0

    # Fan-in bonus: highly-used modules are important (small bonus)
    fanin_bonus = min(5.0, fan_in * 0.3) if fan_in > 3 else 0.0

    raw = (
        base
        + doc_boost
        - loc_penalty
        - fanout_penalty
        - empty_catch_penalty
        - magic_num_penalty
        - export_penalty
        - ident_penalty
        + fanin_bonus
    )

    return _clamp(raw)


# ---------------------------------------------------------------------------
# Batch scoring
# ---------------------------------------------------------------------------


_QUALITY_FEATURES = [
    "loc",
    "cyclomatic_complexity",
    "max_nesting",
    "doc_coverage",
    "comment_density",
    "has_module_header",
    "num_functions",
    "avg_func_length",
    "export_ratio",
    "avg_identifier_length",
    "has_error_handling",
    "has_n_plus_one",
    "has_select_star",
    "has_empty_catch",
    "has_magic_numbers",
    "has_deep_nesting",
    "num_todo_fixme",
    "num_referenced_objects",
]


def predict_quality(feature: Dict[str, Any]) -> Optional[int]:
    """Predict code_quality score using trained GBR model. Returns 0-100 or None."""
    model = _load_model()
    if model is None:
        return None
    vals = []
    for col in _QUALITY_FEATURES:
        if col == "num_referenced_objects":
            refs = feature.get("referenced_objects", [])
            vals.append(float(len(refs) if isinstance(refs, list) else 0))
        else:
            v = feature.get(col, 0)
            vals.append(float(v) if isinstance(v, (int, float, bool)) else 0.0)
    prediction = model.predict([vals])[0]
    return _clamp(prediction)


def score_module(feature: Dict[str, Any], domain: str = "Прочее") -> Dict[str, Any]:
    """Compute all three scores for a single module feature dict."""
    cx = score_complexity(
        cyclomatic=feature.get("cyclomatic_complexity", 1),
        max_nesting=feature.get("max_nesting", 0),
        loc=feature.get("loc", 0),
        num_functions=feature.get("num_functions", 0),
        avg_func_length=feature.get("avg_func_length", 0),
        has_n_plus_one=feature.get("has_n_plus_one", False),
    )

    doc = score_documentation(
        doc_coverage=feature.get("doc_coverage", 0.0),
        comment_density=feature.get("comment_density", 0.0),
        has_module_header=feature.get("has_module_header", False),
        num_functions=feature.get("num_functions", 0),
        loc=feature.get("loc", 0),
    )

    mi = score_maintainability(
        complexity_score=cx,
        documentation_score=doc,
        loc=feature.get("loc", 0),
        fan_in=feature.get("fan_in", 0),
        fan_out=feature.get("fan_out", 0),
        has_empty_catch=feature.get("has_empty_catch", False),
        has_magic_numbers=feature.get("has_magic_numbers", False),
        export_ratio=feature.get("export_ratio", 0.0),
        avg_identifier_length=feature.get("avg_identifier_length", 0.0),
    )

    cq = predict_quality(feature)

    return {
        "module_path": feature["module_path"],
        "module_type": feature.get("module_type", "Unknown"),
        "domain": domain,
        "loc": feature.get("loc", 0),
        "complexity_score": cx,
        "documentation_score": doc,
        "maintainability_score": mi,
        "code_quality": cq,
        # Key flags for quick filtering
        "has_n_plus_one": feature.get("has_n_plus_one", False),
        "has_select_star": feature.get("has_select_star", False),
        "has_empty_catch": feature.get("has_empty_catch", False),
        "has_deep_nesting": feature.get("has_deep_nesting", False),
        "has_magic_numbers": feature.get("has_magic_numbers", False),
        "num_todo_fixme": feature.get("num_todo_fixme", 0),
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_scoring(
    features_path: Path,
    domains_path: Path,
    output: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Score all modules from features NDJSON + domains CSV.

    Returns list of scored module dicts and writes JSON.
    """
    # Load features
    features: List[Dict[str, Any]] = []
    with open(features_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                features.append(json.loads(line))

    # Load domain mapping
    domain_map: Dict[str, str] = {}
    with open(domains_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain_map[row["module_path"]] = row["domain"]

    print(f"Scoring {len(features)} modules…", file=sys.stderr)

    # Score each module
    results: List[Dict[str, Any]] = []
    for feat in features:
        domain = domain_map.get(feat["module_path"], "Прочее")
        scored = score_module(feat, domain)
        results.append(scored)

    # Compute aggregate stats
    if results:
        cx_scores = [r["complexity_score"] for r in results]
        doc_scores = [r["documentation_score"] for r in results]
        mi_scores = [r["maintainability_score"] for r in results]

        summary = {
            "total_modules": len(results),
            "avg_complexity": round(float(np.mean(cx_scores)), 1),
            "avg_documentation": round(float(np.mean(doc_scores)), 1),
            "avg_maintainability": round(float(np.mean(mi_scores)), 1),
            "median_complexity": round(float(np.median(cx_scores)), 1),
            "median_documentation": round(float(np.median(doc_scores)), 1),
            "median_maintainability": round(float(np.median(mi_scores)), 1),
            "modules_with_n_plus_one": sum(1 for r in results if r["has_n_plus_one"]),
            "modules_with_select_star": sum(1 for r in results if r["has_select_star"]),
            "modules_with_empty_catch": sum(1 for r in results if r["has_empty_catch"]),
            "modules_with_deep_nesting": sum(
                1 for r in results if r["has_deep_nesting"]
            ),
        }

        print(f"\n  Summary:", file=sys.stderr)
        for k, v in summary.items():
            print(f"    {k}: {v}", file=sys.stderr)
    else:
        summary = {"total_modules": 0}

    output_data = {
        "summary": summary,
        "modules": results,
    }

    # Write output
    out_text = json.dumps(output_data, ensure_ascii=False, indent=2)
    if output:
        output.write_text(out_text, encoding="utf-8")
        print(f"\nScores written to {output}", file=sys.stderr)
    else:
        sys.stdout.write(out_text + "\n")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BSL quality scoring")
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--domains", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    run_scoring(args.features, args.domains, args.output)
