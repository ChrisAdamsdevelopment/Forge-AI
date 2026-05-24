# OpenWrt Router MCP Server - Setup & Deployment Guide

## Overview

The `router_server.py` is a FastMCP server that automates your OpenWrt router (TP-Link Archer C7 or compatible) via the official rpcd JSON-RPC API on port 8002.

**Router**: 192.168.1.1 (OpenWrt with rpcd enabled)
**MCP Server**: Port 8002 (Windows)
**API Endpoint**: `http://192.168.1.1/ubus` (OpenWrt router)

## Architecture

### ConnectionManager Class

Handles all UBUS JSON-RPC communication with:
- **Session Caching**: Caches authentication tokens across requests
- **Token Refresh**: Auto-refreshes tokens 5 minutes before expiry (typical 1-hour sessions)
- **Error Translation**: Converts UBUS status codes into structured Python exceptions
- **Async HTTP**: Uses `httpx.AsyncClient` for concurrent request handling

### Tool Categories

#### Read-Only Tools (Safe, no changes)
- `router_system_info()` - Board, firmware, uptime, load averages, memory
- `router_network_list()` - All network interfaces with IP addresses
- `router_interface_status(interface)` - Detailed stats for one interface
- `router_ping_test(target)` - Ping diagnostics from router
- `router_wifi_scan(radio)` - WiFi network scan results
- `router_wifi_clients()` - Connected WiFi clients with signal strength
- `router_system_logs(lines)` - Recent system log entries
- `router_uci_get(config, section, option)` - Read UCI configuration
- `router_uci_sections(config)` - List UCI sections
- `router_firewall_rules()` - List firewall rules and zones
- `router_packages_list(filter)` - Installed packages
- `router_packages_search(query)` - Search package repository

#### Destructive Tools (Configuration changes)
- `router_uci_set()` - **Two-phase UCI commit** (stage → validate → commit)
- `router_uci_revert()` - Rollback uncommitted changes
- `router_interface_restart(interface)` - Restart network interface
- `router_firewall_rule_add()` - Add firewall rule
- `router_firewall_rule_delete()` - Delete firewall rule
- `router_service_reload(service)` - Restart services (dnsmasq, firewall, etc.)
- `router_package_install(package)` - Install package via opkg

## Prerequisites

### On Your Windows PC (Already Done)
```bash
# In C:\dev\forge:
pip install -r implementation/backend/requirements.txt
python implementation/backend/forge/router_server.py
```

This starts the MCP server on port 8002.

### On Your OpenWrt Router

The router needs:
1. **rpcd** daemon running (handles JSON-RPC)
2. **ACL file** installed for the `mcp_ai_agent` user
3. **mcp_ai_agent user** created with restricted shell

#### Step 1: Enable rpcd on Router

SSH into your router:
```bash
ssh root@192.168.1.1
```

Ensure rpcd is enabled and running:
```bash
opkg install rpcd rpcd-mod-uci
service rpcd enable
service rpcd start

# Verify it's listening on /ubus
netstat -tlnp | grep rpcd
# Should show: tcp LISTEN on port 5555 or similar (internal)
```

#### Step 2: Create mcp_ai_agent User

On the router:
```bash
# Create user with restricted login (nologin shell)
useradd -m -s /usr/sbin/nologin -d /tmp/mcp_ai_agent mcp_ai_agent

# Set password (or use SSH key)
passwd mcp_ai_agent
# Enter password when prompted
```

#### Step 3: Deploy ACL File

Copy the ACL file to the router and enable it:

**Option A: Via SCP (from Windows)**
```powershell
# In PowerShell on your Windows PC:
scp C:\dev\forge\implementation\backend\forge\acl_mcp_ai_agent.json root@192.168.1.1:/usr/share/rpcd/acl.d/mcp_ai_agent.json
```

**Option B: Manual Copy (via SSH)**
```bash
# SSH into router and create the file
ssh root@192.168.1.1
cat > /usr/share/rpcd/acl.d/mcp_ai_agent.json << 'EOF'
[paste contents of acl_mcp_ai_agent.json here]
EOF
```

#### Step 4: Verify ACL Configuration

On the router:
```bash
# Check ACL file is readable
ls -la /usr/share/rpcd/acl.d/mcp_ai_agent.json

# Reload rpcd to apply ACL
service rpcd reload

# Test authentication (should succeed)
curl -X POST http://127.0.0.1/ubus \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "call",
    "params": ["00000000000000000000000000000000", "session", "login", {
      "username": "mcp_ai_agent",
      "password": "your_password_here"
    }]
  }' | jq .
```

Should return a `ubus_rpc_session` token.

## Configuration

### Environment Variables (Optional)

Set on your Windows PC before running `router_server.py`:
```powershell
$env:ROUTER_HOST = "192.168.1.1"
$env:ROUTER_USERNAME = "mcp_ai_agent"
$env:ROUTER_PASSWORD = "your_password"
$env:ROUTER_PORT = "80"  # or 8080 if using different port
```

Or edit `router_server.py` directly (lines 35-39):
```python
ROUTER_HOST = "192.168.1.1"
ROUTER_PORT = 80
ROUTER_USERNAME = "mcp_ai_agent"  # Created above
ROUTER_PASSWORD = "your_password"  # Set here or via env
```

### Port Configuration

- **Windows MCP Server**: Port 8002 (edit in `router_server.py` line 40)
- **Router UBUS Endpoint**: Port 80 HTTP (default OpenWrt)

## Usage Examples

### In Forge Agent (when integrated)

