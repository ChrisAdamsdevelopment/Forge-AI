"""Terminal execution MCP server.

Port 8012: Provides shell command execution across multiple shells.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastmcp import FastMCP
from forge.agent.tools.terminal import terminal_execute
from forge.mcp_servers.base import get_port

mcp = FastMCP("Terminal Execution Agent")


@mcp.tool(description="Execute a terminal command with optional shell and working directory.", destructiveHint=True)
async def run_terminal_cmd(
    command: str,
    shell: str = "powershell",
    working_dir: str | None = None,
) -> dict:
    """Execute terminal command.
    
    Args:
        command: Command to execute
        shell: Shell to use (powershell, cmd, wsl, bash, gitbash)
        working_dir: Optional working directory
        
    Returns:
        Dict with exit_code, stdout, stderr
    """
    return await terminal_execute(command, shell=shell, working_dir=working_dir)


async def main() -> None:
    """Start terminal MCP server on port 8012."""
    port = get_port("terminal")
    print(f"Starting Terminal MCP Server on port {port}...")
    await mcp.run(port=port)


if __name__ == "__main__":
    asyncio.run(main())
