"""Memory persistence MCP server.

Port 8016: Provides persistent memory storage, retrieval, and search.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastmcp import FastMCP
from forge.agent.tools.memory import memory_retrieve, memory_store
from forge.mcp_servers.base import get_port

mcp = FastMCP("Memory Persistence Agent")


@mcp.tool(description="Store data in persistent memory.", destructiveHint=True)
async def store_memory(key: str, value: str, tags: list[str] | None = None) -> dict:
    """Store memory entry.
    
    Args:
        key: Memory key
        value: Memory value
        tags: Optional tags for categorization
        
    Returns:
        Dict with status and stored key
    """
    return await memory_store(key, value, tags=tags)


@mcp.tool(description="Retrieve data from persistent memory.", readOnlyHint=True)
async def retrieve_memory(key: str) -> dict:
    """Retrieve memory entry.
    
    Args:
        key: Memory key to retrieve
        
    Returns:
        Dict with status and value
    """
    return await memory_retrieve(key)


async def main() -> None:
    """Start memory MCP server on port 8016."""
    port = get_port("memory")
    print(f"Starting Memory MCP Server on port {port}...")
    await mcp.run(port=port)


if __name__ == "__main__":
    asyncio.run(main())
