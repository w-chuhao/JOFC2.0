from __future__ import annotations

from pathlib import Path

from starter.retrieval import CatalogRetriever

class Agent:
    """Evaluator entry point; Member 2 will add state before calling retrieval."""

    def __init__(self, catalog_path: str | Path = "data/catalog.jsonl") -> None:
        self.retriever = CatalogRetriever(catalog_path)
        self._sessions: set[str] = set()

    def reset(self, session_id: str, user_profile: dict) -> None:
        # The profile is anonymized and may be used for personalization.
        self._sessions.add(session_id)

    def respond(
        self,
        session_id: str,
        user_message: str,
        turn: int,
        top_k: int,
    ) -> dict:
        if session_id not in self._sessions:
            raise RuntimeError("reset must be called before respond")
        result = self.retriever.search(user_message, constraints={}, top_k=top_k)
        recommendations = [{"parent_asin": asin} for asin in result.recommendation_ids]
        return {
            "message": "Here are the closest matches I found.",
            "ask_attribute": None,
            "recommendations": recommendations,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }
