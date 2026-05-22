from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RagDocument(BaseModel):
    document_id: str
    source_path: str
    title: str | None = None
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagChunk(BaseModel):
    chunk_id: str
    document_id: str
    source_path: str
    chunk_index: int = Field(ge=0)
    heading_path: list[str] = Field(default_factory=list)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    text: str
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagIngestRequest(BaseModel):
    source_paths: list[str] = Field(default_factory=list)
    recurse: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagIngestResult(BaseModel):
    ingested_documents: int = 0
    ingested_chunks: int = 0
    skipped_paths: list[dict[str, str]] = Field(default_factory=list)
    failed_paths: list[dict[str, str]] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)


class RagSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=100)
    metadata_filter: dict[str, Any] = Field(default_factory=dict)


class RagCitation(BaseModel):
    chunk_id: str
    source_path: str
    title: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)


class RagSearchResult(BaseModel):
    chunk: RagChunk
    score: float
    citation: RagCitation
