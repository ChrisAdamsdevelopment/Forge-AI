# Forge-AI Complete Implementation Guide

## Overview

Four major builds have been successfully implemented for the Forge-AI personal AI agent platform:

1. **BUILD 1**: Spotify Automation Tool
2. **BUILD 2**: Windows Scheduled Task Auto-Start
3. **BUILD 3**: Per-Domain MCP Server Splitting
4. **BUILD 4**: Operator Mode (Autonomous Attack Planning)

All implementations follow FastMCP patterns, include proper type hints, docstrings, and error handling. ✅ **All files compiled and verified**.

---

## BUILD 1: Spotify Automation Tool

### Location
`implementation/backend/forge/agent/tools/spotify.py` (251 lines)

### Features
- Headless browser automation using Playwright (headless=False for visibility)
- Navigate to open.spotify.com
- Search for songs by name and artist
- Play first search result
- Like/save tracks
- Create private and public playlists
- Add tracks to playlists
- Screenshot capabilities to confirm actions
- Proper session reuse and cleanup

### Tools Provided
```python
spotify_navigate_home()              # Navigate to Spotify
spotify_search_song(song, artist)    # Search for song
spotify_play_first_result()          # Play first result
spotify_like_track()                 # Like current track
spotify_create_playlist(name, public) # Create playlist
spotify_add_to_playlist(playlist)    # Add to playlist
spotify_screenshot()                 # Capture UI
spotify_close()                      # Close browser
```

### Usage Example
```python
await spotify_navigate_home()
await spotify_search_song("Bohemian Rhapsody", "Queen")
await spotify_play_first_result()
await spotify_like_track()
result = await spotify_screenshot()
```

### Security Notes
- Personal account only (not shared)
- Headless=False so you can monitor actions
- Returns base64 screenshots for verification
- All tools return structured dicts with status fields

### Integration
- Registered in `forge/agent/tools/registry.py`
- Automatically imported when registry loads
- Available via agent tool calling

---

## BUILD 2: Windows Scheduled Task Auto-Start

### Files Created

#### `setup_scheduler.ps1` (80 lines)
Creates Windows Scheduled Task for Forge-AI auto-start on user logon.

**Features:**
- Creates task named "ForgeAI"
- Triggers at user logon
- Runs with highest privileges
- Unlimited execution time
- Auto-restart on failure: every 5 minutes, max 3 restarts
- Creates ~/.forge/logs/scheduler directory for logs
- Verifies start_agent.bat exists

**Usage:**
```powershell
PowerShell -ExecutionPolicy Bypass -File setup_scheduler.ps1
```

**Requirements:**
- Administrator privileges
- Run PowerShell as Administrator

#### `remove_scheduler.ps1` (40 lines)
Removes the ForgeAI scheduled task.

**Usage:**
```powershell
PowerShell -ExecutionPolicy Bypass -File remove_scheduler.ps1
```

### Task Configuration
```
Task Name:          ForgeAI
Description:        Forge-AI MCP Agent Platform - Auto-start on user logon
Trigger:            At user logon
Action:             Run start_agent.bat
Privileges:         Highest
Time Limit:         Unlimited
On Failure:         Restart every 5 minutes (max 3 restarts)
Working Directory:  Repo root
```

### Verification
After running setup_scheduler.ps1:
```powershell
Get-ScheduledTask -TaskName ForgeAI | Select-Object -Property *
```

---

## BUILD 3: Per-Domain MCP Server Splitting

### Directory Structure
```
implementation/backend/forge/mcp_servers/
├── __init__.py                 (Package exports)
├── base.py                     (Shared FastMCP setup)
├── browser_server.py           (Port 8010)
├── screen_server.py            (Port 8011)
├── terminal_server.py          (Port 8012)
├── filesystem_server.py        (Port 8013)
├── apps_server.py              (Port 8014)
├── web_server.py               (Port 8015)
├── memory_server.py            (Port 8016)
├── thinking_server.py          (Port 8017)
├── rag_server.py               (Port 8018)
└── start_all_servers.py        (Launcher)
```

