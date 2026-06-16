"""CLI entry point for Рентген-Скоринг — token-free BSL code analysis engine."""

import argparse
import sys
from pathlib import Path


def cmd_extract(args):
    from .extract import run_extraction

    run_extraction(
        config_path=Path(args.config_path),
        output=Path(args.output) if args.output else None,
    )


def cmd_classify(args):
    from .classify import run_classification

    run_classification(
        config_path=Path(args.config_path),
        features_path=Path(args.features),
        output=Path(args.output) if args.output else None,
    )


def cmd_score(args):
    from .score import run_scoring

    run_scoring(
        features_path=Path(args.features),
        domains_path=Path(args.domains),
        output=Path(args.output) if args.output else None,
    )


def cmd_run(args):
    """Full pipeline: extract → classify → score."""
    import json
    import tempfile
    from .extract import run_extraction
    from .classify import run_classification
    from .score import run_scoring

    config_path = Path(args.config_path)
    output = Path(args.output) if args.output else None

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        features_path = tmp / "features.ndjson"
        domains_path = tmp / "domains.csv"

        print("[1/3] Extracting features…", file=sys.stderr)
        run_extraction(config_path=config_path, output=features_path)

        print("[2/3] Classifying domains…", file=sys.stderr)
        run_classification(
            config_path=config_path, features_path=features_path, output=domains_path
        )

        print("[3/3] Scoring…", file=sys.stderr)
        run_scoring(
            features_path=features_path, domains_path=domains_path, output=output
        )

    print("Done.", file=sys.stderr)


def cmd_calibrate(args):
    from .calibrate import run_calibration

    run_calibration(ground_truth=Path(args.ground_truth), scores_path=Path(args.scores))


def cmd_train(args):
    from .train_quality import train

    train(
        ground_truth_path=Path(args.ground_truth),
        features_path=Path(args.features),
        model_output=Path(args.model_output),
    )


def cmd_load(args):
    from .load_neo4j import load_scores

    load_scores(
        scores_path=Path(args.scores),
        batch_size=args.batch_size,
    )


def main():
    parser = argparse.ArgumentParser(
        prog="bsl_scoring",
        description="Рентген-Скоринг: token-free BSL code analysis engine",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # extract
    p_ext = sub.add_parser("extract", help="Extract features from .bsl files")
    p_ext.add_argument(
        "--config-path", required=True, help="Path to unpacked 1C config"
    )
    p_ext.add_argument(
        "--output", default=None, help="Output NDJSON file (default: stdout)"
    )
    p_ext.set_defaults(func=cmd_extract)

    # classify
    p_cls = sub.add_parser("classify", help="Classify modules into functional domains")
    p_cls.add_argument(
        "--config-path", required=True, help="Path to unpacked 1C config"
    )
    p_cls.add_argument(
        "--features", required=True, help="Features NDJSON from extract step"
    )
    p_cls.add_argument(
        "--output", default=None, help="Output CSV file (default: stdout)"
    )
    p_cls.set_defaults(func=cmd_classify)

    # score
    p_scr = sub.add_parser("score", help="Compute quality scores")
    p_scr.add_argument("--features", required=True, help="Features NDJSON")
    p_scr.add_argument("--domains", required=True, help="Domains CSV")
    p_scr.add_argument(
        "--output", default=None, help="Output JSON file (default: stdout)"
    )
    p_scr.set_defaults(func=cmd_score)

    # run (full pipeline)
    p_run = sub.add_parser("run", help="Full pipeline: extract → classify → score")
    p_run.add_argument(
        "--config-path", required=True, help="Path to unpacked 1C config"
    )
    p_run.add_argument(
        "--output", default=None, help="Output JSON file (default: stdout)"
    )
    p_run.set_defaults(func=cmd_run)

    # calibrate
    p_cal = sub.add_parser(
        "calibrate", help="Compare formula scores vs LLM ground truth"
    )
    p_cal.add_argument(
        "--ground-truth", required=True, help="Path to checkpoint.jsonl with LLM scores"
    )
    p_cal.add_argument(
        "--scores", required=True, help="Path to scores.json from score step"
    )
    p_cal.set_defaults(func=cmd_calibrate)

    # train
    p_train = sub.add_parser("train", help="Train code_quality GBR model")
    p_train.add_argument(
        "--ground-truth", required=True, help="Path to checkpoint.jsonl"
    )
    p_train.add_argument("--features", required=True, help="Path to features.ndjson")
    p_train.add_argument(
        "--model-output",
        default="C:/1cAI/gabriel_runs/code_quality_model.pkl",
        help="Output pickle path",
    )
    p_train.set_defaults(func=cmd_train)

    # load
    p_load = sub.add_parser("load", help="Load scores into Neo4j")
    p_load.add_argument("--scores", required=True, help="Path to scores.json")
    p_load.add_argument("--batch-size", type=int, default=2000)
    p_load.set_defaults(func=cmd_load)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
