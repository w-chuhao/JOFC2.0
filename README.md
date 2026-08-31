# RouteWise — TechJam 2026 Shopping Copilot

RouteWise is our submission for Track 4, **Shopping Copilot: AI Conversational Search and Recommendations**. It is a local Python agent that turns a multi-turn shopping conversation into up to ten ranked products from the organiser's frozen 50,000-item Amazon Clothing, Shoes and Jewelry catalogue.

The evaluator secretly selects one target product for each session. RouteWise never receives that target ID. It sees only an anonymised profile and one customer message at a time, and it must place the exact catalogue `parent_asin` in the Top 10 as early and as highly ranked as possible. Customers may begin with a vague browsing request, disclose a hard requirement, say that an attribute does not matter, or replace an earlier preference. The session ends on a hit or after ten turns.

This is a retrieval and conversation-state system, not a web application. The required entry point is [`starter/agent.py`](starter/agent.py), and the default submission path is fully local: deterministic conversation parsing, an in-memory SQLite FTS5/BM25 index, constraint-aware ranking, and zero model tokens. A guarded local MiniLM CrossEncoder can be enabled as an optional second-stage reranker; it never searches the whole catalogue or produces product IDs.

## Setup and run

The complete setup is kept here at the top. Run every command from the repository root, `JOFC2.0`.

### 1. Create the Python environment

Python 3.11 is the recommended reproducible version. The deterministic agent uses only the Python standard library.

```text
conda create -n jofc python=3.11 -y
conda activate jofc
python --version
```

### 2. Locate the competition data

The public development set is committed at `data/public_set.jsonl`. The frozen catalogue is deliberately not committed; every collaborator must point the evaluator to their own copy. This checkout keeps it one directory above the repository as `../catalog.jsonl`.

PowerShell:

```powershell
$catalogPath = (Resolve-Path "..\catalog.jsonl").Path
Test-Path $catalogPath
Test-Path "data\public_set.jsonl"
```

macOS/Linux:

```bash
CATALOG_PATH="../catalog.jsonl"
test -f "$CATALOG_PATH"
test -f data/public_set.jsonl
```

Both data checks must succeed. Always pass the catalogue path explicitly; do not assume that another machine uses the same location.

### 3. Run the test suite

```text
python -m unittest discover -s tests
```

### 4. Run the 200-session public evaluator

PowerShell:

```powershell
python -m evaluator.local_evaluator `
  --catalog "$catalogPath" `
  --dataset data/public_set.jsonl `
  --output results.json
```

macOS/Linux:

```bash
python -m evaluator.local_evaluator \
  --catalog "$CATALOG_PATH" \
  --dataset data/public_set.jsonl \
  --output results.json
```

This is the complete deterministic setup. It requires no API key, network service, model download, vector database, or third-party Python package.

### 5. Optional: enable the guarded MiniLM reranker

MiniLM is an experiment layered on top of the same deterministic search. Install its local runtime only if you intend to test semantic reranking:

```text
python -m pip install -r requirements-local-reranker.txt
```

PowerShell:

```powershell
$env:LOCAL_RERANKER_MODEL="cross-encoder/ms-marco-MiniLM-L6-v2"
$env:LOCAL_RERANKER_ALLOW_DOWNLOAD="1"  # First cache/download only
$env:LOCAL_RERANKER_WEIGHT="0.35"
$env:LOCAL_RERANKER_CANDIDATES="20"
$env:LOCAL_RERANKER_MIN_CONSTRAINTS="2"
$env:LOCAL_RERANKER_MIN_SCORE_GAP="0.3"

python -m evaluator.local_evaluator `
  --catalog "$catalogPath" `
  --dataset data/public_set.jsonl `
  --output results.minilm.json

Remove-Item Env:LOCAL_RERANKER_ALLOW_DOWNLOAD
```

macOS/Linux:

```bash
export LOCAL_RERANKER_MODEL="cross-encoder/ms-marco-MiniLM-L6-v2"
export LOCAL_RERANKER_ALLOW_DOWNLOAD="1"  # First cache/download only
export LOCAL_RERANKER_WEIGHT="0.35"
export LOCAL_RERANKER_CANDIDATES="20"
export LOCAL_RERANKER_MIN_CONSTRAINTS="2"
export LOCAL_RERANKER_MIN_SCORE_GAP="0.3"

python -m evaluator.local_evaluator \
  --catalog "$CATALOG_PATH" \
  --dataset data/public_set.jsonl \
  --output results.minilm.json

unset LOCAL_RERANKER_ALLOW_DOWNLOAD
```

