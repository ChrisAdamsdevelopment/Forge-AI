"""Browser automation MCP server.

Port 8010: Provides browser navigation, clicking, typing, screenshots, and content extraction.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastmcp import FastMCP
from forge.agent.tools.browser import (
    browser_click,
    browser_navigate,
    browser_screenshot,
    browser_type,
)
from forge.mcp_servers.base import get_port

mcp = FastMCP("Browser Automation Agent")


@mcp.tool(description="Navigate browser to the provided URL.", readOnlyHint=True)
async def browser_nav(url: str) -> dict:
    """Navigate to URL."""
    return await browser_navigate(url)


@mcp.tool(description="Capture a screenshot and return as base64.", readOnlyHint=True)
async def browser_snap() -> dict:
    """Take screenshot."""
    return await browser_screenshot()


@mcp.tool(description="Click a page element using CSS selector.", destructiveHint=True)
async def browser_btn_click(selector: str) -> dict:
    """Click element."""
    return await browser_click(selector)


@mcp.tool(description="Type text into an input field.", destructiveHint=True)
async def browser_text_input(selector: str, text: str) -> dict:
    """Type text."""
    return await browser_type(selector, text)


async def main() -> None:
    """Start browser MCP server on port 8010."""
    port = get_port("browser")
    print(f"Starting Browser MCP Server on port {port}...")
    await mcp.run(port=port)


if __name__ == "__main__":
    asyncio.run(main())
