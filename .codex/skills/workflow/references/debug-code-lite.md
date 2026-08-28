# Debug Code Lite

Use this workflow for errors, failing tests, broken features, runtime issues, API bugs, database bugs, agent/tool-calling bugs, or unexpected behavior.

## Core Rule

Do not guess and do not rewrite broadly. Capture the symptom, inspect the smallest relevant path, test likely causes, then apply the smallest safe fix when the user has asked for a fix.

For obvious one-file failures, use a compact version of this workflow and continue implementation.

## Debugging Flow

### 1. Capture The Symptom

Identify:

- Exact error message or failing behavior.
- Command, action, request, or UI step that caused it.
- Expected behavior.
- Actual behavior.
- Affected area: frontend, backend, database, agent, config, dependency, environment, or unknown.

If the user provides logs or screenshots, extract only the relevant error details.

### 2. Reproduce Or Trace

Use the smallest useful check:

- Inspect the failing file, stack frame, route, component, service, repository, query, or test.
- Inspect nearby error handling and data mapping.
- Inspect config or environment variables only when directly relevant.
- Run the smallest targeted test or command when practical.

Avoid scanning the whole repo unless the failure clearly crosses multiple areas.

### 3. Build Hypotheses

For ambiguous failures, create 2-4 possible causes. For obvious failures, name the single likely cause and verify it.

For each hypothesis, include:

- Why it might be true.
- What evidence supports it.
- What evidence would disprove it.
- Which file or command can verify it.

Do not commit to a cause without evidence.

### 4. Narrow Down

Check the highest-probability hypothesis first.

Prefer:

- Reading the exact failing path.
- Running the smallest relevant test.
- Checking the exact function, route, query, component, or data shape involved.
- Comparing expected frontend/backend response shapes with actual shapes.

Avoid broad refactors and unrelated cleanup.

### 5. Fix Safely

When the user asks to fix the issue:

1. Modify only the files needed for the confirmed root cause.
2. Preserve existing style, naming, and boundaries.
3. Keep FastAPI routes thin and put orchestration in services.
4. Keep Neo4j access in repositories or query modules.
5. Keep frontend API calls in `frontend/src/api`, graph logic in `frontend/src/graph`, reusable UI in components, and data loading in hooks where practical.
6. Avoid new dependencies unless necessary.
7. Add or update a small focused test when the project already has tests for the affected area.
8. Explain uncertainty before editing if the root cause cannot be confirmed.

### 6. Verify

After fixing, provide:

- Command run and result.
- Manual test steps if no automated test exists.
- Expected result.
- Remaining risks, if any.

## Output Before Fixing

For non-trivial debugging, respond briefly with:

```yaml
debug_summary:
  symptom: string
  affected_area: frontend | backend | database | agent | config | dependency | environment | unknown
  likely_files:
    - path: string
      reason: string
  hypotheses:
    - cause: string
      evidence_for: string
      evidence_needed: string
  next_check:
    - string
  safe_fix_plan:
    - string
```

For simple obvious failures, use a short prose summary instead of the full YAML block.
