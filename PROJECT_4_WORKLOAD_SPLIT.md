# Detailed and Balanced Workload Split - Three-Person Team

## The team goal

Build one reliable `Agent` in `starter/agent.py` that beats the supplied BM25 baseline, works across Buying, Browsing, Intent Override, and Boundary sessions, and is ready to submit by **Tuesday, 1 September, 12:00 PM SGT**.

The work is split into three equally important technical tracks:

```text
Person 1: Find relevant products
Person 2: Understand and remember the customer
Person 3: Prove the agent works and improve it from evidence
```

Each person writes code, tests their work, joins daily integration, and contributes to the final README/demo. Documentation is not assigned as a separate "lighter" job.

## Shared interface - agree on this first

Before anyone makes a large change, agree on the data passed between the retrieval and conversation parts:

```python
constraints = {
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

search(query: str, constraints: dict, top_k: int) -> list[str]
```

The return value is a list of real catalog `parent_asin` strings, in ranking order. Do not return product titles or full catalog objects to the evaluator.

## Person 1 - Retrieval and ranking engineer

### Main responsibility

Turn the catalog and the latest customer requirements into a strong, valid Top-10 recommendation list.

### Code ownership

- `starter/retrieval.py`, if created, or the retrieval-related methods in `starter/agent.py`.
- Product text normalisation and in-memory SQLite FTS5/BM25 index.
- Candidate retrieval, filtering, rescoring, de-duplication, and ranking.

### Tasks

1. Understand the existing BM25 starter code and confirm which fields are indexed: title, categories, features, details, store, and description.
2. Extract the current SQL query into a reusable `search()` function matching the shared interface.
3. Use customer constraints to strengthen the query and/or rerank results:
   - large boost for category matches;
   - strong boost for directly requested material or brand;
   - moderate boost for colour, size, style, feature, and use case;
   - penalty for clear conflicts, such as a different category after an override.
4. Ensure outputs are unique, real catalog IDs and contain no more than `top_k` recommendations.
5. Keep a simple BM25-only fallback; do not make the entire agent depend on a downloaded model or external service.
6. If the local agent is stable by Sunday, optionally test semantic candidate retrieval. It must be in-memory and must be compared with BM25 using the official evaluator.

### Tests to write

- A search for "lightweight stainless steel hoop earrings" returns ten valid unique IDs.
- Adding `material="leather"` changes the ranking toward leather products.
- Adding a category constraint prevents unrelated product categories from dominating.
- Empty/broad queries do not crash and return valid output.

### Deliverables

| Deadline | Deliverable |
|---|---|
| Thu 18:00 | `search()` interface agreed and a BM25-only version callable by Person 2. |
| Fri 18:00 | Constraint-aware ranking and tests committed. |
| Sat 12:00 | Retrieval is integrated into the evaluator-facing `Agent`. |
| Sun 18:00 | Optional semantic experiment results or a documented decision not to add it. |

## Person 2 - Conversation and decision engineer

### Main responsibility

Make the agent behave like a useful shopping assistant across multiple turns: remember answers, ask the right question, and abandon old preferences after a change of mind.

### Code ownership

- `starter/state.py`, if created, or state/decision-related methods in `starter/agent.py`.
- Per-session state created in `Agent.reset()`.
- Message parsing, constraint updates, override handling, clarification policy, and final response assembly.

### Tasks

1. Create a session-state dictionary keyed by `session_id`. Store `user_profile`, constraints, message history, and last asked attribute.
2. Write lightweight extraction rules for catalogue-relevant attributes: category, material, colour, size, style, brand, budget, feature, and use case.
3. Merge new information into state. If the evaluator replies "For that, what matters is: cotton", remember `material="cotton"` for later turns.
4. Detect overrides using language such as "actually", "instead", "ignore", "not", and "rather". Clear/rewrite the old conflicting state instead of accumulating impossible requirements.
5. Choose at most one useful `ask_attribute` each turn. For a broad message, ask category first; then ask the most valuable missing constraint. Use `null` when asking is not useful.
6. Call Person 1's `search()` on every turn and return its IDs alongside the question. Never return a question alone.
7. Keep the exact required response format, including `usage` values. For a no-LLM implementation, report zero tokens.

### Tests to write

- `reset()` creates isolated state for two different sessions.
- A material response remains in state on the following turn.
- "Actually, ignore the red dress; I need black shoes" removes/replaces old category and colour assumptions.
- A broad request asks an allowed attribute.
- A response includes a string `message`, valid `ask_attribute`, recommendations, and non-negative token counts.

### Deliverables

