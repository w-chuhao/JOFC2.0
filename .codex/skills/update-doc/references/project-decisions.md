# Project Decisions

Use these as durable project context when updating docs.

## Current Architecture

```text
Neo4j     -> dependency graph source of truth
Postgres  -> chat sessions, session state, audit events, user preferences
LangGraph -> primary AI workflow orchestration
LangChain -> typed tools/model wrappers inside workflows
Gemini    -> current model provider
React     -> frontend graph/chat/import UI
FastAPI   -> backend API and service boundary
```

## Future Data Split

```text
Neo4j
- dependency relationships
- graph traversal
- impact/root-cause paths

Postgres
- sessions
- audit
- durable memory records
- user preferences
- app-owned metadata

Postgres + pgvector
- semantic retrieval over durable memory summaries
- similar prior investigations
- similar failure patterns

OpenSearch
- runbooks
- incidents
- tickets
- alert summaries
- selected logs or log summaries
- investigation summaries
- hybrid keyword/vector search
- filtering and aggregations

Prometheus
- metrics and time-series signals
- alert/risk inputs such as latency, error rate, saturation, restart counts

Loki or OpenSearch
- logs, depending on future scale and operational needs
```

## Current vs Future Rule

Document OpenSearch, Prometheus, Loki, Kubernetes discovery, incident detection,
and richer RAG as future or roadmap unless code/docs already show they exist.

## Long-Term Memory Rule

Long-term memory should remain authoritative in Postgres. OpenSearch may hold a
rebuildable searchable copy of selected memory records later.

Use this split:

```text
Postgres memory is authoritative.
OpenSearch memory index is disposable/rebuildable.
```
