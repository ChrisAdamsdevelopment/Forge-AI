from __future__ import annotations

import hashlib
import re
from pathlib import Path

from forge.rag.schemas import RagChunk

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _markdown_sections(text: str) -> list[dict]:
    matches = list(_HEADING_RE.finditer(text))
    sections: list[dict] = []

    if not matches:
        return [{"heading_path": [], "start": 0, "end": len(text), "text": text}]

    # preface before first heading
    if matches[0].start() > 0:
        sections.append({"heading_path": [], "start": 0, "end": matches[0].start(), "text": text[: matches[0].start()]})

    stack: list[str] = []
    levels: list[int] = []
    for i, match in enumerate(matches):
        level = len(match.group(1))
        heading = match.group(2).strip()
        while levels and levels[-1] >= level:
            levels.pop()
            stack.pop()
        levels.append(level)
        stack.append(heading)

        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append({"heading_path": list(stack), "start": start, "end": end, "text": text[start:end]})

    return sections


def _split_with_overlap(text: str, base_offset: int, target: int, overlap: int) -> list[tuple[int, int, str]]:
    cleaned = text.strip()
    if not cleaned:
        return []
    # map stripped positions
    left_trim = len(text) - len(text.lstrip())
    start = base_offset + left_trim
    data = cleaned

    if len(data) <= target:
        return [(start, start + len(data), data)]

    spans = []
    cursor = 0
    step = max(1, target - overlap)
    while cursor < len(data):
        end = min(len(data), cursor + target)
        spans.append((start + cursor, start + end, data[cursor:end]))
        if end == len(data):
            break
        cursor += step
    return spans


def chunk_text_content(
    text: str,
    source_path: str,
    title: str | None = None,
    chunk_min_chars: int = 200,
    chunk_target_chars: int = 1200,
    chunk_overlap_chars: int = 120,
) -> list[RagChunk]:
    suffix = Path(source_path).suffix.lower()
    sections = _markdown_sections(text) if suffix in {".md", ".markdown"} else [{"heading_path": [], "start": 0, "end": len(text), "text": text}]

    chunks: list[RagChunk] = []
    document_id = _sha256(source_path)[:16]

    for section in sections:
        spans = _split_with_overlap(section["text"], section["start"], chunk_target_chars, chunk_overlap_chars)
        for start, end, chunk_text in spans:
            if len(chunk_text.strip()) < chunk_min_chars and chunks:
                # merge small tail chunks into previous chunk for stability
                prev = chunks[-1]
                prev.text = f"{prev.text}\n\n{chunk_text}".strip()
                prev.char_end = end
                prev.content_hash = _sha256(prev.text)
                prev.chunk_id = _sha256(f"{source_path}:{prev.chunk_index}:{prev.content_hash}")[:24]
                continue
            content_hash = _sha256(chunk_text)
            chunk_index = len(chunks)
            chunk_id = _sha256(f"{source_path}:{chunk_index}:{content_hash}")[:24]
            chunks.append(
                RagChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    source_path=source_path,
                    chunk_index=chunk_index,
                    heading_path=section["heading_path"],
                    char_start=start,
                    char_end=end,
                    text=chunk_text,
                    content_hash=content_hash,
                    metadata={"title": title} if title else {},
                )
            )

    return chunks
