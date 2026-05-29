from __future__ import annotations

import json


async def retrieve(
    db,
    table_name: str,
    query_embedding: list[float],
    top_k: int = 20,
    where: str | None = None,
) -> list[dict]:
    names = await db.table_names()
    if table_name not in names:
        return []

    table = await db.open_table(table_name)
    search = table.search(query_embedding).limit(top_k)
    if where:
        search = search.where(where)

    records = await search.to_list()
    results: list[dict] = []
    for row in records:
        metadata_raw = row.get("metadata", "{}")
        try:
            metadata = (
                json.loads(metadata_raw)
                if isinstance(metadata_raw, str)
                else metadata_raw
            )
        except Exception:
            metadata = {}
        results.append(
            {
                "content": row.get("content", ""),
                "filename": row.get("filename", ""),
                "metadata": metadata,
                "_distance": row.get("_distance"),
            }
        )
    return results
