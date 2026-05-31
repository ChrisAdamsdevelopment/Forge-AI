"""Modular MCP servers for Forge-AI.

Each domain has a separate FastMCP server that can be started independently.
This allows users to enable/disable capabilities selectively.

Available servers:
- browser_server.py (port 8010) - Browser automation
- screen_server.py (port 8011) - Screen capture and input
- terminal_server.py (port 8012) - Terminal execution
- filesystem_server.py (port 8013) - Filesystem operations
- apps_server.py (port 8014) - Application management
- web_server.py (port 8015) - Web content fetching
- memory_server.py (port 8016) - Memory persistence
- thinking_server.py (port 8017) - Sequential thinking
- rag_server.py (port 8018) - RAG search

Start all servers:
    python -m forge.mcp_servers.start_all_servers

Start a single server:
    python -m forge.mcp_servers.browser_server
    python -m forge.mcp_servers.screen_server
    etc.
"""

from forge.mcp_servers.base import (
    MCP_PORTS,
    SERVER_DESCRIPTIONS,
    create_server,
    get_port,
    print_servers_info,
    run_server,
)

__all__ = [
    "MCP_PORTS",
    "SERVER_DESCRIPTIONS",
    "create_server",
    "get_port",
    "print_servers_info",
    "run_server",
]
