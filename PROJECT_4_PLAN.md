# Project 4: Shopping Copilot - Project Plan

## One-sentence summary

Build an in-memory conversational shopping agent for the 50,000-item Amazon Clothing, Shoes and Jewelry catalog. It should distinguish high-intent buying requests from exploratory browsing, retrieve products through multiple routes, remember and revise user constraints across turns, and return the correct eventual purchase in as few turns as possible.

## What the challenge requires

The organiser supplies a Python starter agent, a fixed catalog, 200 labelled development sessions, and a deterministic local evaluator. The hidden final set contains 800 separate sessions. Our agent must follow the published Python interface and be evaluated headlessly; a web UI is out of scope.

The central requirements are:

- Route each utterance into a **Buying** track (hard constraints such as category, price, colour, size, brand) or a **Browsing** track (open-ended needs such as occasion, style, or use case).
- Use an in-memory hybrid retrieval pipeline: keyword, category/metadata, and vector/semantic retrieval, followed by semantic ranking.
- Keep multi-turn state: add constraints when the user gives more information, and remove/replace stale constraints when they change their mind.
- When a request is too broad, avoid an unhelpful huge retrieval and ask a targeted clarification question.
- Optimise for Hit Rate@10, MRR, Top-K hit rate, efficiency, and MTTC (mean turns to conversion).

## Proposed solution: `RouteWise`

`RouteWise` is a lightweight, reproducible hybrid shopping agent with no dependency on paid model APIs.

1. **Intent router** - a deterministic rules-and-score router detects Buying, Browsing, clarification, and override turns. It is transparent, easy to debug, and avoids sacrificing time to train a bespoke classifier.
2. **Conversation state machine** - maintains slots for category, gender/audience, brand, colour, size, price, material, occasion, and style. New facts merge into state; explicit negations or replacements clear the affected slot.
3. **Dual retrieval** -
   - Buying: metadata/category filters plus BM25, prioritising hard-constraint satisfaction.
   - Browsing: BM25 plus local dense embeddings; diversified candidates prevent near-duplicate results.
4. **Hybrid reranker** - a weighted, explainable score combines lexical match, semantic similarity, category fit, slot satisfaction, and a modest diversity penalty. Weights are tuned only on the 200 public sessions.
5. **Clarification policy** - if the query/state produces a very large or weakly differentiated candidate set, ask one high-information question (for example category, audience, budget, or occasion). Never exceed the hard limit of 10 turns.

This is deliberately scoped for a strong working submission: it satisfies all four pillars without a heavy vector database, full LLM fine-tuning, or a UI.

## Technical shape

```text
User utterance
  -> intent + override detector
  -> state update / slot reset
  -> clarification decision OR retrieval
       Buying: filters + BM25
       Browsing: BM25 + local dense search + diversity
  -> hybrid reranker
  -> official agent response
  -> local evaluator
```

Suggested stack: Python, the supplied starter kit/evaluator, pandas or Polars for catalog loading, scikit-learn/rank-bm25 for lexical retrieval, sentence-transformers plus NumPy for local dense retrieval, and pytest. Cache embeddings locally; do not commit downloaded models, data, credentials, or generated cache files.

## Definition of done

- Official starter interface and local evaluator run from a clean setup.
- Agent handles both Buying and Browsing sessions, including one explicit intent override.
- Retrieval stays entirely in memory and catalog data remains read-only.
- Results are compared against the supplied BM25 baseline on the public sessions, with metrics recorded.
- Tests cover routing, slot accumulation, slot overwrite/erasure, clarification, and ranking/format contract.
- Public repository contains a reproducible README, contribution summary, limitations, and no secrets.
- A short public YouTube demo shows setup, a successful multi-turn session, evaluation output, and the design rationale.

## Timeline to Tuesday, 1 September, 12:00 PM (SGT)

| When | Milestone | Evidence |
|---|---|---|
| Wed 26 Aug - Thu 27 Aug AM | Bootstrap the kit; run the baseline and evaluator; inspect data/session format | Baseline metrics and environment notes |
| Thu 27 Aug PM | Implement router and state model; agree scoring contract and repo structure | Unit tests for intent and slot updates |
| Fri 28 Aug - Sat 29 Aug | Implement BM25/filter retrieval and local dense retrieval; wire hybrid reranker | End-to-end agent produces ranked results |
| Sun 30 Aug | Add clarification/diversification; tune only on development sessions | Metric comparison against baseline |
| Mon 31 Aug AM | Integrate, test edge cases, freeze dependencies, clean code | `pytest` and official evaluator pass |
| Mon 31 Aug PM | Write README/Devpost draft; create and upload demo video | Submission assets ready |
| Tue 1 Sep 09:00-11:00 | Final clean-clone run, evaluator run, repo check, submit | Submission links verified |
| Tue 1 Sep 11:00-12:00 | Buffer for upload or last-mile fixes only | Submit before noon |

## Submission checklist

- Devpost description: problem, approach, tools/APIs, libraries, datasets/assets, metrics, and limitations.
- Public GitHub repository: structured/commented code, setup, reproduction steps, limitations/future work, and each member's contribution.
- Public YouTube demo linked from Devpost; no unlicensed material or exposed secrets.
- Capture a compact table comparing baseline vs final on Hit Rate@10, MRR, MTTC, Efficiency, and TechnicalScore.

## Risks and guardrails

- Do not tune against or leak hidden-session assumptions; use only the 200 public development sessions.
- Dense embeddings may be slow to download or build. Keep BM25 + metadata filtering as a fully functional fallback, cache vectors, and cap candidate sets before reranking.
- Avoid a paid LLM dependency. The organiser provides no credentials and does not require one.
- Start integration early: a sophisticated component that does not conform to the official agent contract earns nothing.
