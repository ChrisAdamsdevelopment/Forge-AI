# Forge Project Brief

## Mission

Forge is a self-hosted personal AI agent platform that lets the user run open-weight models, define their own system prompt, index their own documents, control tool access, automate workflows, and eventually fine-tune behavior without depending on proprietary AI APIs.

Forge is not merely a local chat UI. Forge is an execution environment with six core layers:

1. Open-weight model layer
2. Inference runtime layer
3. UI and agent-host layer
4. Tool and MCP layer
5. Retrieval/RAG layer
6. Training and evaluation layer

## Primary user goal

The user wants an assistant that can perform real work, follow durable instructions, inspect approved files, access the web, use terminal/browser tools, generate and edit code, research deeply, and run reusable automations without fighting vendor policy limitations.

## Product target

Forge should become a desktop-first application with optional web dashboard and mobile companion.

The desktop app is the primary control plane. The web dashboard is for LAN/Tailscale access. The mobile app is for approvals, monitoring, quick commands, and module triggers.

## MVP definition

The first useful Forge version must support:

- Local Ollama inference
- Open WebUI-compatible or custom FastAPI chat API
- Persistent system prompt
- Project document RAG
- MCP filesystem access with approved roots only
- Web fetch/search through approved tools
- Basic terminal execution inside a sandbox
- Tool approval policy
- Session storage
- Module runner for reusable workflows
- Evaluation seed tasks

## Long-term vision

Forge becomes a local AI operating layer similar in spirit to Tasker for Android:

- Users create modules
- Modules combine prompts, tools, triggers, file scopes, input schemas, and output rules
- Modules can be shared
- Modules can be reviewed, versioned, imported, exported, and sandboxed
- Users can chain modules into workflows
