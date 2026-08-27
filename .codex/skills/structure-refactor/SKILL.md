---
name: structure-refactor
description: Behavior-preserving package and module structure refactors for this repository. Use when Codex needs to move related code into focused domain folders, group or repair __init__.py exports, clean up package layout, update imports after module moves, consolidate duplicate entrypoints or compatibility shims, or reorganize backend/frontend logic without changing behavior.
---

# Structure Refactor

Use this skill for contained code organization refactors. The goal is clearer
package structure with unchanged behavior, public contracts, routes, tool names,
database semantics, and frontend response shapes.

## First Steps

1. Read `AGENTS.md` and `README.md`.
2. If the refactor touches AI, graph chat, memory, RAG, tools, or verifier
   behavior, read `docs/ai-agent-architecture.md` and the relevant `docs/ai/`
   chapter.
3. If the refactor touches observability, incidents, Kubernetes, logs, metrics,
   traces, or future storage boundaries, read `docs/future-architecture.md`.
4. Check `git status --short` before editing. Do not revert unrelated changes.
5. Read `references/package-refactor-checklist.md` before moving files, deleting
   compatibility modules, or changing package exports.

## Refactor Workflow

### 1. Audit Current Structure

- List files in the target package and identify the current public entrypoints.
- Search imports, tests, docs, worker modules, route registration, package
  `__init__.py` exports, config references, and scripts.
- Classify files as implementation, package entrypoint, compatibility shim,
  generated/cache artifact, test/doc reference, or external contract.
- Preserve behavior by default. Do not move code only because a file is large.

### 2. Choose Target Layout

- Group by domain responsibility and change cadence, not by file size alone.
- Prefer focused subpackages with clear `__init__.py` exports when several files
  form a domain area.
- Keep a stable root package entrypoint when existing callers import from the
  package root.
- Avoid wrapper modules unless they are needed for compatibility.

### 3. Move Safely

- Move implementation files in small batches.
- Add or update subpackage `__init__.py` files to re-export the intended public
  symbols.
- Update relative imports after directory-depth changes.
- Update call sites, tests, docs, worker entrypoints, route modules, and package
  exports in the same batch.
- Delete compatibility shims only after a stale-reference search proves no
  active references remain.
- Remove generated `__pycache__` folders under touched areas after tests.

### 4. Verify

- For backend package moves, run `python -m compileall backend\app`.
- Run focused pytest files for the touched subsystem.
- Run `python -m pytest backend\tests` when package entrypoints, graph chat, AI,
  memory, Telegram, routes, or shared service imports are touched.
- Run stale-reference searches for old module paths, old class names, and old
  command names.
- Report what moved, what compatibility surface was preserved, what was removed,
  and which checks passed.

## Boundaries

- Preserve FastAPI route paths, request/response shapes, AI tool names, graph
  chat read-only behavior, Neo4j traversal semantics, CSV preview/apply flow,
  stable graph IDs, and worker CLI behavior unless explicitly asked otherwise.
- Keep secrets out of frontend code and docs.
- Do not delete migrations, tests, route modules, public API clients, scripts,
  or docs without strong evidence and explicit justification.
- If evidence is incomplete, keep the file and report the deferred cleanup.
