from __future__ import annotations

import copy
import os
from pathlib import Path

from starter import state
from starter.conversation_llm import (
    ConversationLLM,
    DeepSeekConversationLLM,
    TokenUsage,
)
from starter.local_reranker import LocalCrossEncoderReranker
from starter.retrieval import CatalogSearch, SemanticReranker
from starter.state import (
    OVERRIDE_RE,
    SessionState,
    apply_llm_state_delta,
    choose_clarification,
    record_response,
    response_message,
    state_for_llm,
    update_state,
    validated_llm_clarification,
)


class Agent:
    """Hybrid shopping agent with deterministic retrieval and LLM-safe state."""

    def __init__(
        self,
        catalog_path: str | Path = "data/catalog.jsonl",
        *,
        conversation_llm: ConversationLLM | None = None,
        enable_llm: bool = True,
        semantic_reranker: SemanticReranker | None = None,
        enable_local_reranker: bool = True,
        semantic_weight: float | None = None,
        semantic_candidate_limit: int | None = None,
    ) -> None:
        self.catalog_path = Path(catalog_path)
        project_root = Path(__file__).resolve().parents[1]
        if semantic_reranker is None and enable_local_reranker:
            try:
                semantic_reranker = LocalCrossEncoderReranker.from_environment(
                    project_root
                )
            except Exception:
                semantic_reranker = None
        if semantic_weight is None:
            try:
                semantic_weight = float(
                    os.environ.get("LOCAL_RERANKER_WEIGHT", "0.35")
                )
            except ValueError:
                semantic_weight = 0.35
        if semantic_candidate_limit is None:
            try:
                semantic_candidate_limit = int(
                    os.environ.get("LOCAL_RERANKER_CANDIDATES", "20")
                )
            except ValueError:
                semantic_candidate_limit = 20
        try:
            semantic_min_specific_constraints = int(
                os.environ.get("LOCAL_RERANKER_MIN_CONSTRAINTS", "2")
            )
        except ValueError:
            semantic_min_specific_constraints = 2
        self.retrieval = CatalogSearch(
            self.catalog_path,
            semantic_reranker=semantic_reranker,
            semantic_weight=semantic_weight,
            semantic_candidate_limit=semantic_candidate_limit,
            semantic_min_specific_constraints=semantic_min_specific_constraints,
        )
        self.connection = self.retrieval.connection
        self.sessions: dict[str, SessionState] = {}
        if not enable_llm:
            self.conversation_llm = None
        elif conversation_llm is not None:
            self.conversation_llm = conversation_llm
        else:
            self.conversation_llm = DeepSeekConversationLLM.from_environment(
                project_root
            )

    def reset(self, session_id: str, user_profile: dict) -> None:
        self.sessions[session_id] = SessionState.create(user_profile)

    @staticmethod
    def _shown_recommendation_ids(state: SessionState) -> set[str]:
        """Return IDs shown before the current turn for result diversification."""
        return {
            parent_asin
            for item in state.history
            if item.get("role") == "assistant"
            for parent_asin in item.get("recommendations", [])
            if isinstance(parent_asin, str)
        }

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
        constraints_before = copy.deepcopy(state.constraints)
        override_seen_before = state.override_seen
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

        constraints_changed = constraints_before != state.constraints
        override_applied = (
            OVERRIDE_RE.search(user_message) is not None
            or (state.override_seen and not override_seen_before)
        )
        exclude_ids = (
            set()
            if constraints_changed or override_applied
            else self._shown_recommendation_ids(state)
        )
        priorities = state.constraint_priorities()
        feature_evidence = [
            (str(item.value), item.source_kind)
            for item in state.constraint_evidence["feature"]
        ]
        if feature_evidence:
            priorities["feature"] = self.retrieval.feature_priority(feature_evidence)
        route = (
            "buying"
            if any(
                attribute not in {"category"} and priority == "required"
                for attribute, priority in priorities.items()
            )
            else "browsing"
        )

        retrieval_constraints = copy.deepcopy(state.constraints)
        if state.category_context and retrieval_constraints.get("category"):
            retrieval_constraints["category"] = state.category_context

        result = self.retrieval.search(
            query=state.retrieval_query_for(user_message),
            constraints=retrieval_constraints,
            top_k=top_k,
            exclude_ids=exclude_ids,
            constraint_priorities=priorities,
            excluded_constraints=state.excluded_constraints,
            feature_evidence=feature_evidence,
            route=route,
        )
        state.last_search_diagnostics = result.diagnostics
        recommendations = [
            {"parent_asin": parent_asin}
            for parent_asin in result.recommendation_ids
        ]
        ask_attribute = choose_clarification(
            state,
            turn,
            result.candidate_attribute_stats,
        )
        message = response_message(ask_attribute)

        if self.conversation_llm is not None:
            try:
                clarification, clarification_usage = (
                    self.conversation_llm.plan_clarification(
                        current_state=state_for_llm(state),
                        fallback_attribute=ask_attribute,
                        candidate_summary=result.candidate_attribute_stats,
                    )
                )
                usage += clarification_usage
                validated = validated_llm_clarification(
                    state,
                    turn,
                    ask_attribute,
                    clarification,
                    allow_attribute_override=True,
                )
                if validated is not None:
                    ask_attribute, message = validated
            except Exception:
                pass

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
