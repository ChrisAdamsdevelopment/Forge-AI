"""Screen capture and input MCP server.

Port 8011: Provides screen capture, mouse, keyboard, and coordinate utilities.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastmcp import FastMCP
from forge.agent.tools.screen import (
    keyboard_press,
    keyboard_type,
    mouse_click,
    mouse_move,
    mouse_position,
    screen_capture,
)
from forge.mcp_servers.base import get_port

mcp = FastMCP("Screen Capture & Input Agent")


@mcp.tool(description="Capture the current screen and return as base64.", readOnlyHint=True)
async def screen_shot() -> dict:
    """Capture screen."""
    return await screen_capture()


@mcp.tool(description="Get current mouse position as (x, y).", readOnlyHint=True)
async def mouse_pos() -> dict:
    """Get mouse position."""
    return await mouse_position()


@mcp.tool(description="Move mouse to coordinates.", destructiveHint=True)
async def mouse_mv(x: int, y: int) -> dict:
    """Move mouse."""
    return await mouse_move(x, y)


@mcp.tool(description="Click at coordinates with optional button.", destructiveHint=True)
async def mouse_btn_click(x: int, y: int, button: str = "left") -> dict:
    """Click mouse."""
    return await mouse_click(x, y, button)


@mcp.tool(description="Type text using keyboard.", destructiveHint=True)
async def keyboard_txt(text: str) -> dict:
    """Type text."""
    return await keyboard_type(text)


@mcp.tool(description="Press a keyboard key (e.g., 'Enter', 'Tab', 'Escape').", destructiveHint=True)
async def keyboard_key_press(key: str) -> dict:
    """Press key."""
    return await keyboard_press(key)


async def main() -> None:
    """Start screen MCP server on port 8011."""
    port = get_port("screen")
    print(f"Starting Screen MCP Server on port {port}...")
    await mcp.run(port=port)


if __name__ == "__main__":
    asyncio.run(main())
