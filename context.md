# TechJam Project Context and Required Working Style

## Read this first

This repository is our submission for the **TechJam Conversational E-Commerce Search Challenge**. Before changing any code, read this file, `README.md`, `docs/agent_api_contract.json`, and `PROJECT_4_PLAN.md`.

The project deadline is **Tuesday, 1 September 2026, 12:00 PM SGT**. Treat Monday 10:00 AM as feature freeze: after then, make only bug fixes, tests, reproducibility, documentation, and demo changes.

## What we are building

Build one Python shopping agent that receives an anonymized customer profile and a customer message, asks useful single-attribute follow-up questions when needed, and returns up to ten catalog product IDs (`parent_asin`).

The evaluator ends a session when its hidden target product appears in the Top 10 or after ten turns. The target is unknown to the agent.

## Latest local evaluation (200 public sessions)

The following result was produced on `feature/retrieval-integration-v2` with:

```bash
DEEPSEEK_ENABLED=0 python3 -m evaluator.local_evaluator \
  --catalog ../catalog.jsonl \
  --dataset data/public_set.jsonl \
  --output /private/tmp/jofc-retrieval-integration-v2.json
```

It evaluates only the 200 released labelled development sessions. The final
competition evaluation uses separate private sessions, so this is evidence for
local development rather than a guaranteed final score.

| Metric | Latest result | Ideal score | What it measures |
|---|---:|---:|---|
| Sessions | 200 | N/A | Number of labelled public conversations evaluated. |
| Hit Rate@10 | 1.000 (200/200) | 1.000 (200/200) | Fraction of sessions where the target appears in the Top 10 on at least one turn. |
| MRR | 0.623800 | 1.000 | Ranking quality: rank 1 contributes 1, rank 2 contributes 0.5, rank 10 contributes 0.1, and a miss contributes 0. |
| MTTC | 1.735 turns | 1.000 turn | Mean first turn on which the target appears. Lower is better; a miss is assigned turn 11. |
| Efficiency | 0.9265 | 1.000 | Speed score calculated as `clip((11 - MTTC) / 10, 0, 1)`. |
| Recommended Technical Score | 0.872440 | 1.000 | Weighted overall score: `0.50 * Hit Rate@10 + 0.30 * MRR + 0.20 * Efficiency`. This is +0.038429 over the post-PR main result of 0.834011. |
| Reported LLM tokens | 0 prompt / 0 completion | No required perfect value | The run used deterministic retrieval/state fallbacks and made no LLM calls. Token use is reported for feasibility, not included in the Technical Score. |

| Scenario | Sessions | Hit Rate@10 | MRR | MTTC | Reading the result |
|---|---:|---:|---:|---:|---|
| Boundary | 10 | 1.000 | 0.790000 | 2.300 | All targets were found; boundary replies remain the slowest non-override group. |
| Browsing | 80 | 1.000 | 0.526627 | 1.3625 | All targets were found quickly; first-rank quality remains the largest opportunity. |
| Buying | 80 | 1.000 | 0.638080 | 1.325 | All targets were found, usually on the first or second turn. |
| Intent Override | 30 | 1.000 | 0.789444 | 3.633333 | All targets were found after deterministic preference replacement. |

For all scored metrics, higher is better except MTTC, where the best possible
value is turn 1. A perfect Technical Score is therefore 1.000.

The required evaluator-facing implementation is:

```text
starter/agent.py -> class Agent
```

The evaluator imports it directly with:

```python
from starter.agent import Agent
```

Do not build a UI, database server, PostgreSQL, pgvector deployment, or cloud service. The intended implementation is local and in-memory.

## Non-negotiable rules

- Do **not** modify `evaluator/`, `data/public_set.jsonl`, or `data/catalog.jsonl`. The evaluator is frozen; build companion scripts outside `evaluator/` for tracing, diagnostics, or local analysis.
- Treat every evaluator session as isolated. Use the supplied aggregate `user_profile` only as short-term session context; do not create cross-session user memory or profile persistence.
- Do not add spelling-correction or ASR-noise handling to the competition path: evaluator inputs are pre-cleaned text.
- Do **not** read public-session target labels from inside the agent or hard-code target ASINs.
- Do **not** invent product IDs. Every recommendation must be a real catalog `parent_asin`.
- Return at most ten distinct recommendations on every turn, including turns where a question is asked.
- `ask_attribute` must be exactly one of `category`, `material`, `color`, `size`, `style`, `brand`, `budget`, `feature`, `use_case`, `other`, or `None`/`null`.
- Never commit API keys, secrets, downloaded models, caches, or private data.
- An LLM is optional. Build and preserve a fully functional local BM25/state-based solution first.

