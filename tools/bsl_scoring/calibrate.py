"""Calibration: compare formula scores vs LLM ground truth.

Reads 611 LLM-scored modules from checkpoint.jsonl and compares
against formula-computed scores. Reports Pearson/Spearman correlation
and MAE per metric.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats


# ---------------------------------------------------------------------------
# Metric name mapping: LLM field → formula field
# ---------------------------------------------------------------------------

_METRIC_MAPPING = {
    "complexity": "complexity_score",
    "documentation": "documentation_score",
    "maintainability": "maintainability_score",
}

# Alternate LLM field names (some checkpoints use different keys)
_LLM_FIELD_ALIASES = {
    "complexity": ["complexity_score", "complexity", "score_complexity"],
    "documentation": [
        "documentation_score",
        "documentation",
        "score_documentation",
        "doc_score",
    ],
    "maintainability": [
        "maintainability_score",
        "maintainability",
        "score_maintainability",
        "mi_score",
    ],
}


def _extract_llm_score(record: Dict[str, Any], metric: str) -> Optional[float]:
    """Extract a score value from an LLM checkpoint record, trying multiple field names."""
    aliases = _LLM_FIELD_ALIASES.get(metric, [metric])

    # Try top-level fields
    for alias in aliases:
        if alias in record:
            val = record[alias]
            if isinstance(val, (int, float)):
                return float(val)

    # Try nested "scores" dict
    scores = record.get("scores", {})
    if isinstance(scores, dict):
        for alias in aliases:
            if alias in scores:
                val = scores[alias]
                if isinstance(val, (int, float)):
                    return float(val)

    # Try nested "result" dict
    result = record.get("result", {})
    if isinstance(result, dict):
        for alias in aliases:
            if alias in result:
                val = result[alias]
                if isinstance(val, (int, float)):
                    return float(val)
        # Check result.scores
        result_scores = result.get("scores", {})
        if isinstance(result_scores, dict):
            for alias in aliases:
                if alias in result_scores:
                    val = result_scores[alias]
                    if isinstance(val, (int, float)):
                        return float(val)

    return None


def _extract_module_path(record: Dict[str, Any]) -> Optional[str]:
    """Extract module path from an LLM checkpoint record."""
    for key in ["module_path", "path", "file", "file_path", "filepath"]:
        if key in record and isinstance(record[key], str):
            return record[key].replace("\\", "/")
    # Try nested
    for container_key in ["input", "request", "metadata"]:
        container = record.get(container_key, {})
        if isinstance(container, dict):
            for key in ["module_path", "path", "file", "file_path", "filepath"]:
                if key in container and isinstance(container[key], str):
                    return container[key].replace("\\", "/")
    return None


# ---------------------------------------------------------------------------
# Main calibration
# ---------------------------------------------------------------------------


def run_calibration(
    ground_truth: Path,
    scores_path: Path,
) -> Dict[str, Any]:
    """Compare formula scores vs LLM ground truth.

    Args:
        ground_truth: Path to checkpoint.jsonl with LLM scores
        scores_path: Path to scores.json from score step

    Returns:
        Calibration report dict
    """
    # Load ground truth
    gt_records: List[Dict[str, Any]] = []
    with open(ground_truth, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    gt_records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    print(f"Loaded {len(gt_records)} ground truth records.", file=sys.stderr)

    # Load formula scores
    with open(scores_path, "r", encoding="utf-8") as f:
        scores_data = json.load(f)

    if isinstance(scores_data, dict) and "modules" in scores_data:
        formula_modules = scores_data["modules"]
    elif isinstance(scores_data, list):
        formula_modules = scores_data
    else:
        print("ERROR: Unexpected scores.json format.", file=sys.stderr)
        return {}

    # Build path → scores lookup
    formula_map: Dict[str, Dict[str, Any]] = {}
    for mod in formula_modules:
        path = mod.get("module_path", "").replace("\\", "/")
        if path:
            formula_map[path] = mod

    print(f"Loaded {len(formula_map)} formula-scored modules.", file=sys.stderr)

    # Match records
    report: Dict[str, Any] = {}
    overall_matched = 0

    for metric_name, formula_field in _METRIC_MAPPING.items():
        llm_values: List[float] = []
        formula_values: List[float] = []

        for gt_rec in gt_records:
            gt_path = _extract_module_path(gt_rec)
            if gt_path is None:
                continue

            llm_score = _extract_llm_score(gt_rec, metric_name)
            if llm_score is None:
                continue

            # Find matching formula score
            formula_rec = formula_map.get(gt_path)
            if formula_rec is None:
                # Try suffix matching
                for fpath, frec in formula_map.items():
                    if fpath.endswith(gt_path) or gt_path.endswith(fpath):
                        formula_rec = frec
                        break

            if formula_rec is None:
                continue

            formula_score = formula_rec.get(formula_field)
            if formula_score is None:
                continue

            llm_values.append(float(llm_score))
            formula_values.append(float(formula_score))

        n = len(llm_values)
        if n < 3:
            print(
                f"\n  {metric_name}: Only {n} matched pairs — skipping correlation.",
                file=sys.stderr,
            )
            report[metric_name] = {
                "matched_pairs": n,
                "status": "insufficient_data",
            }
            continue

        overall_matched = max(overall_matched, n)

        llm_arr = np.array(llm_values)
        formula_arr = np.array(formula_values)

        # Pearson correlation
        pearson_r, pearson_p = scipy_stats.pearsonr(llm_arr, formula_arr)

        # Spearman correlation
        spearman_r, spearman_p = scipy_stats.spearmanr(llm_arr, formula_arr)

        # Mean absolute error
        mae = float(np.mean(np.abs(llm_arr - formula_arr)))

        # Root mean squared error
        rmse = float(np.sqrt(np.mean((llm_arr - formula_arr) ** 2)))

        # Distribution stats
        metric_report = {
            "matched_pairs": n,
            "pearson_r": round(pearson_r, 4),
            "pearson_p": round(pearson_p, 6),
            "spearman_r": round(spearman_r, 4),
            "spearman_p": round(spearman_p, 6),
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "llm_mean": round(float(np.mean(llm_arr)), 2),
            "llm_std": round(float(np.std(llm_arr)), 2),
            "formula_mean": round(float(np.mean(formula_arr)), 2),
            "formula_std": round(float(np.std(formula_arr)), 2),
            "mean_bias": round(float(np.mean(formula_arr - llm_arr)), 2),
        }

        report[metric_name] = metric_report

    # Print report
    print("\n" + "=" * 70, file=sys.stderr)
    print("  CALIBRATION REPORT: Formula Scores vs LLM Ground Truth", file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    for metric_name, metrics in report.items():
        print(f"\n  [{metric_name.upper()}]", file=sys.stderr)
        if metrics.get("status") == "insufficient_data":
            print(
                f"    Insufficient data ({metrics['matched_pairs']} pairs)",
                file=sys.stderr,
            )
            continue

        print(f"    Matched pairs:     {metrics['matched_pairs']}", file=sys.stderr)
        print(
            f"    Pearson r:         {metrics['pearson_r']:+.4f}  (p={metrics['pearson_p']:.6f})",
            file=sys.stderr,
        )
        print(
            f"    Spearman ρ:        {metrics['spearman_r']:+.4f}  (p={metrics['spearman_p']:.6f})",
            file=sys.stderr,
        )
        print(f"    MAE:               {metrics['mae']:.2f}", file=sys.stderr)
        print(f"    RMSE:              {metrics['rmse']:.2f}", file=sys.stderr)
        print(
            f"    Mean bias:         {metrics['mean_bias']:+.2f}  (formula - LLM)",
            file=sys.stderr,
        )
        print(
            f"    LLM distribution:  μ={metrics['llm_mean']:.1f}  σ={metrics['llm_std']:.1f}",
            file=sys.stderr,
        )
        print(
            f"    Formula distrib:   μ={metrics['formula_mean']:.1f}  σ={metrics['formula_std']:.1f}",
            file=sys.stderr,
        )

    print("\n" + "=" * 70, file=sys.stderr)

    # Quality assessment
    print("\n  ASSESSMENT:", file=sys.stderr)
    for metric_name, metrics in report.items():
        if metrics.get("status") == "insufficient_data":
            continue
        r = metrics["spearman_r"]
        mae = metrics["mae"]
        if r >= 0.7 and mae <= 15:
            verdict = "GOOD — formula tracks LLM well"
        elif r >= 0.5 and mae <= 25:
            verdict = "FAIR — some correlation, needs tuning"
        elif r >= 0.3:
            verdict = "WEAK — limited correlation, significant tuning needed"
        else:
            verdict = "POOR — formula does not track LLM scores"
        print(f"    {metric_name}: {verdict}", file=sys.stderr)

    print("", file=sys.stderr)

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BSL score calibration")
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--scores", required=True, type=Path)
    args = parser.parse_args()
    run_calibration(args.ground_truth, args.scores)
