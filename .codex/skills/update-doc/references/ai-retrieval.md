# AI And Retrieval Guidance

Use this reference when updating docs about graph chat, agent workflows, memory,
OpenSearch, RAG, or generated queries.

## Orchestration

Keep LangGraph as the primary orchestration layer for multi-step workflows.

PydanticAI may be considered only for narrow helper roles such as structured
output or schema validation if it improves a specific LangGraph node without
reducing safety, testability, auditability, or workflow visibility.

## Query Safety

Do not recommend free-form model-generated SQL, Cypher, OpenSearch DSL, PromQL,
or log queries for the normal user workflow.

Prefer approved typed tools with validated structured parameters. Backend
services should build and execute the actual queries.

Prefer generic typed tools over many one-off tools when the domain supports it:

```text
queryDependencyImpact(...)
searchOperationalEvidence(...)
aggregateOperationalEvents(...)
```

## Parallel Evidence Gathering

Document future parallel querying as bounded, dependency-aware concurrency.

Good pattern:

```text
resolve system IDs and graph scope
-> plan evidence needs
-> run independent lookups concurrently with semaphores
-> normalize partial evidence
-> verify and answer
```

Use concurrency limits at multiple levels:

- global investigation limit
- per-session limit
- per-incident limit
- per-backend limits for OpenSearch, metrics, logs, databases, and model calls

Do not recommend blind fanout. Narrow scope with the graph before launching
high-volume log, metric, or OpenSearch queries. If one backend fails or times
out, return partial evidence with explicit source status where possible.

## OpenSearch

Document OpenSearch as a future search database/search engine, not just a
library and not a replacement for Neo4j or Postgres.

OpenSearch is useful for:

- large-scale text search
- hybrid keyword/vector retrieval
- metadata filtering
- aggregations
- log-style search
- evidence retrieval over runbooks, incidents, tickets, alerts, and summaries

OpenSearch should sit behind typed backend tools:

```text
searchOperationalEvidence(query, sources, filters, limit)
searchRunbooks(query, systemId?, tags?, limit?)
searchIncidents(query, systemId?, timeRange?, severity?, limit?)
searchTickets(query, systemId?, status?, timeRange?, limit?)
aggregateOperationalEvents(metric, groupBy, filters, timeRange)
```

## Ingestion

Use a Bronze/Silver/Gold lifecycle for searchable operational evidence:

```text
Bronze/raw
  original uploaded/imported source
Silver/extracted
  text, tables, metadata, source references, normalized system IDs
Gold/enriched
  chunks, embeddings, summaries, labels, search records
```

Use asynchronous enrichment with concurrency limits for repeated model calls.

## RAG Evaluation

When documenting RAG, include evaluation, not just embeddings.

Useful metrics:

```text
coverage
- whether known answer spans appear fully inside at least one chunk

precision/noise
- how much unrelated text surrounds the answer in the chunk

retrieval hit rate
- whether expected sources appear in top results

citation usefulness
- whether returned references are specific enough to inspect
```

Short chunks usually improve precision. Long chunks usually improve coverage.
Default chunking should be based on measured project data.
