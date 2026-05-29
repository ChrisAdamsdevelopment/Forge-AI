"""Runtime configuration for MCP/ngrok local setup."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from repo root if present
_env_path = Path(__file__).resolve().parents[3] / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

NGROK_DOMAIN = os.environ.get("NGROK_DOMAIN", "")
NGROK_TUNNEL_ID = os.environ.get("NGROK_TUNNEL_ID", "")
FASTAPI_PORT = int(os.environ.get("FASTAPI_PORT", "9147"))
FAST_MCP_PORT = int(os.environ.get("FAST_MCP_PORT", "8000"))
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "7999"))
PENTEST_MCP_PORT = int(os.environ.get("PENTEST_MCP_PORT", "8001"))
PENTEST_MAX_SESSIONS = int(os.environ.get("PENTEST_MAX_SESSIONS", "10"))
PENTEST_DEFAULT_TIMEOUT = int(os.environ.get("PENTEST_DEFAULT_TIMEOUT", "30"))
PENTEST_WSL_DISTRO = os.environ.get("PENTEST_WSL_DISTRO", "Ubuntu")
ROUTER_MCP_PORT = int(os.environ.get("ROUTER_MCP_PORT", "8002"))
ROUTER_HOST = os.environ.get("ROUTER_HOST", "192.168.1.1")
ROUTER_USERNAME = os.environ.get("ROUTER_USERNAME", "root")
