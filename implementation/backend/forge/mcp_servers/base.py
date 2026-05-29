"""Shared FastMCP base configuration and utilities for modular MCP servers.

Provides common setup, port allocation, and ngrok registration patterns
for split domain-specific MCP servers.
"""

from __future__ import annotations

from typing import Callable

from fastmcp import FastMCP

# Port allocation for split servers
MCP_PORTS = {
    "browser": 8010,
    "screen": 8011,
    "terminal": 8012,
    "filesystem": 8013,
    "apps": 8014,
    "web": 8015,
    "memory": 8016,
    "thinking": 8017,
    "rag": 8018,
}

# Human-readable descriptions
SERVER_DESCRIPTIONS = {
    "browser": "Browser automation and web interaction",
    "screen": "Screen capture and keyboard/mouse control",
    "terminal": "Terminal and shell command execution",
    "filesystem": "File system operations (read/write/search)",
    "apps": "Application management and window control",
    "web": "Web content fetching and scraping",
    "memory": "Persistent memory storage and retrieval",
    "thinking": "Sequential thinking and reasoning tools",
    "rag": "RAG index ingestion and search",
}


def create_server(domain: str, description: str | None = None) -> FastMCP:
    """Create a FastMCP server instance for a specific domain.

    Args:
        domain: Domain name (key in MCP_PORTS)
        description: Optional override for server description

    Returns:
        FastMCP server instance

    Raises:
        ValueError: If domain not in MCP_PORTS
    """
    if domain not in MCP_PORTS:
        raise ValueError(
            f"Unknown domain: {domain}. Available: {list(MCP_PORTS.keys())}"
        )

    desc = description or SERVER_DESCRIPTIONS.get(
        domain, f"Forge {domain.title()} MCP Server"
    )
    return FastMCP(desc)


def get_port(domain: str) -> int:
    """Get the MCP server port for a domain.

    Args:
        domain: Domain name

    Returns:
        Port number

    Raises:
        ValueError: If domain not in MCP_PORTS
    """
    if domain not in MCP_PORTS:
        raise ValueError(
            f"Unknown domain: {domain}. Available: {list(MCP_PORTS.keys())}"
        )
    return MCP_PORTS[domain]


async def run_server(
    domain: str,
    register_fn: Callable[[FastMCP], None],
    port: int | None = None,
) -> None:
    """Run a domain-specific MCP server.

    Args:
        domain: Domain name (used to determine port if not provided)
        register_fn: Function to call with FastMCP instance to register tools
        port: Optional explicit port (overrides domain default)

    Example:
        async def register_tools(mcp: FastMCP):
            @mcp.tool()
            async def my_tool():
                return {"status": "ok"}

        await run_server("browser", register_tools)
    """
    if port is None:
        port = get_port(domain)

    mcp = create_server(domain)
    register_fn(mcp)

    print(f"Starting {domain.title()} MCP Server on port {port}...")
    await mcp.run(port=port)


def print_servers_info() -> None:
    """Print information about all available MCP servers."""
    print("\n" + "=" * 70)
    print("FORGE-AI MCP SERVERS - MODULAR ARCHITECTURE")
    print("=" * 70)
    print("\nAvailable domain-specific servers:\n")
    for domain, port in sorted(MCP_PORTS.items()):
        desc = SERVER_DESCRIPTIONS.get(domain, "No description")
        print(f"  {domain:15} | Port {port:5} | {desc}")
    print("\n" + "=" * 70)
    print("\nTo start a specific server:")
    print("  python -m forge.mcp_servers.{domain}_server")
    print("\nTo start all servers:")
    print("  python start_all_servers.py")
    print("=" * 70 + "\n")
