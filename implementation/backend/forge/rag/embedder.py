from __future__ import annotations

from typing import Any

import httpx

from forge.core.config import settings


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    payload: dict[str, Any] = {
        "model": settings.embed_model or "bge-m3",
        "input": texts,
    }
    url = f"{settings.ollama_base_url}/api/embed"

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    embeddings = data.get("embeddings") or []
    vectors: list[list[float]] = [[float(v) for v in emb] for emb in embeddings]
    if len(vectors) != len(texts):
        raise ValueError(
            f"Embedding count mismatch: expected {len(texts)} got {len(vectors)}"
        )
    return vectors


async def embed_query(text: str) -> list[float]:
    vectors = await embed_texts([text])
    return vectors[0] if vectors else []
