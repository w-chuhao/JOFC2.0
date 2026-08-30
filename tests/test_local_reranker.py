from __future__ import annotations

import math
import os
import unittest
from pathlib import Path
from unittest import mock

from starter.local_reranker import LocalCrossEncoderReranker


class LocalCrossEncoderRerankerTest(unittest.TestCase):
    def test_rank_orders_existing_ids_by_descending_model_score(self) -> None:
        reranker = LocalCrossEncoderReranker(
            "unused-in-test",
            scorer=lambda query, texts: [0.2, 0.9, 0.5],
        )

        result = reranker.rank(
            "comfortable walking shoes",
            [("A", "first"), ("B", "second"), ("C", "third")],
        )

        self.assertEqual(result, ["B", "C", "A"])

    def test_rank_rejects_wrong_score_count(self) -> None:
        reranker = LocalCrossEncoderReranker(
            "unused-in-test",
            scorer=lambda query, texts: [0.5],
        )

        with self.assertRaisesRegex(ValueError, "one score per document"):
            reranker.rank("query", [("A", "first"), ("B", "second")])

    def test_rank_rejects_non_finite_scores(self) -> None:
        reranker = LocalCrossEncoderReranker(
            "unused-in-test",
            scorer=lambda query, texts: [math.nan],
        )

        with self.assertRaisesRegex(ValueError, "finite"):
            reranker.rank("query", [("A", "first")])

    def test_missing_environment_configuration_keeps_reranker_disabled(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            reranker = LocalCrossEncoderReranker.from_environment(Path("."))

        self.assertIsNone(reranker)


if __name__ == "__main__":
    unittest.main()
