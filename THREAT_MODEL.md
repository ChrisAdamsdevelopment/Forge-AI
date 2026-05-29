# Forge AI — Dual-Use Threat Analysis

**Author:** Christopher Adams, developer of Forge AI  
**Date:** May 2026  
**Status:** Self-authored threat model. This document was written by the developer,
not by an independent third-party security researcher. It is published as part of
responsible disclosure rather than claimed as external validation.  
**Repository:** https://github.com/ChrisAdamsdevelopment/Forge-AI

---

## 1. Purpose of This Document

I built Forge AI as a personal productivity tool. During development I realized that
the same architectural properties that make it useful — autonomous tool execution,
persistent memory, modular extensibility, router integration — also describe the
architecture of a sophisticated AI-native implant.

This document is my honest analysis of that dual-use risk. It is written for three
audiences:

1. **Security researchers** who need an accurate description of what this platform
   can do and what converting it to a malicious system would require
2. **Journalists and content creators** who cover security topics and want technically
   accurate source material
3. **Defenders** who need to understand what AI-native threats will look like before
   they appear in the wild

I am not a threat actor. I am a developer raising a flag.

---

## 2. What Forge AI Actually Is

Forge is a local-first AI agent platform. When running normally, it:

- Accepts natural language instructions via a web UI or desktop app
- Routes instructions through a LangGraph agent loop backed by a local LLM (Ollama)
- Executes instructions using a suite of MCP (Model Context Protocol) tool servers
- Stores conversation history and persistent memory in local SQLite
- Retrieves relevant context from indexed documents via a RAG pipeline (LanceDB + BGE-M3)
- Optionally orchestrates an OpenWrt router via its RPCD JSON-RPC API

The code is real. The tools work. A person who clones this repository and follows the
setup instructions gets a functioning personal AI agent.

---

## 3. The Dual-Use Gap

### 3.1 What Makes a Good AI Agent

A capable personal AI agent requires:

| Property | Why it's needed for legitimate use |
|---|---|
| Persistent background process | Stay ready to act without user re-launching |
| Broad tool access | Be useful across different tasks |
| Autonomous multi-step execution | Complete complex goals without constant supervision |
| Persistent memory | Remember context across sessions |
| Self-improvement capability | Learn from interactions |
| Network integration | Act on the user's behalf online |
| Local model (no cloud dependency) | Privacy, speed, offline operation |

### 3.2 What Makes a Good AI Implant

A capable AI implant requires:

| Property | Why it's needed for malicious use |
|---|---|
| Persistent background process | Survive reboots, stay hidden |
| Broad tool access | Exfiltrate data, execute commands, capture credentials |
| Autonomous multi-step execution | Operate without attacker interaction |
| Persistent memory | Track targets, build victim profiles over time |
| Self-improvement capability | Adapt to changing environments |
| Network integration | C2 communication, exfiltration channels |
| Local model (no cloud dependency) | No API logs, no content filtering |

These are the same list. That is the finding.

### 3.3 The Conversion Gap

The security analysis I conducted on my own codebase estimated that converting
Forge AI from a legitimate personal agent to an autonomous malware platform would
require approximately **50–80 hours of additional development work**. The core
capabilities — autonomous execution, persistence, network integration, memory —
already exist. The work required is:

| Addition needed | Estimated effort | Notes |
|---|---|---|
| Covert C2 channel (Discord/Slack webhook) | 4–8 hours | Routes to trusted domains, bypasses network monitoring |
| Keylogger / credential capture | 6–12 hours | PyAutoGUI already controls keyboard; capture is an extension |
| Self-preservation logic (process watchdog) | 8–16 hours | Detect termination attempts, restart from router |
| Detection evasion (code mutation) | 12–20 hours | LLM-generated code variation; breaks signature detection |
| Router-based persistence | 10–16 hours | Router server already exists; add re-infection logic |
| Steganographic exfiltration | 8–12 hours | Hide data in image uploads to bypass DLP |
| **Total** | **48–84 hours** | One to two weeks for a competent developer |

This is not a future threat. The scaffolding exists in this repository. The gap between
"useful tool" and "advanced persistent threat" is a skilled developer's two-week sprint.

---

## 4. Component-Level Analysis

### 4.1 Browser Server (port 8010)

**Legitimate:** Navigate to URLs, click elements, fill forms, take screenshots.

**Dual-use risk:** A malicious operator could use this to:
- Capture screenshots of sensitive content (banking, email, documents)
- Exfiltrate data through the user's authenticated browser sessions
- Submit forms or initiate transactions on behalf of the victim
- Capture displayed credentials before they are sent to a password manager

**Current implementation:** Real Playwright automation. Fully functional.

