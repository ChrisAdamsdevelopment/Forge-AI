from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa

DB_PATH = Path("~/.forge/lancedb").expanduser()


def _schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("content", pa.string()),
            pa.field("embedding", pa.list_(pa.float32(), 1024)),
            pa.field("metadata", pa.string()),
            pa.field("filename", pa.string()),
            pa.field("chunk_index", pa.int32()),
        ]
    )


async def init_db() -> lancedb.AsyncConnection:
    DB_PATH.mkdir(parents=True, exist_ok=True)
    return await lancedb.connect_async(str(DB_PATH))


async def create_table(db: lancedb.AsyncConnection, table_name: str):
    names = await db.table_names()
    if table_name in names:
        return await db.open_table(table_name)
    return await db.create_table(table_name, schema=_schema())


async def index_document(
    db,
    table_name: str,
    chunks: list[str],
    embeddings: list[list[float]],
    filename: str,
    metadata: dict | None = None,
):
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings length mismatch")
    table = await create_table(db, table_name)
    metadata = metadata or {}
    rows: list[dict[str, Any]] = []
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "content": chunk,
                "embedding": [float(v) for v in emb],
                "metadata": json.dumps(metadata),
                "filename": filename,
                "chunk_index": i,
            }
        )
    if rows:
        await table.add(rows)


async def delete_document(db, table_name: str, filename: str):
    names = await db.table_names()
    if table_name not in names:
        return
    table = await db.open_table(table_name)
    safe_filename = filename.replace("'", "''")
    await table.delete(f"filename = '{safe_filename}'")
