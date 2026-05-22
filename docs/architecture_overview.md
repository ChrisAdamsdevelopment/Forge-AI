# Forge Architecture Overview

## Core architecture

Forge is a local-first agent stack.

Verbal system diagram:

User clients feed requests into the Forge API. The API hands the task to the agent engine. The agent engine assembles context from system prompts, session history, RAG results, and live tool results. The inference service calls a local or remote open-weight model. If the model requests tools, the tool registry enforces policy and routes approved calls to MCP servers or sandbox services. The final answer streams back to the UI and the session is stored.

## Main layers

1. Presentation layer
   - Desktop app
   - Web dashboard
   - Mobile companion

2. API layer
   - FastAPI
   - REST endpoints
   - WebSocket streaming
   - local bearer-token auth

3. Agent layer
   - state graph
   - context assembly
   - inference call
   - tool loop
   - finalization

4. Inference layer
   - Ollama local
   - llama.cpp fallback
   - vLLM/SGLang remote GPU option

5. RAG layer
   - document parsing
   - chunking
   - embeddings
   - vector search
   - reranking
   - citation mapping

6. Tool layer
   - MCP filesystem
   - MCP git
   - MCP fetch
   - MCP memory
   - terminal sandbox
   - browser automation

7. Module layer
   - Tasker-style reusable automations
   - triggers
   - inputs
   - steps
   - safety contracts
   - shareable manifests

8. Evaluation/training layer
   - golden tasks
   - prompt regression
   - RAG regression
   - tool-call regression
   - LoRA/QLoRA dataset export
