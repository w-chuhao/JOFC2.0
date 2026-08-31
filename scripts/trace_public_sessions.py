"""Run a small public-set evaluation subset and save its full dialogue trace."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluator.local_evaluator import (
    MAX_TURNS,
    TOP_K,
    catalog_index,
    coarse_category,
    customer_reply,
    initial_message,
    load_jsonl,
    materialize_hidden_fields,
    normalize_recommendations,
)
from starter.agent import Agent


SCENARIO_ORDER = ("buying", "browsing", "intent_override", "boundary")
DEFAULT_SCENARIO_COUNTS = {
    "buying": 30,
    "browsing": 30,
    "intent_override": 10,
    "boundary": 10,
}
DEFAULT_OUTPUT = Path("outputs/public_prompt_trace.json")


def _attribute_contribution_total(candidate: dict[str, Any]) -> float:
    contributions = candidate.get("attribute_contributions")
    if not isinstance(contributions, dict):
        return 0.0
    return sum(
        float(item.get("contribution", 0.0))
        for items in contributions.values()
        if isinstance(items, list)
        for item in items
        if isinstance(item, dict)
    )


def ranking_comparison(
    retrieval_diagnostics: object,
    target_parent_asin: str,
) -> dict[str, Any] | None:
    """Compare a public target with rank one using opt-in score diagnostics."""
    if not isinstance(retrieval_diagnostics, dict):
        return None
    candidates = retrieval_diagnostics.get("ranking_candidates")
    if not isinstance(candidates, list):
        return None
    valid_candidates = [item for item in candidates if isinstance(item, dict)]
    rank_one = next(
        (item for item in valid_candidates if item.get("returned_rank") == 1),
        None,
    )
    target = next(
        (
            item
            for item in valid_candidates
            if item.get("parent_asin") == target_parent_asin
        ),
        None,
    )
    if rank_one is None or target is None:
        return None

    component_names = (
        "retrieval_score",
        "budget_adjustment",
        "feature_phrase_bonus",
        "popularity_contribution",
        "rating_contribution",
    )
    component_gaps = {
        name: float(rank_one.get(name, 0.0)) - float(target.get(name, 0.0))
        for name in component_names
    }
    component_gaps["attribute_contribution"] = (
        _attribute_contribution_total(rank_one)
        - _attribute_contribution_total(target)
    )
    total_score_gap = (
        float(rank_one.get("total_score", 0.0))
        - float(target.get("total_score", 0.0))
    )
    explained_score_gap = sum(component_gaps.values())
    target_semantic_score = target.get("semantic_score")
    rank_one_semantic_score = rank_one.get("semantic_score")
    semantic_score_gap = None
    if isinstance(target_semantic_score, (int, float)) and isinstance(
        rank_one_semantic_score,
        (int, float),
    ):
        semantic_score_gap = rank_one_semantic_score - target_semantic_score
    return {
        "target_parent_asin": target_parent_asin,
        "target_rank": target.get("returned_rank"),
        "rank_one_parent_asin": rank_one.get("parent_asin"),
        "rank_one_total_score": rank_one.get("total_score"),
        "target_total_score": target.get("total_score"),
        "total_score_gap": total_score_gap,
        "explained_score_gap": explained_score_gap,
        "unexplained_score_gap": total_score_gap - explained_score_gap,
        "component_gaps": component_gaps,
        "semantic_evidence": {
            "target_rank": target.get("semantic_rank"),
            "rank_one_rank": rank_one.get("semantic_rank"),
            "target_score": target_semantic_score,
            "rank_one_score": rank_one_semantic_score,
            "score_gap": semantic_score_gap,
        },
    }


def select_samples(
    samples: list[dict[str, Any]],
    per_scenario: int | dict[str, int],
    sample_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Choose explicit samples, or an even deterministic scenario split."""
    by_id = {str(sample["sample_id"]): sample for sample in samples}
    if sample_ids:
        unknown_ids = [sample_id for sample_id in sample_ids if sample_id not in by_id]
        if unknown_ids:
            raise ValueError(f"Unknown sample IDs: {', '.join(unknown_ids)}")
        return [by_id[sample_id] for sample_id in sample_ids]

    selected: list[dict[str, Any]] = []
    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        by_scenario[str(sample["scenario_type"])].append(sample)
    for scenario in SCENARIO_ORDER:
        count = (
            per_scenario[scenario]
            if isinstance(per_scenario, dict)
            else per_scenario
        )
        choices = sorted(by_scenario[scenario], key=lambda sample: str(sample["sample_id"]))
        if len(choices) < count:
            raise ValueError(
                f"Dataset has only {len(choices)} {scenario} samples; "
                f"need {count}."
            )
        selected.extend(choices[:count])
    return selected


