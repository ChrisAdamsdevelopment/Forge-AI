# Forge — Codex Build Instructions

> This file is for **Codex** (the AI writing the code).
> ChatGPT will use the prompts in `prompts/` to generate task specs.
> You implement those specs by writing files into this repo.

---

## 0. What Forge Is

Forge is a **self-hosted personal AI agent platform** — a local-first desktop app plus
optional web dashboard and mobile companion that lets one user:

- Run open-weight models (via Ollama) and optionally route to a remote GPU
- Chat with a persistent system prompt and full session history
- Index personal documents and retrieve them with RAG (LanceDB + BGE-M3)
- Execute tools (filesystem, git, web fetch, memory) via the MCP protocol
- Run reusable **Modules** (Tasker-style workflow packages users can build and share)
- Evaluate and eventually fine-tune model behavior

Everything the user owns: the model, the prompts, the documents, the tool policy.
No vendor lock-in. Runs fully offline for core features.

---

## 1. Repo Layout

```
forge/
├── CODEX_INSTRUCTIONS.md          ← you are here
├── docs/                          ← architecture docs, read these first
│   ├── project_brief.md           ← mission and MVP definition
│   ├── architecture_overview.md   ← system layers diagram (text)
│   ├── tasker_style_module_system.md ← module spec
│   ├── operating_rules.md         ← agent behavior rules
│   └── ...
├── prompts/                       ← agent + system prompts
│   ├── system_prompt.md           ← Forge's system prompt
│   └── ...
├── runtime/
│   ├── Modelfile                  ← Ollama model definition
│   ├── mcp.json                   ← MCP server config
│   └── docker-compose.yaml        ← full stack
├── modules/                       ← Tasker-style module packages
│   ├── schemas/module.schema.json ← JSON Schema for module manifests
│   ├── specs/                     ← module system specs
│   └── examples/                  ← example module YAML files
├── eval/                          ← golden task evaluation suite
├── training/                      ← LoRA fine-tuning config + example data
├── implementation/
│   ├── backend/                   ← ★ PRIMARY CODEBASE (Python / FastAPI)
│   │   ├── pyproject.toml
│   │   └── forge/
│   │       ├── main.py            ← FastAPI app factory
│   │       ├── core/
│   │       │   ├── config.py      ← Settings (pydantic-settings)
│   │       │   ├── database.py    ← SQLAlchemy async engine
│   │       │   ├── models.py      ← ORM models
│   │       │   └── security.py    ← API key auth
│   │       ├── api/
│   │       │   └── routes.py      ← all REST + WebSocket routes
│   │       ├── services/
│   │       │   ├── inference_service.py  ← Ollama + remote backend
│   │       │   ├── module_service.py     ← HTTP wrapper for modules
│   │       │   └── session_service.py    ← session CRUD + context window
│   │       ├── modules/
│   │       │   └── runner.py      ← module load/validate/execute
│   │       └── rag/
│   │           └── chunker.py     ← markdown + text document chunker
│   ├── desktop/                   ← Electron + React (to be built)
│   ├── scripts/
│   └── tests/
│       └── test_module_manifest.py
```

---

## 2. Coding Standards

### Python (backend)

- Python **3.12+** only. Use `from __future__ import annotations`.
- All functions that do I/O are `async def`. Use `await` throughout.
- Use **type hints everywhere** — function signatures, local variables where non-obvious.
- Use `pydantic` for all request/response models. Never pass raw `dict` to API boundary.
- Raise `HTTPException` at the route layer; raise `ValueError` / domain exceptions in services.
- Log with `logging.getLogger(__name__)`, not `print`.
- Every module gets a docstring explaining what it does and how to use it.
- Format with **ruff** (`ruff format .`). Lint with `ruff check .`.

### TypeScript (frontend — coming later)

- React 19 + TypeScript strict mode.
- Zustand for client state. Tanstack Query for server state.
- TailwindCSS + shadcn/ui only — no external component libraries.
- Every component file is a single default export.

### General rules

- **Never commit secrets, API keys, or tokens.** Use `.env` + the `auth.key` file.
- **Never hardcode paths.** Everything flows through `settings` (config.py).
- Tests live in `implementation/tests/`. Use `pytest` + `pytest-asyncio`.
- Write tests for every new service method and every non-trivial function.

