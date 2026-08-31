from __future__ import annotations

import argparse
import unittest

from scripts.sweep_semantic_score_gap import DEFAULT_GAPS, gap_label, parse_gap


class SemanticScoreGapSweepTest(unittest.TestCase):
    def test_default_gap_sweep_samples_around_the_current_best_value(self) -> None:
        self.assertEqual(DEFAULT_GAPS, (0.2, 0.25, 0.3, 0.35, 0.4))

    def test_parse_gap_accepts_finite_non_negative_values(self) -> None:
        self.assertEqual(parse_gap("0.15"), 0.15)
        self.assertEqual(parse_gap("0"), 0.0)

    def test_parse_gap_rejects_negative_and_non_finite_values(self) -> None:
        for value in ("-0.1", "nan", "inf", "not-a-number"):
            with self.assertRaises(argparse.ArgumentTypeError):
                parse_gap(value)

    def test_gap_label_is_stable_for_result_filenames(self) -> None:
        self.assertEqual(gap_label(0.15), "0_15")


if __name__ == "__main__":
    unittest.main()
