from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _build_allowed_roots() -> list[str]:
    """Build ALLOWED_ROOTS from environment or fall back to a safe local root."""
    env_roots = os.environ.get("FORGE_ALLOWED_ROOTS", "")
    if env_roots:
        return [r.strip() for r in env_roots.split(":") if r.strip()]

    try:
        home = Path.home()
        if str(home) and home.exists():
            return [str(home)]
    except RuntimeError as exc:
        logger.warning("Could not resolve user home directory: %s", exc)

    fallback = "C:\\" if os.name == "nt" else "/"
    logger.warning("Falling back to broad filesystem root for ALLOWED_ROOTS: %s", fallback)
    return [fallback]


ALLOWED_ROOTS = _build_allowed_roots()


def _is_allowed(path: Path) -> bool:
    resolved = path.resolve()
    for root in ALLOWED_ROOTS:
        root_path = Path(root).resolve()
        if resolved == root_path or root_path in resolved.parents:
            return True
    return False


def _ensure_allowed(path_str: str) -> Path:
    path = Path(path_str)
    if not _is_allowed(path):
        raise PermissionError(f"Path is outside ALLOWED_ROOTS: {path}")
    return path


async def file_read(path: str, lines: int | None = None) -> dict[str, str]:
    """Read a file (optionally limited to first N lines)."""
    file_path = _ensure_allowed(path)
    content = file_path.read_text(encoding="utf-8")
    if lines is not None:
        content = "\n".join(content.splitlines()[:lines])
    return {"path": str(file_path), "content": content}


async def file_write(path: str, content: str) -> dict[str, str | int]:
    """Write content to a file."""
    file_path = _ensure_allowed(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return {"status": "ok", "path": str(file_path), "bytes_written": len(content.encode("utf-8"))}


async def file_delete(path: str) -> dict[str, str]:
    """Delete a file."""
    file_path = _ensure_allowed(path)
    file_path.unlink(missing_ok=True)
    return {"status": "ok", "path": str(file_path)}


async def file_list(path: str) -> dict[str, list[str] | str]:
    """List directory contents."""
    directory = _ensure_allowed(path)
    items = [p.name for p in directory.iterdir()]
    return {"path": str(directory), "items": items}


async def file_search(directory: str, pattern: str) -> dict[str, list[str] | str]:
    """Search for files matching a glob pattern."""
    root = _ensure_allowed(directory)
    matches = [str(p) for p in root.rglob(pattern)]
    return {"directory": str(root), "pattern": pattern, "matches": matches}


async def file_mkdir(path: str) -> dict[str, str]:
    """Create a directory path."""
    directory = _ensure_allowed(path)
    directory.mkdir(parents=True, exist_ok=True)
    return {"status": "ok", "path": str(directory)}
