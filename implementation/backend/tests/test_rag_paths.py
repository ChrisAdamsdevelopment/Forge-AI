from pathlib import Path

import pytest

from forge.rag.paths import RagPathError, resolve_knowledge_path


def test_reject_path_traversal_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()

    with pytest.raises(RagPathError):
        resolve_knowledge_path(root, "../../etc/passwd", [".md", ".txt"])


def test_reject_disallowed_extension(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()

    with pytest.raises(RagPathError):
        resolve_knowledge_path(root, "safe/file.py", [".md", ".txt"])


def test_accept_valid_markdown_path_inside_root(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()

    resolved = resolve_knowledge_path(root, "docs/guide.md", [".md", ".txt"])
    assert resolved == (root / "docs/guide.md").resolve()
