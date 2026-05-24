# Forge Security Model

## Overview

Forge is designed for a **single trusted operator** running a local-first assistant on their own machine. The platform can read files, call tools, use browser/screen interfaces, and execute terminal commands. That capability introduces security risk from:

- Prompt injection in untrusted content.
- Unsafe tool usage.
- Over-broad filesystem access.
- Module supply-chain risk.
- Secret leakage through logs, responses, or indexed corpora.

This document defines the current trust model and required protections.

## Local bearer token authentication

Forge API endpoints are protected by a local bearer token. The token model assumes:

- One user controls the local machine.
- The backend listens on localhost by default.
- Token theft risk is primarily local (malware, shell history leakage, copied config files).

### Threat model assumptions

- **In scope:** accidental token exposure, local process snooping, misconfigured local services.
- **Partially in scope:** LAN exposure when users intentionally publish endpoints.
- **Out of scope:** hardened multi-tenant isolation across mutually untrusted users.

### Security expectations

- Token is never hard-coded into source control.
- Token is never printed to logs.
- Token is rotated if local compromise is suspected.

## MCP root isolation and ALLOWED_ROOTS

Tool access is constrained to explicit filesystem roots. Forge enforces an allow-list model: tools only operate inside `ALLOWED_ROOTS`.

- Paths outside `ALLOWED_ROOTS` must be denied.
- Symlink/path traversal checks must resolve to a permitted canonical path.
- This isolation is a primary containment boundary against data exfiltration.

## Tool risk levels

Forge classifies tools by operational risk. Policy, approvals, and UI warnings should key off this level.

- **Low risk**
  - Read-only file and screen operations.
  - Examples: file read/list, screenshot capture, metadata inspection.
- **Medium risk**
  - File writes and terminal commands that are non-destructive.
  - Examples: create/edit files, formatting commands, read-only shell diagnostics.
- **High risk**
  - Destructive or disruptive operations.
  - Examples: file delete, force app close, terminal commands that can mutate/remove data.
- **Critical risk**
  - Arbitrary shell execution (including commands with unknown side effects).
  - Must require explicit user approval and clear auditing.

## Module sandboxing and explicit enablement

Imported modules are considered untrusted until reviewed.

- Newly imported modules start **disabled by default**.
- User must explicitly enable each module before execution.
- Permissions requested by a module should be surfaced before enablement.
- High/critical permission modules should trigger elevated warning/review UX.

## Electron security posture

Forge Desktop follows standard Electron hardening controls:

- Use `contextBridge` for narrow, explicit renderer APIs.
- Keep `nodeIntegration` disabled in renderer processes.
- Maintain process isolation between privileged main process and renderer.

Additional recommended controls include strict Content Security Policy (CSP), vetted preload contracts, and dependency hygiene.

## LAN access and ngrok exposure

By default, Forge is intended for localhost-only access. If a user enables ngrok (or similar tunneling), the threat model changes:

- The endpoint becomes remotely reachable.
- Bearer token becomes a network credential, not only a local credential.
- Replay, brute-force, and token leakage risk increases.

When ngrok is enabled:

- Use a strong random token.
- Rotate token after sharing sessions.
- Limit exposure duration.
- Treat shared links as sensitive secrets.

## Secret management requirements

Secrets must never be exposed through normal Forge operation:

- **Never in logs.**
- **Never in API responses.**
- **Never in RAG-indexed documents.**

Operationally, this implies:

- Redaction before logging model/tool payloads.
- Filtering/deny-listing sensitive paths from indexing.
- Defensive prompt and retrieval policies that avoid secret recall.

## Future enhancement: Docker sandbox for terminal execution

Forge intends to add optional terminal execution sandboxing using Docker to reduce host risk from command execution.

Target design goals:

- Run terminal tools in a constrained container runtime.
- Mount only minimal approved roots.
- Restrict network and privilege flags by default.
- Preserve auditable command traces while limiting host impact.

This is planned hardening and does not replace current approval controls.
