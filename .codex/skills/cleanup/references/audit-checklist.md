# Audit Checklist

Use this checklist to make cleanup evidence explicit.

## Read-Only Discovery

Start with:

```powershell
git status --short
Get-ChildItem . -Force
Get-ChildItem backend,frontend,docs,.codex -Force
```

Prefer `rg` for searches when it works:

```powershell
rg -n "OldName|old_file|old/path" backend frontend docs .codex
rg --files backend frontend docs .codex
```

Fallback:

```powershell
Get-ChildItem backend,frontend,docs,.codex -Recurse -File |
  Select-String -Pattern "OldName","old_file","old/path"
```

## Backend Checks

Check:

- imports and package `__init__.py` exports
- FastAPI router inclusion and dependency providers
- service constructor injection sites
- repository method usage
- LangGraph runner nodes and tool providers
- tool metadata registration
- memory/session/pipeline worker entrypoints
- migration and README command references
- tests for imported names and expected response shapes

Suggested verification:

```powershell
python -m compileall backend\app
python -m pytest backend\tests\test_changed_area.py
python -m pytest backend\tests
```

## Frontend Checks

Check:

- `frontend/src/main.tsx` and `App.tsx`
- component imports
- hooks and API clients
- graph helper imports
- CSS class names referenced in JSX
- route or tab wiring
- Vite/TypeScript build

Suggested verification:

```powershell
npm run build
```

## Docs And Skill Checks

Check:

- README links and commands
- AGENTS guidance
- architecture docs
- local `.codex/skills/*/SKILL.md`
- skill references and agents metadata

Suggested verification:

```powershell
python D:\Codex\.codex\skills\.system\skill-creator\scripts\quick_validate.py .codex\skills\<skill-name>
```

## Cleanup Report Format

Report:

```text
Removed:
- path/symbol: evidence and reason

Renamed:
- old -> new: reason and compatibility impact

Deferred:
- candidate: missing evidence or risk

Checks:
- command: result
```