---

## 3. Architecture Decisions (do not override)

| Decision | Why |
|---|---|
| FastAPI + Uvicorn | Async-native, automatic OpenAPI docs, WebSocket support |
| SQLite + aiosqlite | Zero-config single-user local app. WAL mode for reads. |
| LanceDB | Embedded vector DB, no separate process, disk-native |
| Ollama for local inference | One-command install, Modelfile support, OpenAI-compatible |
| MCP for tools | Standard protocol, pre-built servers, least-privilege roots |
| LangGraph for agent loop | Explicit state machine, debuggable, not magic |
| Jinja2 for prompt templates | Module prompts must be renderable with user input |
| Pydantic-settings | Config from env/file, validated, typed |
| Local bearer token auth | Single user, zero deps, generated on first launch |

---

## 4. What Has Already Been Built

The following files are **production-ready** and should not be rewritten
without a good reason:

| File | Status |
|---|---|
| `forge/core/config.py` | ✅ Complete |
| `forge/core/database.py` | ✅ Complete |
| `forge/core/models.py` | ✅ Complete (Session, Message, Document, EvalRun, Adapter) |
| `forge/core/security.py` | ✅ Complete |
| `forge/main.py` | ✅ Complete |
| `forge/api/routes.py` | ✅ Routes for /health, /chat, /ws/chat, /models, /modules, /config |
| `forge/services/inference_service.py` | ✅ Ollama + Remote backends, streaming, embed |
| `forge/services/module_service.py` | ✅ Complete |
| `forge/services/session_service.py` | ✅ CRUD + context window management |
| `forge/modules/runner.py` | ✅ Load, validate, render, execute |
| `forge/rag/chunker.py` | ✅ Markdown + text chunking with overlap |
| `implementation/tests/test_module_manifest.py` | ✅ Manifest + chunker tests |

---

## 5. What Needs to Be Built Next (Priority Order)

### Phase 1 — RAG Pipeline (next)

**Task: `forge/rag/embedder.py`**
- Class `Embedder` with `async embed(text: str) -> list[float]`
- Calls `InferenceService().embed(text)` from inference_service.py
- Batching: `async embed_batch(texts: list[str]) -> list[list[float]]` — sequential with
  configurable concurrency limit (default 4)
- Cache embeddings of identical strings in memory (LRU, max 1000 entries)

**Task: `forge/rag/indexer.py`**
- Class `RAGIndex` wrapping LanceDB
- `async upsert(chunks: list[Chunk]) -> None` — stores chunk content + vector + metadata
- `async search(query_vector: list[float], top_k: int) -> list[dict]` — ANN search
- `async delete_source(source_path: str) -> None` — remove all chunks from a file
- `async stats() -> dict` — count of indexed documents and chunks
- LanceDB table name: `"forge_chunks"`
- Schema: id (str), content (str), source (str), heading (str), chunk_index (int), vector (list[float])

**Task: `forge/rag/retriever.py`**
- Class `Retriever` using `Embedder` + `RAGIndex`
- `async retrieve(query: str, top_k: int | None = None) -> list[dict]`
- Returns top_k chunks sorted by relevance score
- Add source citation format: `[source_filename, chunk_index]`

**Task: `forge/rag/reranker.py`**
- Class `Reranker`
- `rerank(query: str, chunks: list[dict], top_n: int) -> list[dict]`
- Naive implementation: re-score by keyword overlap (BM25-style term frequency)
- Note in docstring: replace with BGE reranker model call when available

**Task: `forge/services/rag_service.py`**
- `async ingest_file(path: str) -> dict` — chunk + embed + index one file
- `async ingest_directory(path: str, extensions: list[str]) -> dict` — walk dir
- `async search(query: str) -> list[dict]` — retrieve + rerank
- `async delete_source(source_path: str) -> None`
- `async stats() -> dict`

**Task: Add RAG routes to `forge/api/routes.py`**
- `POST /rag/ingest` — body: `{"path": "...", "type": "file"|"directory"}`
- `GET  /rag/search?q=...` — returns top chunks
- `GET  /rag/stats` — document + chunk counts
- `DELETE /rag/source` — body: `{"source_path": "..."}`

---

### Phase 2 — Agent Loop (LangGraph)

