# Forge AI

A local-first, self-hosted personal AI agent platform. Forge gives a single operator
AI-driven control over their own machine — browser automation, terminal execution,
filesystem operations, screen capture, router orchestration, and autonomous security
research — running entirely on local hardware with no cloud dependency.

> **Warning:** This project provides powerful system automation capabilities. Use only on systems you own and control. Read [SECURITY.md](SECURITY.md) before deploying.

Project governance and risk documents: [Security Policy](SECURITY.md), [Threat Model](THREAT_MODEL.md), [Contributing Guide](CONTRIBUTING.md), [License](LICENSE).

---

## What It Can Do

| Capability | Implementation | Notes |
|---|---|---|
| Browser automation | Playwright | Navigate, click, type, screenshot |
| Screen capture & input | PyAutoGUI | Full mouse/keyboard control |
| Terminal execution | subprocess | PowerShell, CMD, WSL, Bash |
| Filesystem operations | pathlib | Read, write, delete, search (within ALLOWED_ROOTS) |
| App/window control | pygetwindow | Open, focus, close applications |
| Web fetch | httpx + BeautifulSoup | Fetch and parse web content |
| Persistent memory | SQLite (aiosqlite) | Key-value store across sessions |
| RAG document system | LanceDB + FlagEmbedding | Ingest, chunk, embed, retrieve, rerank |
| Sequential thinking | Structured prompt chain | Multi-step reasoning tool |
| Autonomous pentesting | Beam Search + MCTS | Recon → enumeration → vuln analysis → reporting |
| Router orchestration | OpenWrt RPCD / JSON-RPC | WiFi, firewall, VPN, DNS, diagnostics |
| Self-improvement | Conversation-to-training-data | Export sessions as LoRA fine-tune datasets |
| Modular extensions | Dynamic module loader | Tasker-style reusable automations |

---

## Prerequisites

| Requirement | Purpose | Required for |
|---|---|---|
| Python 3.12 | Runtime | Everything |
| [Ollama](https://ollama.ai) | Local model inference | Core agent |
| WSL2 + Ubuntu | Pentest tools (nmap, gobuster, etc.) | Pentest server only |
| OpenWrt router | Router orchestration | Router server only |
| [ngrok](https://ngrok.com) account | Remote access tunnel | Optional / LAN bypass only |

Pull a model before starting:
```bash
ollama pull llama3
```

---

## Quick Start

**Requirements:** Python 3.12, [Ollama](https://ollama.ai) running locally

```bash
git clone https://github.com/ChrisAdamsdevelopment/Forge-AI.git
cd Forge-AI

# Install Python dependencies
pip install -r implementation/backend/requirements.txt

# Install Playwright browser (required for browser automation)
playwright install chromium

# Pull a local model
ollama pull llama3
```

**Configure your environment:**
```bash
cp .env.example .env
# Open .env and set FORGE_ALLOWED_ROOTS to the directories you want the agent to access
```

**Start the agent:**
```bash
# Windows
start_agent.bat

# Linux / Mac
python implementation/backend/forge/main.py
```

Access the web UI at `http://localhost:9147`

> **Note:** The pentest server requires WSL2 with Ubuntu and pentest tools installed
> (nmap, gobuster, whatweb). The router server requires an OpenWrt router.
> Both are optional — core agent functionality works without them.

## Configuration

Forge reads configuration from environment variables. Key settings:

| Variable | Default | Description |
|---|---|---|
| `FORGE_ALLOWED_ROOTS` | User home directory | Colon-separated list of filesystem roots the agent can access |
| `NGROK_DOMAIN` | *(unset)* | Your ngrok reserved domain. Leave unset to disable remote access. |
| `ROUTER_HOST` | `192.168.1.1` | OpenWrt router IP address |
| `ROUTER_USERNAME` | `root` | Router login username |
| `ROUTER_PASSWORD` | *(unset)* | Router login password — set via env, never in source |
| `PENTEST_WSL_DISTRO` | `Ubuntu` | WSL distro for pentest tools |

See [SECURITY.md](SECURITY.md) and [THREAT_MODEL.md](THREAT_MODEL.md) for deployment guidance and risk analysis.

---

## Architecture

```
User (browser / desktop app)
        │
        ▼
   FastAPI backend  ──────────────────────────────┐
        │                                          │
        ▼                                          ▼
  LangGraph agent loop                    Module loader
        │                                 (Tasker-style automations)
        ├─ Context assembly
        │   ├─ System prompt
        │   ├─ Session history (SQLite)
        │   └─ RAG retrieval (LanceDB + BGE-M3)
        │
        ├─ Inference  ──►  Ollama (local)  /  vLLM (GPU)
        │
        └─ Tool dispatch (FastMCP)
            ├─ browser_server.py    :8010
            ├─ screen_server.py     :8011
            ├─ terminal_server.py   :8012
            ├─ filesystem_server.py :8013
            ├─ apps_server.py       :8014
            ├─ web_server.py        :8015
            ├─ memory_server.py     :8016
            ├─ thinking_server.py   :8017
            ├─ rag_server.py        :8018
            ├─ pentest_server.py    :8001  (WSL required)
            └─ router_server.py     :8002  (OpenWrt required)
```

Full architecture documentation: `docs/architecture_overview.md`

---

## Repository Layout

```
Forge-AI/
├── implementation/
│   └── backend/
│       └── forge/
│           ├── agent/          # LangGraph graph, operator mode, tool registry
│           ├── api/            # FastAPI routes
│           ├── mcp_servers/    # Per-domain FastMCP servers
│           ├── rag/            # Ingest, chunk, embed, retrieve, rerank
│           ├── services/       # Streaming parser, inference adapter
│           ├── main.py         # Application entry point
│           ├── pentest_server.py
│           └── router_server.py
├── modules/                    # Modular automation packs
├── training/                   # Dataset builder, axolotl config
├── eval/                       # Golden tasks, promptfoo config
├── docs/                       # Architecture, security model, roadmap
├── runtime/                    # Docker compose, Ollama Modelfile
└── start_agent.bat             # Windows one-click startup
```

---

## Development

```bash
# Lint
ruff check implementation/

# Test
pytest implementation/backend/tests/

# Type check
mypy implementation/backend/forge/
```

Read `CODEX_INSTRUCTIONS.md` for full workflow guidance.

---

## Security

This project has meaningful dual-use potential. Please read [SECURITY.md](SECURITY.md)
before deploying, contributing, or building on this codebase.

To report a vulnerability: **chris@spectracleanse.com**

---

## License

MIT License — see [LICENSE](LICENSE)

## Author

Christopher Adams — Prescott Valley, AZ  
chris@spectracleanse.com  
https://github.com/ChrisAdamsdevelopment/Forge-AI
