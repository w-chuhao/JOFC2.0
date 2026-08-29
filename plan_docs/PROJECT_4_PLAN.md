# Final Plan - TechJam Conversational E-Commerce Search

## The goal in plain English

You are building a shopping assistant, not a website and not a general chatbot. It receives a customer message such as "I need lightweight earrings for a wedding" and must recommend up to ten products from the provided 50,000-product catalog.

The organiser secretly knows the one product the customer eventually bought. Your score improves when that exact product's `parent_asin` appears in your Top 10, especially on an early turn. You get at most ten turns.

The only file you need to change for the competition is `starter/agent.py`. The evaluator imports `Agent` from that file and runs it against 200 public practice sessions. Do not edit the evaluator, catalog, or public labels.

## What a product is

Each catalog line is one product. You use text fields such as `title`, `features`, `description`, `categories`, `details`, and `store` to find matching products. You return only product IDs:

```python
{"parent_asin": "B07K34RX5J"}
```

You never know the hidden target ID during a session. Your job is to rank likely matches using what the customer has told you.

## What the agent does on every turn

```text
Customer message + remembered preferences
        |
        v
1. Extract useful facts
   "black leather ankle boots under $80"
   -> colour=black, material=leather, category=boots, budget=80
        |
        v
2. Update or replace the session state
   "Actually, not boots - I need sandals"
   -> remove category=boots; set category=sandals
        |
        v
3. Search the catalog
   BM25 keyword search + category/attribute filtering
        |
        v
4. Rank the candidates
   Products matching more important facts rank higher
        |
        v
5. Respond
   Return up to 10 valid parent_asin IDs and, if useful,
   ask exactly one focused clarification question.
```

Always return recommendations, even when asking a question. A correct recommendation on turn 1 ends the session early and earns a better score.

## The version we should build first

Build a strong local retrieval agent first, then place an optional LLM **planner** around it. The LLM may interpret a message and choose a question, but it must never invent or rank product IDs. Retrieval remains local, deterministic, and the only source of `parent_asin` values.

## Chosen hybrid workflow

This is the agreed workflow when the optional LLM is enabled:

```text
1. Customer sends a message
2. LLM proposes a structured StateDelta (new facts, replacements, and removals)
3. Validate the StateDelta; update the conversation state
4. Local retriever searches and ranks the catalog
5. Retriever returns Top-10 IDs plus aggregate candidate-attribute statistics
6. LLM proposes one useful allowed ask_attribute and natural-language question
7. Validate the proposal; otherwise use deterministic question rules
8. Agent returns the Top-10 IDs, question, and ask_attribute
```

When the customer replies, repeat from step 2 using the existing state. The LLM sees only the customer message, a compact session-state summary, and aggregate candidate statistics - not all 50,000 products and not target labels.

### Why this is a good design

- The LLM helps with ambiguous language and changes of mind.
- Local retrieval stays fast, reproducible, and grounded in real catalog IDs.
- Candidate statistics make questions data-driven: ask about the feature that would best separate the current candidates.
- Strict validation prevents an unreliable LLM response from breaking the evaluator contract.
- If there is no API key, a model error, a timeout, or a cost concern, the deterministic path still works.

### Part A - Keep and improve the existing BM25 search

The starter already creates an in-memory SQLite FTS5 index and performs BM25 keyword search. Keep it. Person 1 will turn the current SQL query into a reusable search function.

It should search the title, features, descriptions, categories, details, and store. Give title/categories more weight than long descriptions, and use the customer's latest message plus remembered constraints as the query.

### Part B - Interpret, validate, and remember the conversation

For each `session_id`, save a small dictionary called state:

```python
{
    "profile": user_profile,
    "constraints": {
        "category": "earrings",
        "material": "stainless steel",
        "color": "black",
        "budget": 40,
        "use_case": "wedding"
    },
    "history": ["..."]
}
```

Use a `StateDelta` contract to represent what the latest message changes. Example:

```python
{
    "set": {"category": "sandals", "color": "black"},
    "clear": ["style"],
    "confidence": 0.92,
}
```

An optional LLM may propose this JSON, but code must validate it before applying it: only known keys are allowed, values must have the right type, budgets must be numeric, and `clear` may contain only known keys. A deterministic rule extractor produces the same shape when no LLM is used.

The main value is remembering information the evaluator gives after you ask a valid question. When a message is an override, clear conflicting old state before setting new values.

### Part C - Ask useful questions

If the user is broad, ask for the one piece of information most likely to narrow the current candidate set. The retriever should report aggregate candidate statistics, such as how many of the best 50 products have each material, colour, or category. The question planner can choose the most informative missing attribute from these statistics.

