# Security Policy

## Intended Use

Forge AI is designed for **single-operator, local-first use** on systems you own or have
explicit written authorization to access. This means:

- Your own personal machine
- Your own home lab or test environment
- Systems where you are the authorized administrator
- Penetration testing engagements with a signed scope-of-work agreement

**Forge is not authorized for use against systems you do not own or lack explicit permission
to test.** Unauthorized use may violate the Computer Fraud and Abuse Act (18 U.S.C. § 1030),
the UK Computer Misuse Act, or equivalent laws in your jurisdiction.

---

## Dual-Use Disclosure

Forge's capabilities were designed to be useful. They are also capable of causing harm if
misused. The developer acknowledges this openly.

### What Forge Can Do (Legitimate Use)

- Automate repetitive personal workflows on your own machine
- Perform authorized security research against your own systems
- Run autonomous penetration tests against lab environments you control
- Manage and monitor your own OpenWrt router
- Ingest and query your own documents via RAG

### What the Same Architecture Could Enable (Misuse)

The same modular, tool-integrated, persistent architecture that makes Forge useful as a
personal agent also makes it architecturally similar to an advanced implant if weaponized.
Specifically:

- **Browser + screen + memory servers** — could be combined for credential capture
  and session replay against the operator's own browser state
- **Terminal server** — arbitrary command execution in any shell
- **Filesystem server** — read/write/delete within ALLOWED_ROOTS
- **Router server** — firewall rule modification, VPN rotation, DNS manipulation,
  traffic interception via redsocks on an OpenWrt device
- **Operator mode (pentest server)** — autonomous recon, enumeration, and
  attack-graph planning using Beam Search and MCTS

The developer's position: these dual-use risks are real. They are documented here because
the security industry needs to understand what AI-native agent architectures enable — both
the legitimate uses and the threat surface they represent.

### What Is Intentionally Not Implemented

The following capabilities are explicitly stubbed out and return `{"status": "blocked"}`
rather than executing:

- SQL injection exploitation (`exploit_sqli`)
- Credential brute-force via Hydra (`exploit_hydra`)
- Post-exploitation loot collection (`post_loot_collect`)
- Pivot scanning from compromised sessions (`post_pivot_scan`)

These stubs exist as architectural markers — documenting where an attacker converting this
codebase would need to add code — without providing that code.

---

## Threat Model

### In Scope

- Single trusted operator running Forge on their own machine
- Accidental credential exposure (ngrok domain, router password, bearer token)
- Prompt injection via untrusted content ingested into RAG
- Module supply-chain risk (malicious module.json / module code)
- Over-broad filesystem access via misconfigured ALLOWED_ROOTS
- LAN exposure when ngrok or enable_lan is active

### Out of Scope

- Multi-tenant isolation (Forge has no concept of multiple untrusted users)
- Hardened sandboxing against a compromised operator (Forge runs as the operator)

### Router Deployment Note

The router server gives Forge programmatic access to your network infrastructure.
If deployed carelessly, it can:

- Modify firewall rules
- Rotate VPN exit nodes
- Redirect DNS queries
- Intercept unencrypted traffic via redsocks

**Only deploy the router server against your own router. Never expose the router server
endpoint to untrusted networks.**

---

## Configuration Hardening Checklist

Before running Forge in any context beyond local development:

- [ ] `FORGE_ALLOWED_ROOTS` is set to the minimum directories the agent needs
- [ ] `NGROK_DOMAIN` is set via environment variable, not hardcoded in source
- [ ] `ROUTER_PASSWORD` is set via environment variable, never committed to git
- [ ] Bearer token (`~/.forge/auth.key`) has not been shared or logged
- [ ] `enable_lan` is `false` unless you explicitly need LAN access
- [ ] Router server is not exposed to untrusted networks
- [ ] You have reviewed which modules are enabled in `modules/*/module.json`

---

## Reporting a Vulnerability

If you find a security vulnerability in this codebase — including prompt injection vectors,
authentication bypasses, path traversal in filesystem tools, or router server exploits —
please report it privately before disclosing publicly.

**Contact:** chris@spectracleanse.com  
**Subject line:** `[Forge-AI Security] <brief description>`

Please include:
- A description of the vulnerability
- Steps to reproduce
- Your assessment of impact
- Any suggested fix (optional but appreciated)

I will acknowledge receipt within 48 hours and aim to resolve confirmed issues within
14 days. I will credit researchers who report valid vulnerabilities unless they prefer
to remain anonymous.

**Please do not open a public GitHub issue for security vulnerabilities.**

---

## Responsible Disclosure Philosophy

This project exists in part to demonstrate that the architecture of a good AI agent and
the architecture of a good AI implant are functionally identical — differing only in
intent. That finding is worth making public so the security industry can prepare defenses
before this class of threat appears in the wild.

The developer is committed to:

1. Honest documentation of what the platform can do
2. Not shipping exploitation capabilities, only documenting their architectural location
3. Responding to security reports seriously and promptly
4. Supporting researchers and journalists who cover this topic responsibly

---

*Last updated: May 2026*