`LOCAL_RERANKER_ALLOW_DOWNLOAD=1` is only for the initial model download. Official scoring may disable network access, so an offline submission must use an already-cached or approved local checkpoint. If the model is absent, misconfigured, or fails during inference, RouteWise automatically keeps the deterministic ranking.

| Environment variable | Default | Purpose |
|---|---:|---|
| `LOCAL_RERANKER_MODEL` | unset | Enables MiniLM by naming a cached model or local checkpoint. Unset means deterministic-only. |
| `LOCAL_RERANKER_ALLOW_DOWNLOAD` | `0` | Permits a first model download when explicitly set to a truthy value. |
| `LOCAL_RERANKER_WEIGHT` | `0.35` | Weight of semantic rank during deterministic/semantic rank fusion. |
| `LOCAL_RERANKER_CANDIDATES` | `20` | Maximum number of already-retrieved candidates MiniLM may inspect. |
| `LOCAL_RERANKER_MIN_CONSTRAINTS` | `2` | Minimum number of non-category constraints required before MiniLM is considered. |
| `LOCAL_RERANKER_MIN_SCORE_GAP` | `0.3` | Minimum CrossEncoder score advantage required before it can change the order. |
| `LOCAL_RERANKER_BATCH_SIZE` | `16` | CPU inference batch size. |
| `LOCAL_RERANKER_MAX_LENGTH` | `256` | Maximum tokenised pair length. |

## Required agent contract

The evaluator imports the class directly:

```python
from starter.agent import Agent
```

`Agent.reset(session_id, user_profile)` creates isolated state for one conversation. `Agent.respond(session_id, user_message, turn, top_k)` processes the next turn and returns:

```python
{
    "message": "Do you have a preferred material?",
    "ask_attribute": "material",
    "recommendations": [{"parent_asin": "B000..."}],
    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
}
```

The response must contain natural customer-facing text, at most one structured clarification attribute, and ordered catalogue-derived IDs. The evaluator validates and scores only the first ten unique `parent_asin` values. RouteWise returns recommendations even when it also asks a question, so clarification does not consume an otherwise useful recommendation turn.

## End-to-end pipeline

Every call to `respond(...)` follows the same connected pipeline:

```text
customer message + isolated session state
                    |
                    v
     parse facts, exclusions, and overrides
                    |
                    v
 required / preferred / excluded constraints
                    |
                    v
 build lexical query + choose Buying or Browsing
                    |
                    v
 field-weighted multi-route SQLite FTS5 / BM25
                    |
                    v
 reciprocal-rank fusion of candidate routes
                    |
                    v
 deterministic filters + constraint-aware scoring
                    |
                    +----> optional guarded MiniLM over the top 20
                    |              |
                    |       safe deterministic fallback
                    v              v
       ranked real catalogue parent_asin values
                    |
                    v
 candidate statistics -> one useful clarification
                    |
                    v
     Top 10 recommendations + question + zero tokens
```

The stages are deliberately dependent. Conversation state makes search more precise; BM25 supplies grounded candidates; deterministic ranking enforces catalogue facts and customer constraints; MiniLM may refine only that validated shortlist; candidate statistics then decide what the agent should ask next.

## 1. Conversation state and intent handling

[`starter/state.py`](starter/state.py) stores one `SessionState` per `session_id`. It remembers:

- category, material, colour, size, style, brand, budget, feature, and use case;
- the evidence and turn that produced each constraint;
- required, preferred, and excluded values;
- questions already asked and attributes for which the customer said “no preference”;
- recommendation IDs already shown; and
- whether an intent override has occurred.

The parser is deterministic and catalogue-independent. It recognises labelled requirements, replies to a previous clarification, budgets, common attribute values, exclusions such as “not leather,” and override language such as “actually,” “instead,” or “ignore.” Product-benefit phrases such as “will not fade” remain positive feature evidence rather than being mistaken for exclusions.