| Deadline | Deliverable |
|---|---|
| Thu 18:00 | State schema and shared constraints contract agreed. |
| Fri 18:00 | State update, basic questions, and response-format tests committed. |
| Sat 12:00 | Intent Override and Boundary behaviour integrated with Person 1's search. |
| Sun 18:00 | Test cases cover all four scenario types. |

## Person 3 - Evaluation, quality, and experiment engineer

### Main responsibility

Make improvements measurable, catch regressions before they reach submission, and turn evaluator evidence into the team’s next technical decision. This is a coding and analysis role, not merely documentation.

### Code ownership

- `tests/` additions and any safe analysis helpers outside `evaluator/`.
- A metrics/experiment log.
- Response-validation helper tests, reproducibility checks, error analysis, final metrics table, README/evidence, and demo script.

### Tasks

1. Preserve the starting baseline results, then maintain a metrics log with date, Git commit, change, Hit Rate@10, MRR, MTTC, TechnicalScore, and scenario notes.
2. Run `python -m evaluator.local_evaluator` after every merged change. Compare overall and scenario metrics with the previous best result.
3. Build tests for response validity and reliability:
   - at most ten recommendations;
   - no duplicate IDs;
   - every returned ID exists in the catalog;
   - `ask_attribute` is allowed or `null`;
   - failure or empty input does not crash the agent.
4. Read `results.json` after each run, group misses by scenario type, and identify specific failure patterns for Persons 1 and 2. Examples: category mismatch, forgotten answer, bad override, weak vague-query result.
5. Create small local test fixtures for important conversation behaviours. Do not alter the evaluator, catalog, or public session labels.
6. Own clean-run reproducibility: a new machine/user should be able to follow README instructions, build the index, run the evaluator, and obtain the recorded result.
7. Write the README/Devpost and demo from verified evidence, with input from Persons 1 and 2. Include actual model choice, cost, latency, tokens, metrics, limitations, and contributions.

### Tests and artefacts to write

- `tests/test_agent.py` or equivalent response-contract tests.
- A concise `metrics.md` or CSV experiment log.
- A final before/after metric table: starter baseline vs final agent.
- Failure-analysis notes with two or three representative improvements.

### Deliverables

| Deadline | Deliverable |
|---|---|
| Thu 12:00 | Baseline `results.json` recorded; metrics log and initial contract tests created. |
| Fri 18:00 | Automated response-validity tests running locally. |
| Sat 18:00 | Integrated run report, scenario breakdown, and prioritised failure list. |
| Sun 18:00 | Reproducibility check, final metric table draft, and README outline. |
| Mon 18:00 | README, Devpost draft, demo video/script, and submission checklist ready. |

## Integration plan - nobody waits for another person

| Time | Person 1 | Person 2 | Person 3 | Shared outcome |
|---|---|---|---|---|
| Wed night | Read BM25/index code | Read agent contract/state flow | Save baseline and inspect `results.json` | Everyone can run the baseline. |
| Thu | Create callable `search()` | Create session state and extractor | Create metrics log and contract tests | Agree shared constraints interface by 18:00. |
| Fri | Add filters/reranking | Add questions/overrides | Test outputs and track metrics | First integrated agent by end of day. |
| Sat | Tune retrieval | Tune state/question policy | Run evaluator and analyse failures | Beat baseline without regressions. |
| Sun | Optional semantic trial | Improve failure cases | Reproducibility/error analysis | Decide final technical scope. |
| Mon | Fix only scored defects | Fix only scored defects | Docs/demo/final test | Feature freeze at 10:00. |
| Tue | Final evaluation | Final scenario smoke test | Submission verification | Submit by 11:30. |

## Daily working agreement

1. **09:30, 10 minutes:** say what evidence you produced yesterday, what you will deliver today, and what blocks you.
2. **Before coding:** pull the latest shared branch; do not overwrite another person’s changes.
3. **Small commits:** commit a working unit with a clear message. Do not wait until the end of the day.
4. **18:00 integration:** merge compatible work, run the official evaluator, and log metrics. A feature is not complete until it survives this run.
5. **Feature freeze Monday 10:00:** after that, only defects, tests, reproducibility, documentation, and demo work. No speculative rewrite.

## Submission rules everyone must remember

- Change `starter/agent.py` and your own helper/test files only; do not edit the evaluator or labels.
- Search `data/catalog.jsonl`, but do not mutate it or invent ASINs.
- Return only exact `parent_asin` recommendations, maximum ten, on every turn.
- Ask at most one valid attribute per turn and keep recommending while asking.
- Use only the 200 public sessions to evaluate/tune; never hard-code target products from them.
- Do not commit API keys, secrets, model caches, or private data.
- If you use an LLM, disclose model, estimated cost, latency, and returned token usage. It remains optional.
