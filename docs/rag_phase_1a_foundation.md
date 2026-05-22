# RAG Phase 1A Foundation

## Implemented in this phase

Phase 1A adds backend-only RAG foundation components without wiring retrieval into chat:

- **Configuration defaults** for curated knowledge-root and chunking behavior in `forge.core.config.Settings`.
- **RAG schemas** for document/chunk/ingestion/search/citation records in `implementation/backend/forge/rag/schemas.py`.
- **Deterministic chunking utility** in `implementation/backend/forge/rag/chunking.py`:
  - heading-aware Markdown sectioning,
  - plain text fallback,
  - deterministic chunk IDs based on source path + chunk index + content hash,
  - character offsets retained for citation mapping.
- **Knowledge-root path safety helper** in `implementation/backend/forge/rag/paths.py`:
  - resolves candidate paths,
  - enforces in-root access,
  - rejects traversal and out-of-root absolute paths,
  - enforces allowed extensions.
- **Unit tests** for chunking determinism and path safety under `implementation/backend/tests/`.

## Intentionally deferred

This phase intentionally does **not** implement:

- vector database writes/reads,
- embeddings,
- reranking,
- chat endpoint retrieval injection,
- ingestion/upload API routes,
- MCP filesystem wiring,
- browser/desktop/module-runner/training features.

## Supported file types (current foundation)

RAG path validation defaults to curated text types only:

- `.md`
- `.markdown`
- `.txt`

## Root safety model

- RAG operations must resolve inside configured `FORGE_KNOWLEDGE_ROOT`.
- Relative paths are resolved against this root.
- Absolute paths are allowed only when still inside this root.
- Any traversal/out-of-root target is rejected.
- Disallowed extensions are rejected before ingestion operations proceed.

This matches Forge curated-source-only policy and avoids broad filesystem scanning.

## Next recommended task

Implement **Phase 1B ingestion service layer** (no chat wiring yet):

1. File discovery constrained to knowledge root + allowed extensions.
2. Safe file read and hashing.
3. Document + chunk creation using current schemas/chunker.
4. Persistence abstraction (interface only first, concrete store in later phase).
5. Tests for idempotent re-ingestion and skip behavior.
