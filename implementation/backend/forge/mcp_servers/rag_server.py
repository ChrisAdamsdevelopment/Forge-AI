"""RAG (Retrieval-Augmented Generation) MCP server.

Port 8018: Provides RAG index ingestion and semantic search.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastmcp import FastMCP
from forge.services.rag_service import rag_service
from forge.mcp_servers.base import get_port

mcp = FastMCP("RAG Retrieval Agent")


@mcp.tool(
    description="Ingest a local file into the Forge RAG index.",
    annotations={"destructiveHint": True},
)
async def ingest_rag_file(file_path: str) -> dict:
    """Ingest file to RAG index.

    Args:
        file_path: Path to file to ingest

    Returns:
        Dict with ingestion status and chunks count
    """
    return await rag_service.ingest_file(file_path)


@mcp.tool(
    description="Search the Forge RAG index for relevant chunks.",
    annotations={"readOnlyHint": True},
)
async def search_rag_index(query: str, top_k: int = 5) -> dict:
    """Search RAG index.

    Args:
        query: Search query
        top_k: Number of top results to return

    Returns:
        Dict with relevant chunks and scores
    """
    return await rag_service.search(query=query, top_k=top_k)


async def main() -> None:
    """Start RAG MCP server on port 8018."""
    port = get_port("rag")
    print(f"Starting RAG MCP Server on port {port}...")
    await mcp.run(port=port)


if __name__ == "__main__":
    asyncio.run(main())
