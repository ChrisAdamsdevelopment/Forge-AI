from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from forge.core.config import settings
from forge.rag.chunking import chunk_text_content
from forge.rag.paths import RagPathError, resolve_knowledge_path
from forge.rag.schemas import RagChunk, RagDocument, RagIngestRequest, RagIngestResult
from forge.rag.store import RagStore


@dataclass(frozen=True)
class _DiscoveryOutcome:
    ingest_paths: list[Path]
    skipped: list[dict[str, str]]


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _document_id(source_path: str, content_hash: str) -> str:
    return hashlib.sha256(f"{source_path}:{content_hash}".encode("utf-8")).hexdigest()[:24]


def discover_ingest_files(
    knowledge_root: Path | str,
    source_paths: list[str] | None,
    recurse: bool,
    allowed_extensions: list[str],
) -> _DiscoveryOutcome:
    root = Path(knowledge_root).expanduser().resolve()
    candidates: list[Path | str]
    if source_paths:
        candidates = source_paths
    else:
        if recurse:
            candidates = [p for p in root.rglob("*") if p.is_file()]
        else:
            candidates = [p for p in root.iterdir() if p.is_file()]

    ingest_set: set[Path] = set()
    skipped: list[dict[str, str]] = []

    for candidate in candidates:
        try:
            resolved = resolve_knowledge_path(root, candidate, allowed_extensions)
        except RagPathError as exc:
            skipped.append({"path": str(candidate), "reason": str(exc)})
            continue

        if resolved.is_dir():
            skipped.append({"path": str(candidate), "reason": "directory is not ingestible"})
            continue
        if not resolved.exists():
            skipped.append({"path": str(candidate), "reason": "path does not exist"})
            continue
        if not resolved.is_file():
            skipped.append({"path": str(candidate), "reason": "path is not a regular file"})
            continue

        ingest_set.add(resolved)

    return _DiscoveryOutcome(ingest_paths=sorted(ingest_set), skipped=skipped)


def _read_text_file(path: Path) -> str:
    data = path.read_bytes()
    return data.decode("utf-8")


def ingest_documents(
    request: RagIngestRequest,
    store: RagStore,
    knowledge_root: Path | str | None = None,
    allowed_extensions: list[str] | None = None,
    chunk_min_chars: int | None = None,
    chunk_target_chars: int | None = None,
    chunk_overlap_chars: int | None = None,
) -> RagIngestResult:
    root = Path(knowledge_root or settings.knowledge_root).expanduser().resolve()
    extensions = allowed_extensions or list(settings.rag_allowed_extensions)

    discovery = discover_ingest_files(
        knowledge_root=root,
        source_paths=request.source_paths,
        recurse=request.recurse,
        allowed_extensions=extensions,
    )

    result = RagIngestResult(skipped_paths=list(discovery.skipped))

    for path in discovery.ingest_paths:
        rel_source = str(path.relative_to(root))
        try:
            raw_text = _read_text_file(path)
            text = _normalize_text(raw_text)
            content_hash = _hash_text(text)
            document_id = _document_id(rel_source, content_hash)

            document = RagDocument(
                document_id=document_id,
                source_path=rel_source,
                content_hash=content_hash,
                metadata={**request.metadata},
            )

            chunks: list[RagChunk] = chunk_text_content(
                text=text,
                source_path=rel_source,
                title=document.title,
                chunk_min_chars=chunk_min_chars or settings.rag_chunk_min_chars,
                chunk_target_chars=chunk_target_chars or settings.rag_chunk_target_chars,
                chunk_overlap_chars=chunk_overlap_chars or settings.rag_chunk_overlap_chars,
            )
            for chunk in chunks:
                chunk.document_id = document_id

            store.upsert_document(document, chunks)
            result.ingested_documents += 1
            result.ingested_chunks += len(chunks)
            result.document_ids.append(document_id)
        except UnicodeDecodeError as exc:
            result.skipped_paths.append({"path": rel_source, "reason": f"utf-8 decode error: {exc}"})
        except Exception as exc:  # noqa: BLE001 - retain ingestion continuity
            result.failed_paths.append({"path": rel_source, "error": str(exc)})

    return result
