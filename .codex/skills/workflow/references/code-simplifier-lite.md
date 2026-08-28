# Code Simplifier Lite

Use this workflow for simplifying, cleaning up, removing duplication, improving naming, or lightly refactoring working code without changing behavior.

## Core Rule

Preserve behavior. Make code cleaner, smaller, and easier to maintain while
keeping the same external behavior, inputs, outputs, side effects, API
responses, database behavior, graph behavior, tool behavior, and error handling.

Do not use this workflow to redesign a feature or restructure the whole project unless the user explicitly asks.

## Understand Current Behavior

Before editing, identify the relevant subset of:

- Inputs and outputs.
- Side effects.
- Public function signatures, exports, component props, and route contracts.
- API request and response shapes.
- Database queries, traversal direction, and result mapping.
- External calls, model calls, or tool calls.
- Error behavior and status codes.
- Existing tests or manual checks.

If behavior is unclear, state the uncertainty before editing.

## Simplification Opportunities

Look for:

- Duplicated logic.
- Repeated conditions.
- Unnecessary variables.
- Overly complex branching.
- Unclear names.
- Long functions doing multiple things.
- Repeated API response formatting.
- Repeated error handling.
- Unnecessary comments.
- Confirmed dead code.
- Inconsistent local formatting.
- Small local structure improvements.
- A large file acting as both coordinator and utility bucket.
- Helper functions that naturally group into routing, formatting, verification, parsing, persistence, or API-specific concerns.
- Private methods that can move into nearby focused modules without changing external behavior.
- Repeated internal sections that suggest a package entrypoint plus helper modules.

Remove dead code only when usage search and tests or context make it clear that it is unused.

## Preserve Behavior

Do not change:

- Function signatures unless explicitly asked.
- Route paths, HTTP methods, status codes, or response shapes.
- Database schema or Cypher query meaning.
- Neo4j traversal direction, relationship semantics, `propagate` behavior,
  protocol naming, or returned data shape.
- Stable system, node, edge, or relationship IDs used by frontend graph
  selection, inspection, fit, or highlighting.
- CSV preview-first/apply-second behavior.
- Graph chat read-only behavior.
- AI tool names, argument schemas, safety checks, fallback behavior, or
  write-blocking behavior.
- Environment variable names.
- Public component props.
- Exported names used elsewhere.
- Test expectations.
- User-facing text unless requested.

## Simplify Safely

When implementation is requested:

1. Make the smallest useful cleanup.
2. Prefer local simplification over broad refactoring, but allow contained structural refactors when they clearly improve readability.
3. When a file mixes orchestration with multiple helper concerns, prefer splitting it into a focused package or module group.
4. Keep one obvious entrypoint file when splitting:
   - For example, keep `chat_service.py` as the coordinator and move grouped helper logic into nearby files with clear names.
5. Preserve public imports and call sites where practical so the refactor is easy to adopt.
6. Keep existing style and naming patterns unless they are clearly confusing.
7. Extract helpers only when they improve clarity, reduce meaningful duplication, or separate distinct responsibilities.
8. Remove duplication only when the shared logic is truly the same.
9. Avoid clever code.
10. Avoid introducing new dependencies.
11. Keep changes easy to review.

## Coding Style And Design Preferences

Use these preferences during simplification:

- Prefer simple, readable code over clever, compact, or unnecessarily complex
  code.
- Use object-oriented design where it creates clearer behavior boundaries,
  better extension points, or easier testing.
- Do not force OOP where a small function, plain data structure, or React
  component is clearer.
- Apply abstraction, encapsulation, separation of concerns, single
  responsibility, explicit data contracts, predictable error handling, and
  minimal duplication.
- Avoid large, catch-all files:
  - When code grows beyond one clear responsibility, split it into relevant
    domain-specific folders and files.
  - Each file should have a focused purpose, clear boundaries, and an intuitive
    name that explains what part of the domain it owns.
- Keep `backend/app/services` organized into domain folders when there are
  multiple related service files.
- Avoid adding new loose service modules at the services root unless the file is
  genuinely cross-cutting and a package would make the code harder to
  understand.
- Name modules, classes, functions, variables, and tests clearly enough that the
  code explains the domain intent.
- Add file-level comments or docstrings when a file's purpose is not obvious
  from its name and location.
- Add function or method comments when behavior has important domain rules,
  non-obvious control flow, side effects, or integration constraints.
- Keep comments useful and maintainable:
  - Explain intent, constraints, and reasoning.
  - Avoid restating obvious code line by line.
  - Use the project’s standard documentation style, such as docstrings for Python and JSDoc/TSDoc for TypeScript, when documenting public APIs or complex behavior.
  - Remove stale, misleading, redundant, or unrelated comments when touching nearby code.
- Keep file and function names intuitive.

Preferred readability refactor pattern for large service files:

- Keep one public/coordinator file as the stable entrypoint.
- Move related private logic into nearby focused files.
- Group files by responsibility, such as routing, verification, formatting, memory handling, or direct tool execution.
- Re-export the main service from the package entrypoint when needed to preserve imports.

## Project-Specific Notes

For this React/Vite + FastAPI + Neo4j + LangGraph/LangChain/Gemini project:

- Keep FastAPI routes thin and move orchestration into services.
- Keep backend services in domain folders when related service files grow.
- Keep Neo4j access in repository classes and query modules.
- Keep frontend API calls inside `frontend/src/api`.
- Keep graph transformation and graph action logic inside `frontend/src/graph` where practical.
- Keep reusable frontend UI inside components and data loading inside hooks where practical.
- Keep model-generated database queries out of the execution path.

## Verify

After simplifying:

- Explain why behavior should remain the same.
- Run or suggest the smallest relevant tests or manual checks.
- Mention any behavior that might have changed accidentally.
- Mention remaining messy areas if they were intentionally left alone.

## Output Before Simplifying

For non-trivial simplification, respond briefly with:

```yaml
simplification_plan:
  current_behavior: string
  files_to_simplify:
    - path: string
      reason: string
  cleanup_opportunities:
    - string
  behavior_to_preserve:
    - string
  safe_plan:
    - string
  suggested_checks:
    - string
```

For small local cleanups, use concise prose instead of the full YAML block.
