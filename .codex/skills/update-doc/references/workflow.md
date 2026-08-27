# Update Workflow

Follow this workflow when updating docs from chat context.

1. Restate the documentation goal in one sentence.
2. Read the routing docs first:

```text
AGENTS.md
README.md
docs/index.md
structure.md
```

3. Read only the relevant chapter files for the task:

```text
docs/app/*.md
docs/ai/*.md
docs/architecture/*.md
docs/database/*.md
docs/rag/plan-b/*.md
docs/chatbot.md
docs/graph-schema.md
docs/presentation_script.md
```

4. Extract durable decisions from the current chat context.
5. Classify each decision as:

```text
current implementation
near-term planned work
long-term roadmap
rejected/non-goal
open question
```

6. Patch the smallest set of docs that should own those decisions.
7. Remove duplicate or scratch-note wording when converting it into proper docs.
8. Verify with `git diff` and targeted text search for key terms.
9. Report changed files and the main concepts added.

## Editing Rules

- Keep `README.md` short and link deeper details to `docs/`.
- Keep `AGENTS.md` concise; it is loaded often.
- Keep `structure.md` as a short current-flow router.
- Put detailed current-flow content in `docs/app/`.
- Put detailed future platform direction in `docs/architecture/` and route through `docs/future-architecture.md`.
- Put detailed AI/tool/memory direction in `docs/ai/` and route through `docs/ai-agent-architecture.md`.
- Use ASCII unless the edited file already needs non-ASCII.
- Do not update generated outputs, dependency folders, caches, or `.env` files.
