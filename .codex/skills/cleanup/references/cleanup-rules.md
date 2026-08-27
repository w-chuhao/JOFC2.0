# Cleanup Rules

Use these repository-specific rules before making cleanup edits.

## Boundaries To Preserve

- Keep FastAPI routes thin; move behavior to services only when cleanup reveals
  route logic doing orchestration.
- Keep backend orchestration in service classes.
- Keep Neo4j access in repository classes and query modules.
- Keep frontend API calls in `frontend/src/api`.
- Keep graph transformation and action logic in `frontend/src/graph`.
- Keep reusable UI in `frontend/src/components`.
- Keep data loading in hooks where practical.
- Preserve CSV import preview-first/apply-second behavior.
- Preserve graph chat as read-only for Neo4j unless a task explicitly adds a
  controlled write workflow.
- Preserve AI tool names, argument schemas, tool traces, verifier behavior, and
  unsupported/write-blocking behavior unless the user explicitly asks to change
  them.

## Naming Preferences

Prefer names that reveal domain intent:

- Prefer `dependency_graph_service.py` over `service.py` inside ambiguous
  packages.
- Prefer `run_context.py`, `workflow_state.py`, `tool_metadata.py`, and
  `tool_provider_base.py` over generic names such as `context.py`, `schemas.py`,
  `metadata.py`, or `base.py`.
- Prefer frontend component names that distinguish display purpose, such as
  `ChatAnswerVerification` versus RAG or pipeline verifiers.
- Keep public class aliases when a clearer class name replaces an established
  import path and a full migration would be noisy.

## Deletion Policy

Require user confirmation before deleting:

- database migrations
- tests or fixtures
- docs linked from README, AGENTS, architecture docs, or skills
- route modules
- public API clients
- scripts used by workers or commands
- local Codex skills
- generated artifacts whose source is unknown

Safe removal usually requires all of:

- no imports or references after search
- no config or dynamic loading path
- no public route/tool/API contract
- no docs or scripts pointing to it
- tests/builds still pass after removal

## Common False Positives

Do not classify these as dead only from import search:

- FastAPI route dependencies loaded through app startup
- LangGraph tools listed in prompt/tool registries
- migration files
- docs that serve as architecture records
- CSS classes used through JSX string names
- scripts executed manually from README or operational notes
- files loaded by Codex skills or local automations
