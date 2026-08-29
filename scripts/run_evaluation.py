"""Run the public evaluator and append its summary to the team metrics history."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SUMMARY_KEYS = (
    "sample_count",
    "hit_rate_at_10",
    "mrr",
    "mttc",
    "efficiency",
    "recommended_technical_score",
    "reported_token_usage",
    "scenario_metrics",
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY_PATH = REPOSITORY_ROOT / "outputs" / "evaluation_history.json"
DEFAULT_RESULTS_PATH = REPOSITORY_ROOT / "results.json"


def default_tester() -> str:
    """Use the configured GitHub username, falling back to the OS username."""
    completed = subprocess.run(
        ["git", "config", "user.name"],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() or getpass.getuser()


def evaluation_summary(results: dict[str, Any]) -> dict[str, Any]:
    """Keep the durable aggregate matrix, not the 200-session detail payload."""
    missing = [key for key in SUMMARY_KEYS if key not in results]
    if missing:
        raise ValueError(f"Evaluator output is missing summary fields: {', '.join(missing)}")
    return {key: results[key] for key in SUMMARY_KEYS}


def append_evaluation_run(
    history_path: Path,
    results_path: Path,
    tested_by: str,
    note: str | None,
) -> dict[str, Any]:
    """Append one evaluator summary and return the new history entry."""
    results = json.loads(results_path.read_text(encoding="utf-8"))
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
    else:
        history = {"schema_version": 1, "runs": []}

    runs = history.setdefault("runs", [])
    entry = {
        "test_number": len(runs) + 1,
        "tested_by": tested_by,
        "tested_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "note": note or "",
        "metrics": evaluation_summary(results),
    }
    runs.append(entry)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    return entry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the public evaluator and record its summary matrix."
    )
    parser.add_argument(
        "--tested-by",
        default=default_tester(),
        help="Person who ran the test (defaults to the configured GitHub username).",
    )
    parser.add_argument("--note", help="Optional description of the tested change.")
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = [
        sys.executable,
        "-m",
        "evaluator.local_evaluator",
        "--output",
        str(args.output),
    ]
    completed = subprocess.run(command, cwd=REPOSITORY_ROOT, check=False)
    if completed.returncode != 0:
        return completed.returncode

    entry = append_evaluation_run(
        history_path=args.history,
        results_path=args.output,
        tested_by=args.tested_by,
        note=args.note,
    )
    score = entry["metrics"]["recommended_technical_score"]
    print(f"Recorded test #{entry['test_number']} for {entry['tested_by']} (score {score}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
