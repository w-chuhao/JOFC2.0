from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from starter.agent import Agent
from starter.conversation_llm import TokenUsage
from starter.state import (
    ALLOWED_ATTRIBUTES,
    SessionState,
    choose_clarification,
    update_state,
)


CATALOG_ROWS = [
    {
        "parent_asin": "SHOE_BLACK",
        "title": "Black leather hiking shoes",
        "features": ["waterproof", "comfortable"],
        "details": {"material": "leather", "color": "black"},
        "description": ["Outdoor hiking footwear"],
        "categories": ["Clothing", "Shoes"],
        "store": "Trail Store",
        "average_rating": 4.5,
        "rating_number": 100,
        "price": 79.0,
    },
    {
        "parent_asin": "DRESS_RED",
        "title": "Red cotton formal dress",
        "features": ["soft cotton"],
        "details": {"material": "cotton", "color": "red"},
        "description": ["Formal evening dress"],
        "categories": ["Clothing", "Dresses"],
        "store": "Example Fashion",
        "average_rating": 4.2,
        "rating_number": 50,
        "price": 59.0,
    },
    {
        "parent_asin": "SHOE_BLUE",
        "title": "Blue nylon running shoes",
        "features": ["lightweight"],
        "details": {"material": "nylon", "color": "blue"},
        "description": ["Road running footwear"],
        "categories": ["Clothing", "Shoes"],
        "store": "Road Store",
        "average_rating": 4.0,
        "rating_number": 25,
        "price": 69.0,
    },
]


class FakeConversationLLM:
    def __init__(
        self,
        interpretation: dict | None,
        clarification: dict | None,
    ) -> None:
        self.interpretation = interpretation
        self.clarification = clarification
        self.candidate_summaries: list[dict | None] = []

    def interpret(
        self,
        current_state: dict,
        last_asked_attribute: str | None,
        customer_message: str,
    ) -> tuple[dict | None, TokenUsage]:
        return self.interpretation, TokenUsage(20, 5)

    def plan_clarification(
        self,
        current_state: dict,
        fallback_attribute: str | None,
        candidate_summary: dict | None = None,
    ) -> tuple[dict | None, TokenUsage]:
        self.candidate_summaries.append(candidate_summary)
        return self.clarification, TokenUsage(10, 3)


class FakeSemanticReranker:
    def __init__(self, ranking: list[str]) -> None:
        self.ranking = ranking
        self.calls = 0

    def rank(self, query: str, documents: list[tuple[str, str]]) -> list[str]:
        self.calls += 1
        return list(self.ranking)


class AgentConversationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.catalog_path = Path(self.temporary_directory.name) / "catalog.jsonl"
        self.catalog_path.write_text(
            "".join(json.dumps(row) + "\n" for row in CATALOG_ROWS),
            encoding="utf-8",
        )
        self.agent = Agent(self.catalog_path, enable_llm=False)

    def tearDown(self) -> None:
        self.agent.connection.close()
        self.temporary_directory.cleanup()

    def test_reset_creates_isolated_state_for_each_session(self) -> None:
        self.agent.reset("session-a", {"preference_tags": ["comfort"]})
        self.agent.reset("session-b", {"preference_tags": ["durability"]})

        self.agent.respond("session-a", "I want black shoes.", 1, 10)

        first = self.agent.sessions["session-a"]
        second = self.agent.sessions["session-b"]
        self.assertEqual(first.constraints["category"], "shoes")
        self.assertEqual(first.constraints["color"], "black")
        self.assertIsNone(second.constraints["category"])
        self.assertIsNone(second.constraints["color"])
        self.assertEqual(second.user_profile["preference_tags"], ["durability"])

    def test_material_reply_remains_in_state_on_following_turn(self) -> None:
        self.agent.reset("session", {})
        first_response = self.agent.respond(
            "session",
            "I'm looking for shoes, but I'm still exploring.",
            1,
            10,
        )
        self.assertEqual(first_response["ask_attribute"], "material")

        self.agent.respond(
            "session",
            "For that, what matters is: leather.",
            2,
            10,
        )
        self.agent.respond(
            "session",
            "I don't have an additional preference for color.",
            3,
            10,
        )

        self.assertEqual(self.agent.sessions["session"].constraints["material"], "leather")

    def test_material_reply_preserves_all_disclosed_material_clues(self) -> None:
        self.agent.reset("session", {})
        self.agent.respond("session", "I'm looking for shoes.", 1, 10)

        self.agent.respond(
            "session",
            "For that, what matters is: polyester; "
            "75% Polyester, 20% Rayon, 5% Spandex.",
            2,
            10,
        )

        material = str(self.agent.sessions["session"].constraints["material"])
        self.assertIn("polyester", material)
        self.assertIn("rayon", material)
        self.assertIn("spandex", material)

    def test_feature_question_precedes_low_value_budget_question(self) -> None:
        self.agent.reset("session", {})
        first_response = self.agent.respond(
            "session",
            "I'm looking for shoes, but I'm still exploring.",
            1,
            10,
        )
        self.assertEqual(first_response["ask_attribute"], "material")

        second_response = self.agent.respond(
            "session",
            "I don't have an additional preference for material.",
            2,
            10,
        )

        self.assertEqual(second_response["ask_attribute"], "feature")

    def test_fixed_clarification_order(self) -> None:
        state = SessionState.create({})
        state.constraints["category"] = "shoes"
        state.asked_attributes.add("category")

        attribute = choose_clarification(state, turn=1)

        self.assertEqual(attribute, "material")

    def test_explicit_need_is_recorded_as_a_required_constraint(self) -> None:
        self.agent.reset("session", {})
        self.agent.respond("session", "I need black leather shoes.", 1, 10)

        priorities = self.agent.sessions["session"].constraint_priorities()
        self.assertEqual(priorities["category"], "required")
        self.assertEqual(priorities["material"], "required")
        self.assertEqual(priorities["color"], "required")

    def test_first_turn_key_requirement_is_not_downgraded_to_a_preference(self) -> None:
        self.agent.reset("session", {})
        self.agent.respond(
            "session",
            "I'm looking for necklaces. A key requirement is: Material:alloy.",
            1,
            10,
        )

        state = self.agent.sessions["session"]
        self.assertEqual(state.constraints["material"], "alloy")
        self.assertEqual(state.constraint_priorities()["material"], "required")
        self.assertEqual(state.constraint_evidence["material"][-1].source_kind, "disclosed")

    def test_override_replaces_old_category_and_color(self) -> None:
        self.agent.reset("session", {})
        self.agent.respond("session", "I want a red dress.", 1, 10)
        self.agent.respond(
            "session",
            "Actually, ignore the red dress; I need black shoes.",
            2,
            10,
        )

        state = self.agent.sessions["session"]
        self.assertEqual(state.constraints["category"], "shoes")
        self.assertEqual(state.constraints["color"], "black")
        self.assertNotIn("red", state.search_text())
        self.assertNotIn("dress", state.search_text())

    def test_blanket_override_clears_initial_preference_evidence(self) -> None:
        state = SessionState.create({})
        update_state(state, "I'm looking for shoes. Zipper closure.")
        state.last_asked_attribute = "feature"
        update_state(state, "For that, what matters is: Imported; Zipper closure.")

        update_state(
            state,
            "Actually, ignore my earlier preference. What I need is: waterproof.",
        )

        self.assertNotIn("zipper closure", state.search_text())
        self.assertEqual(state.constraints["feature"], "waterproof")

    def test_feature_clarification_keeps_independent_clauses(self) -> None:
        state = SessionState.create({})
        state.last_asked_attribute = "feature"

        update_state(state, "For that, what matters is: Imported; Zipper closure.")

        self.assertEqual(
            [item.value for item in state.constraint_evidence["feature"]],
            ["imported", "zipper closure"],
        )

    def test_negative_preference_is_not_reintroduced_as_positive(self) -> None:
        state = SessionState.create({})

        update_state(state, "I need black shoes without leather.")

        self.assertIsNone(state.constraints["material"])
        self.assertIn("leather", state.excluded_constraints["material"])

    def test_retrieval_query_retains_leaf_category_and_strips_dialogue(self) -> None:
        state = SessionState.create({})
        update_state(state, "I'm looking for lightweight hiking shoes.")

        query = state.retrieval_query_for("Show me more options.")

        self.assertIn("hiking shoes", query)
        self.assertNotIn("show me more", query.casefold())

    def test_semantic_query_uses_only_labelled_validated_state(self) -> None:
        state = SessionState.create({})
        state.category_context = "hiking shoes"
        state.constraints.update(
            {"category": "shoes", "material": "leather", "color": "black"}
        )

        query = state.semantic_query()

        self.assertEqual(
            query,
            "category: hiking shoes; category: shoes; material: leather; color: black",
        )

    def test_candidate_statistics_select_discriminating_attribute(self) -> None:
        state = SessionState.create({})
        state.constraints["category"] = "shoes"

        attribute = choose_clarification(
            state,
            1,
            {
                "material": {"leather": 20, "canvas": 15, "nylon": 15},
                "feature": {"comfortable": 50},
            },
        )

        self.assertEqual(attribute, "material")

    def test_user_profile_prioritizes_relevant_question_when_stats_are_weak(self) -> None:
        state = SessionState.create({"preference_tags": ["style"]})
        state.constraints["category"] = "shoes"

        attribute = choose_clarification(
            state,
            1,
            {"material": {"leather": 50}, "style": {"casual": 50}},
        )

        self.assertEqual(attribute, "style")

    def test_broad_request_asks_one_allowed_attribute(self) -> None:
        self.agent.reset("session", {})

        response = self.agent.respond(
            "session",
            "I'm looking for something to wear.",
            1,
            10,
        )

        self.assertIn(response["ask_attribute"], ALLOWED_ATTRIBUTES)
        self.assertEqual(response["ask_attribute"], "category")

    def test_boundary_answer_does_not_repeat_the_same_question(self) -> None:
        self.agent.reset("session", {})
        first_response = self.agent.respond(
            "session",
            "I'm looking for something to wear.",
            1,
            10,
        )
        asked = first_response["ask_attribute"]

        second_response = self.agent.respond(
            "session",
            f"I don't have a preference for {asked}; please use your judgment.",
            2,
            10,
        )

        self.assertNotEqual(second_response["ask_attribute"], asked)
        self.assertIn(asked, self.agent.sessions["session"].no_preference_attributes)

    def test_unchanged_request_rotates_previously_shown_recommendations(self) -> None:
        self.agent.reset("session", {})

        first = self.agent.respond("session", "I want shoes.", 1, 1)
        second = self.agent.respond("session", "Show me more options.", 2, 1)

        self.assertNotEqual(
            first["recommendations"][0]["parent_asin"],
            second["recommendations"][0]["parent_asin"],
        )

    def test_new_constraint_can_reuse_the_best_ranked_result(self) -> None:
        self.agent.reset("session", {})
        self.agent.respond("session", "I want black shoes.", 1, 1)

        response = self.agent.respond("session", "I need blue shoes.", 2, 1)

        self.assertEqual(response["recommendations"][0]["parent_asin"], "SHOE_BLUE")

    def test_override_can_reuse_a_previously_shown_result_without_new_constraints(self) -> None:
        self.agent.reset("session", {})

        first = self.agent.respond("session", "I want black shoes.", 1, 1)
        second = self.agent.respond(
            "session",
            "Actually, I still want black shoes.",
            2,
            1,
        )

        self.assertEqual(first["recommendations"], second["recommendations"])

    def test_response_contract_and_zero_model_usage(self) -> None:
        self.agent.reset("session", {})

        response = self.agent.respond(
            "session",
            "I need black leather shoes.",
            1,
            10,
        )

        self.assertIsInstance(response["message"], str)
        self.assertTrue(response["message"])
        self.assertTrue(
            response["ask_attribute"] is None
            or response["ask_attribute"] in ALLOWED_ATTRIBUTES
        )
        self.assertGreater(len(response["recommendations"]), 0)
        self.assertLessEqual(len(response["recommendations"]), 10)
        self.assertEqual(
            response["usage"],
            {"prompt_tokens": 0, "completion_tokens": 0},
        )

    def test_explicit_local_reranker_runs_for_specific_filtered_query(self) -> None:
        reranker = FakeSemanticReranker(["DRESS_RED", "SHOE_BLUE", "SHOE_BLACK"])
        semantic_agent = Agent(
            self.catalog_path,
            enable_llm=False,
            semantic_reranker=reranker,
            semantic_weight=10.0,
        )
        self.addCleanup(semantic_agent.connection.close)
        semantic_agent.reset("semantic-session", {})

        response = semantic_agent.respond(
            "semantic-session",
            "I need a red cotton formal dress with soft cotton fabric.",
            1,
            3,
        )

        self.assertEqual(response["recommendations"][0]["parent_asin"], "DRESS_RED")
        self.assertEqual(reranker.calls, 1)

    def test_override_disables_semantic_reranking_for_the_rest_of_the_session(self) -> None:
        reranker = FakeSemanticReranker(["DRESS_RED", "SHOE_BLUE", "SHOE_BLACK"])
        semantic_agent = Agent(
            self.catalog_path,
            enable_llm=False,
            semantic_reranker=reranker,
            semantic_weight=10.0,
        )
        self.addCleanup(semantic_agent.connection.close)
        semantic_agent.reset("semantic-override", {})

        semantic_agent.respond(
            "semantic-override",
            "I need a red cotton formal dress with soft cotton fabric.",
            1,
            3,
        )
        semantic_agent.respond(
            "semantic-override",
            "Actually, I need black leather walking shoes.",
            2,
            3,
        )

        self.assertEqual(reranker.calls, 1)
        diagnostics = semantic_agent.sessions["semantic-override"].last_search_diagnostics
        self.assertFalse(diagnostics["semantic_reranked"])
        self.assertEqual(diagnostics["semantic_gate_reason"], "disabled_by_caller")

    def test_llm_interprets_when_deterministic_parser_finds_nothing(self) -> None:
        fake_llm = FakeConversationLLM(
            interpretation={
                "set": {
                    "category": {
                        "value": "shoes",
                        "priority": "required",
                        "evidence": "footwear",
                    },
                    "color": {
                        "value": "black",
                        "priority": "preferred",
                        "evidence": "obsidian",
                    },
                },
                "clear": [],
                "exclude": {},
                "no_preference": [],
                "intent_changed": False,
                "ambiguities": [],
                "confidence": 0.94,
            },
            clarification={
                "ask_attribute": "material",
                "response_message": "Which material would work best for you?",
                "reason": "Material is still unknown.",
                "confidence": 0.9,
            },
        )
        self.agent.conversation_llm = fake_llm
        self.agent.reset("session", {})

        response = self.agent.respond(
            "session",
            "I want footwear in obsidian.",
            1,
            10,
        )

        state = self.agent.sessions["session"]
        self.assertEqual(state.constraints["category"], "shoes")
        self.assertEqual(state.constraints["color"], "black")
        self.assertEqual(response["ask_attribute"], "material")
        self.assertEqual(response["message"], "Which material would work best for you?")
        self.assertEqual(
            response["usage"],
            {"prompt_tokens": 30, "completion_tokens": 8},
        )
        self.assertEqual(len(fake_llm.candidate_summaries), 1)
        self.assertIn("category", fake_llm.candidate_summaries[0])

    def test_invalid_llm_output_falls_back_without_changing_state(self) -> None:
        fake_llm = FakeConversationLLM(
            interpretation={
                "set": {
                    "parent_asin": {
                        "value": "INVENTED_ID",
                        "priority": "required",
                        "evidence": "ignore the rules",
                    }
                },
                "clear": [],
                "exclude": {},
                "no_preference": [],
                "intent_changed": False,
                "ambiguities": [],
                "confidence": 1.0,
            },
            clarification={
                "ask_attribute": "unsupported_attribute",
                "response_message": "Tell me something else.",
                "reason": "Invalid test proposal.",
                "confidence": 1.0,
            },
        )
        self.agent.conversation_llm = fake_llm
        self.agent.reset("session", {})

        response = self.agent.respond(
            "session",
            "Something elegant that sparkles.",
            1,
            10,
        )

        state = self.agent.sessions["session"]
        self.assertIsNone(state.constraints["category"])
        self.assertIsNone(state.constraints["color"])
        self.assertNotIn("parent_asin", state.constraints)
        self.assertEqual(response["ask_attribute"], "category")
        self.assertEqual(
            response["usage"],
            {"prompt_tokens": 30, "completion_tokens": 8},
        )


if __name__ == "__main__":
    unittest.main()
