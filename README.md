# JOFC 2.0 - TechJam Conversational E-Commerce Search

This repository is our submission for the TechJam Conversational E-Commerce Search Challenge. It implements a Python shopping agent that receives an anonymized customer profile and one message at a time, asks at most one useful follow-up question, and returns up to ten real product IDs from a frozen 50,000-item Amazon Clothing, Shoes and Jewelry catalog.

The challenge evaluator holds a hidden target product for each conversation. The agent succeeds when that exact `parent_asin` appears in its Top 10, ideally on an early turn. This is a retrieval-and-conversation-state project, not a web application: the required entry point is [`starter/agent.py`](starter/agent.py).

## Complete setup (Windows/Conda)

The agent uses the Python standard library. On a new computer, obtain the frozen competition data first, then run this from the repository root in one PowerShell terminal:

```powershell
# 1. Confirm the frozen competition data is present.
Test-Path data\catalog.jsonl
Test-Path data\public_set.jsonl

# 2. Create and enter an isolated Python environment.
conda create -n jofc python=3.11 -y
conda activate jofc
python -c "import sys; print(sys.executable)"

# 3. Verify the agent and run the public evaluator.
python -m unittest discover -s tests
python -m evaluator.local_evaluator --output results.json
```

Both `Test-Path` commands must return `True`, and the interpreter path must contain `envs\\jofc\\python.exe`. No API key, model download, or Python package installation is required for the BM25 agent.

## What is in this repository

- `data/catalog.jsonl` - frozen product catalog used by the agent.
- `data/public_set.jsonl` - 200 labelled public development sessions.
- `starter/agent.py` - evaluator-facing `Agent` class and turn orchestration.
- `starter/state.py` - session state, rule extraction, overrides, exclusions, validation, and deterministic clarification fallback.
- `starter/retrieval.py` - SQLite FTS5/BM25 retrieval, constraint-aware reranking, aliases, candidate statistics, and result diversification.
- `starter/conversation_llm.py` - optional, guarded DeepSeek planner. It never selects product IDs.
- `evaluator/` - frozen local evaluator. Do not modify it.
- `scripts/` - evaluation history, public-conversation tracing, and an opt-in DeepSeek connection check.
- `outputs/` - generated traces and evaluation history. It is intentionally ignored by Git.

## How to evaluate changes

Run the frozen evaluator after each meaningful retrieval or state-management change:

```powershell
python -m evaluator.local_evaluator --output results.json
```

For a durable local history entry with the tester and note, use the wrapper:

```powershell
python scripts/run_evaluation.py --tested-by "Your Name" --note "Describe the change"
```

It writes the latest evaluator result to `results.json` and appends the compact metric summary to `outputs/evaluation_history.json`.

The public set is for development only. The final competition evaluation uses 800 separate private sessions. Never read public target labels from agent code, hard-code ASINs, or modify `evaluator/`, `data/public_set.jsonl`, or `data/catalog.jsonl`.

### Metrics

- **Hit Rate@10**: fraction of sessions where the hidden target appears in the Top 10.
- **MRR**: ranking quality. A target at rank 1 contributes `1`; rank 2, `0.5`; rank 10, `0.1`; a miss, `0`.
- **MTTC**: mean turn of the first correct Top-10 result. Lower is better; a miss is counted as turn 11.
- **Technical Score**: `0.50 * Hit Rate@10 + 0.30 * MRR + 0.20 * Efficiency`, where `Efficiency = clip((11 - MTTC) / 10, 0, 1)`.

The supplied weak baseline achieved Hit Rate@10 `0.125`, MRR `0.068034`, and MTTC `9.81` on the public set. Treat each new public result as a regression check, not evidence that the private set will score identically.

## Agent flow

Every evaluator session is isolated and follows this flow:

```text
customer message + current session state
        |
        v
deterministic extraction (optional DeepSeek proposal for unresolved language)
        |
        v
validated constraints, priorities, exclusions, and intent overrides
        |
        v
multi-route BM25 candidates
        |
        v
constraint-aware reranking and candidate-attribute statistics
        |
        v
Top-10 real catalog IDs + one validated clarification question
```

`Agent.reset(session_id, user_profile)` creates fresh state. Each `Agent.respond(session_id, user_message, turn, top_k)` call returns this evaluator contract:

```python
{
    "message": "Do you have a preferred material?",
    "ask_attribute": "material",
    "recommendations": [{"parent_asin": "B000..."}],
    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
}
```

Only catalog-derived, distinct `parent_asin` values are returned. Asking a question never prevents the agent from returning recommendations on that turn.

## Current implementation

### Conversation state and clarification

`starter/state.py` remembers category, material, color, size, style, brand, budget, feature, and use-case constraints for one session. It distinguishes:

- **required constraints**, such as an explicit need or budget;
- **preferred constraints**, which improve rank but do not eliminate matches;
- **excluded constraints**, such as "not black"; and
- **no-preference answers**, so the agent does not ask the same unhelpful question again.

Intent-override language replaces stale constraints instead of accumulating contradictions. The deterministic clarification policy uses candidate distributions when they meaningfully separate unresolved attributes, then falls back to profile hints and a fixed safe question order.

### Retrieval and ranking

`starter/retrieval.py` builds an in-memory SQLite FTS5 index over title, categories, features, details, store, and description. It combines field-aware BM25 routes, catalog aliases (for example, `handbag`/`purse`), and a constraint-aware reranker.

Required constraints receive full scoring weight and clear excluded matches are removed; preferred constraints receive a smaller bonus. Exact multi-word feature clues receive a phrase bonus, while a modest rating/popularity tie-break decays during cross-turn exploration. All BM25 candidate routes use inclusive term matching, rather than a strict Buying-only AND route, because the latter reduced the public evaluator's composite score. Broader Browsing requests also avoid repeating products shown earlier in the same session. The retriever returns aggregate category/material/color/style/brand/use-case/feature/size/budget counts for diagnostics and the optional planner, never as product recommendations.

### Optional DeepSeek planner

DeepSeek is not required for evaluation. When configured, it may propose a structured state update for language the rule extractor does not handle and a single clarification question. Code validates those proposals; retrieval, ranking, state mutation, and product IDs remain deterministic and local.

Create an ignored `.env` file in the repository root:

```text
DEEPSEEK_KEY=your_key_here
# Optional overrides
# DEEPSEEK_MODEL=deepseek-v4-flash
# DEEPSEEK_TIMEOUT_SECONDS=2
# DEEPSEEK_ENABLED=1
```

Verify the connection with one tiny request (16-token response cap):

```powershell
python -m scripts.test_deepseek_connection
```

This check sends no catalog or evaluator data. It requires outbound HTTPS access to `api.deepseek.com`; the agent safely falls back to deterministic behaviour on missing credentials, invalid replies, timeouts, or network errors.

## Inspecting conversations and retrieval behaviour

Trace an 80-session public-set sample (30 buying, 30 browsing, 10 intent override,
and 10 boundary sessions—the largest practical mix without repeating boundaries):

```powershell
python -m scripts.trace_public_sessions
```

Use `--per-scenario 10` for a balanced 40-session comparison trace.

The full trace is saved to `outputs/public_prompt_trace.json`. To inspect specific public samples instead:

```powershell
python -m scripts.trace_public_sessions --sample-ids public_0001,public_0014
```

The trace includes evaluator prompts, responses, state constraints, priorities, exclusions, and retrieval diagnostics. Use it to investigate failure patterns; do not use hidden target labels in runtime agent logic.

## Development rules

- Keep `starter/agent.py` as the evaluator-facing entry point.
- Preserve session isolation: do not create cross-session user memory.
- Add or update tests with changes to state, retrieval, response formatting, or external-client failure handling.
- Keep API keys, generated outputs, and private data out of Git. `.env` and `outputs/` are ignored.
- Inputs are pre-cleaned. Spelling correction and ASR-noise handling are out of scope for the competition path.

For the competition contract and detailed implementation plan, see [`docs/agent_api_contract.json`](docs/agent_api_contract.json) and [`plan_docs/PROJECT_4_PLAN.md`](plan_docs/PROJECT_4_PLAN.md).

## Data attribution

The catalog and sessions are derived from Amazon Reviews 2023 by McAuley Lab, UCSD. Read [`DATA_ATTRIBUTION.md`](DATA_ATTRIBUTION.md) before redistributing the data.