| What is missing? | Ask attribute | Example question |
|---|---|---|
| Product type | `category` | "What type of item are you looking for?" |
| Material | `material` | "Do you have a preferred material?" |
| Colour | `color` | "Is there a colour you would prefer?" |
| Budget | `budget` | "What price range works for you?" |
| Occasion | `use_case` | "What will you be using it for?" |

An optional LLM may propose the question and attribute. Code must validate both. `ask_attribute` must be one of the values allowed by the contract: `category`, `material`, `color`, `size`, `style`, `brand`, `budget`, `feature`, `use_case`, `other`, or `null`. If the proposal is missing, invalid, slow, or unavailable, use the deterministic priority rule instead.

### Part D - Handle a change of mind

The evaluator includes Intent Override sessions. Detect words such as "actually", "instead", "ignore", "not", and "rather". When a customer replaces a preference, remove the old value rather than adding both values. Example: "Actually, ignore the red dress; I want black shoes" means old dress/red constraints must not dominate later ranking.

### Part E - Rank better than raw BM25

After BM25 returns candidates, add simple extra points for facts that match the remembered state. Example scoring:

```text
BM25 score                       -> base relevance
+ category match                 -> strong bonus
+ explicitly requested material  -> strong bonus
+ colour, brand, size, use case  -> smaller bonuses
- clearly conflicting feature    -> penalty
```

Keep this transparent and tune its weights only by running the public evaluator. This is your first complete solution.

## Retrieval evolution: intent routing and lexical candidates

Keep the deterministic version as the required baseline, then evaluate each step independently with no regression to Hit Rate@10.

1. **Constraint-aware precision:** carry required, preferred, and excluded values from state into retrieval. Use hard filters only for explicit, reliable Buying constraints; use soft preferences and popularity as reranking signals; reject excluded matches.
2. **Buying/Browsing routing:** send precise requests to a filter-first route and vague requests to a broader, diversity-aware route. If the candidate pool remains too broad, ask the missing attribute with the highest information gain rather than following a fixed question order.
3. **Aliases and field routes:** add catalog-specific category aliases and exact-title, category, brand, details, and feature routes before fusion.
4. **LLM planner:** optionally use one only for validated `StateDelta` or clarification proposals; it cannot select, rank, or invent product IDs. An API-backed planner remains an experiment, not a scoring dependency.

The evaluator treats every conversation as an isolated session. The supplied profile may influence the current session's ranking or question choice, but the agent must not persist user information across sessions. Inputs are pre-cleaned, so typo/ASR correction is out of scope.

## File structure you should aim for

You may keep all code in `starter/agent.py` initially. Once it works, small helper files make ownership clearer:

```text
starter/
  agent.py        # required Agent interface and orchestration
  retrieval.py    # Person 1: BM25, filters, ranking
  state.py        # Person 2: StateDelta validation and constraints
  planner.py      # Person 2: optional LLM planner + deterministic fallback
tests/
  test_agent.py   # key behaviour tests
```

`agent.py` must remain the entry point because the evaluator imports it.

## How to measure progress

Run this after every meaningful integrated change:

```powershell
python -m evaluator.local_evaluator
```

Read `results.json` and record:

- **Hit Rate@10:** how many sessions find the target at all.
- **MRR:** whether the target ranks near #1 rather than #10.
- **MTTC:** how quickly the target appears; lower is better.
- **TechnicalScore:** combined score used for comparison.

The starter reference is Hit Rate@10 `0.125`, MRR `0.068034`, and MTTC `9.81`. Your first objective is to beat these numbers without breaking any scenario type.

## Timeline: Wednesday 26 August to Tuesday 1 September, 12:00 PM SGT

| Time | Outcome |
|---|---|
| Wed night | Everyone can run baseline; agree interfaces and create first commit. |
| Thu | Add session state, basic constraint extraction, and reusable BM25 search. |
| Fri | Add filtering, state-aware ranking, questions, and override handling. |
| Sat | Integrate and tune against the 200 public sessions. Compare every change to baseline. |
| Sun | Add tests and analyse failures by scenario. |
| Mon 10:00 AM | Feature freeze. From now on: only fixes, tests, documentation, and demo work. |
| Mon PM | README, Devpost text, metrics table, demo video, clean-run rehearsal. |
| Tue 09:00-11:30 AM | Final evaluator, clean-clone test, check links and secrets, submit. |
| Tue 11:30 AM-12:00 PM | Buffer only. |

## Definition of done

- `python -m evaluator.local_evaluator` works from a clean setup.
- Your `Agent` returns valid, distinct catalog `parent_asin` IDs.
- The agent recommends and asks useful questions across Buying, Browsing, Intent Override, and Boundary sessions.
- You have recorded final metrics and a comparison with the starter baseline.
- README explains setup, reproduction, approach, limitations, and team contributions.
- The public repository contains no API keys or private data.
- Devpost and public demo video are ready before Tuesday noon.
