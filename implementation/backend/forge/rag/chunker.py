"""
forge/rag/chunker.py

Splits documents into overlapping chunks suitable for embedding.
Supports: Markdown (heading-aware), plain text, and code files.

All sizes are in approximate characters (chars ÷ 4 ≈ tokens).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Chunk:
    content: str
    index: int
    source: str = ""
    heading: str = ""          # nearest Markdown heading, if any
    char_start: int = 0
    metadata: dict = field(default_factory=dict)


# ── Markdown chunker ──────────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


def chunk_markdown(
    text: str,
    max_chars: int = 2048,
    overlap_chars: int = 256,
    source: str = "",
) -> list[Chunk]:
    """
    Splits Markdown text into chunks that respect heading boundaries.

    Strategy:
    1. Split on top-level headings first.
    2. If a section is still > max_chars, split on paragraphs.
    3. If a paragraph is still > max_chars, hard-split with overlap.
    """
    chunks: list[Chunk] = []
    sections = _split_on_headings(text)

    for heading, body in sections:
        if len(body) <= max_chars:
            chunks.append(
                Chunk(
                    content=body.strip(),
                    index=len(chunks),
                    source=source,
                    heading=heading,
                    char_start=text.find(body),
                )
            )
        else:
            # Split on double newlines (paragraphs)
            for para_chunk in _split_paragraphs(body, max_chars, overlap_chars):
                chunks.append(
                    Chunk(
                        content=para_chunk.strip(),
                        index=len(chunks),
                        source=source,
                        heading=heading,
                    )
                )

    return [c for c in chunks if c.content]


def _split_on_headings(text: str) -> list[tuple[str, str]]:
    """Returns list of (heading, body) pairs."""
    positions = [(m.start(), m.group(1)) for m in _HEADING_RE.finditer(text)]
    if not positions:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    for i, (pos, heading) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        body = text[pos:end]
        sections.append((heading, body))

    # Content before the first heading
    if positions[0][0] > 0:
        sections.insert(0, ("", text[: positions[0][0]]))

    return sections


def _split_paragraphs(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Split text on blank lines, then hard-split oversized paragraphs."""
    paragraphs = re.split(r"\n{2,}", text)
    result: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                result.append(current)
            if len(para) > max_chars:
                result.extend(_hard_split(para, max_chars, overlap_chars))
                current = ""
            else:
                current = para

    if current:
        result.append(current)

    return result


def _hard_split(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Last resort: split by character count with overlap."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        start = end - overlap_chars
    return chunks


# ── Plain text / code chunker ─────────────────────────────────────────────────

def chunk_text(
    text: str,
    max_chars: int = 2048,
    overlap_chars: int = 256,
    source: str = "",
) -> list[Chunk]:
    """
    Simple line-aware chunker for plain text and source code.
    Splits on newlines, keeps overlap for context continuity.
    """
    lines = text.splitlines(keepends=True)
    chunks: list[Chunk] = []
    current_lines: list[str] = []
    current_len = 0

    for line in lines:
        if current_len + len(line) > max_chars and current_lines:
            content = "".join(current_lines)
            chunks.append(Chunk(content=content.strip(), index=len(chunks), source=source))
            # Carry over the last `overlap_chars` worth of lines
            overlap: list[str] = []
            ol = 0
            for l in reversed(current_lines):
                if ol + len(l) > overlap_chars:
                    break
                overlap.insert(0, l)
                ol += len(l)
            current_lines = overlap
            current_len = ol

        current_lines.append(line)
        current_len += len(line)

    if current_lines:
        chunks.append(
            Chunk(content="".join(current_lines).strip(), index=len(chunks), source=source)
        )

    return [c for c in chunks if c.content]


# ── File dispatcher ───────────────────────────────────────────────────────────

_MD_SUFFIXES = {".md", ".mdx", ".markdown"}
_CODE_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".sh", ".bash", ".yaml", ".yml", ".toml", ".json",
}


def chunk_file(
    path: Path | str,
    max_chars: int = 2048,
    overlap_chars: int = 256,
) -> list[Chunk]:
    """
    Read a file from disk and chunk it using the appropriate strategy.
    Returns an empty list if the file cannot be read as UTF-8 text.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return []

    source = str(path)
    suffix = path.suffix.lower()

    if suffix in _MD_SUFFIXES:
        return chunk_markdown(text, max_chars, overlap_chars, source)
    else:
        return chunk_text(text, max_chars, overlap_chars, source)
