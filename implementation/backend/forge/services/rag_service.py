from __future__ import annotations

from pathlib import Path

from forge.rag.chunker import chunk_document
from forge.rag.embedder import embed_query, embed_texts
from forge.rag.indexer import create_table, delete_document, index_document, init_db
from forge.rag.reranker import rerank
from forge.rag.retriever import retrieve

TABLE_NAME = "forge_docs"


class RagService:
    async def ingest_file(self, file_path: str) -> dict:
        path = Path(file_path).expanduser()
        text = path.read_text(encoding="utf-8", errors="replace")
        chunks = chunk_document(text)
        embeddings = await embed_texts(chunks)

        db = await init_db()
        await create_table(db, TABLE_NAME)
        await index_document(
            db,
            TABLE_NAME,
            chunks,
            embeddings,
            filename=path.name,
            metadata={"path": str(path)},
        )

        return {"filename": path.name, "chunks_count": len(chunks), "status": "indexed"}

    async def ingest_directory(self, dir_path: str, pattern: str = "*") -> dict:
        base = Path(dir_path).expanduser()
        results = []
        for file in base.glob(pattern):
            if file.is_file():
                results.append(await self.ingest_file(str(file)))
        return {
            "dir_path": str(base),
            "pattern": pattern,
            "results": results,
            "status": "ok",
        }

    async def search(self, query: str, top_k: int = 5) -> dict:
        db = await init_db()
        query_embedding = await embed_query(query)
        candidates = await retrieve(
            db, TABLE_NAME, query_embedding=query_embedding, top_k=max(top_k * 4, 20)
        )
        ranked = await rerank(query, candidates, top_k=top_k)

        context_parts = []
        for chunk in ranked:
            context_parts.append(
                f"[DOC: {chunk.get('filename', 'unknown')}] {chunk.get('content', '')}\n\n---"
            )

        return {
            "query": query,
            "context": "\n\n".join(context_parts),
            "chunks": ranked,
            "count": len(ranked),
            "status": "ok",
        }

    async def delete_from_index(self, filename: str) -> dict:
        db = await init_db()
        await delete_document(db, TABLE_NAME, filename)
        return {"filename": filename, "status": "deleted"}


rag_service = RagService()