**Task: `forge/agent/state.py`**
```python
class AgentState(TypedDict):
    session_id: str
    messages: list[dict]
    rag_context: str
    pending_tool_calls: list[dict]
    tool_results: list[dict]
    model_config: dict
    final_response: str | None
    error: str | None
    iteration_count: int
```

**Task: `forge/agent/nodes/context_node.py`**
- Assembles final messages list: system prompt + RAG context (injected into system) + history
- RAG context format: `"\n\nRelevant documents:\n[DOC 1] filename.md:\n{content}\n\n[DOC 2] ..."`
- Respects `settings.num_ctx` token budget

**Task: `forge/agent/nodes/inference_node.py`**
- Calls `InferenceService.chat()` with assembled messages + available tool schemas
- Parses response: text content → set `final_response`, tool_calls → set `pending_tool_calls`
- Increments `iteration_count`, returns to tool_node or finalize_node

**Task: `forge/agent/nodes/tool_node.py`**
- Dispatches `pending_tool_calls` to MCPRegistry (see below)
- Formats results as tool-role messages
- Appends to `tool_results` and back to `messages`

**Task: `forge/agent/nodes/finalize_node.py`**
- Saves assistant message to DB via SessionService
- Clears pending state

**Task: `forge/agent/graph.py`**
- Wire all nodes into a LangGraph `StateGraph`
- Loop condition: if pending_tool_calls → tool_node, else → finalize_node
- Max iterations guard: if `iteration_count >= settings.max_tool_iterations` → finalize

---

### Phase 3 — MCP Server Manager

**Task: `forge/agent/tools/registry.py`**

This is the most complex missing piece. See `docs/architecture_overview.md` section 6.1.

```python
class MCPRegistry:
    """
    Reads runtime/mcp.json, spawns each MCP server as a subprocess,
    communicates via JSON-RPC over stdio, and exposes a unified tool interface.
    """
    async def start(self) -> None  # spawn all servers
    async def stop(self) -> None   # terminate all servers
    async def list_tools(self) -> list[ToolSchema]  # aggregate tool list
    async def execute(self, tool_name: str, arguments: dict) -> str  # call a tool
    async def health(self) -> dict[str, bool]  # per-server status
```

Protocol: MCP uses JSON-RPC 2.0 over stdio.
- Send: `{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}\n`
- Send: `{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"...", "arguments":{...}}}\n`
- Read response lines, match by id.

Each server is spawned with `asyncio.create_subprocess_exec`, communicating via
`process.stdin` / `process.stdout`.

---

### Phase 4 — Evaluation Service

**Task: `forge/services/eval_service.py`**

Loads `eval/golden_tasks.yaml`, runs each task through the full agent loop,
and checks assertions:
- `contains`: list of strings that must appear in the response
- `not_contains`: strings that must NOT appear
- `tool_calls_include`: tool names that must have been called
- `max_duration_seconds`: timeout

Returns an `EvalRun` record with per-task pass/fail detail.

---

### Phase 5 — Desktop App (Electron + React)

> Start Phase 5 only after the backend passes all Phase 1–3 tests.

**Task: `apps/desktop/` scaffold**
- Electron 33 + React 19 + TypeScript
- Vite for renderer bundling
- TailwindCSS + shadcn/ui
- Zustand stores: chatStore, sessionStore, configStore, toolStore
- Component list: ChatView, MessageBubble, StreamingText, ToolCallCard, InputBar,
  Sidebar, SessionList, SettingsPanel, ModelSettings, RAGSettings, ToolSettings

**Task: `apps/desktop/src/main/process-manager.ts`**

Spawns and manages:
1. Forge Python backend (port 9147)
2. Ollama (port 11434)
3. MCP servers (spawned by registry — no direct desktop management needed)

State machine: `STOPPED → STARTING → RUNNING → UNHEALTHY → RESTARTING`

---

## 6. Module System (Tasker-Style) — Full Spec

A **Forge Module** is a portable workflow package in its own folder.
Users create them, run them, and share them (as zipped folders or via a future marketplace).

### Module folder structure

