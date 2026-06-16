"""Train GradientBoostingRegressor for code_quality prediction."""

import json
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import cross_val_score
from sklearn.metrics import mean_absolute_error, r2_score

# Feature columns to use (all numeric features from features.ndjson)
FEATURE_COLS = [
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


def _normalize_path(p: str) -> str:
    """Normalize path to forward slashes, lowercase."""
    return p.replace("\\", "/").lower()


def _extract_features(record: Dict[str, Any]) -> List[float]:
    """Extract feature vector from a features.ndjson record."""
    vals = []
    for col in FEATURE_COLS:
        if col == "num_referenced_objects":
            refs = record.get("referenced_objects", [])
            vals.append(float(len(refs) if isinstance(refs, list) else 0))
        else:
            v = record.get(col, 0)
            vals.append(float(v) if isinstance(v, (int, float, bool)) else 0.0)
    return vals


def _suffix_match(gt_path: str, feat_path: str) -> bool:
    """Check if normalized ground-truth path ends with normalized feature path."""
    gt_norm = _normalize_path(gt_path)
    feat_norm = _normalize_path(feat_path)
    return gt_norm.endswith(feat_norm) or feat_norm.endswith(gt_norm)


def train(
    ground_truth_path: Path,
    features_path: Path,
    model_output: Path,
) -> Dict[str, Any]:
    """Train GBR model for code_quality prediction.

    1. Load features into path->record map
    2. Load ground truth, match by suffix to features
    3. Build X (feature matrix) and y (code_quality scores)
    4. Train GBR with 5-fold cross-validation
    5. Print metrics: CV MAE, CV R², feature importances
    6. Retrain on full data, save model as pickle
    7. Return metrics dict
    """
    # 1. Load features into path->record map
    print(f"Loading features from {features_path}...", file=sys.stderr)
    feat_by_path: Dict[str, Dict[str, Any]] = {}
    with open(features_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            mp = rec.get("module_path", "")
            if mp:
                feat_by_path[_normalize_path(mp)] = rec
    print(f"  Loaded {len(feat_by_path)} feature records.", file=sys.stderr)

    # 2. Load ground truth, match by suffix to features
    print(f"Loading ground truth from {ground_truth_path}...", file=sys.stderr)
    gt_records: List[Dict[str, Any]] = []
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            gt_records.append(json.loads(line))
    print(f"  Loaded {len(gt_records)} ground truth records.", file=sys.stderr)

    # Match ground truth to features by suffix
    X_rows: List[List[float]] = []
    y_vals: List[float] = []
    matched = 0
    unmatched = 0
    unmatched_paths: List[str] = []

    for gt in gt_records:
        gt_path = _normalize_path(gt.get("filepath", ""))
        quality = gt.get("code_quality")
        if quality is None:
            continue

        found = False
        for feat_path, feat_rec in feat_by_path.items():
            if gt_path.endswith(feat_path) or feat_path.endswith(gt_path):
                X_rows.append(_extract_features(feat_rec))
                y_vals.append(float(quality))
                matched += 1
                found = True
                break

        if not found:
            unmatched += 1
            if len(unmatched_paths) < 5:
                unmatched_paths.append(gt_path)

    print(f"\n  Matched: {matched}, Unmatched: {unmatched}", file=sys.stderr)
    if unmatched_paths:
        print(f"  Sample unmatched paths: {unmatched_paths[:5]}", file=sys.stderr)

    if matched == 0:
        print("ERROR: No samples matched. Cannot train.", file=sys.stderr)
        sys.exit(1)

    # 3. Build X and y arrays
    X = np.array(X_rows, dtype=np.float64)
    y = np.array(y_vals, dtype=np.float64)
    print(f"\n  X shape: {X.shape}, y shape: {y.shape}", file=sys.stderr)
    print(
        f"  y stats: mean={y.mean():.1f}, median={np.median(y):.1f}, "
        f"std={y.std():.1f}, min={y.min():.0f}, max={y.max():.0f}",
        file=sys.stderr,
    )

    # 4. Train GBR with 5-fold cross-validation
    print("\nTraining GradientBoostingRegressor with 5-fold CV...", file=sys.stderr)
    gbr = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        min_samples_leaf=10,
        subsample=0.8,
        random_state=42,
    )

    cv_mae_scores = cross_val_score(gbr, X, y, cv=5, scoring="neg_mean_absolute_error")
    cv_r2_scores = cross_val_score(gbr, X, y, cv=5, scoring="r2")

    cv_mae = -cv_mae_scores.mean()
    cv_mae_std = cv_mae_scores.std()
    cv_r2 = cv_r2_scores.mean()
    cv_r2_std = cv_r2_scores.std()

    print(f"\n  5-Fold CV Results:", file=sys.stderr)
    print(f"    MAE:  {cv_mae:.2f} ± {cv_mae_std:.2f}", file=sys.stderr)
    print(f"    R²:   {cv_r2:.3f} ± {cv_r2_std:.3f}", file=sys.stderr)

    # 5. Feature importance ranking
    print("\nRetraining on full dataset...", file=sys.stderr)
    gbr.fit(X, y)

    importances = gbr.feature_importances_
    indices = np.argsort(importances)[::-1]

    print("\n  Top 10 Feature Importances:", file=sys.stderr)
    for rank, idx in enumerate(indices[:10], 1):
        print(
            f"    {rank:2d}. {FEATURE_COLS[idx]:<30s} {importances[idx]:.4f}",
            file=sys.stderr,
        )

    # Full-data metrics
    y_pred = gbr.predict(X)
    train_mae = mean_absolute_error(y, y_pred)
    train_r2 = r2_score(y, y_pred)
    print(f"\n  Full-data train MAE: {train_mae:.2f}", file=sys.stderr)
    print(f"  Full-data train R²:  {train_r2:.3f}", file=sys.stderr)

    # 6. Save model as pickle
    model_output.parent.mkdir(parents=True, exist_ok=True)

    model_artifact = {
        "model": gbr,
        "feature_cols": FEATURE_COLS,
        "metrics": {
            "cv_mae": cv_mae,
            "cv_mae_std": cv_mae_std,
            "cv_r2": cv_r2,
            "cv_r2_std": cv_r2_std,
            "train_mae": train_mae,
            "train_r2": train_r2,
            "n_samples": matched,
        },
    }

    with open(model_output, "wb") as f:
        pickle.dump(model_artifact, f, protocol=pickle.HIGHEST_PROTOCOL)

    model_size = model_output.stat().st_size
    print(f"\n  Model saved to: {model_output}", file=sys.stderr)
    print(
        f"  Model file size: {model_size:,} bytes ({model_size / 1024:.1f} KB)",
        file=sys.stderr,
    )

    # 7. Return metrics dict
    metrics = {
        "matched_samples": matched,
        "unmatched_samples": unmatched,
        "cv_mae": round(cv_mae, 3),
        "cv_mae_std": round(cv_mae_std, 3),
        "cv_r2": round(cv_r2, 3),
        "cv_r2_std": round(cv_r2_std, 3),
        "train_mae": round(train_mae, 3),
        "train_r2": round(train_r2, 3),
        "top_features": [
            {"name": FEATURE_COLS[idx], "importance": round(float(importances[idx]), 4)}
            for idx in indices[:10]
        ],
        "model_path": str(model_output),
        "model_size_bytes": model_size,
    }

    print(f"\nDone.", file=sys.stderr)
    return metrics


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train code_quality GBR model")
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument(
        "--model-output",
        default=Path("C:/1cAI/gabriel_runs/code_quality_model.pkl"),
        type=Path,
    )
    args = parser.parse_args()
    train(args.ground_truth, args.features, args.model_output)
