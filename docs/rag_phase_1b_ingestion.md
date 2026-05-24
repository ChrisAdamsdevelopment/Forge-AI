# RAG Phase 1B — Ingestion Service

Phase 1B adds a backend-only ingestion service layer for safe discovery, text read, hashing, chunk generation, and in-memory persistence.

## Implemented behavior
- Root-constrained file discovery with deterministic sorted ordering.
- Extension filtering and structured skipped-path reasons.
- UTF-8 safe read with decode-error handling per file.
- SHA-256 content hashing with deterministic document id from relative source path + hash.
- Chunk generation via existing `chunk_text_content` helper, then rebinding chunk `document_id` to ingestion document id.
- In-memory upsert/list/get store abstraction.
- Ingestion result reporting for ingested counts, skipped paths, failed paths, and document ids.

## Safety model
- All requested inputs are resolved via `resolve_knowledge_path` against configured knowledge root.
- Out-of-root traversal attempts are rejected and reported.
- Files are processed independently so one bad file cannot terminate the full batch.

## Skipped/failed handling
- Skipped paths include disallowed extension, out-of-root paths, missing paths, or UTF-8 decode failures.
- Failed paths are reserved for unexpected runtime exceptions and include an error string.

## Store in this phase
- `InMemoryRagStore` supports `upsert_document`, `get_document`, `list_documents`, `list_chunks`.
- No database/vector store integration in Phase 1B.

## Deferred items
- Embeddings/vector DB/reranking.
- Chat route retrieval injection.
- Template metadata loader and streaming parser.
- CI expansion and runtime packaging tasks.

## Next recommended Codex task
Phase 1C: retrieval/query baseline over in-memory docs/chunks with deterministic keyword fallback ranking and citations.