```
modules/my_module/
    module.yaml              ← manifest (REQUIRED)
    README.md
    prompts/
        main.md              ← Jinja2 prompt template (REQUIRED)
        critique.md          ← optional self-critique
    schemas/
        input.schema.json    ← JSON Schema for user input (REQUIRED)
        output.schema.json   ← JSON Schema for expected output
    policy/
        tool_policy.yaml     ← which tools this module needs
    examples/
        example_input.json
        example_output.md
    tests/
        golden_tasks.yaml
```

### Module manifest fields (module.yaml)

```yaml
id: "forge.modules.my_module"       # stable reverse-domain id
name: "My Module"
version: "0.1.0"
author: "username"
description: "One sentence."
category: research | coding | file_ops | media | security | writing | monitoring | utility
entrypoint: "prompts/main.md"       # relative to module folder
input_schema: "schemas/input.schema.json"
output_schema: "schemas/output.schema.json"
permissions:
  tools:
    - "filesystem.read"
    - "git.status"
  roots:
    - "workspace"
  network: false
  terminal: false                   # or "approval_required"
safety:
  destructive_actions: false
  reads_secrets: false
  approval_required: []             # list of tool names needing user OK
```

### Prompt template (prompts/main.md)

Jinja2 syntax. Input schema fields are available as variables:

```markdown
# Task: Inspect Repository

Repository path: {{ repo_path }}

Please analyze the repository at the path above and produce:
1. A file tree summary (top 2 levels)
2. A list of detected languages and frameworks
3. An implementation risk assessment
...
```

### Risk levels and enforcement

| Risk | Trigger | Behavior |
|---|---|---|
| low | read-only tools, no network | runs automatically |
| medium | network access or web fetch | runs automatically, logs all fetches |
| high | terminal access | requires user approval before execution |
| critical | delete tools or secrets access | requires user approval + confirmation |

Modules imported from other users start **disabled** until the user reviews and enables them.

---

## 7. Running the Backend Locally

```bash
cd implementation/backend
poetry install
poetry run forge
# → http://127.0.0.1:9147
# → Docs at http://127.0.0.1:9147/docs
```

The API key is auto-generated at `~/.forge/auth.key` on first run.
Set the `Authorization: Bearer <key>` header on all requests.

### Running tests

```bash
cd implementation/backend
poetry run pytest implementation/tests/ -v
```

---

## 8. Environment Variables

All prefixed with `FORGE_`. See `runtime/.env.example` for the full list.

Key ones for development:

```env
FORGE_LOG_LEVEL=debug
FORGE_RELOAD=true
FORGE_DEFAULT_MODEL=qwen3.5
FORGE_OLLAMA_BASE_URL=http://127.0.0.1:11434
FORGE_REMOTE_INFERENCE_URL=http://my-gpu-server:8000   # optional
FORGE_ENABLE_LAN=false
```

---

## 9. Security Rules — Never Violate

1. **Never log the API key or any credentials**, even at DEBUG level.
2. **Never expose `settings.api_key` or `settings.remote_inference_key` in API responses**.
3. **Never write to paths outside approved MCP roots.** The agent must respect `file_roots.md`.
4. **Modules imported from external sources start disabled.** They must be reviewed before running.
5. **High and critical risk modules always require explicit user approval** — never auto-execute.
6. **The `.env` file and `auth.key` are gitignored** — never commit them.
7. **Never execute shell commands outside of a sandboxed environment** (Docker or explicit approval).

---

## 10. Definition of Done for Each Phase

### Phase 1 (RAG) is done when:
- `pytest implementation/tests/` passes, including RAG ingest + search tests
- `/api/v1/rag/ingest` can index a markdown file
- `/api/v1/rag/search?q=...` returns relevant chunks
- Chunks appear correctly in the `/api/v1/chat` context

### Phase 2 (Agent Loop) is done when:
- A multi-turn `/api/v1/chat` with `tools` correctly loops and returns tool results
- The agent respects `max_tool_iterations`
- Session history is saved to SQLite and survives restart

### Phase 3 (MCP) is done when:
- `MCPRegistry` spawns the servers from `runtime/mcp.json`
- `filesystem.read` works on a file within approved roots
- Tool calls appear in the WebSocket event stream

### Phase 5 (Desktop) is done when:
- The Electron app starts the Python backend automatically
- Chat with streaming tokens works
- Sessions are listed in the sidebar
- Module list shows installed modules
