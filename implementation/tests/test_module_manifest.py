"""
tests/test_module_manifest.py

Unit tests for module manifest validation and risk classification.
Run with: pytest implementation/tests/
"""
from __future__ import annotations

import pytest

from forge.modules.runner import classify_risk, validate_manifest


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _full_manifest(**overrides) -> dict:
    base = {
        "id": "forge.test.example",
        "name": "Example Module",
        "version": "0.1.0",
        "author": "Test",
        "description": "A test module",
        "category": "utility",
        "entrypoint": "prompts/main.md",
        "input_schema": "schemas/input.schema.json",
        "output_schema": "schemas/output.schema.json",
        "permissions": {"tools": [], "roots": ["workspace"], "network": False},
        "safety": {"destructive_actions": False, "reads_secrets": False, "approval_required": []},
    }
    base.update(overrides)
    return base


# ── validate_manifest tests ───────────────────────────────────────────────────

class TestValidateManifest:
    def test_valid_full_manifest(self):
        result = validate_manifest(_full_manifest())
        assert result["valid"] is True
        assert result["missing"] == []
        assert result["invalid"] == []

    def test_missing_required_fields(self):
        result = validate_manifest({"id": "x"})
        assert result["valid"] is False
        assert "name" in result["missing"]
        assert "version" in result["missing"]
        assert "entrypoint" in result["missing"]

    def test_invalid_category(self):
        result = validate_manifest(_full_manifest(category="invalid_category"))
        assert result["valid"] is False
        assert result["invalid"]

    def test_valid_categories(self):
        for cat in ("research", "coding", "file_ops", "media", "writing", "monitoring", "utility"):
            result = validate_manifest(_full_manifest(category=cat))
            assert result["valid"] is True, f"Category '{cat}' should be valid"

    def test_approval_required_surfaced(self):
        m = _full_manifest()
        m["safety"]["approval_required"] = ["terminal.execute"]
        result = validate_manifest(m)
        assert "terminal.execute" in result["approval_required"]


# ── classify_risk tests ───────────────────────────────────────────────────────

class TestClassifyRisk:
    def test_low_risk_read_only(self):
        manifest = _full_manifest()
        manifest["permissions"]["tools"] = ["filesystem.read", "git.status"]
        assert classify_risk(manifest) == "low"

    def test_medium_risk_network(self):
        manifest = _full_manifest()
        manifest["permissions"]["network"] = True
        assert classify_risk(manifest) == "medium"

    def test_medium_risk_fetch_tool(self):
        manifest = _full_manifest()
        manifest["permissions"]["tools"] = ["web.fetch"]
        assert classify_risk(manifest) == "medium"

    def test_high_risk_terminal(self):
        manifest = _full_manifest()
        manifest["permissions"]["terminal"] = True
        assert classify_risk(manifest) == "high"

    def test_high_risk_execute_tool(self):
        manifest = _full_manifest()
        manifest["permissions"]["tools"] = ["terminal.execute"]
        assert classify_risk(manifest) == "high"

    def test_critical_risk_delete_tool(self):
        manifest = _full_manifest()
        manifest["permissions"]["tools"] = ["filesystem.delete"]
        assert classify_risk(manifest) == "critical"

    def test_critical_risk_reads_secrets(self):
        manifest = _full_manifest()
        manifest["permissions"]["reads_secrets"] = True
        assert classify_risk(manifest) == "critical"

    def test_requires_review_on_high(self):
        manifest = _full_manifest()
        manifest["permissions"]["terminal"] = True
        result = validate_manifest(manifest)
        assert result["requires_review"] is True

    def test_no_review_on_low(self):
        result = validate_manifest(_full_manifest())
        assert result["requires_review"] is False


# ── Chunker tests ─────────────────────────────────────────────────────────────

class TestChunker:
    def test_small_text_produces_one_chunk(self):
        from forge.rag.chunker import chunk_markdown
        chunks = chunk_markdown("Hello world", max_chars=2048)
        assert len(chunks) == 1
        assert chunks[0].content == "Hello world"

    def test_large_text_is_split(self):
        from forge.rag.chunker import chunk_text
        big = "line\n" * 500
        chunks = chunk_text(big, max_chars=200, overlap_chars=20)
        assert len(chunks) > 1

    def test_overlap_carries_content(self):
        from forge.rag.chunker import chunk_text
        text = "AAAA\n" * 100 + "BBBB\n" * 100
        chunks = chunk_text(text, max_chars=300, overlap_chars=50)
        # Overlap means later chunks start with content from the previous chunk
        assert len(chunks) >= 2

    def test_markdown_heading_aware(self):
        from forge.rag.chunker import chunk_markdown
        md = "# Section A\n\nContent A\n\n# Section B\n\nContent B\n"
        chunks = chunk_markdown(md, max_chars=2048)
        headings = [c.heading for c in chunks]
        assert "Section A" in headings
        assert "Section B" in headings

    def test_empty_text_returns_no_chunks(self):
        from forge.rag.chunker import chunk_markdown, chunk_text
        assert chunk_markdown("") == []
        assert chunk_text("") == []
