from __future__ import annotations

from pathlib import Path


class RagPathError(ValueError):
    """Raised when a requested path violates RAG safety rules."""


def normalize_allowed_extensions(extensions: list[str]) -> set[str]:
    normalized: set[str] = set()
    for ext in extensions:
        ext = ext.strip().lower()
        if not ext:
            continue
        normalized.add(ext if ext.startswith(".") else f".{ext}")
    return normalized


def resolve_knowledge_path(
    knowledge_root: Path | str,
    requested_path: Path | str,
    allowed_extensions: list[str] | set[str],
) -> Path:
    root = Path(knowledge_root).expanduser().resolve()
    requested = Path(requested_path).expanduser()

    candidate = (
        requested.resolve() if requested.is_absolute() else (root / requested).resolve()
    )

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RagPathError(f"Path is outside knowledge root: {requested_path}") from exc

    allowed = normalize_allowed_extensions(list(allowed_extensions))
    if candidate.suffix.lower() not in allowed:
        raise RagPathError(
            f"Disallowed extension for RAG ingestion: {candidate.suffix}"
        )

    return candidate