### 4.2 Screen Server (port 8013)

**Legitimate:** Capture what's on the screen, move the mouse, type text.

**Dual-use risk:**
- Continuous screen recording / keylogging
- Capturing clipboard content
- Reading information that is displayed but never written to disk (e.g., OTP codes, displayed passwords)

**Current implementation:** Real PyAutoGUI. Fully functional.

### 4.3 Terminal Server (port 8012)

**Legitimate:** Run shell commands, execute scripts, manage processes.

**Dual-use risk:** Arbitrary command execution across PowerShell, CMD, WSL, and Bash.
This is the highest-risk individual component. A malicious actor with access to this
server can do essentially anything a logged-in user can do.

**Current implementation:** Real subprocess execution with a 120-second timeout. No
content filtering beyond what the LLM layer provides. Fully functional.

### 4.4 Filesystem Server (port 8011)

**Legitimate:** Read, write, delete, search files within ALLOWED_ROOTS.

**Dual-use risk:**
- Exfiltrate documents, source code, credentials, SSH keys
- Modify files (configuration poisoning, code injection into developer projects)
- Plant files (staging for supply-chain attacks on code the developer pushes)

**Current implementation:** Real pathlib operations. ALLOWED_ROOTS provides the
primary containment boundary. Fully functional.

### 4.5 Router Server (port 8002)

**Legitimate:** Manage WiFi networks, configure firewall rules, monitor diagnostics,
rotate VPN connections on your own router.

**Dual-use risk — this is the most significant component:**

The router server gives programmatic access to a device that:
- Has no antivirus, no EDR, no security monitoring (none exists for consumer OpenWrt)
- Survives OS reinstalls on connected machines
- Runs 24/7, often years between reboots
- Has visibility into all network traffic before it reaches endpoint security tools
- Can re-infect connected machines if they are cleaned but not the router

Specific capabilities that become dangerous in malicious hands:
- **redsocks traffic interception** — transparent proxy for HTTP/HTTPS traffic
- **dnsmasq DNS manipulation** — redirect specific domains to attacker-controlled IPs
- **firewall rule modification** — open ports, create persistent tunnels
- **VPN rotation** — anonymize C2 communications
- **WiFi manipulation** — rogue AP creation, client deauthentication
- **Custom rpcd plugins** — arbitrary code execution on the router if abused

**Current implementation:** 759 lines of real, working OpenWrt RPCD orchestration.
Token caching, UCI two-phase commits, full ACL enforcement. Fully functional against
a real OpenWrt router.

### 4.6 Operator Mode / Pentest Server (port 8001)

**Legitimate:** Autonomous security research against lab environments and systems you
are authorized to test.

**Dual-use risk:** A malicious actor who removes or bypasses the human-in-the-loop
checkpoints has a turnkey offensive reconnaissance platform:
- Nmap port scanning
- WhatWeb technology fingerprinting
- Gobuster directory enumeration
- DNS enumeration
- Whois/RDAP lookups
- WHOIS history
- Autonomous attack path planning via Beam Search (deterministic) and MCTS (probabilistic)
- Persistent tmux sessions that survive reboots

**What is NOT implemented:** SQL injection exploitation, credential brute-force,
post-exploitation data collection, and pivot scanning are stubbed and return blocked
status. These architectural slots are documented but not filled.

**Current implementation:** Full recon pipeline is real and functional. Exploitation
capabilities are intentional stubs.

### 4.7 Memory Server + RAG Pipeline

**Legitimate:** Persistent cross-session memory, document search.

**Dual-use risk:** Over time, a compromised system could build a detailed profile of
the victim's activities, contacts, projects, and credentials — all stored in the same
LanceDB vector store used for legitimate document search.

---

## 5. Why Current Detection Fails

### 5.1 Signature-Based Antivirus

Forge is a Python project using standard libraries (Playwright, PyAutoGUI, httpx,
FastMCP, LanceDB). None of these have malware signatures. The agent code itself
could be mutated daily by an LLM — same behavior, different implementation, different
file hash. Traditional AV has no purchase here.

### 5.2 Endpoint Detection and Response (EDR)

EDR tools look for: unsigned binaries, process injection, suspicious registry
modifications, known-bad network endpoints, unusual process trees.

Forge does none of these things. It is a Python process. It spawns subprocesses
that look like developer tooling. It communicates with api.slack.com and
api.github.com — trusted domains used by millions of legitimate applications.
EDR cannot distinguish "developer running their AI assistant" from "AI implant
operating autonomously."

### 5.3 Network Monitoring / IDS

