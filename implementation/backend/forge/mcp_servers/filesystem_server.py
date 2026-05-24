"""Filesystem operations MCP server.

Port 8013: Provides file read/write/delete/search and directory operations.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastmcp import FastMCP
from forge.agent.tools.filesystem import (
    file_delete,
    file_list,
    file_mkdir,
    file_read,
    file_search,
    file_write,
)
from forge.mcp_servers.base import get_port

mcp = FastMCP("Filesystem Operations Agent")


@mcp.tool(description="Read a file and return its contents.", readOnlyHint=True)
async def read_file(path: str) -> dict:
    """Read file."""
    return await file_read(path)


@mcp.tool(description="Write text to a file (creates or overwrites).", destructiveHint=True)
async def write_file(path: str, content: str) -> dict:
    """Write file."""
    return await file_write(path, content)


@mcp.tool(description="Delete a file or directory.", destructiveHint=True)
async def delete_file(path: str) -> dict:
    """Delete file."""
    return await file_delete(path)


@mcp.tool(description="List files and directories in a path.", readOnlyHint=True)
async def list_files(path: str) -> dict:
    """List directory."""
    return await file_list(path)


@mcp.tool(description="Search for files by name pattern.", readOnlyHint=True)
async def search_files(pattern: str, directory: str = ".") -> dict:
    """Search files."""
    return await file_search(pattern, directory)


@mcp.tool(description="Create a directory and parents if needed.", destructiveHint=True)
async def create_directory(path: str) -> dict:
    """Create directory."""
    return await file_mkdir(path)


async def main() -> None:
    """Start filesystem MCP server on port 8013."""
    port = get_port("filesystem")
    print(f"Starting Filesystem MCP Server on port {port}...")
    await mcp.run(port=port)


if __name__ == "__main__":
    asyncio.run(main())
