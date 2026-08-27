# Verification

Before finishing a documentation update:

1. Run `git diff` for changed docs.
2. Search for key terms added or changed.
3. Check that current implementation is not overstated as already built.
4. Check that roadmap items are in roadmap docs or clearly labeled as future.
5. Check that `AGENTS.md` remains concise.
6. Check that no secrets, env values, generated outputs, dependency folders, or
   scratch files were edited.
7. In the final answer, list changed files and summarize the durable decisions
   added.

Useful commands:

```powershell
git diff -- README.md AGENTS.md structure.md docs
Select-String -Path README.md,AGENTS.md,structure.md,docs\*.md -Pattern "OpenSearch|PydanticAI|RAG|generated query"
git status --short
```
