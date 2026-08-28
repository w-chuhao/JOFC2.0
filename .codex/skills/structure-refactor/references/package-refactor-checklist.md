# Shopping Agent Structural Refactor Checklist

Use this checklist before and after moving code in `starter/`.

## Audit

- Run `git status --short`; preserve unrelated work.
- Read `context.md`, `README.md`, and `docs/agent_api_contract.json`.
- Identify which responsibility is moving: evaluator facade, session state,
  constraint parsing, clarification policy, catalog retrieval, ranking, or
  response formatting.
- Search references in `starter/`, `tests/`, `evaluator/`, docs, and commands
  before changing module paths or exported names.
- Record the relevant current evaluator metrics before making the refactor.

## Target Layout

- Keep `starter/agent.py` as the evaluator-facing `Agent` entry point.
- Keep catalog I/O, FTS5/BM25, and candidate ranking within `starter/retrieval`
  or a tightly focused retrieval subpackage.
- Place mutable conversation state behind one explicit owner, preferably a small
  dataclass plus a session store/coordinator when state becomes non-trivial.
- Keep deterministic parsing and question selection separate if they have
  independent rules or tests.
- Keep pure utility functions near the domain that owns their rule; do not add a
  generic `utils.py` bucket.
- Prefer a small number of cohesive modules over a deep hierarchy or needless
  object wrappers.

## Safe Moves

- Move one responsibility at a time.
- Keep constructor, `reset`, and `respond` signatures stable.
- Preserve the `search(query, constraints, top_k)` contract and `SearchResult`
  shape for retrieval callers.
- Update imports, unit tests, and relevant documentation together.
- Add a temporary compatibility re-export only for an active import that cannot
  be migrated immediately; delete it once no active references remain.
- Do not mix a structural refactor with ranking, extraction, or dialogue-policy
  experiments unless those behaviour changes are explicitly requested.

## Verification

- Run focused tests for the moved code, then `python -m pytest` when shared
  imports change.
- Run `python -m evaluator.local_evaluator` and compare overall and per-scenario
  Hit Rate@10, MRR, and MTTC with the pre-refactor result.
- Confirm all returned recommendations remain unique real `parent_asin` values
  and there are at most ten per turn.
- Search for stale module paths, exports, and obsolete documentation.
- Report preserved contracts, changed locations, checks run, metric comparison,
  and deferred work.
