"""Evaluate several local-reranker confidence gaps and record each result."""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import subprocess
import sys

try:
    from scripts.run_evaluation import (
        DEFAULT_HISTORY_PATH,
        REPOSITORY_ROOT,
        append_evaluation_run,
        default_tester,
    )
except ModuleNotFoundError:  # Supports `python scripts/sweep_semantic_score_gap.py`.
    from run_evaluation import (  # type: ignore[no-redef]
        DEFAULT_HISTORY_PATH,
        REPOSITORY_ROOT,
        append_evaluation_run,
        default_tester,
    )


DEFAULT_GAPS = (0.2, 0.25, 0.3, 0.35, 0.4)
DEFAULT_RESULTS_DIRECTORY = REPOSITORY_ROOT / "outputs" / "semantic_score_gap_sweep"


def parse_gap(value: str) -> float:
    """Accept a non-negative finite within-query score-gap threshold."""
    try:
        gap = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("gap must be a number") from error
    if not math.isfinite(gap) or gap < 0.0:
        raise argparse.ArgumentTypeError("gap must be a finite non-negative number")
    return gap


def gap_label(gap: float) -> str:
    """Create a stable filename component without platform-specific punctuation."""
    return f"{gap:.2f}".replace(".", "_")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep local-reranker score-gap thresholds on the public evaluator."
    )
    parser.add_argument(
        "--gaps",
        nargs="+",
        type=parse_gap,
        default=DEFAULT_GAPS,
        help="Non-negative gaps to test (default: 0.2 0.25 0.3 0.35 0.4).",
    )
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.jsonl"))
    parser.add_argument("--dataset", type=Path, default=Path("data/public_set.jsonl"))
    parser.add_argument("--tested-by", default=default_tester())
    parser.add_argument(
        "--note-prefix",
        default="Phase 2E score-gap sweep",
        help="Prefix recorded before the tested gap in evaluation history.",
    )
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY_PATH)
    parser.add_argument(
        "--results-directory",
        type=Path,
        default=DEFAULT_RESULTS_DIRECTORY,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gaps = list(dict.fromkeys(args.gaps))
    args.results_directory.mkdir(parents=True, exist_ok=True)

    for gap in gaps:
        output_path = args.results_directory / f"results_gap_{gap_label(gap)}.json"
        environment = os.environ.copy()
        environment["LOCAL_RERANKER_MIN_SCORE_GAP"] = str(gap)
        command = [
            sys.executable,
            "-m",
            "evaluator.local_evaluator",
            "--catalog",
            str(args.catalog),
            "--dataset",
            str(args.dataset),
            "--output",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            env=environment,
            check=False,
        )
        if completed.returncode != 0:
            return completed.returncode

        entry = append_evaluation_run(
            history_path=args.history,
            results_path=output_path,
            tested_by=args.tested_by,
            note=f"{args.note_prefix}: LOCAL_RERANKER_MIN_SCORE_GAP={gap:g}",
        )
        score = entry["metrics"]["recommended_technical_score"]
        print(f"Gap {gap:g}: recorded test #{entry['test_number']} (score {score}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
