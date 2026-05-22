from pathlib import Path

from forge.rag.ingestion import discover_ingest_files, ingest_documents
from forge.rag.schemas import RagIngestRequest
from forge.rag.store import InMemoryRagStore


def test_recursive_discovery_only_allowed_extensions(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    (root / "a").mkdir(parents=True)
    (root / "a/doc.md").write_text("hello", encoding="utf-8")
    (root / "a/notes.txt").write_text("hello", encoding="utf-8")
    (root / "a/code.py").write_text("print(1)", encoding="utf-8")

    found = discover_ingest_files(root, source_paths=None, recurse=True, allowed_extensions=[".md", ".txt"])

    assert [p.name for p in found.ingest_paths] == ["doc.md", "notes.txt"]
    assert any("Disallowed extension" in s["reason"] for s in found.skipped)


def test_out_of_root_paths_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")

    found = discover_ingest_files(root, source_paths=[str(outside)], recurse=False, allowed_extensions=[".md"])
    assert not found.ingest_paths
    assert any("outside knowledge root" in item["reason"] for item in found.skipped)


def test_bad_file_does_not_fail_entire_run(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    (root / "good.md").write_text("# title\nvalid text" * 40, encoding="utf-8")
    (root / "bad.md").write_bytes(b"\xff\xfe\x00")

    store = InMemoryRagStore()
    result = ingest_documents(RagIngestRequest(recurse=True), store=store, knowledge_root=root, allowed_extensions=[".md"])

    assert result.ingested_documents == 1
    assert result.ingested_chunks >= 1
    assert result.skipped_paths


def test_repeated_ingestion_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    (root / "doc.md").write_text("# Title\n" + ("body\n" * 200), encoding="utf-8")
    req = RagIngestRequest(recurse=True)
    store = InMemoryRagStore()

    first = ingest_documents(req, store=store, knowledge_root=root, allowed_extensions=[".md"])
    second = ingest_documents(req, store=store, knowledge_root=root, allowed_extensions=[".md"])

    assert first.document_ids == second.document_ids
    assert len(store.list_documents()) == 1


def test_content_change_updates_document_and_chunks(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    path = root / "doc.md"
    path.write_text("alpha\n" * 250, encoding="utf-8")
    req = RagIngestRequest(recurse=True)
    store = InMemoryRagStore()

    first = ingest_documents(req, store=store, knowledge_root=root, allowed_extensions=[".md"])
    path.write_text("beta\n" * 250, encoding="utf-8")
    second = ingest_documents(req, store=store, knowledge_root=root, allowed_extensions=[".md"])

    assert first.document_ids[0] != second.document_ids[0]
    second_repeat = ingest_documents(req, store=store, knowledge_root=root, allowed_extensions=[".md"])
    assert second.document_ids == second_repeat.document_ids
    assert second.ingested_chunks == second_repeat.ingested_chunks


def test_chunks_reference_document_id_and_no_outside_reads(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    (root / "doc.md").write_text("# T\n" + ("hello\n" * 200), encoding="utf-8")
    outside = tmp_path / "secret.md"
    outside.write_text("dontread", encoding="utf-8")

    store = InMemoryRagStore()
    req = RagIngestRequest(source_paths=["doc.md", str(outside)], recurse=False)
    result = ingest_documents(req, store=store, knowledge_root=root, allowed_extensions=[".md"])

    docs = store.list_documents()
    chunks = store.list_chunks(docs[0].document_id)
    assert chunks
    assert all(c.document_id == docs[0].document_id for c in chunks)
    assert any("outside knowledge root" in s.get("reason", "") for s in result.skipped_paths)
