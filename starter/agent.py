from __future__ import annotations

import copy
import os
from pathlib import Path

from starter.local_reranker import LocalCrossEncoderReranker
from starter.retrieval import CatalogSearch, SemanticReranker
from starter.state import (
    OVERRIDE_RE,
    SessionState,
    choose_clarification,
    record_response,
    response_message,
    update_state,
)


class Agent:
    """Shopping agent with deterministic state and hybrid local retrieval."""

    def __init__(
        self,
        catalog_path: str | Path = "data/catalog.jsonl",
        *,
        semantic_reranker: SemanticReranker | None = None,
        enable_local_reranker: bool = True,
        semantic_weight: float | None = None,
        semantic_candidate_limit: int | None = None,
        semantic_min_score_gap: float | None = None,
        enable_ranking_diagnostics: bool = False,
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
        if semantic_min_score_gap is None:
            try:
                semantic_min_score_gap = float(
                    os.environ.get("LOCAL_RERANKER_MIN_SCORE_GAP", "0.3")
                )
            except ValueError:
                semantic_min_score_gap = 0.3
        self.retrieval = CatalogSearch(
            self.catalog_path,
            semantic_reranker=semantic_reranker,
            semantic_weight=semantic_weight,
            semantic_candidate_limit=semantic_candidate_limit,
            semantic_min_specific_constraints=semantic_min_specific_constraints,
            semantic_min_score_gap=semantic_min_score_gap,
            enable_ranking_diagnostics=enable_ranking_diagnostics,
        )
        self.connection = self.retrieval.connection
        self.sessions: dict[str, SessionState] = {}

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

        constraints_before = copy.deepcopy(state.constraints)
        override_seen_before = state.override_seen
        update_state(state, user_message)

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

        retrieval_query = state.retrieval_query_for(user_message)
        result = self.retrieval.search(
            query=retrieval_query,
            semantic_query=state.semantic_query(),
            constraints=retrieval_constraints,
            top_k=top_k,
            exclude_ids=exclude_ids,
            constraint_priorities=priorities,
            excluded_constraints=state.excluded_constraints,
            feature_evidence=feature_evidence,
            route=route,
            semantic_rerank_allowed=not state.override_seen,
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

        record_response(state, message, ask_attribute, recommendations)

        return {
            "message": message,
            "ask_attribute": ask_attribute,
            "recommendations": recommendations,
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
        }
