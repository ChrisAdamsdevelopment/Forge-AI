"""Web fetching and scraping MCP server.

Port 8015: Provides web content fetching, parsing, and scraping utilities.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastmcp import FastMCP
from forge.agent.tools.web import web_fetch
from forge.mcp_servers.base import get_port

mcp = FastMCP("Web Content Fetching Agent")


@mcp.tool(
    description="Fetch and parse web content from a URL.",
    annotations={"readOnlyHint": True},
)
async def fetch_web_content(url: str, include_html: bool = False) -> dict:
    """Fetch web content.

    Args:
        url: URL to fetch
        include_html: Include raw HTML in response

    Returns:
        Dict with status, content, title, links, etc.
    """
    return await web_fetch(url, include_html=include_html)


async def main() -> None:
    """Start web MCP server on port 8015."""
    port = get_port("web")
    print(f"Starting Web MCP Server on port {port}...")
    await mcp.run(port=port)


if __name__ == "__main__":
    asyncio.run(main())
