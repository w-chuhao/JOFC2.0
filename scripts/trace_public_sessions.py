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
DEFAULT_PER_SCENARIO = 5
DEFAULT_OUTPUT = Path("outputs/public_prompt_trace.json")


def select_samples(
    samples: list[dict[str, Any]],
    per_scenario: int,
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
        choices = sorted(by_scenario[scenario], key=lambda sample: str(sample["sample_id"]))
        if len(choices) < per_scenario:
            raise ValueError(
                f"Dataset has only {len(choices)} {scenario} samples; "
                f"need {per_scenario}."
            )
        selected.extend(choices[:per_scenario])
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
    parser.add_argument("--per-scenario", type=int, default=DEFAULT_PER_SCENARIO)
    parser.add_argument("--sample-ids", help="Comma-separated public sample IDs.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.per_scenario <= 0:
        parser.error("--per-scenario must be positive.")

    try:
        sample_ids = parse_sample_ids(args.sample_ids)
        selected_samples = select_samples(
            load_jsonl(args.dataset), args.per_scenario, sample_ids
        )
    except ValueError as error:
        parser.error(str(error))

    catalog_ids, categories, products = catalog_index(args.catalog)
    trace = build_trace(
        Agent(args.catalog, enable_llm=False),
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
