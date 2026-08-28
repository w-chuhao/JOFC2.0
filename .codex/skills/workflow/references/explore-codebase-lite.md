# Explore Codebase Lite

Use this workflow to do a targeted, read-only context pass before changing unfamiliar code.

## Core Rule

For non-trivial changes, explore before editing. For small local fixes where the file and pattern are already obvious, do a quick targeted check and continue.

## Exploration Rules

1. Search only the relevant part of the repository.
2. Prefer `rg` and `rg --files` for searches.
3. Read only files related to the task.
4. Avoid secrets, `.env` files, credential files, generated outputs, dependency folders, caches, and unrelated large artifacts.
5. Do not scan the whole repository unless the user asks for broad exploration, onboarding, audit, or architecture review.
6. Keep findings concise.
7. Note uncertainty instead of guessing.
8. Keep the exploration read-only until the relevant files and existing pattern are clear.

## Exploration Depth

Choose the smallest useful depth:

- `quick`: find a file, route, function, component, hook, test, query, or config key.
- `medium`: understand one bug, feature, endpoint, component, service, repository method, or database query.
- `thorough`: use only when the task crosses multiple areas, such as frontend plus backend, API plus Neo4j, CSV import plus UI, or AI agent plus route plus tests.

Avoid very broad exploration unless the user explicitly asks for a full architecture review, audit, or onboarding map.

## What To Check

Look for the task-relevant subset of:

- Entry points and callers.
- Existing naming and folder conventions.
- API routes, request/response shapes, and error handling.
- Services, repositories, query modules, and data mapping.
- Frontend API clients, hooks, components, and graph action logic.
- Related tests and fixtures.
- Config or environment variables only when directly relevant.
- Risks, missing context, assumptions, and compatibility concerns.

For this repository, respect `AGENTS.md`: keep FastAPI routes thin, keep orchestration in services, keep Neo4j access in repositories/query modules, keep frontend API calls in `frontend/src/api`, graph logic in `frontend/src/graph`, reusable UI in components, and data loading in hooks where practical.

## Output Before Implementation

Before implementation on non-trivial work, respond briefly with:

```yaml
exploration_summary:
  depth: quick | medium | thorough
  relevant_files:
    - path: string
      reason: string
  existing_patterns:
    - string
  risks_or_gaps:
    - string
  smallest_safe_plan:
    - string
  suggested_tests:
    - string
```

If the task is simple and local, keep the summary to one or two sentences instead of a full YAML block.
