from __future__ import annotations

import asyncio
import importlib
import inspect
import json
from typing import Any

from aiohttp import web
from fastmcp import FastMCP

from forge.config import DASHBOARD_PORT, FAST_MCP_PORT, NGROK_DOMAIN
from forge.services.rag_service import rag_service

TOOL_MODULES = [
    "forge.agent.tools.browser",
    "forge.agent.tools.screen",
    "forge.agent.tools.terminal",
    "forge.agent.tools.filesystem",
    "forge.agent.tools.apps",
    "forge.agent.tools.web",
    "forge.agent.tools.memory",
    "forge.agent.tools.thinking",
]

mcp = FastMCP("forge-tools")
REGISTERED_TOOLS: list[dict[str, Any]] = []
MISSING_MODULES: list[str] = []
NON_ASYNC_FUNCTIONS: list[str] = []


async def rag_ingest_file(file_path: str) -> dict:
    """Ingest a local file into the Forge RAG index."""
    return await rag_service.ingest_file(file_path)


async def rag_search(query: str, top_k: int = 5) -> dict:
    """Search the Forge RAG index for relevant chunks."""
    return await rag_service.search(query=query, top_k=top_k)



def _is_public_tool_function(obj: Any, module_name: str) -> bool:
    return inspect.isfunction(obj) and obj.__module__ == module_name and not obj.__name__.startswith("_")


def register_tools() -> None:
    mcp.tool(name="rag_ingest_file", description="Ingest a local file into the Forge RAG index.")(rag_ingest_file)
    mcp.tool(name="rag_search", description="Search the Forge RAG index for relevant chunks.")(rag_search)
    for module_name in TOOL_MODULES:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            MISSING_MODULES.append(module_name)
            continue

        for _, fn in inspect.getmembers(module, lambda o: _is_public_tool_function(o, module_name)):
            if not inspect.iscoroutinefunction(fn):
                NON_ASYNC_FUNCTIONS.append(f"{module_name}.{fn.__name__}")
                continue
            mcp.tool(name=fn.__name__, description=(inspect.getdoc(fn) or "").strip())(fn)
            REGISTERED_TOOLS.append(
                {
                    "name": fn.__name__,
                    "module": module_name,
                    "signature": str(inspect.signature(fn)),
                    "annotations": {k: str(v) for k, v in fn.__annotations__.items()},
                }
            )


async def dashboard_handler(_: web.Request) -> web.Response:
    data = {
        "ngrok_domain": NGROK_DOMAIN,
        "mcp_server": f"http://0.0.0.0:{FAST_MCP_PORT}",
        "status": "running",
        "registered_tools": REGISTERED_TOOLS,
        "missing_modules": MISSING_MODULES,
        "non_async_functions": NON_ASYNC_FUNCTIONS,
    }
    tools_html = "".join(
        f"<li><code>{t['name']}{t['signature']}</code> <small>({t['module']})</small></li>" for t in REGISTERED_TOOLS
    ) or "<li>No tools discovered yet.</li>"
    html = f"""
    <html>
      <head><title>Forge MCP Dashboard</title></head>
      <body style='font-family: Arial, sans-serif; max-width: 900px; margin: 24px auto;'>
        <h1>Forge MCP Dashboard</h1>
        <p><b>ngrok domain:</b> {NGROK_DOMAIN}</p>
        <p><b>MCP server:</b> http://localhost:{FAST_MCP_PORT}</p>
        <p><b>Dashboard:</b> http://localhost:{DASHBOARD_PORT}</p>
        <h2>Registered MCP Tools ({len(REGISTERED_TOOLS)})</h2>
        <ul>{tools_html}</ul>
        <h2>Diagnostics</h2>
        <pre>{json.dumps(data, indent=2)}</pre>
      </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")


async def start_dashboard() -> None:
    app = web.Application()
    app.add_routes([web.get("/", dashboard_handler)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=DASHBOARD_PORT)
    await site.start()


async def run_mcp_server() -> None:
    await mcp.run_async(transport="streamable-http", host="0.0.0.0", port=FAST_MCP_PORT)


async def main() -> None:
    register_tools()
    await start_dashboard()
    await run_mcp_server()


if __name__ == "__main__":
    asyncio.run(main())