Evidence determines priority. Category, budget, explicit requirements, clarification answers, and override values are treated as required. Softer first-turn preferences remain preferred. When the category genuinely changes, old non-category constraints are cleared instead of being carried into the new search. A “no preference” reply resolves that attribute without trapping the conversation in a repeated-question loop.

The anonymised `user_profile` helps choose which unresolved attribute to ask about. Broad tags such as `material` or `fit` identify useful question dimensions; they are not interpreted as desired product values and do not directly add ranking bonuses.

## 2. Query construction and Buying/Browsing routing

RouteWise builds two related queries from validated state:

- The **lexical retrieval query** combines the current useful message, stable leaf-category context, and remembered constraints. Dialogue-only filler is removed so phrases such as “I am still exploring” do not dominate search.
- The **semantic query** is a compact labelled representation such as `category: tunics; material: polyester; feature: breathable`. MiniLM receives this clean state summary rather than the raw conversation history.

The agent selects the **Buying** route when at least one non-category constraint is required. Otherwise it selects **Browsing**. Both routes use the same grounded catalogue index, but they behave differently after retrieval:

- Buying may hard-filter required attributes, but only when at least `top_k` exact candidates remain. This avoids turning one strict clue into an empty or undersized result set.
- Browsing keeps a wider discovery pool and suppresses previously shown IDs on unchanged later turns so the shopper sees new options.
- A new constraint or a genuine override reopens the full candidate set because earlier products may now be relevant under the changed intent.

## 3. In-memory catalogue index

[`starter/retrieval.py`](starter/retrieval.py) reads the JSONL catalogue once when `Agent` is constructed and builds an in-memory SQLite FTS5 table. No server or persistent database is required.

The searchable fields and BM25 field weights are:

| Field | BM25 weight | Why it matters |
|---|---:|---|
| title | 6.0 | Strongest concise description of the product. |
| categories | 4.0 | Keeps results in the intended product family. |
| features | 2.5 | Captures material, construction, and benefits. |
| details | 2.5 | Captures structured metadata such as department and model details. |
| store | 1.5 | Supports brand/store requirements. |
| description | 1.0 | Adds recall without allowing long prose to dominate. |

`parent_asin` is stored but not searched. It is returned only after a real indexed catalogue row has survived retrieval and ranking.

Search terms use inclusive `OR` matching. This is intentional: a product does not need to repeat every conversational token to enter the candidate pool. Exact constraints are enforced later by guarded filtering and reranking, where the system can distinguish a genuine conflict from missing metadata.

## 4. Multi-route BM25 candidate retrieval

A single large query can bury a useful product when one field is verbose or one clue is rare. RouteWise therefore runs several complementary BM25 routes:

| Candidate route | Fusion weight | Candidate cap |
|---|---:|---:|
| current message + all remembered constraints | 2.0 | 800 |
| category | 3.0 | 500 |
| material | 1.8 | 400 |
| colour | 1.4 | 300 |
| size | 1.2 | 300 |
| style | 1.2 | 300 |
| brand | 1.5 | 300 |
| feature | 1.5 | 500 |
| use case | 1.2 | 300 |

Small catalogue-aware aliases, such as `handbag`/`purse` and `footwear`/`shoes`, expand recall before search.

Each route produces a ranked list. Route results are combined with weighted reciprocal-rank fusion:

```text
candidate retrieval score += route_weight / (60 + rank_in_route)
```

This rewards products supported by several independent clues without requiring raw BM25 scores from different queries to be directly comparable. BM25 and RRF answer **which products deserve consideration**; the next stage answers **which of those candidates best satisfies the conversation**.

## 5. Deterministic filtering and ranking

Candidate ranking begins with the fused retrieval score and then applies customer-specific evidence.

| Constraint | Full required weight |
|---|---:|
| category | 6.0 |
| material | 4.0 |
| colour | 3.0 |
| brand | 3.0 |
| size | 2.5 |
| feature | 2.5 |
| style | 2.0 |
| use case | 2.0 |

Attribute coverage is the fraction of requested terms found in the field appropriate to that attribute. Required evidence uses the full weight. Preferred evidence uses a `0.4` multiplier, so it can improve ordering without overpowering an explicit need. Missing required evidence receives an attribute-specific penalty.

The remaining signals work as follows:

- products with a known price above the budget are removed; an in-budget known price receives a small bonus;
- products matching an excluded value are removed;
- distinctive exact feature phrases receive a `0.75` bonus;
- catalogue-common feature clauses are softened unless the customer explicitly marked them as required;
- `0.02 * log(1 + rating_count)` provides a modest popularity tie-break, which decays as more products are shown across turns; and
- `0.002 * average_rating` provides a small rating tie-break.

These steps work together rather than replacing BM25. Lexical retrieval preserves recall, guarded filters enforce reliable hard facts, and weighted reranking moves the best-supported candidates toward rank 1. If a query produces no BM25 candidates, the code safely falls back to the catalogue before applying the same filters and scoring.

## 6. MiniLM's role

[`starter/local_reranker.py`](starter/local_reranker.py) loads `cross-encoder/ms-marco-MiniLM-L6-v2` when `LOCAL_RERANKER_MODEL` is configured. This is a **CrossEncoder**, not a vector-search engine: it reads the semantic query and one candidate product together and returns a relevance score for that pair.

MiniLM does not replace any earlier stage:

- it does not parse or mutate session state;
- it does not query all 50,000 products;
- it cannot add, remove, or invent `parent_asin` values;
- it cannot bypass exclusions, budget checks, category filtering, or required-constraint logic; and
- it is never required for the deterministic agent to run.

The semantic path is guarded:

1. Deterministic search and ranking run first.
2. At least two non-category constraints must be known.
3. Only the top 20 deterministic candidates are scored.
4. Up to the first two candidates are protected when they already satisfy every required constraint.
5. MiniLM must prefer a different movable leader by at least the configured `0.3` raw-score gap.
6. The remaining deterministic and semantic ranks are fused using reciprocal-rank fusion with semantic weight `0.35`.
7. After an intent override, semantic reranking stays disabled for that session to avoid promotion based on stale phrasing.
8. Any model-loading, inference, malformed-output, or non-finite-score failure returns the unchanged deterministic order.

This narrow role is deliberate. The independent 18-case hard-negative benchmark shows that L6 MiniLM can substantially improve ordering when a query is richly specified and the correct product is already in a fixed candidate pool. Broad public browsing queries did not consistently benefit, and local CPU inference adds latency. MiniLM therefore remains an opt-in precision tool for difficult shortlist ordering, while BM25 and deterministic constraint logic remain authoritative for end-to-end recall and safety. See [`docs/testing/semantic-model-comparison.md`](docs/testing/semantic-model-comparison.md) for the benchmark design and limitations.

## 7. Clarification and final response

After ranking, the retriever summarises attribute frequencies across the best 50 candidates for category, material, colour, style, brand, use case, feature, size, and budget buckets. [`choose_clarification(...)`](starter/state.py) estimates how well each unresolved attribute would split the current candidate set using normalised entropy.

The agent asks the highest-value attribute when its information score is strong enough. Otherwise it uses safe profile-informed and fixed-priority fallbacks. It never asks after turn 10, avoids attributes already answered or declined, and can ask a general `other` question after repeated no-preference replies.

Finally, `Agent.respond(...)` records the assistant turn and returns:

- a natural-language message;
- one allowed `ask_attribute` or `null`;
- up to `top_k` distinct catalogue-derived recommendation IDs; and
- zero prompt and completion tokens.

## Evaluation

The public set contains 200 labelled development sessions; the organiser evaluates 800 separate private sessions. The public scenario mix is Buying 40%, Browsing 40%, Intent Override 15%, and Boundary 5%.

| Metric | Meaning |
|---|---|
| Hit Rate@10 | Fraction of sessions in which the hidden target appears in the first ten valid recommendations. |
| MRR | Mean reciprocal target rank: rank 1 contributes `1`, rank 2 contributes `0.5`, rank 10 contributes `0.1`, and a miss contributes `0`. |
| MTTC | Mean first correct turn; lower is better, and a miss is counted as turn 11. |
| Efficiency | `clip((11 - MTTC) / 10, 0, 1)`. |
| Technical Score | `0.50 * Hit Rate@10 + 0.30 * MRR + 0.20 * Efficiency`. |

The current deterministic result was reproduced on `main` on 31 August 2026 with 88 tests passing:

