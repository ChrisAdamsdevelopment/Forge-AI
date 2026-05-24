"""Start all modular MCP servers simultaneously.

Launches browser, screen, terminal, filesystem, apps, web, memory, thinking,
and RAG servers on their respective ports (8010-8018).

Run this instead of tool_server.py to use the split architecture.
"""

from __future__ import annotations

import asyncio
import sys
import subprocess
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from forge.mcp_servers import MCP_PORTS, print_servers_info

SERVERS = [
    "browser_server",
    "screen_server",
    "terminal_server",
    "filesystem_server",
    "apps_server",
    "web_server",
    "memory_server",
    "thinking_server",
    "rag_server",
]


def start_all_servers() -> None:
    """Start all MCP servers as subprocesses."""
    print_servers_info()
    
    print(f"Starting {len(SERVERS)} MCP servers...\n")
    
    processes = []
    for server_name in SERVERS:
        port = MCP_PORTS.get(server_name.replace("_server", ""))
        if not port:
            continue
        
        print(f"  → Launching {server_name} on port {port}...")
        
        # Launch as subprocess
        module_path = f"forge.mcp_servers.{server_name}"
        cmd = [sys.executable, "-m", module_path]
        
        try:
            proc = subprocess.Popen(cmd)
            processes.append((server_name, proc))
        except Exception as exc:
            print(f"    ERROR: Failed to start {server_name}: {exc}")
    
    print(f"\n✓ Started {len(processes)} servers\n")
    print("To stop all servers, press Ctrl+C or close this window.\n")
    
    # Keep running
    try:
        for _, proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        for _, proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        print("All servers stopped.")


if __name__ == "__main__":
    start_all_servers()
