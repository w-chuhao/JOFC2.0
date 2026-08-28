# Code Review Lite

Use this workflow for solo local review before committing, submitting, or treating a change as done.

## Core Rule

Review like a careful engineer, not like a style linter. Find real risks first, explain why they matter, and suggest the smallest safe improvement. Do not rewrite code immediately unless the user asks for fixes after the review.

## Scope

Prefer reviewing:

1. `git status` and `git diff` changed files.
2. Files directly related to the changed behavior.
3. Tests related to the changed behavior.
4. Config or environment files only when directly relevant.

If there are no changed files, review the files or feature area the user named.

Do not scan the whole repository unless the user asks for a broad audit, architecture review, or onboarding review.

## Review Priorities

Check for issues in this order:

1. Logic bugs that cause wrong behavior.
2. Boundary conditions: empty input, null values, missing fields, invalid IDs, duplicates, failed API responses, empty database results, timeouts, or permission errors.
3. Regression risk: changed API shapes, query result shapes, function signatures, frontend state behavior, error handling, or environment assumptions.
4. Security and safety: exposed secrets, unsafe logging, injection risk, unsafe query construction, missing validation, destructive operations, or overly broad permissions.
5. Test gaps for changed behavior or important edge cases.
6. Maintainability only when it affects clarity, future changes, or defect risk.

Avoid nitpicks unless the user explicitly asks for style review.

## Project-Specific Checks

For this repository, verify relevant contracts:

- FastAPI routes stay thin and delegate orchestration to services.
- Services validate semantics and coordinate repositories, model clients, or resolvers.
- Neo4j access stays in repositories or query modules.
- Cypher uses parameters and preserves correct traversal direction, relationship type, `propagate` handling, protocol naming, and stable `systemId` mapping.
- API responses preserve stable IDs needed by the frontend to select, inspect, fit, or highlight graph nodes and edges.
- Frontend API calls stay in `frontend/src/api`.
- Graph transformation and graph actions stay in `frontend/src/graph` where practical.
- Components handle loading, empty, and error states.
- CSV import remains preview-first and writes dependency rows only during explicit apply.
- Graph chat remains read-only unless a task explicitly adds a controlled write path.
- AI workflows use approved tools and keep model-generated database queries out of execution.

## Severity

Classify findings as:

- `high`: likely incorrect behavior in common cases, security exposure, data loss risk, broken core workflow, or unsafe write behavior.
- `medium`: edge case bug, missing validation, meaningful regression risk, or missing test for changed behavior.
- `low`: maintainability, clarity, naming, or minor cleanup that is worth doing but not blocking.

Use `critical` only for immediate data loss, secret exposure, destructive behavior, or a core feature that cannot function.

## Output

Lead with findings, ordered by severity. Use file and line references when available.

If there are no actionable findings, say that clearly and still note any test gaps or residual risk.

For solo pre-commit review, use:

```yaml
self_review:
  overall_risk: low | medium | high | critical
  blocking_findings:
    - severity: critical | high | medium | low
      file: string
      issue: string
      why_it_matters: string
      suggested_fix: string
  non_blocking_notes:
    - string
  edge_cases_to_test:
    - string
  suggested_checks:
    - string
  verdict: ready_to_commit | commit_after_minor_cleanup | fix_before_commit
```

For tiny reviews, use concise prose instead of the full YAML block.
