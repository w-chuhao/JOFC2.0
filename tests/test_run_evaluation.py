from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_evaluation import (
    DEFAULT_HISTORY_PATH,
    REPOSITORY_ROOT,
    append_evaluation_run,
    evaluation_summary,
)


RESULTS = {
    "sample_count": 200,
    "hit_rate_at_10": 0.925,
    "mrr": 0.579095,
    "mttc": 3.67,
    "efficiency": 0.733,
    "recommended_technical_score": 0.782829,
    "reported_token_usage": {"prompt_tokens": 0, "completion_tokens": 0},
    "scenario_metrics": {"buying": {"sample_count": 80, "hit_rate_at_10": 0.9}},
    "sessions": [{"sample_id": "public_0001"}],
}


class EvaluationHistoryTest(unittest.TestCase):
    def test_default_history_is_stored_under_outputs(self) -> None:
        self.assertEqual(
            DEFAULT_HISTORY_PATH,
            REPOSITORY_ROOT / "outputs" / "evaluation_history.json",
        )

    def test_append_evaluation_run_records_summary_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results_path = root / "results.json"
            history_path = root / "evaluation_history.json"
            results_path.write_text(json.dumps(RESULTS), encoding="utf-8")

            entry = append_evaluation_run(
                history_path=history_path,
                results_path=results_path,
                tested_by="Member 1",
                note="Constraint reranking",
            )

            saved_history = json.loads(history_path.read_text(encoding="utf-8"))
            self.assertEqual(entry["test_number"], 1)
            self.assertEqual(entry["tested_by"], "Member 1")
            self.assertEqual(entry["note"], "Constraint reranking")
            self.assertIn("tested_at", entry)
            self.assertNotIn("git_commit", entry)
            self.assertEqual(saved_history["runs"], [entry])
            self.assertNotIn("sessions", entry["metrics"])

    def test_evaluation_summary_rejects_incomplete_output(self) -> None:
        with self.assertRaises(ValueError):
            evaluation_summary({"sample_count": 200})


if __name__ == "__main__":
    unittest.main()
