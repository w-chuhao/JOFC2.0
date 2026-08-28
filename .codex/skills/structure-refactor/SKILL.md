---
name: structure-refactor
description: Behavior-preserving structural refactors for this conversational shopping-agent repository. Use to improve separation of concerns, responsibility boundaries, and maintainable object-oriented design while preserving the evaluator contract and retrieval behaviour.
---

# Structure Refactor

Use this skill for a contained structural refactor of the shopping agent. Its
goal is clearer ownership and stronger software-engineering design—not changing
the shopping strategy, evaluator rules, or scored behaviour unless the user
explicitly asks for that.

## Relationship to Code Simplifier

This skill complements `code-simplifier-lite`; it does not replace it.

- Use code simplification for small, local cleanup, naming, duplication removal,
  or a light behaviour-preserving refactor.
- Use this skill when responsibilities need to move between modules or when a
  stateful domain boundary needs a clearer design.
- Do not create classes, packages, or abstractions merely to make code look more
  object-oriented. Prefer a plain function or dataclass when it is the clearest
  fit.

## Project Contracts and Boundaries

Before editing, read `context.md`, `README.md`, and
`docs/agent_api_contract.json`. Check `git status --short` and preserve
unrelated user changes. Read `references/package-refactor-checklist.md` before
moving modules or changing imports.

Preserve these boundaries unless the user explicitly requests a contract change:

- `starter.agent.Agent` is the evaluator-facing entry point. Preserve the
  constructor and the `reset(session_id, user_profile)` and
  `respond(session_id, user_message, turn, top_k)` interface.
- `starter.retrieval` owns catalog loading, in-memory indexing, candidate
  retrieval, reranking, and `SearchResult`. Keep the shared
  `search(query, constraints, top_k)` contract usable.
- Conversation orchestration owns session lifecycle, remembered preferences,
  intent overrides, clarification policy, and evaluator-response assembly.
- `evaluator/`, `data/public_set.jsonl`, and `data/catalog.jsonl` are fixtures
  and evaluation infrastructure: do not restructure or modify them.
- Recommendations must remain real, distinct catalog `parent_asin` values, with
  no more than ten returned per evaluator turn.

## Design Principles

Apply these principles proportionately:

- **Single responsibility:** Each module/class should own one cohesive purpose.
  Split a growing module only when it mixes stable concerns, such as session
  state, constraint parsing, question selection, and catalog retrieval.
- **Separation of concerns:** Keep policy/orchestration separate from data access
  and pure transformations. The evaluator-facing `Agent` should coordinate;
  retrieval should not decide dialogue policy; a question policy should not
  access SQLite directly.
- **Encapsulation:** Keep mutable session state behind a small, explicit owner.
  Use dataclasses for structured state/result data and methods only when they
  naturally protect a stateful invariant.
- **Dependency direction:** High-level conversation logic depends on a narrow
  retrieval interface, not SQLite details. Pass collaborators in where that
  aids testing; do not introduce a dependency-injection framework.
- **Explicit contracts:** Keep validated constraints, `SearchResult`, and
  evaluator payloads as clear data boundaries. Avoid passing unstructured
  mutable dictionaries across every layer when a focused type clarifies intent.
- **Low coupling and high cohesion:** Group code by domain responsibility, not
  merely by technical type or file size. Keep pure parsing/ranking helpers close
  to the domain that owns their rules.
- **Testability:** Make deterministic extraction, state transitions, ranking,
  and response formatting independently testable without loading the full
  catalog where practical.

## Refactor Workflow

### 1. Audit the Current Responsibilities

- Identify the public entry points, callers, tests, and data flow for the
  target area.
- Search imports, evaluator references, test fixtures, and documentation before
  moving a module or exported symbol.
- State the behaviour and score-sensitive rules that must remain unchanged.
- Do not refactor purely because a file is long; first identify mixed
  responsibilities, duplicated ownership, or a difficult-to-test boundary.

### 2. Choose the Smallest Useful Layout

For this repository, a healthy layout commonly has this shape when the current
single-file agent grows enough to justify it:

```text
starter/
  agent.py              # stable evaluator-facing facade/coordinator
  retrieval.py          # catalog index, search, reranking, SearchResult
  session_state.py      # session dataclass/store and transitions, if needed
  constraints.py        # deterministic preference extraction/normalisation, if needed
  question_policy.py    # clarification choice, if needed
```

This is a guide, not a required target. Keep small cohesive logic together;
avoid speculative modules and one-class-per-file designs.

### 3. Make the Refactor Safely

- Move one cohesive responsibility at a time and update its imports, tests, and
  documentation in the same change.
- Keep `agent.py` as the stable facade; it may compose a retriever, session
  owner, parser, and question policy, but should not become a utility bucket.
- Preserve existing import paths where practical. Add a compatibility re-export
  only when active callers cannot migrate in the same change; remove it after a
  stale-reference search proves it is unused.
- Prefer descriptive domain names over generic names such as `utils`,
  `helpers`, `manager`, or `common`.
- Do not redesign BM25 weights, query construction, constraints, dialogue
  policy, or scoring as an incidental consequence of structural work.

### 4. Verify

- Run focused tests for every moved responsibility.
- Run `python -m pytest` when shared agent, retrieval, or evaluator-facing
  imports change.
- Run `python -m evaluator.local_evaluator` from the repository root and compare
  Hit Rate@10, MRR, MTTC, and scenario metrics with the pre-refactor result.
- Search for stale old module paths and exports.
- Report the responsibilities moved, contracts preserved, verification evidence,
  and any intentionally deferred cleanup.

## Boundaries

- Do not modify the evaluator or data files to improve a score.
- Do not leak `ground_truth` labels into the agent or hard-code catalog IDs.
- Do not add network services, databases, heavy frameworks, or dependencies for
  a behaviour-preserving structural refactor.
- If a proposed split would change how a conversation is interpreted or ranked,
  treat that as feature work and obtain or follow explicit user direction.