## How the system should work

```text
Customer message + remembered session state
    -> propose a structured StateDelta (optional LLM or rules)
    -> validate StateDelta and update constraints
    -> detect and handle an intent override
    -> BM25 search plus state-aware filtering/reranking
    -> receive aggregate candidate-attribute statistics
    -> propose and validate one clarification question
    -> Top-10 valid parent_asin response
```

## End-to-end turn pipeline

The proposed Person 2 / Person 1 pipeline is:

1. The user sends a query.
2. Person 2's LLM interprets it as a structured `StateDelta`.
3. Person 2 validates the proposed delta and applies it to conversation state.
4. Person 1 searches and ranks the catalogue using the updated state.
5. Person 1 returns the Top 10 product IDs and candidate attribute statistics.
6. Person 2's LLM proposes the most useful allowed `ask_attribute`.
7. Person 2 validates the clarification proposal.
8. The agent returns the Top 10 product IDs, a clarifying question, and the validated `ask_attribute`.

When the customer answers, repeat from step 2 using the existing session state:

```text
Customer answer -> update state -> search again -> ask the next useful question
```

Both LLM outputs are proposals only. Deterministic code owns validation, state mutation, catalogue access, product IDs, and the final evaluator-facing response. If the LLM or candidate statistics are unavailable, preserve the deterministic fallback.

The starter's SQLite FTS5/BM25 index is a useful base, not disposable code. Improve it through better query construction, filtering, and transparent reranking.

## Current retrieval implementation and remaining validation

The agent now rotates results across turns, represents required/preferred/excluded constraints explicitly, applies exclusions inside retrieval, preserves stable leaf-category query context, uses catalog aliases, and returns expanded candidate statistics. Clarification uses those statistics when they provide useful separation, then falls back to user-profile hints and the fixed deterministic order. Generic clues such as `cotton`, `polyester`, and `Imported` are still weak discriminators, so ranking quality and unseen-session robustness remain the main risks.

The implemented retrieval paths are:

- **Buying:** precision-oriented scoring with required constraints at full weight, excluded-match rejection, exact feature-phrase bonuses, and constraint-aware reranking. Candidate construction remains inclusive; it does not use a strict all-term (AND) query route.
- **Browsing:** broader multi-route BM25 candidates, result diversification, and the same validated clarification policy.
- **Both routes:** a modest rating/popularity tie-break decays as more products are shown, while retrieval diagnostics remain available for tracing.

### Rejected retrieval experiments (29 August 2026)

The earlier public-set ablation tested candidate-statistics-driven clarification selection and a strict Buying-only BM25 AND route for two or more required values. The strict AND route remains rejected. Candidate statistics were later integrated with stable category queries, override-safe state, and the decaying tie-break; the combined configuration improved the measured result to `0.872440`.

| Configuration | Hit Rate@10 | MRR | MTTC | Technical Score |
|---|---:|---:|---:|---:|
| Fixed clarification only | 0.985 | 0.589452 | 3.240 | 0.824536 |
| Strict Buying AND route disabled only | 0.990 | 0.613825 | 3.990 | 0.819348 |
| Both additions disabled (chosen) | 0.995 | 0.600369 | 3.180 | 0.834011 |

Do not reintroduce the strict AND route without a new controlled ablation that improves the overall Technical Score without an unacceptable Hit Rate@10 or MTTC regression. It modestly improved MRR in isolation but lengthened conversations enough to reduce the composite score.

Person 1 should now prioritize evaluation and careful tuning rather than adding unmeasured complexity:

- Measure each route with the public evaluator, scenario metrics, trace output, latency, and cross-turn uniqueness.
- Report every change's overall and scenario-level evaluation results to the team. Whether to retain or revert a change is a team decision; record the decision and its rationale in the team metrics log.
- Keep popularity as a modest, decaying tie-breaker; do not let it override validated constraints, and do not add typo correction because evaluator inputs are pre-cleaned.

Evaluate each improvement using HR@10, MRR, MTTC, cross-turn uniqueness, latency, and paraphrased or unseen edge cases to avoid overfitting the 200 public sessions.

Keep a session state for each `session_id`, containing at least the user profile, constraints, history, and last asked attribute. When a customer changes their mind (for example, "Actually, not boots; I need sandals"), replace conflicting old constraints instead of accumulating both.