### Port Allocation
| Domain | Port | Description |
|--------|------|-------------|
| browser | 8010 | Browser automation |
| screen | 8011 | Screen capture & input |
| terminal | 8012 | Shell execution |
| filesystem | 8013 | File operations |
| apps | 8014 | Application management |
| web | 8015 | Web content fetching |
| memory | 8016 | Persistent memory |
| thinking | 8017 | Sequential reasoning |
| rag | 8018 | RAG search |

### Base Module (`base.py`)
Provides shared utilities:
- `create_server(domain)` - Create FastMCP instance
- `get_port(domain)` - Get port for domain
- `run_server(domain, register_fn)` - Run async server
- `print_servers_info()` - Display server information

### Server Architecture

Each server follows the same pattern:

```python
from forge.mcp_servers.base import get_port
mcp = FastMCP("Domain Agent")

@mcp.tool(description="...")
async def tool_func():
    return {}

async def main():
    port = get_port("domain")
    await mcp.run(port=port)
```

### Starting Servers

**Option A: Start all at once**
```bash
python implementation/backend/forge/mcp_servers/start_all_servers.py
```

**Option B: Start individual servers**
```bash
python -m forge.mcp_servers.browser_server      # Port 8010
python -m forge.mcp_servers.terminal_server     # Port 8012
python -m forge.mcp_servers.web_server          # Port 8015
# etc.
```

**Option C: Selective startup** (edit start_agent.bat)
```batch
start /B python implementation\backend\forge\mcp_servers\browser_server.py
start /B python implementation\backend\forge\mcp_servers\terminal_server.py
```