def trace_session(
    agent: Agent,
    sample: dict[str, Any],
    catalog_ids: set[str],
    categories: dict[str, list[str]],
    products: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Mirror one evaluator session while retaining every exchanged message."""
    sample_id = str(sample["sample_id"])
    target = str(sample["ground_truth"]["parent_asin"])
    agent.reset(f"trace_{sample_id}", sample["user_profile"])
    intent_card, behavior = materialize_hidden_fields(sample, products)
    effective_sample = {**sample, "intent_card": intent_card, "behavior": behavior}
    disclosed: set[str] = set()
    boundary_used = False
    override_applied = sample["scenario_type"] != "intent_override"
    user_message = initial_message(
        effective_sample,
        coarse_category(categories.get(target, [])),
        disclosed,
    )
    turns: list[dict[str, Any]] = []
    hit_turn: int | None = None
    best_rank: int | None = None

    for turn in range(1, MAX_TURNS + 1):
        agent_error: str | None = None
        try:
            response = agent.respond(f"trace_{sample_id}", user_message, turn, TOP_K)
        except Exception as error:  # Match evaluator failure handling while exposing it.
            response = {"message": "", "ask_attribute": None, "recommendations": []}
            agent_error = f"{type(error).__name__}: {error}"
        if not isinstance(response, dict) or not isinstance(response.get("message"), str):
            response = {"message": "", "ask_attribute": None, "recommendations": []}
            agent_error = agent_error or "Invalid agent response"

        ranked = normalize_recommendations(response.get("recommendations"), catalog_ids)
        target_rank = ranked.index(target) + 1 if target in ranked else None
        scored_hit = override_applied and target_rank is not None
        state = getattr(agent, "sessions", {}).get(f"trace_{sample_id}")
        state_snapshot = {
            "constraints": dict(getattr(state, "constraints", {})),
            "priorities": (
                state.constraint_priorities() if state is not None else {}
            ),
            "excluded_constraints": {
                attribute: sorted(values)
                for attribute, values in getattr(state, "excluded_constraints", {}).items()
                if values
            },
        }
        retrieval_diagnostics = getattr(state, "last_search_diagnostics", {})
        turns.append(
            {
                "turn": turn,
                "customer_prompt": user_message,
                "agent_message": response["message"],
                "ask_attribute": response.get("ask_attribute"),
                "recommendation_ids": ranked,
                "target_rank": target_rank,
                "scored_hit": scored_hit,
                "usage": response.get("usage"),
                "agent_error": agent_error,
                "state": state_snapshot,
                "retrieval": retrieval_diagnostics,
                "ranking_comparison": ranking_comparison(
                    retrieval_diagnostics,
                    target,
                ),
            }
        )
        if scored_hit:
            hit_turn = turn
            best_rank = target_rank
            break
        if turn == MAX_TURNS:
            break

        override = behavior.get("override") or {}
        if not override_applied and turn + 1 == int(override.get("turn", 3)):
            override_applied = True
            new_value = str(override.get("new_value", ""))
            if new_value:
                disclosed.add(new_value)
            user_message = str(
                override.get("message", "Actually, please ignore my earlier preference.")
            )
        else:
            user_message, boundary_used = customer_reply(
                effective_sample,
                response.get("ask_attribute"),
                disclosed,
                boundary_used,
            )

    return {
        "sample_id": sample_id,
        "scenario_type": sample["scenario_type"],
        "difficulty_bucket": sample.get("difficulty_bucket"),
        "target_parent_asin": target,
        "stop_reason": "hit" if hit_turn is not None else "max_turns",
        "hit_turn": hit_turn,
        "best_rank": best_rank,
        "turns": turns,
    }


def build_trace(
    agent: Agent,
    samples: list[dict[str, Any]],
    catalog_ids: set[str],
    categories: dict[str, list[str]],
    products: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sessions = [
        trace_session(agent, sample, catalog_ids, categories, products)
        for sample in samples
    ]
    return {
        "sample_count": len(sessions),
        "scenario_counts": dict(Counter(session["scenario_type"] for session in sessions)),
        "sessions": sessions,
    }


def print_trace(trace: dict[str, Any]) -> None:
    for session in trace["sessions"]:
        print(
            f"\n[{session['sample_id']}] {session['scenario_type']} "
            f"target={session['target_parent_asin']} "
            f"result={session['stop_reason']} rank={session['best_rank']}"
        )
        for turn in session["turns"]:
            print(f"  Turn {turn['turn']} customer: {turn['customer_prompt']}")
            print(f"  Turn {turn['turn']} agent: {turn['agent_message']}")
            print(
                f"    ask={turn['ask_attribute']} rank={turn['target_rank']} "
                f"recommendations={', '.join(turn['recommendation_ids'])}"
            )
            if turn["agent_error"]:
                print(f"    error={turn['agent_error']}")


def parse_sample_ids(raw_value: str | None) -> list[str] | None:
    if raw_value is None:
        return None
    sample_ids = [value.strip() for value in raw_value.split(",") if value.strip()]
    if not sample_ids:
        raise ValueError("--sample-ids must contain at least one ID.")
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("--sample-ids must not contain duplicates.")
    return sample_ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace public evaluator conversations.")
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument(
        "--per-scenario",
        type=int,
        help="Use an equal sample count for every scenario instead of the default 80-session mix.",
    )
    parser.add_argument("--sample-ids", help="Comma-separated public sample IDs.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.per_scenario is not None and args.per_scenario <= 0:
        parser.error("--per-scenario must be positive.")

    try:
        sample_ids = parse_sample_ids(args.sample_ids)
        selected_samples = select_samples(
            load_jsonl(args.dataset),
            args.per_scenario if args.per_scenario is not None else DEFAULT_SCENARIO_COUNTS,
            sample_ids,
        )
    except ValueError as error:
        parser.error(str(error))

    catalog_ids, categories, products = catalog_index(args.catalog)
    trace = build_trace(
        Agent(
            args.catalog,
            enable_llm=False,
            enable_ranking_diagnostics=True,
        ),
        selected_samples,
        catalog_ids,
        categories,
        products,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    print_trace(trace)
    print(f"\nSaved {trace['sample_count']} session traces to {args.output}.")


if __name__ == "__main__":
    main()