An LLM is optional and may only act as a **planner**. It may propose a JSON `StateDelta` and a clarification question. It must not generate, select, or rank `parent_asin` values. Validate all planner output in code and fall back to deterministic extraction/question rules on missing credentials, errors, timeouts, or invalid output.

## Shared technical contract

Use this interface between conversation logic and retrieval logic:

```python
search(
    query: str,
    constraints: dict,
    top_k: int,
    *,
    exclude_ids: set[str] | None = None,
    constraint_priorities: dict[str, str] | None = None,
    excluded_constraints: dict[str, set[str]] | None = None,
    route: str = "browsing",
) -> SearchResult
```

`constraints` uses the keys:

```python
{
    "category": None,
    "material": None,
    "color": None,
    "size": None,
    "style": None,
    "brand": None,
    "budget": None,
    "feature": None,
    "use_case": None,
}
```

`SearchResult` contains:

```python
{
    "recommendation_ids": ["B000..."],  # real parent_asin values, best first
    "candidate_attribute_stats": {
        "category": {"earrings": 32, "necklaces": 11},
        "material": {"stainless steel": 18, "fabric": 9},
        "brand": {"example brand": 6},
        "feature": {"lightweight": 12},
    },
    "diagnostics": {"candidate_count": 800, "route": "browsing"},
}
```

The final evaluator response uses only `recommendation_ids`. Candidate statistics are aggregate data used to choose a high-value follow-up question; they are not product recommendations.

## Team ownership

- **Person 1:** retrieval, BM25, attribute-aware filters/reranking, valid Top-10 IDs.
- **Person 2:** session state, attribute extraction, clarification policy, intent overrides, response assembly.
- **Person 3:** evaluator metrics, response-contract tests, regression analysis, reproducibility, README/Devpost/demo evidence.

All contributors write tests and participate in daily integration. See `PROJECT_4_WORKLOAD_SPLIT.md` for detailed deliverables and deadlines.

## Required workflow for every code change

1. Pull/read the latest work before editing. Keep changes focused on one responsibility.
2. Preserve the `Agent.reset()` and `Agent.respond()` contract.
3. Add or update a test when changing retrieval, state, response formatting, or error handling.
4. Run the official evaluator from the repository root. To append the result,
   tester, and timestamp to `outputs/evaluation_history.json`, use the tracker
   wrapper:

   ```powershell
   python scripts/run_evaluation.py --tested-by "Member 1" --note "Describe the change tested"
   ```

5. Inspect `results.json` and the newly appended history entry. Record Hit Rate@10, MRR, MTTC, TechnicalScore, and scenario-specific changes in the team metrics log.
6. Report whether the change works reliably, including its overall and scenario-level metric impact. The team decides whether to retain or revert it and records the rationale in the team metrics log. Do not trade away another scenario without explicit team agreement.
7. Commit small, working changes with a clear message. Integrate daily around 18:00 SGT.

## Evaluation facts

- The 200 sessions in `data/public_set.jsonl` are for local development/evaluation only.
- The organisers use 800 different private sessions for final evaluation.
- The starter benchmark is Hit Rate@10 `0.125`, MRR `0.068034`, MTTC `9.81`.
- A correct target in the Top 10 ends that session immediately. Early accurate recommendations are valuable.
- The evaluator simulates customer replies based on the attribute requested in `ask_attribute`; it is not a human user or a second shopping agent.

## End-to-end turn pipeline

The proposed Person 2 / Person 1 pipeline is:

1. The user sends a query.
2. Person 2's LLM interprets it as a structured `StateDelta`.
3. Person 2 validates the proposed delta and applies it to conversation state.
4. Person 1 searches and ranks the catalogue using the updated state.
5. Person 1 returns the Top 10 product IDs and candidate attribute statistics.
6. Person 2's LLM proposes the most useful allowed `ask_attribute`.
7. Person 2 validates the clarification proposal.
8. The agent returns the Top 10 product IDs, a clarifying question, and the validated `ask_attribute`.

When the customer answers, repeat from step 2 using the existing session state:

```text
Customer answer -> update state -> search again -> ask the next useful question
```

Both LLM outputs are proposals only. Deterministic code owns validation, state mutation, catalogue access, product IDs, and the final evaluator-facing response. If the LLM or candidate statistics are unavailable, preserve the deterministic fallback.

## Before declaring work complete

- Run `python -m evaluator.local_evaluator` successfully.
- Confirm returned IDs are valid, unique, and no more than ten.
- Confirm Buying, Browsing, Intent Override, and Boundary behaviours still work.
- Ensure no secrets or generated heavy files are staged.
- Report the change, test evidence, metrics impact, and any limitation to the team.