C2 traffic routed through Discord webhooks, Slack incoming webhooks, or GitHub
Gist updates is indistinguishable from legitimate use of those platforms. HTTPS
payloads encrypted with AES-256-GCM before being wrapped in a legitimate API call
appear as normal JSON to TLS inspection.

### 5.4 Zero Trust Architecture

Zero Trust answers: "Is this entity authorized to access this resource?"

An AI implant running in the legitimate user's session uses the legitimate user's
credentials, the legitimate user's MFA tokens, the legitimate user's device (which
passes compliance checks), and the legitimate user's approved applications. Zero
Trust sees an authorized user performing authorized actions. The authorization
framework has no mechanism to evaluate whether the entity controlling those
credentials is the human user or an AI agent running on their behalf.

This is not a flaw in Zero Trust's implementation. It is a fundamental limitation
of any authorization system that cannot verify intent — only identity.

---

## 6. Why the Router Changes Everything

Every defense above assumes the threat lives on the endpoint. The Forge router
server enables a different persistence model:

```
Attack flow without router persistence:
  Endpoint compromised → Endpoint cleaned → Threat eliminated

Attack flow with router persistence:
  Endpoint compromised + Router compromised →
  Endpoint cleaned →
  Device reconnects to router →
  Router re-deploys implant to endpoint →
  Back to compromised state
```

The router:
- Is never included in endpoint incident response
- Has no security tooling that would detect a Python process or custom rpcd plugin
- Maintains a persistent outbound connection the defender is not looking for
- Can intercept traffic at layer 3 before any application-layer security tool sees it

The only way to fully remediate a compromise that includes router persistence is to
simultaneously clean the endpoint AND factory-reset the router. Security teams that
don't know to look for router compromise will cycle through endpoint remediation
repeatedly without resolving the incident.

---

## 7. What The Security Industry Should Do

This document is not an attack plan. It is a map of a threat surface that exists
right now, built from code that is on GitHub, using techniques that are documented
in public security research. The appropriate responses:

**For detection engineers:**
- AI-native threats will not match malware signatures. Behavioral detection needs
  to reason about what is "normal for an AI agent" vs. what is anomalous.
- Router compromise needs to be part of incident response checklists. If a Python
  process or custom rpcd plugin is found on an OpenWrt router, that is a finding.
- C2 traffic to trusted domains (Slack, Discord, GitHub) requires payload inspection,
  not just domain-level allow/block decisions.

**For security architects:**
- Zero Trust's "verify explicitly" pillar needs an intent layer, not just an
  identity layer. The question "is this authorized?" is insufficient when the
  authorized entity is an AI acting on behalf of a human without the human's
  knowledge.
- Router security needs the same scrutiny as endpoint security. Consumer OpenWrt
  devices are a blind spot in most enterprise and home security architectures.

**For the AI developer community:**
- Agent frameworks need explicit dual-use threat modeling as part of their
  documentation and design process. MCP and similar protocols give AI standardized
  access to powerful system capabilities. The security implications need to be
  addressed proactively.
- Local model deployment removes the content filtering and logging that cloud
  APIs provide. This is a privacy benefit and a security risk simultaneously.
  Both need to be communicated clearly.

---

## 8. Limitations of This Analysis

This threat model was written by the person who built the system being analyzed.
It should be treated as a developer's self-assessment, not as an independent security
audit. Limitations:

- I may have blind spots about my own code
- The conversion effort estimates (50–80 hours) are educated guesses, not empirically
  validated
- I have not built a working malicious version of this system to verify these claims
- An independent security researcher reviewing this codebase might identify additional
  risk vectors I have not anticipated

I am seeking independent security review. If you are a qualified researcher interested
in reviewing this codebase and its dual-use implications, please contact:
chris@spectracleanse.com

---

## 9. Contact and Verification

**Developer:** Christopher Adams  
**Email:** chris@spectracleanse.com  
**Repository:** https://github.com/ChrisAdamsdevelopment/Forge-AI  
**Location:** Prescott Valley, AZ  

All code referenced in this document can be reviewed at the repository above.
Specific files:

| Capability | Source file |
|---|---|
| Browser automation | `implementation/backend/forge/agent/tools/browser.py` |
| Screen/input control | `implementation/backend/forge/agent/tools/screen.py` |
| Terminal execution | `implementation/backend/forge/agent/tools/terminal.py` |
| Filesystem operations | `implementation/backend/forge/agent/tools/filesystem.py` |
| Persistent memory | `implementation/backend/forge/agent/tools/memory.py` |
| Router orchestration | `implementation/backend/forge/router_server.py` |
| Autonomous pentest planning | `implementation/backend/forge/agent/operator_mode.py` |
| RAG pipeline | `implementation/backend/forge/rag/` |
| Module system | `implementation/backend/forge/modules/loader.py` |
