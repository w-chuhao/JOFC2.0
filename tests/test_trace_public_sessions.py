from __future__ import annotations

import unittest

from scripts.trace_public_sessions import (
    build_trace,
    parse_sample_ids,
    ranking_comparison,
    select_samples,
)


def sample(sample_id: str, scenario: str, target: str) -> dict:
    return {
        "sample_id": sample_id,
        "scenario_type": scenario,
        "difficulty_bucket": "easy",
        "ground_truth": {"parent_asin": target},
        "user_profile": {},
        "intent_card": {"hard_constraints": [], "soft_preferences": []},
        "behavior": {},
    }


class ScriptedAgent:
    def reset(self, session_id: str, user_profile: dict) -> None:
        self.session_id = session_id

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        return {
            "message": "What material do you prefer?",
            "ask_attribute": "material",
            "recommendations": [{"parent_asin": "TARGET"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }


class TracePublicSessionsTest(unittest.TestCase):
    def test_select_samples_uses_an_even_deterministic_scenario_split(self) -> None:
        samples = [
            sample(f"{scenario}_{number}", scenario, "TARGET")
            for scenario in ("buying", "browsing", "intent_override", "boundary")
            for number in range(3)
        ]

        selected = select_samples(samples, per_scenario=2)

        self.assertEqual(len(selected), 8)
        self.assertEqual(
            [item["sample_id"] for item in selected],
            [
                "buying_0", "buying_1", "browsing_0", "browsing_1",
                "intent_override_0", "intent_override_1", "boundary_0", "boundary_1",
            ],
        )

    def test_select_samples_supports_uneven_scenario_counts(self) -> None:
        samples = [
            sample(f"{scenario}_{number}", scenario, "TARGET")
            for scenario in ("buying", "browsing", "intent_override", "boundary")
            for number in range(3)
        ]

        selected = select_samples(
            samples,
            {"buying": 3, "browsing": 2, "intent_override": 1, "boundary": 1},
        )

        self.assertEqual(
            [item["sample_id"] for item in selected],
            [
                "buying_0", "buying_1", "buying_2", "browsing_0", "browsing_1",
                "intent_override_0", "boundary_0",
            ],
        )

    def test_explicit_sample_ids_override_default_selection(self) -> None:
        samples = [sample("public_0001", "buying", "TARGET")]

        self.assertEqual(
            select_samples(samples, per_scenario=5, sample_ids=["public_0001"]),
            samples,
        )
        with self.assertRaisesRegex(ValueError, "Unknown sample IDs"):
            select_samples(samples, per_scenario=5, sample_ids=["missing"])

    def test_trace_records_full_turn_data_and_a_hit(self) -> None:
        trace = build_trace(
            ScriptedAgent(),
            [sample("public_0001", "buying", "TARGET")],
            {"TARGET"},
            {"TARGET": ["Clothing", "Shoes"]},
            {"TARGET": {"parent_asin": "TARGET"}},
        )

        session = trace["sessions"][0]
        turn = session["turns"][0]
        self.assertEqual(trace["scenario_counts"], {"buying": 1})
        self.assertEqual(session["stop_reason"], "hit")
        self.assertEqual(session["hit_turn"], 1)
        self.assertIn("I'm looking for", turn["customer_prompt"])
        self.assertEqual(turn["ask_attribute"], "material")
        self.assertEqual(turn["recommendation_ids"], ["TARGET"])
        self.assertEqual(turn["target_rank"], 1)
        self.assertTrue(turn["scored_hit"])

    def test_override_trace_does_not_score_a_pre_override_target_match(self) -> None:
        override_sample = sample("public_0002", "intent_override", "TARGET")
        override_sample["behavior"] = {
            "override": {
                "turn": 3,
                "old_value": "original requirement",
                "new_value": "replacement requirement",
                "message": "Actually, use the replacement requirement.",
            }
        }

        trace = build_trace(
            ScriptedAgent(),
            [override_sample],
            {"TARGET"},
            {"TARGET": ["Clothing", "Shoes"]},
            {"TARGET": {"parent_asin": "TARGET"}},
        )

        session = trace["sessions"][0]
        self.assertEqual(session["hit_turn"], 3)
        self.assertFalse(session["turns"][0]["scored_hit"])
        self.assertFalse(session["turns"][1]["scored_hit"])
        self.assertTrue(session["turns"][2]["scored_hit"])

    def test_parse_sample_ids_rejects_empty_and_duplicate_values(self) -> None:
        self.assertEqual(parse_sample_ids("public_0001, public_0002"), ["public_0001", "public_0002"])
        with self.assertRaisesRegex(ValueError, "at least one"):
            parse_sample_ids(",")
        with self.assertRaisesRegex(ValueError, "duplicates"):
            parse_sample_ids("public_0001,public_0001")

    def test_ranking_comparison_reports_rank_one_advantages(self) -> None:
        diagnostics = {
            "ranking_candidates": [
                {
                    "parent_asin": "FIRST",
                    "returned_rank": 1,
                    "total_score": 7.0,
                    "retrieval_score": 0.4,
                    "budget_adjustment": 0.0,
                    "attribute_contributions": {
                        "category": [{"contribution": 6.0}],
                    },
                    "feature_phrase_bonus": 0.0,
                    "popularity_contribution": 0.5,
                    "rating_contribution": 0.1,
                    "semantic_rank": 1,
                    "semantic_score": 2.5,
                },
                {
                    "parent_asin": "TARGET",
                    "returned_rank": 2,
                    "total_score": 6.5,
                    "retrieval_score": 0.3,
                    "budget_adjustment": 0.0,
                    "attribute_contributions": {
                        "category": [{"contribution": 6.0}],
                    },
                    "feature_phrase_bonus": 0.0,
                    "popularity_contribution": 0.15,
                    "rating_contribution": 0.05,
                    "semantic_rank": 2,
                    "semantic_score": 1.5,
                },
            ]
        }

        comparison = ranking_comparison(diagnostics, "TARGET")

        self.assertIsNotNone(comparison)
        self.assertEqual(comparison["target_rank"], 2)
        self.assertEqual(comparison["rank_one_parent_asin"], "FIRST")
        self.assertAlmostEqual(comparison["total_score_gap"], 0.5)
        self.assertAlmostEqual(comparison["unexplained_score_gap"], 0.0)
        self.assertAlmostEqual(
            comparison["component_gaps"]["popularity_contribution"],
            0.35,
        )
        self.assertEqual(comparison["semantic_evidence"]["target_rank"], 2)
        self.assertAlmostEqual(comparison["semantic_evidence"]["score_gap"], 1.0)


if __name__ == "__main__":
    unittest.main()
