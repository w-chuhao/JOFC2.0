# Package Refactor Checklist

Use this checklist before and after moving code between packages.

## Audit

- Run `git status --short` and treat unrelated changes as user work.
- List the target package files and existing subpackages.
- Search for old package paths and exported symbols in:
  - backend and frontend imports
  - tests and fixtures
  - docs and README commands
  - route registration and worker entrypoints
  - package `__init__.py` exports
  - scripts and config files
- Identify compatibility shims separately from implementation files.

## Target Layout

- Group files by domain responsibility:
  - orchestration/coordinator files stay near the package root when they connect
    several subdomains
  - domain implementation files move into focused subpackages
  - helper modules move with the domain that owns their rules
- Prefer clear names such as `long_term`, `short_term`, `ingestion`, `routing`,
  `verification`, or `formatting` over generic buckets.
- Keep root `__init__.py` exports stable if callers already import from the
  package root.

## Moving Files

- Move implementation first, then patch relative imports.
- Add subpackage `__init__.py` files that export the public service classes,
  constants, and helper functions expected by callers.
- Update tests to import from the new canonical path unless root exports are the
  intended public surface.
- Update docs in the same batch as code moves.
- Avoid creating compatibility wrappers unless a public import path cannot be
  migrated safely in the same change.

## Compatibility Shims

- Keep a shim only when README commands, external scripts, operational docs, or
  user-facing CLIs still reference the old module.
- Remove a shim when a stale-reference search proves the old module name is no
  longer used.
- After removing a shim, update README/docs to name the single canonical command.

## Verification

- Backend structural refactor:
  - `python -m compileall backend\app`
  - focused pytest for the moved subsystem
  - `python -m pytest backend\tests` when shared imports, routes, graph chat, AI,
    memory, or workers are touched
- Frontend structural refactor:
  - `npm run build` from `frontend`
  - typecheck when available
- Always search for stale old paths after the move.
- Remove generated `__pycache__` folders under touched Python packages after
  verification.

## Memory Package Example

For a memory package split, prefer a layout like:

```text
memory/
  __init__.py
  coordinator.py
  routing.py
  tool_trace.py
  long_term/
    __init__.py
    service.py
    curation.py
    retrieval_evaluation/
  short_term/
    __init__.py
    session_memory.py
    session_context.py
    short_term_memory.py
    write_guard.py
  ingestion/
    __init__.py
    pipeline.py
    rag_evidence_verifier.py
    worker.py
```

Preserve `backend.app.services.memory` exports when existing graph chat, routes,
or tests import from the package root. Collapse duplicate app-level worker shims
into one canonical `memory_worker.py` only after references to older module
names are removed.
