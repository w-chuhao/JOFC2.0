from __future__ import annotations

from pathlib import Path

from starter.retrieval import CatalogSearch
from starter.state import (
    SessionState,
    choose_clarification,
    record_response,
    response_message,
    update_state,
)


class Agent:
    """Local BM25 agent with deterministic per-session conversation state."""

    def __init__(self, catalog_path: str | Path = "data/catalog.jsonl") -> None:
        self.catalog_path = Path(catalog_path)
        self.retrieval = CatalogSearch(self.catalog_path)
        self.connection = self.retrieval.connection
        self.sessions: dict[str, SessionState] = {}

    def reset(self, session_id: str, user_profile: dict) -> None:
        self.sessions[session_id] = SessionState.create(user_profile)

    def respond(
        self,
        session_id: str,
        user_message: str,
        turn: int,
        top_k: int,
    ) -> dict:
        try:
            state = self.sessions[session_id]
        except KeyError as error:
            raise RuntimeError("reset must be called before respond") from error

        update_state(state, user_message)
        parent_asins = self.retrieval.search(
            query=user_message,
            constraints=state.constraints,
            top_k=top_k,
        )
        recommendations = [
            {"parent_asin": parent_asin}
            for parent_asin in parent_asins
        ]
        ask_attribute = choose_clarification(state, turn)
        message = response_message(ask_attribute)
        record_response(state, message, ask_attribute, recommendations)

        return {
            "message": message,
            "ask_attribute": ask_attribute,
            "recommendations": recommendations,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }
