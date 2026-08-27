---
name: update-doc
description: Use when the user explicitly invokes $update-doc, "Update Doc", or asks to update this repository's documentation based on the current chat discussion, architecture decisions, roadmap ideas, implementation tradeoffs, or future project direction. Applies to README, AGENTS.md, structure.md, docs/future-architecture.md, docs/ai-agent-architecture.md, docs/chatbot.md, docs/database.md, docs/graph-schema.md, and related repo docs.
---

# Update Doc

Use this skill only for this repository.

DO NOT UPDATE rag-architecture.md and unused.md.

Purpose: update project documentation from the current conversation context so
future Codex sessions and the developer can refer back to durable decisions,
tradeoffs, constraints, and roadmap direction.

## Start Here

Always read:

- `references/workflow.md`
- `references/doc-map.md`

Then read only the relevant reference files:

- `references/project-decisions.md` for current-vs-future architecture,
  storage boundaries, and platform direction.
- `references/ai-retrieval.md` for LangGraph, PydanticAI positioning,
  generated-query boundaries, OpenSearch, memory, and RAG evaluation.
- `references/verification.md` before finishing.

## Core Rules

1. Preserve the distinction between current implementation and future roadmap.
2. Prefer updating existing docs over creating new docs.
3. Do not add chat transcripts. Convert discussion into stable documentation.
4. Do not imply a feature exists today unless source code or existing docs show
   it exists.
5. Keep docs concise, durable, and project-specific.
