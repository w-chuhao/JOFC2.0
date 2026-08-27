# Documentation Map

Use this map to decide where each update belongs.

## `README.md`

Use for high-level current state, setup implications, short roadmap notes, and
links to deeper docs. Avoid detailed architecture essays here.

## `AGENTS.md`

Use for durable repo guidance for future agents, code boundaries, AI/tooling
rules that affect future edits, and concise future direction that changes
implementation choices. Keep it short.

## `docs/index.md`

Use as the first routing file for project documentation. Keep it short and link to focused chapter files.

## `structure.md` and `docs/app/`

Use `structure.md` as a short router. Put current request flow, source layout, backend/frontend boundaries, and current implementation details in the relevant `docs/app/` chapter.

## `docs/ai-agent-architecture.md` and `docs/ai/`

Use `docs/ai-agent-architecture.md` as a short router. Put LangGraph workflow, tool safety, memory behavior, RAG/tool-use architecture, verifier behavior, PydanticAI positioning, and generated query boundaries in focused `docs/ai/` chapters.

## `docs/future-architecture.md` and `docs/architecture/`

Use `docs/future-architecture.md` as a short router. Put long-term platform roadmap, observability, OpenSearch, Kubernetes, incidents, logs, metrics, traces, ingestion pipelines, detection and risk scoring, and frontend evidence panels in focused `docs/architecture/` chapters.

## `docs/chatbot.md`

Use for user-facing graph chat behavior, agent tool contract, future tool
families, and safety boundaries.

## `docs/database.md` and `docs/database/`

Use `docs/database.md` as a short router. Put current Neo4j/Postgres responsibilities, future database/search backend responsibilities, memory storage boundaries, and OpenSearch index roles in focused `docs/database/` chapters.

## `docs/rag-plan-b-without-opensearch.md` and `docs/rag/plan-b/`

Use the root file as a short router. Put fallback Postgres/pgvector RAG, Loki/Prometheus summary storage, continuous monitoring, Gemini review, ingestion, retrieval, evaluation, and OpenSearch migration details in focused `docs/rag/plan-b/` chapters.

## `docs/graph-schema.md`

Use for Neo4j graph model, dependency direction, node/edge fields, and traversal
semantics.