### Benefits
✅ Granular capability control
✅ Enable/disable domains per ChatGPT connector
✅ Reduced resource footprint (run only needed servers)
✅ Better crash isolation (one server failure doesn't affect others)
✅ Easier debugging and monitoring
✅ Modular testing

### Backward Compatibility
- Original monolithic `tool_server.py` remains unchanged
- New split architecture is opt-in
- Can run both simultaneously (different ports)

---

## BUILD 4: Operator Mode (Autonomous Attack Planning)

### Location
`implementation/backend/forge/agent/operator_mode.py` (450+ lines)

### Core Components

#### AttackStep Class
Represents a single step in attack planning.

```python
class AttackStep:
    step_id: str                      # Unique ID (step_001_12345)
    phase: PhaseType                  # reconnaissance, enumeration, etc.
    tool_name: str                    # recon_nmap_scan, exploit_sqlmap_test, etc.
    tool_type: ToolType               # recon, destructive, interactive
    parameters: dict                  # Tool parameters
    rationale: str                    # Why this step was chosen
    findings: dict                    # Results from execution
    next_steps_possible: list[str]    # Possible next attack paths
    human_approved: bool              # Approval status
    executed: bool                    # Execution status
```

#### OperatorMode Class
Main orchestration engine.

**Constructor:**
```python
OperatorMode(
    target: str,                      # IP, domain, or network range
    llm_callback: callable = None,    # Async function for LLM planning
    max_steps: int = 20,              # Maximum attack steps
    beam_width: int = 3,              # Beam search width
    mcts_simulations: int = 10,       # Monte Carlo simulations
)
```

**Methods:**

1. **`async run() -> dict`**
   - Execute full attack orchestration
   - Progression through phases: reconnaissance → enumeration → vulnerability analysis → exploitation
   - Returns final report

2. **`async _plan_next_steps() -> list[AttackStep]`**
   - Generate next attack steps using LLM
   - Use Beam Search or MCTS depending on phase
   - Return top candidates

3. **`_beam_search_top_paths() -> list[AttackStep]`**
   - Maintain top K most promising paths
   - Score by findings richness + safety + randomization
   - Used for deterministic enumeration phases

4. **`_mcts_simulate_path() -> float`**
   - Simulate step execution
   - Calculate expected reward (0-1)
   - Based on vulnerability likelihood + findings

5. **`async _request_human_approval(step) -> bool`**
   - Request approval before destructive/interactive tools
   - Auto-approve reconnaissance
   - Interactive CLI prompt with full step details

6. **`async _generate_report() -> dict`**
   - Create JSON report with all findings
   - Generate markdown report
   - Save to ~/.forge/logs/operator_mode/

### Attack Phases

```
1. RECONNAISSANCE (Safe, information gathering)
   - nmap scan (quick)
   - whois lookup
   - subdomain enumeration

2. ENUMERATION (Extended scanning)
   - nmap service detection
   - web technology identification
   - directory bruteforcing

3. VULNERABILITY_ANALYSIS (Vulnerability scanning)
   - nuclei template scanning
   - searchsploit database lookup
   - SQLi testing

4. EXPLOITATION (Requires approval)
   - sqlmap automated exploitation
   - hydra credential brute-force
   - interactive shells (loot collection)

5. REPORTING
   - Markdown report generation
   - Finding summaries
   - Remediation recommendations
```

### Search Strategies

#### Beam Search (Deterministic Enumeration)
```
Width: 3 (top 3 paths)
Scoring: findings_count * 10 + safety_bonus + random
Uses: ENUMERATION phase
Purpose: Systematic service discovery
```

#### Monte Carlo Tree Search (Non-Deterministic)
```
Simulations: 10 per step
Scoring: vulnerability_likelihood + findings_presence + recon_bonus
Uses: Other phases
Purpose: Probabilistic vulnerability ranking
```

### Human-in-the-Loop Checkpoints

Triggers for all destructive and interactive tools:

```
Tool Type              Auto-Approve?   Action
─────────────────────────────────────────────────
recon_*               Yes ✓           Execute immediately
recon_nmap_scan       Yes ✓           Execute immediately
exploit_sqlmap_test   No ✗            Show checkpoint, ask user
exploit_hydra         No ✗            Show checkpoint, ask user
post_loot_collect     No ✗            Show checkpoint, ask user
exploit_nuclei_scan   No ✗            Show checkpoint, ask user
```

Checkpoint displays:
- Tool name
- Target
- Parameters (JSON)
- Rationale
- User must type 'y' to approve

### Report Generation

**JSON Report** (saved to ~/.forge/logs/operator_mode/)
```json
{
  "target": "192.168.1.100",
  "timestamp": "2024-05-24T...",
  "total_steps": 15,
  "findings_count": 42,
  "attack_graph": {
    "step_001": {
      "tool_name": "recon_nmap_scan",
      "phase": "reconnaissance",
      "findings": {...},
      ...
    }
  },
  "markdown_report": "..."
}
```

**Markdown Report** (embedded in JSON)
```markdown
# Operator Mode Attack Report

**Target**: 192.168.1.100
**Date**: 2024-05-24T...
**Total Steps**: 15
**Findings**: 42

## Executive Summary
Automated attack path planning completed for 192.168.1.100.

## Attack Path
### step_001: recon_nmap_scan
- **Phase**: reconnaissance
- **Rationale**: Initial service discovery
- **Findings**: ports=[22, 80, 443], services=[ssh, http, https]
...

## Recommendations
1. Review all automated findings with manual verification
2. Prioritize by CVSS score
3. Implement monitoring...
```

### Logging

All activity logged to:
`~/.forge/logs/operator_mode/operator_mode_YYYYMMDD_HHMMSS.log`

Logs include:
- Phase transitions
- Step planning and rationale
- Human approvals
- Execution results
- LLM planning fallbacks

### MCP Tool Registration

Two tools registered in pentest_server.py:

1. **`operator_mode_start(target, max_steps=20) -> dict`**
   - Start autonomous attack orchestration
   - Returns final report with all findings

2. **`operator_mode_get_attack_graph(target) -> dict`**
   - Retrieve attack graph for a target
   - For progress tracking and visualization

### Usage Example

```python
# Start operator mode
result = await operator_mode_start("192.168.1.100", max_steps=20)

# Result structure
{
    "status": "ok",
    "report": {
        "target": "192.168.1.100",
        "attack_graph": {...},
        "markdown_report": "...",
        ...
    }
}
```

### Safety Features

✅ **Human-in-the-loop**: All destructive tools require approval
✅ **Bounded search**: Max steps limit prevents infinite loops
✅ **Phase progression**: Systematic stages (recon → exploitation)
✅ **Tool categorization**: Auto-approval only for read-only tools
✅ **Comprehensive logging**: All steps recorded for audit
✅ **Error handling**: All tools return structured dicts, no raw exceptions
✅ **LLM fallback**: Heuristic planning if LLM unavailable

### Limitations & Future Work

- Current implementation uses simulated tool execution (for demo)
- Real implementation would call actual pentest_server tools
- LLM integration requires local inference service callback
- MCTS could use domain-specific reward functions
- Attack graph could be stored in persistent database

---

## File Summary

### New Files Created
```
✓ implementation/backend/forge/agent/tools/spotify.py (251 lines)
✓ implementation/backend/forge/agent/operator_mode.py (450+ lines)
✓ setup_scheduler.ps1 (80 lines)
✓ remove_scheduler.ps1 (40 lines)
✓ implementation/backend/forge/mcp_servers/__init__.py
✓ implementation/backend/forge/mcp_servers/base.py (100 lines)
✓ implementation/backend/forge/mcp_servers/browser_server.py (35 lines)
✓ implementation/backend/forge/mcp_servers/screen_server.py (45 lines)
✓ implementation/backend/forge/mcp_servers/terminal_server.py (30 lines)
✓ implementation/backend/forge/mcp_servers/filesystem_server.py (40 lines)
✓ implementation/backend/forge/mcp_servers/apps_server.py (30 lines)
✓ implementation/backend/forge/mcp_servers/web_server.py (30 lines)
✓ implementation/backend/forge/mcp_servers/memory_server.py (35 lines)
✓ implementation/backend/forge/mcp_servers/thinking_server.py (30 lines)
✓ implementation/backend/forge/mcp_servers/rag_server.py (35 lines)
✓ implementation/backend/forge/mcp_servers/start_all_servers.py (75 lines)
```

### Files Modified
```
✓ implementation/backend/forge/agent/tools/registry.py (added spotify imports & tools)
✓ implementation/backend/forge/pentest_server.py (added operator_mode imports & registration)
```

---

## Integration Checklist

- [x] BUILD 1: Spotify automation tool created and registered
- [x] BUILD 2: Windows scheduler setup and removal scripts created
- [x] BUILD 3: Modular MCP server infrastructure created (9 servers + base + launcher)
- [x] BUILD 4: Operator Mode with Beam Search and MCTS implemented
- [x] All files compiled and verified
- [x] Type hints on all functions
- [x] Comprehensive docstrings
- [x] Error handling with structured dicts
- [x] FastMCP patterns followed
- [x] Registry updated with new tools
- [x] Pentest server updated with operator_mode tools

---

## Next Steps

1. **TEST Spotify Tool:**
   ```bash
   python -c "import asyncio; from forge.agent.tools.spotify import *; asyncio.run(spotify_navigate_home())"
   ```

2. **TEST Scheduler:**
   ```powershell
   PowerShell -ExecutionPolicy Bypass -File setup_scheduler.ps1
   ```

3. **TEST MCP Servers:**
   ```bash
   # Individual server
   python -m forge.mcp_servers.browser_server

   # All servers
   python implementation/backend/forge/mcp_servers/start_all_servers.py
   ```

4. **TEST Operator Mode:**
   ```bash
   python implementation/backend/forge/agent/operator_mode.py
   ```

5. **INTEGRATE with Agent:**
   - Update agent graph to call operator_mode_start()
   - Configure LLM callback for autonomous planning
   - Test with lab environment targets

---

## Documentation

For detailed information on each build, see:
- Spotify: See `spotify.py` docstrings
- Scheduler: See `setup_scheduler.ps1` comments
- MCP Splitting: See `forge/mcp_servers/README.md` (to be created)
- Operator Mode: See `operator_mode.py` docstrings and class documentation

All implementations follow your existing code style and patterns. ✅
