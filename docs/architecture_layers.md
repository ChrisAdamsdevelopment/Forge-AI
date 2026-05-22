# Architecture Layers

## 1. Model Layer

Recommended starter model path:

- Local lightweight model: Qwen or Mistral-family instruct model through Ollama
- Coding specialist: Qwen Coder family on rented GPU when needed
- Reasoning specialist: DeepSeek-R1 distill as optional worker
- Experimental uncensored model: isolated lab profile only, never given broad tool access by default

## 2. Runtime Layer

Start with Ollama because it gives the simplest path to:

- local inference
- OpenAI-compatible endpoint
- embeddings
- Modelfile-based system prompt
- model switching

Later add vLLM/SGLang as remote backends for rented GPU performance.

## 3. Agent Host Layer

Forge should eventually own its agent loop instead of relying entirely on Open WebUI.

Open WebUI is useful as an early host, but the custom Forge backend is needed for:

- module marketplace
- tool policy enforcement
- approval history
- eval-aware development
- custom context assembly
- training-data export

## 4. Tool Layer

Tools are not free-form. Every tool must have:

- name
- description
- input schema
- output schema
- risk level
- approval requirement
- allowed file roots
- logging behavior

## 5. RAG Layer

RAG is for curated source knowledge, not the whole filesystem.

Use RAG for:

- project docs
- SOPs
- manuals
- research notes
- codebase architecture docs
- user style guides

Use filesystem tools for:

- current repo inspection
- live file reads
- comparing actual source files
- writing output artifacts

## 6. Module Layer

Modules are shareable user-built workflows. A module is not just a prompt. It is a package containing:

- manifest
- prompt templates
- input schema
- tool requirements
- allowed roots
- safety contract
- optional UI form
- optional tests
- optional examples
