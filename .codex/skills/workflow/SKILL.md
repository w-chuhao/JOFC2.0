---
name: workflow
description: Use when the user explicitly invokes $workflow for this repository to follow its end-to-end code workflow, or an explicitly requested focused sub-workflow, before editing, debugging, reviewing, simplifying, or planning implementation.
---

# Workflow

Use this skill only when the user explicitly asks for `$workflow`.

By default, follow the complete workflow in this sequence:

1. Explore relevant code and existing patterns with `references/explore-codebase-lite.md`.
2. Debug failures or root causes with `references/debug-code-lite.md`.
3. Simplify the intended change with `references/code-simplifier-lite.md`.
4. Review the final diff with `references/code-review-lite.md`.

Use only the corresponding focused sub-workflow when the `$workflow` prompt
explicitly makes that its sole request:

- For codebase exploration, unfamiliar-code investigation, or implementation planning, read `references/explore-codebase-lite.md`.
- For errors, failing tests, broken behavior, or root-cause investigation, read `references/debug-code-lite.md`.
- For a local code review, pre-commit review, changed-file review, or submission-safety check, read `references/code-review-lite.md`.
- For simplifying, cleanup, removing duplication, improving naming, or behavior-preserving refactoring, read `references/code-simplifier-lite.md`.

If the prompt combines a focused request with implementation, debugging, or another objective, use the complete workflow unless it clearly says to perform only the focused task. Remember to remove unused code, comments, and dead paths when simplifying or refactoring. Avoid making changes that are not directly related to the user request unless they are necessary for safety, clarity, or correctness.

## Shared Rules

1. Keep exploration targeted to the current task.
2. Prefer `rg` and `rg --files` for searches.
3. Avoid secrets, `.env` files, credential files, generated outputs, dependency folders, caches, and unrelated large artifacts.
4. Respect this repository's `AGENTS.md` boundaries.
5. Keep summaries concise unless the user asks for a broader architecture view.
6. If the user asks to implement or fix, investigate first, then make the smallest safe change once the relevant pattern or root cause is clear.
7. Prefer readability-oriented structure when editing:
   - When a file mixes multiple responsibilities or grows into a catch-all module, prefer splitting it into focused files or a small package with a clear entrypoint.
   - Keep external behavior and public imports stable unless the user explicitly asks to change them.
   - Prefer a main coordinator file that calls smaller domain-specific helpers when that makes the code easier to read and maintain.