```python
# Check router status
result = await router_system_info()
print(f"Uptime: {result['uptime_seconds']} seconds")

# List WiFi networks
networks = await router_wifi_scan()
for net in networks['networks']:
    print(f"{net['ssid']} ({net['signal_strength_dbm']} dBm)")

# Safe configuration read
lan_ip = await router_uci_get('network', 'lan', 'ipaddr')
print(f"LAN IP: {lan_ip['value']}")

# Two-phase safe configuration change
result = await router_uci_set('network', 'lan', 'ipaddr', '192.168.2.1')
if result['status'] == 'ok':
    print("Configuration committed")

# Add firewall rule
result = await router_firewall_rule_add(
    name='allow_http_from_lan',
    src_zone='lan',
    dest_zone='wan',
    proto='tcp',
    dest_port='80'
)
```

## Security Model

### ACL Enforcement (Router-Side)

The `acl_mcp_ai_agent.json` file grants the `mcp_ai_agent` user **least-privilege** access:

**Read-Only Namespaces** (system, network info):
- `uci get/sections` (read-only UCI config)
- `system info/board/logs` (board info, logs)
- `network interface status` (read interface state)
- `iwinfo scan` (WiFi scanning)

**Controlled Write Access**:
- `uci set/commit/revert` (UCI modification with two-phase commits)
- Only specific UCI sections whitelisted: `network.interface`, `wireless.device`, `firewall.*`, `dhcp.dnsmasq`
- **Denied**: system config, admin settings, root-level operations

**Filesystem Restrictions**:
- Read-only access to `/mnt/usb/*` only
- No access to `/etc`, `/root`, `/sys`, `/proc`, `/dev`

**Rate Limiting** (on router):
- Max 10 concurrent sessions
- 100 requests/minute
- 30-second timeout per request

### Two-Phase UCI Commits

All `router_uci_set()` operations use a safe two-phase process:

1. **Stage Change**: Write to pending configuration
2. **Validate Syntax**: Verify staged config is valid
3. **Commit**: Apply to active configuration
4. **Auto-Revert on Failure**: If commit fails, changes are automatically reverted

This prevents corrupted configurations from disabling the router.

## Troubleshooting

### Connection Refused (192.168.1.1)

```
RuntimeError: Connection failed to http://192.168.1.1/ubus
```

**Solutions**:
- Verify router is on: `ping 192.168.1.1`
- Check rpcd is running: `ssh root@192.168.1.1 service rpcd status`
- Verify HTTP is accessible: `curl http://192.168.1.1` (should show OpenWrt web interface)
- Check firewall allows HTTP: `ssh root@192.168.1.1 ufw allow 80/tcp` (if ufw is enabled)

### Permission Denied (UBUS_STATUS_PERMISSION_DENIED = 6)

```
PermissionError: Permission denied for network.interface.status
```

**Solutions**:
- Verify ACL file is deployed: `ssh root@192.168.1.1 cat /usr/share/rpcd/acl.d/mcp_ai_agent.json`
- Reload rpcd: `ssh root@192.168.1.1 service rpcd reload`
- Check user exists: `ssh root@192.168.1.1 id mcp_ai_agent`
- Verify password is correct in `router_server.py`

### Session Token Expired

The ConnectionManager auto-refreshes tokens 5 minutes before expiry. If you see timeout errors after 1 hour:
- Tokens are cached and refreshed automatically
- No action needed; next request will trigger refresh

### UCI Commit Failures

If two-phase commit fails:
- Check `/var/log/messages` on router: `ssh root@192.168.1.1 tail -f /var/log/messages`
- The tool automatically reverts changes on failure
- Review the `reverted` field in response

## Files Modified/Created

1. **Created**:
   - `implementation/backend/forge/router_server.py` (529 lines)
   - `implementation/backend/forge/acl_mcp_ai_agent.json` (ACL config)

2. **Modified**:
   - `implementation/backend/forge/config.py` - Added `ROUTER_MCP_PORT`, `ROUTER_HOST`, `ROUTER_USERNAME`
   - `start_agent.bat` - Added `router_server.py` startup

3. **To Deploy on Router**:
   - `acl_mcp_ai_agent.json` → `/usr/share/rpcd/acl.d/mcp_ai_agent.json`

## Integration with Forge-AI Agent

Once deployed, the Forge-AI agent can call router tools via the MCP interface:

```
Agent Request: "Scan WiFi networks and list connected clients"
→ router_wifi_scan() (read-only, safe)
→ router_wifi_clients() (read-only, safe)
→ Agent responds with network topology
```

## Next Steps

1. ✅ **Verify Syntax**: `python -m py_compile implementation/backend/forge/router_server.py`
2. ✅ **Start Server**: `python implementation/backend/forge/router_server.py`
3. ✅ **Test Connection**: Curl to `http://192.168.1.1/ubus` from Windows
4. ✅ **Deploy ACL**: Copy `acl_mcp_ai_agent.json` to router
5. ✅ **Create User**: Create `mcp_ai_agent` on router
6. ✅ **Test Tools**: Call individual tools and verify responses

## Reference: UBUS JSON-RPC Format

All requests use the OpenWrt ubus JSON-RPC protocol:

```json
{
  "jsonrpc": "2.0",
  "id": 123,
  "method": "call",
  "params": [
    "ubus_rpc_session_token",
    "namespace",
    "method",
    { "param1": "value1" }
  ]
}
```

Response format:
```json
{
  "jsonrpc": "2.0",
  "id": 123,
  "result": [
    0,
    { "data": "response" }
  ]
}
```

Where `result[0]` is the status code (0 = OK, 6 = permission denied, etc.).
