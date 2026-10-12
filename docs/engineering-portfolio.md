# Forge-AI: applied AI and agent-tooling engineering guide

**Focus:** Python, FastAPI, local-first agent architecture, Model Context Protocol (MCP) tools, RAG, local inference and agent reliability.

Forge-AI is an evolving, single-operator agent system intended for authorized use on the operator's own machine and permitted infrastructure. Some integrations require optional hardware/services and are not supported by a one-command demonstration.

## Architecture

```text
User / UI
   |
FastAPI API and agent orchestration
   +-- Local inference adapter (Ollama; optional additional backends)
   +-- Retrieval: ingestion -> embeddings -> LanceDB -> reranking
   +-- Persistent SQLite memory
   +-- MCP/FastMCP tool dispatch
       +-- browser + screen
       +-- terminal + filesystem
       +-- web + memory + RAG
       +-- optional OpenWrt router and lab-only security tools
```

See [architecture overview](architecture_overview.md), [security policy](../SECURITY.md) and [threat model](../THREAT_MODEL.md). These files describe intended architecture and risks; features should be validated in a specific installed configuration before claiming production readiness.

## What the project demonstrates

| Area | Implementation evidence | Engineering tradeoff |
| --- | --- | --- |
| AI agent integration | FastAPI services, agent loop and modular MCP tool servers | Keep model suggestions separate from privileged actions |
| Local model operation | Ollama inference integration and local runtime configuration | Hardware/runtime setup and model behavior vary by installation |
| Retrieval | Ingestion, embeddings, LanceDB retrieval and reranking | Data-source trust, retrieval quality and indexing consistency |
| Tool capability design | Browser, files, terminal, screen and optional network administration | Least privilege, user approval and allowed-root enforcement matter |
| Durable state | SQLite-backed history/memory and modular workflows | Manage data scope and avoid overprivileged persistent automation |
| Security posture | [Security policy](../SECURITY.md), [threat model](../THREAT_MODEL.md) and capability-boundary documents | Documentation is not proof that all threats have been eliminated |

## Review and run

Follow the root [README](../README.md) for the current dependencies and local setup. Core development emphasizes testable Python tool functions and explicit configuration. Run any automation only on machines and networks you are authorized to control.

Demonstration sequence for recruiters: start a safe local instance, show a constrained filesystem or browser task, trace the model/tool boundary, then inspect the associated permission check or test. Do not demonstrate broad unattended execution or publish credentials.

## Current limits

Forge-AI remains an evolving self-hosted engineering project rather than a fully independently audited managed service. Local-only code and in-progress branches may be ahead of the public default branch. Optional router/security tooling can be omitted from a general applied-AI or developer-platform presentation.

This document describes the technical portfolio value of the existing repository; it does not certify secure production deployment, a specific local model's performance or universal prompt-injection resistance.