| Configuration | Hit Rate@10 | MRR | MTTC | Efficiency | Technical Score | Model tokens |
|---|---:|---:|---:|---:|---:|---:|
| Supplied weak BM25 baseline | 0.125 | 0.068034 | 9.81 | 0.1190 | 0.106710 | Not reported |
| RouteWise deterministic | 1.000 | 0.626341 | 1.735 | 0.9265 | 0.873202 | 0 |

Treat every public result as a development regression check, not a prediction of the private score. Agent code must never read public target labels, hard-code target ASINs, or modify `evaluator/`, `data/public_set.jsonl`, or the frozen catalogue.

## Inspecting a conversation and its ranking

Trace selected public sessions with the same explicit catalogue path:

```bash
python -m scripts.trace_public_sessions \
  --catalog "$CATALOG_PATH" \
  --sample-ids public_0001,public_0014 \
  --output /private/tmp/routewise-trace.json
```

Trace mode enables offline diagnostics that normal evaluation leaves disabled. For each returned candidate it can show route ranks, BM25 values, RRF contributions, attribute contributions, feature bonuses, popularity and rating tie-breaks, deterministic-to-final rank movement, and MiniLM scores when available. The trace tool compares results with public labels only after the agent response; target IDs are never passed into the agent or retriever.

## Repository map

- [`starter/agent.py`](starter/agent.py) — required evaluator-facing class and turn orchestration.
- [`starter/state.py`](starter/state.py) — deterministic parsing, evidence, overrides, exclusions, session state, and clarification policy.
- [`starter/retrieval.py`](starter/retrieval.py) — in-memory FTS5 index, multi-route BM25, RRF, deterministic filtering/ranking, statistics, and semantic guards.
- [`starter/local_reranker.py`](starter/local_reranker.py) — optional local CrossEncoder adapter.
- [`evaluator/`](evaluator) — frozen local evaluator; do not modify it.
- [`data/public_set.jsonl`](data/public_set.jsonl) — 200 labelled public development sessions.
- [`tests/`](tests) — contract, state, retrieval, evaluator, tracing, and local-reranker tests.
- [`scripts/`](scripts) — tracing, evaluation experiments, score-gap sweeps, and semantic benchmarks.
- [`outputs/`](outputs) — ignored generated traces and evaluation history.
- [`docs/agent_api_contract.json`](docs/agent_api_contract.json) — machine-readable request and response contract.
- [`docs/demo_video_script.md`](docs/demo_video_script.md) — timed demo-video narration and shot list.

## Important boundaries and limitations

- RouteWise recommends only from the frozen text catalogue; it does not browse the web, transact, or modify catalogue data.
- The deterministic parser is designed for the competition's pre-cleaned text. General typo correction, ASR repair, and unrestricted natural-language understanding are out of scope.
- Some products have missing prices or descriptions, so those fields cannot be mandatory for recall.
- Session state is isolated. The supplied anonymised profile may guide questions in that session, but no cross-session personal memory is created.
- MiniLM improves semantic ordering only when the relevant product is already in its deterministic shortlist. It cannot repair missing candidate recall.
- A remotely named model is not an offline asset by itself. Model weights must already be cached or supplied through an approved local-asset workflow.
- Public-set scores and the 18-case semantic benchmark are development evidence, not private-set guarantees.

## Development rules

- Keep `starter/agent.py` as the evaluator-facing entry point.
- Do not modify `evaluator/`, public labels, or the frozen catalogue.
- Preserve exact, unique catalogue `parent_asin` outputs and the ten-turn session contract.
- Run the tests and full public evaluator after meaningful state or retrieval changes.
- Add tests for parser, ranking, response-format, and local-model failure behaviour.
- Keep API keys, generated outputs, model caches, and private data out of Git.

For the formal contract and planning background, see [`docs/competition_specification.md`](docs/competition_specification.md), [`docs/submission_rules.md`](docs/submission_rules.md), and [`plan_docs/PROJECT_4_PLAN.md`](plan_docs/PROJECT_4_PLAN.md).

## Data attribution

The catalogue and sessions are derived from Amazon Reviews 2023 by McAuley Lab, UCSD. Read [`DATA_ATTRIBUTION.md`](DATA_ATTRIBUTION.md) before redistributing the data.
