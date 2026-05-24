# CODEX Backlog

## P0 — Keep repo health clean
- Purpose: keep compile/tests/docs green each PR.
- Likely files: test suite, docs, lint config.
- Acceptance: compile + tests pass; no unauthorized scope creep.
- Non-goals: major architecture changes.

## P1 — Finish RAG ingestion/query baseline
- Purpose: complete service-only ingestion + deterministic retrieval baseline.
- Likely files: `forge/rag/*`, RAG docs/tests.
- Acceptance: ingestion + retrieval tests pass with citations.
- Non-goals: embeddings/vector DB.

## P1.5 — StreamingResponseParser
- Purpose: robust streaming parser for model/tool output.
- Likely files: inference streaming modules/tests.
- Acceptance: parser handles partial chunks and malformed boundaries.
- Non-goals: tool policy redesign.

## P1.5 — Template metadata loader
- Purpose: cache model/template metadata and warn on mismatch.
- Likely files: inference client/template loader/tests.
- Acceptance: cached metadata path + mismatch warnings.
- Non-goals: model serving changes.

## P2 — Reranker interface with keyword fallback
- Purpose: abstraction for reranking with default lightweight fallback.
- Likely files: retrieval/rerank modules/tests.
- Acceptance: interface + fallback ranking integrated.
- Non-goals: heavy ML deps in baseline.

## P2 (later) — Optional BGE reranker
- Purpose: optional higher-quality reranking path.
- Likely files: reranker adapters/config/tests.
- Acceptance: feature-flagged optional integration.
- Non-goals: mandatory dependency.

## P3 — MCP/tool policy tests
- Purpose: verify tool boundaries and policy handling.
- Likely files: tool policy tests/docs.
- Acceptance: golden tests for allow/deny paths.
- Non-goals: new tool protocol.

## P4 — Testing strategy + CI
- Purpose: codify test layers and automate in CI.
- Likely files: CI workflows + testing strategy doc.
- Acceptance: CI workflow running compile/tests + strategy doc.
- Non-goals: deployment pipeline.

## P5 — Forge Lite scope
- Purpose: define and ship limited distribution profile.
- Likely files: packaging/runtime docs/scripts.
- Acceptance: scope doc + reproducible local package flow.
- Non-goals: full Electron/mobile feature parity.

## P6 — Electron process manager spec
- Purpose: formal lifecycle spec for desktop runtime.
- Likely files: architecture specs + runtime manager modules.
- Acceptance: approved spec with startup/health/shutdown requirements.
- Non-goals: full implementation.

## P7 — Dataset builder/exporter
- Purpose: export validated JSONL from rated sessions.
- Likely files: sessions/export/training docs/tests.
- Acceptance: deterministic validated exporter.
- Non-goals: model training orchestration.
