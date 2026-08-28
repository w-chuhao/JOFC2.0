---
name: cleanup
description: Use when the user asks to clean up this repository or workspace by finding and safely removing unused code, dead logic, stale files, obsolete references, duplicate helpers, confusing names, or accumulated implementation clutter. Applies to backend, frontend, docs, tests, local Codex skills, and repo-specific architecture cleanup; requires evidence-first auditing before deleting or renaming.
---

# Cleanup

Use this skill for conservative workspace cleanup in this repository. It is for
auditing and removing proven clutter, not redesigning working features.

## First Steps

1. Read `AGENTS.md` and `README.md`.
2. If cleanup touches AI, graph chat, memory, RAG, tools, or verifier behavior,
   read `docs/ai-agent-architecture.md`.
3. If cleanup touches future architecture, observability, Kubernetes, incidents,
   logs, metrics, traces, or data model evolution, read
   `docs/future-architecture.md`.
4. Check `git status --short` before editing. Do not revert unrelated user
   changes. Treat untracked files as user work unless clearly generated.
5. Read `references/cleanup-rules.md` before making cleanup edits.
6. Read `references/audit-checklist.md` before deleting files, deleting code, or
   renaming modules.

## Cleanup Workflow

### 1. Audit Before Editing

Build a candidate table before modifying files:

```text
candidate | reason | evidence checked | proposed action | risk | verification
```

Classify each candidate:

- `safe-remove`: no references, no public contract, covered by checks.
- `rename-only`: behavior stays the same, naming is misleading or too generic.
- `needs-confirmation`: risky deletion or public-facing contract change.
- `keep`: looks unused but is generated, externally loaded, configured, or a
  future/migration artifact.
- `defer`: possible cleanup, but evidence is incomplete.

### 2. Prove Unused Before Deleting

Use searches and local structure, not guesses:

- Search imports, exports, route registration, component imports, test fixtures,
  scripts, docs, config files, package manifests, and migration references.
- Prefer `rg` when available; otherwise use `Get-ChildItem` and
  `Select-String`.
- For Python modules, check package `__init__.py` exports and dynamic entry
  points.
- For frontend files, check Vite entrypoints, component imports, hooks, graph
  helpers, and CSS class coupling.
- For docs, check whether the doc is linked from README, AGENTS, architecture
  docs, skills, or user-facing guidance.

### 3. Edit In Small Batches

Keep cleanup incremental:

- Rename confusing modules before deleting behavior.
- Keep public route paths, tool names, API response shapes, and database
  semantics stable unless the user explicitly asks for a breaking cleanup.
- Add compatibility aliases when clearer class names replace widely-used
  existing names.
- Update imports, tests, and docs in the same batch as a rename.
- Add comments only when they explain non-obvious cleanup constraints or
  integration rules.

### 4. Verify

Run the smallest meaningful checks for the touched area:

- Backend: `python -m compileall backend\app` plus targeted pytest.
- Broad backend cleanup: `python -m pytest backend\tests`.
- Frontend cleanup: `npm run build` from `frontend`.
- Docs or skill cleanup: stale-reference search and skill validation when
  applicable.

Report what was removed or renamed, why behavior should be unchanged, checks
run, and any candidates left deferred.

## Safety Rules

- Never delete files only because they are not imported.
- Never delete migrations, tests, docs, env examples, scripts, or skill files
  without stronger evidence and user confirmation.
- Never remove AI tool names, graph route contracts, CSV import preview/apply
  behavior, stable graph IDs, or Neo4j traversal semantics during cleanup.
- Never run destructive cleanup commands recursively unless the exact target is
  approved and verified to be inside the workspace.
- If evidence is incomplete, keep the file and report the uncertainty.

## Optional Helper

Use `scripts/find_stale_references.py` after renames or removals to scan for
old paths and symbols. The script is a helper only; it does not prove that a
file is safe to delete.
