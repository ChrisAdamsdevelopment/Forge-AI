# Forge AI
A local-first, self-hosted personal AI agent platform with RAG, MCP tools, and desktop app.

## Quick Start
1. `git clone <repo-url>`
2. `cd Forge-AI`
3. `pip install -r implementation/backend/requirements.txt`
4. `python implementation/backend/forge/main.py` (or `start_agent.bat` on Windows)

## What It Can Do
- Browser automation, screen control, terminal execution, and filesystem operations
- App/window control, web fetch, memory tools, and sequential thinking
- RAG ingestion/search and optional prompt-engineering module tools

## Architecture
Forge runs a FastAPI backend, agent graph, MCP tool server, and optional modular tool packs; see `docs/` for architecture plans and implementation notes.

## Development
Read `CODEX_INSTRUCTIONS.md` for workflow guidance. Run `ruff check` and `pytest` before shipping changes.

## Modules
Forge discovers modules from `modules/*/module.json` and loads enabled entries at startup. The `prompt_engineer` module is included as a disabled-by-default example.
