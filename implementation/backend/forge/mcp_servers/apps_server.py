"""Application management MCP server.

Port 8014: Provides app launching, focusing, and window management.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastmcp import FastMCP
from forge.agent.tools.apps import app_focus, app_list_windows, app_open
from forge.mcp_servers.base import get_port

mcp = FastMCP("Application Management Agent")


@mcp.tool(description="Open an application by name or path.", annotations={"destructiveHint": True})
async def open_app(app_name_or_path: str) -> dict:
    """Open application."""
    return await app_open(app_name_or_path)


@mcp.tool(description="Bring a window to focus by app name.", annotations={"destructiveHint": True})
async def focus_app(app_name: str) -> dict:
    """Focus application window."""
    return await app_focus(app_name)


@mcp.tool(description="List all open windows and applications.", annotations={"readOnlyHint": True})
async def list_open_windows() -> dict:
    """List open windows."""
    return await app_list_windows()


async def main() -> None:
    """Start apps MCP server on port 8014."""
    port = get_port("apps")
    print(f"Starting Apps MCP Server on port {port}...")
    await mcp.run(port=port)


if __name__ == "__main__":
    asyncio.run(main())
