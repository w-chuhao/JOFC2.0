from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.benchmark_semantic_models import (
    BenchmarkCase,
    evaluate_rankings,
    load_candidate_documents,
    load_benchmark_cases,
    rank_cases,
    rank_by_scores,
)


class SemanticModelBenchmarkTest(unittest.TestCase):
    def test_load_cases_rejects_public_target_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path = root / "cases.json"
            public_path = root / "public.jsonl"
            cases_path.write_text(
                json.dumps(
                    [
                        {
                            "case_id": "case_1",
                            "query": "a useful query",
                            "target_parent_asin": "PUBLIC_TARGET",
                            "candidate_ids": ["PUBLIC_TARGET", "OTHER"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            public_path.write_text(
                json.dumps(
                    {
                        "ground_truth": {"parent_asin": "PUBLIC_TARGET"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "public target"):
                load_benchmark_cases(cases_path, public_path)

    def test_load_cases_rejects_duplicate_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path = root / "cases.json"
            public_path = root / "public.jsonl"
            cases_path.write_text(
                json.dumps(
                    [
                        {
                            "case_id": "case_1",
                            "query": "a useful query",
                            "target_parent_asin": "TARGET",
                            "candidate_ids": ["TARGET", "TARGET"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            public_path.write_text("", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate candidate"):
                load_benchmark_cases(cases_path, public_path)

    def test_load_cases_rejects_public_candidate_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path = root / "cases.json"
            public_path = root / "public.jsonl"
            cases_path.write_text(
                json.dumps(
                    [
                        {
                            "case_id": "case_1",
                            "query": "a useful query",
                            "target_parent_asin": "PRIVATE_TARGET",
                            "candidate_ids": ["PRIVATE_TARGET", "PUBLIC_OTHER"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            public_path.write_text(
                json.dumps({"ground_truth": {"parent_asin": "PUBLIC_OTHER"}})
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "public candidate"):
                load_benchmark_cases(cases_path, public_path)

    def test_evaluate_rankings_reports_exact_retrieval_metrics(self) -> None:
        cases = [
            BenchmarkCase("first", "query one", "A", ("A", "B", "C")),
            BenchmarkCase("second", "query two", "B", ("A", "C", "B")),
        ]

        result = evaluate_rankings(
            cases,
            {
                "first": ["A", "B", "C"],
                "second": ["A", "C", "B"],
            },
        )

        self.assertEqual(result["case_count"], 2)
        self.assertEqual(result["hit_rate_at_1"], 0.5)
        self.assertEqual(result["hit_rate_at_3"], 1.0)
        self.assertEqual(result["hit_rate_at_10"], 1.0)
        self.assertAlmostEqual(result["mrr"], (1.0 + 1.0 / 3.0) / 2.0)
        self.assertEqual(result["ranks"], {"first": 1, "second": 3})

    def test_evaluate_rankings_rejects_unknown_or_duplicate_ids(self) -> None:
        cases = [BenchmarkCase("case", "query", "A", ("A", "B"))]

        with self.assertRaisesRegex(ValueError, "candidate permutation"):
            evaluate_rankings(cases, {"case": ["A", "UNKNOWN"]})
        with self.assertRaisesRegex(ValueError, "candidate permutation"):
            evaluate_rankings(cases, {"case": ["A", "A"]})

    def test_rank_by_scores_is_descending_and_stable_for_ties(self) -> None:
        ranked = rank_by_scores(
            ("A", "B", "C", "D"),
            [0.1, 0.8, 0.8, -0.2],
        )

        self.assertEqual(ranked, ["B", "C", "A", "D"])

    def test_rank_by_scores_requires_one_finite_score_per_candidate(self) -> None:
        with self.assertRaisesRegex(ValueError, "one finite score"):
            rank_by_scores(("A", "B"), [1.0])
        with self.assertRaisesRegex(ValueError, "one finite score"):
            rank_by_scores(("A", "B"), [1.0, float("nan")])

    def test_catalog_loader_builds_production_order_text_and_checks_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.jsonl"
            catalog_path.write_text(
                json.dumps(
                    {
                        "parent_asin": "A",
                        "title": "Trail shoe",
                        "categories": ["Shoes", "Walking"],
                        "features": ["Waterproof", "Rubber sole"],
                        "details": {"color": "blue"},
                        "store": "Example",
                        "description": ["Comfortable for long walks"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            case = BenchmarkCase("case", "query", "A", ("A",))

            documents = load_candidate_documents(catalog_path, [case])

            self.assertEqual(
                documents["A"],
                "Trail shoe Shoes Walking Waterproof Rubber sole "
                "color blue Example Comfortable for long walks",
            )
            with self.assertRaisesRegex(ValueError, "missing candidate"):
                load_candidate_documents(
                    catalog_path,
                    [BenchmarkCase("missing", "query", "Z", ("Z",))],
                )

    def test_rank_cases_uses_the_same_candidate_set_for_a_scorer(self) -> None:
        cases = [BenchmarkCase("case", "query", "B", ("A", "B", "C"))]
        documents = {"A": "short", "B": "longest text", "C": "medium"}

        result = rank_cases(
            cases,
            documents,
            lambda query, texts: [float(len(text)) for text in texts],
        )

        self.assertEqual(result["rankings"]["case"], ["B", "C", "A"])
        self.assertEqual(result["metrics"]["ranks"], {"case": 1})
        self.assertGreaterEqual(result["ranking_seconds"], 0.0)


if __name__ == "__main__":
    unittest.main()
