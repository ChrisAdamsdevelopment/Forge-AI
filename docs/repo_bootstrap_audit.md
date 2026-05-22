# Repo Bootstrap Audit

Date (UTC): 2026-05-22

## Source-pack discovery

- Source-pack layout appears to already be present in the repository root (`docs/`, `prompts/`, `modules/`, `runtime/`, `eval/`, `training/`, `implementation/`, plus top-level `CODEX_INSTRUCTIONS.md`, `README.md`, `.gitignore`).
- No extraction/copy action from `forge_improved.zip` or a separate `forge/` directory was required in this pass.

## README merge-conflict status

- `README.md` had unresolved merge-conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
- Resolved by preserving the Forge source-pack README content and removing conflict markers.

## Expected directories present/missing

Present:
- `docs/`
- `prompts/`
- `modules/`
- `runtime/`
- `eval/`
- `training/`
- `implementation/`

Missing:
- None from the expected source-pack top-level set.

## Bootstrap fixes made

1. Added missing `build-system` section to `implementation/backend/pyproject.toml` for Poetry build backend.
2. Added `implementation/backend/README.md` so the Poetry `readme = "README.md"` reference is valid.
3. Added backend smoke test under `implementation/backend/tests/test_app.py` so `cd implementation/backend && pytest` works.
4. Updated backend Dockerfile to Python 3.12 and package install via local metadata (`pip install .`).
5. Updated implementation docs curl example to match actual `/api/v1/chat` schema (`messages` array) and include bearer auth header.

## Backend test/build status

Commands executed:
- `python -m compileall implementation/backend/forge` ✅
- `cd implementation/backend && python -m pytest -q` ✅ (1 passed)
- `cd implementation/backend && python -c "from forge.main import app; print(app.title)"` ✅ (`Forge API`)

Notes:
- Test run emitted FastAPI/pytest deprecation warnings under Python 3.14 runtime in this environment.

## Intentionally deferred

- Full RAG implementation
- LangGraph loop
- MCP registry expansion
- Electron/desktop build-out
- Marketplace and fine-tuning pipeline work

## Next recommended Codex task

Implement a narrow **Phase 1 RAG ingestion/query baseline** in backend only:
- add local document ingestion endpoints,
- add a minimal retrieval pipeline with deterministic chunking,
- wire retrieval context into `/api/v1/chat` behind a feature flag,
- and add focused tests for ingestion + retrieval correctness.
