from __future__ import annotations

from pathlib import Path

from starter.conversation_llm import (
    ConversationLLM,
    DeepSeekConversationLLM,
    TokenUsage,
)
from starter.retrieval import CatalogSearch
from starter.state import (
    SessionState,
    apply_llm_state_delta,
    choose_clarification,
    record_response,
    response_message,
    state_for_llm,
    update_state,
)


class Agent:
    """Hybrid shopping agent with deterministic retrieval and LLM-safe state."""

    def __init__(
        self,
        catalog_path: str | Path = "data/catalog.jsonl",
        *,
        conversation_llm: ConversationLLM | None = None,
        enable_llm: bool = True,
    ) -> None:
        self.catalog_path = Path(catalog_path)
        self.retrieval = CatalogSearch(self.catalog_path)
        self.connection = self.retrieval.connection
        self.sessions: dict[str, SessionState] = {}
        if not enable_llm:
            self.conversation_llm = None
        elif conversation_llm is not None:
            self.conversation_llm = conversation_llm
        else:
            project_root = Path(__file__).resolve().parents[1]
            self.conversation_llm = DeepSeekConversationLLM.from_environment(
                project_root
            )

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

        usage = TokenUsage()
        handled = update_state(state, user_message)

        llm_delta: dict | None = None
        if self.conversation_llm is not None and not handled:
            try:
                llm_delta, interpretation_usage = self.conversation_llm.interpret(
                    current_state=state_for_llm(state),
                    last_asked_attribute=state.last_asked_attribute,
                    customer_message=user_message,
                )
                usage += interpretation_usage
            except Exception:
                llm_delta = None
        if llm_delta is not None:
            apply_llm_state_delta(state, user_message, llm_delta)

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
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
            },
        }
