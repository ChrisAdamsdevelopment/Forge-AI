"""Sequential thinking and reasoning MCP server.

Port 8017: Provides structured thinking and reasoning tools.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastmcp import FastMCP
from forge.agent.tools.thinking import sequential_thinking
from forge.mcp_servers.base import get_port

mcp = FastMCP("Sequential Thinking Agent")


@mcp.tool(description="Perform sequential reasoning and thinking steps.", annotations={"readOnlyHint": True})
async def think_through(problem: str, steps: int = 5) -> dict:
    """Sequential thinking.
    
    Args:
        problem: Problem to think through
        steps: Number of thinking steps
        
    Returns:
        Dict with reasoning steps and conclusion
    """
    return await sequential_thinking(problem, num_steps=steps)


async def main() -> None:
    """Start thinking MCP server on port 8017."""
    port = get_port("thinking")
    print(f"Starting Thinking MCP Server on port {port}...")
    await mcp.run(port=port)


if __name__ == "__main__":
    asyncio.run(main())
