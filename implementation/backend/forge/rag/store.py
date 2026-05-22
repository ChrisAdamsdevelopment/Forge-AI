from __future__ import annotations

from typing import Protocol

from forge.rag.schemas import RagChunk, RagDocument


class RagStore(Protocol):
    def upsert_document(self, document: RagDocument, chunks: list[RagChunk]) -> None: ...

    def get_document(self, document_id: str) -> RagDocument | None: ...

    def list_documents(self) -> list[RagDocument]: ...

    def list_chunks(self, document_id: str | None = None) -> list[RagChunk]: ...


class InMemoryRagStore:
    def __init__(self) -> None:
        self._documents: dict[str, RagDocument] = {}
        self._chunks_by_document: dict[str, list[RagChunk]] = {}

    def upsert_document(self, document: RagDocument, chunks: list[RagChunk]) -> None:
        self._documents[document.document_id] = document
        self._chunks_by_document[document.document_id] = list(chunks)

    def get_document(self, document_id: str) -> RagDocument | None:
        return self._documents.get(document_id)

    def list_documents(self) -> list[RagDocument]:
        return [self._documents[k] for k in sorted(self._documents)]

    def list_chunks(self, document_id: str | None = None) -> list[RagChunk]:
        if document_id is not None:
            return list(self._chunks_by_document.get(document_id, []))

        chunks: list[RagChunk] = []
        for doc_id in sorted(self._chunks_by_document):
            chunks.extend(self._chunks_by_document[doc_id])
        return chunks
