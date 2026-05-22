from forge.rag.chunking import chunk_text_content


def test_markdown_chunks_include_heading_path() -> None:
    text = """# Top\nIntro text that is definitely long enough to survive min chars.\n\n## Child\nMore child section content that should be chunked with heading context."""
    chunks = chunk_text_content(
        text=text,
        source_path="docs/guide.md",
        chunk_min_chars=20,
        chunk_target_chars=80,
        chunk_overlap_chars=10,
    )

    assert chunks
    assert any(c.heading_path == ["Top"] for c in chunks)
    assert any(c.heading_path == ["Top", "Child"] for c in chunks)


def test_plain_text_chunking_is_deterministic_and_stable_ids() -> None:
    text = "\n".join([f"line {i} plain text content" for i in range(1, 80)])

    chunks_a = chunk_text_content(
        text=text,
        source_path="notes/reference.txt",
        chunk_min_chars=10,
        chunk_target_chars=180,
        chunk_overlap_chars=20,
    )
    chunks_b = chunk_text_content(
        text=text,
        source_path="notes/reference.txt",
        chunk_min_chars=10,
        chunk_target_chars=180,
        chunk_overlap_chars=20,
    )

    assert [c.text for c in chunks_a] == [c.text for c in chunks_b]
    assert [c.chunk_id for c in chunks_a] == [c.chunk_id for c in chunks_b]
