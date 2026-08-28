from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from starter.agent import Agent
from starter.conversation_llm import TokenUsage
from starter.state import ALLOWED_ATTRIBUTES


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


class AgentConversationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        catalog_path = Path(self.temporary_directory.name) / "catalog.jsonl"
        catalog_path.write_text(
            "".join(json.dumps(row) + "\n" for row in CATALOG_ROWS),
            encoding="utf-8",
        )
        self.agent = Agent(catalog_path, enable_llm=False)

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
