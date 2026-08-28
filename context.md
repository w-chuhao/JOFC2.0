# TechJam Project Context and Required Working Style

## Read this first

This repository is our submission for the **TechJam Conversational E-Commerce Search Challenge**. Before changing any code, read this file, `README.md`, `docs/agent_api_contract.json`, and `PROJECT_4_PLAN.md`.

The project deadline is **Tuesday, 1 September 2026, 12:00 PM SGT**. Treat Monday 10:00 AM as feature freeze: after then, make only bug fixes, tests, reproducibility, documentation, and demo changes.

## What we are building

Build one Python shopping agent that receives an anonymized customer profile and a customer message, asks useful single-attribute follow-up questions when needed, and returns up to ten catalog product IDs (`parent_asin`).

The evaluator ends a session when its hidden target product appears in the Top 10 or after ten turns. The target is unknown to the agent.

## Latest local evaluation (200 public sessions)

The following result was produced locally with:

```powershell
python -m evaluator.local_evaluator --output results.json
```

It evaluates only the 200 released labelled development sessions. The final
competition evaluation uses separate private sessions, so this is evidence for
local development rather than a guaranteed final score.

| Metric | Latest result | Ideal score | What it measures |
|---|---:|---:|---|
| Sessions | 200 | N/A | Number of labelled public conversations evaluated. |
| Hit Rate@10 | 0.925 (185/200) | 1.000 (200/200) | Fraction of sessions where the target appears in the Top 10 on at least one turn. |
| MRR | 0.579095 | 1.000 | Ranking quality: rank 1 contributes 1, rank 2 contributes 0.5, rank 10 contributes 0.1, and a miss contributes 0. |
| MTTC | 3.670 turns | 1.000 turn | Mean first turn on which the target appears. Lower is better; a miss is assigned turn 11. |
| Efficiency | 0.733 | 1.000 | Speed score calculated as `clip((11 - MTTC) / 10, 0, 1)`. |
| Recommended Technical Score | 0.782829 | 1.000 | Weighted overall score: `0.50 * Hit Rate@10 + 0.30 * MRR + 0.20 * Efficiency`. |
| Reported LLM tokens | 0 prompt / 0 completion | No required perfect value | The run used deterministic retrieval/state fallbacks and made no LLM calls. Token use is reported for feasibility, not included in the Technical Score. |

| Scenario | Sessions | Hit Rate@10 | MRR | MTTC | Reading the result |
|---|---:|---:|---:|---:|---|
| Boundary | 10 | 1.000 | 0.831111 | 4.300 | Every target was found; ranking was strong, though some answers arrived later in the dialogue. |
| Browsing | 80 | 0.950 | 0.587192 | 3.275 | Strongest regular-use coverage: 76 of 80 targets were found. |
| Buying | 80 | 0.900 | 0.509469 | 3.500 | 72 of 80 targets were found; this is the main ranking-quality opportunity. |
| Intent Override | 30 | 0.900 | 0.659167 | 4.966667 | 27 of 30 targets were found and ranked well, but preference changes take longer to resolve. |

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

- Do **not** modify `evaluator/`, `data/public_set.jsonl`, or `data/catalog.jsonl`.
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

## TODO: Person 1 - improving catalogue retrieval

The current system misses 20 of 200 targets, mainly because of ranking rather than retrieval: every missed target entered the candidate pool, and 12 reached ranks 11-20. Generic clues such as `cotton`, `polyester`, and `Imported` are insufficient to distinguish similar products, while repeated recommendations limit exploration.

Person 1 should prioritize:

- Rotating recommendations across turns while resetting appropriately after intent overrides. A diagnostic rotation test improved HR@10 from `0.900` to `0.990`.
- Treating required, preferred, excluded, and unknown attributes differently during filtering and ranking.
- Giving more weight to distinctive leaf-category, title, brand, material, and feature matches.
- Providing candidate statistics so Person 2 can ask the attribute that best narrows the results.
- Testing synonyms, typo tolerance, semantic fallback, and a modest popularity tie-breaker.

Evaluate each improvement using HR@10, MRR, MTTC, cross-turn uniqueness, latency, and paraphrased or unseen edge cases to avoid overfitting the 200 public sessions.

Keep a session state for each `session_id`, containing at least the user profile, constraints, history, and last asked attribute. When a customer changes their mind (for example, "Actually, not boots; I need sandals"), replace conflicting old constraints instead of accumulating both.

An LLM is optional and may only act as a **planner**. It may propose a JSON `StateDelta` and a clarification question. It must not generate, select, or rank `parent_asin` values. Validate all planner output in code and fall back to deterministic extraction/question rules on missing credentials, errors, timeouts, or invalid output.

## Shared technical contract

Use this interface between conversation logic and retrieval logic:

```python
search(query: str, constraints: dict, top_k: int) -> SearchResult
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
    },
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
   tester, and timestamp to `metrics/evaluation_history.json`, use the tracker
   wrapper:

   ```powershell
   python scripts/run_evaluation.py --tested-by "Member 1" --note "Describe the change tested"
   ```

5. Inspect `results.json` and the newly appended history entry. Record Hit Rate@10, MRR, MTTC, TechnicalScore, and scenario-specific changes in the team metrics log.
6. Keep a change only if it works reliably and improves the score or fixes a required behaviour. Do not trade away another scenario without explicit team agreement.
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
