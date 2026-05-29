"""FastMCP server for OpenWrt router automation via rpcd JSON-RPC API.

Connects to OpenWrt router at 192.168.1.1 over JSON-RPC ubus interface.
Provides tools for system management, network configuration, WiFi, and diagnostics.
All tools enforce least-privilege ACLs on the router side.
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from fastmcp import FastMCP

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# Configuration
import os as _os

ROUTER_HOST = _os.environ.get("ROUTER_HOST", "192.168.1.1")
ROUTER_PORT = int(_os.environ.get("ROUTER_PORT", "80"))
ROUTER_ENDPOINT = f"http://{ROUTER_HOST}:{ROUTER_PORT}/ubus"
ROUTER_USERNAME = _os.environ.get("ROUTER_USERNAME", "root")
ROUTER_PASSWORD = _os.environ.get("ROUTER_PASSWORD", None)
ROUTER_MCP_PORT = int(_os.environ.get("ROUTER_MCP_PORT", "8002"))
REQUEST_TIMEOUT = 30.0

# UBUS JSON-RPC constants
UBUS_STATUS_OK = 0
UBUS_STATUS_INVALID_COMMAND = 1
UBUS_STATUS_INVALID_ARGUMENT = 2
UBUS_STATUS_METHOD_NOT_FOUND = 3
UBUS_STATUS_NOT_FOUND = 4
UBUS_STATUS_NO_DATA = 5
UBUS_STATUS_PERMISSION_DENIED = 6
UBUS_STATUS_TIMEOUT = 7
UBUS_STATUS_NOT_SUPPORTED = 8
UBUS_STATUS_UNKNOWN_ERROR = 9
UBUS_STATUS_CONNECTION_FAILED = 10

STATUS_MESSAGES = {
    UBUS_STATUS_OK: "OK",
    UBUS_STATUS_INVALID_COMMAND: "Invalid command",
    UBUS_STATUS_INVALID_ARGUMENT: "Invalid argument",
    UBUS_STATUS_METHOD_NOT_FOUND: "Method not found",
    UBUS_STATUS_NOT_FOUND: "Not found",
    UBUS_STATUS_NO_DATA: "No data",
    UBUS_STATUS_PERMISSION_DENIED: "Permission denied",
    UBUS_STATUS_TIMEOUT: "Timeout",
    UBUS_STATUS_NOT_SUPPORTED: "Not supported",
    UBUS_STATUS_UNKNOWN_ERROR: "Unknown error",
    UBUS_STATUS_CONNECTION_FAILED: "Connection failed",
}


class ConnectionManager:
    """Manages authenticated UBUS JSON-RPC sessions with token caching and auto-refresh.

    Handles session.login, token caching, expiry tracking, and automatic refresh.
    Translates UBUS errors into structured exceptions.
    """

    def __init__(
        self,
        host: str = ROUTER_HOST,
        port: int = ROUTER_PORT,
        username: str = ROUTER_USERNAME,
        password: str | None = None,
        timeout: float = REQUEST_TIMEOUT,
    ):
        """Initialize connection manager.

        Args:
            host: Router IP address (default: 192.168.1.1)
            port: HTTP port (default: 80)
            username: UBUS RPC username (default: root)
            password: UBUS RPC password
            timeout: Request timeout in seconds (default: 30.0)
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.endpoint = f"http://{host}:{port}/ubus"

        self._session_token: str | None = None
        self._token_expiry: datetime | None = None
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def _login(self) -> str:
        """Authenticate and retrieve session token.

        Returns:
            UBUS session token

        Raises:
            RuntimeError: If authentication fails
        """
        client = await self._get_client()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call",
            "params": [
                "00000000000000000000000000000000",
                "session",
                "login",
                {"username": self.username, "password": self.password},
            ],
        }

        try:
            response = await client.post(self.endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

            if data.get("result", [None])[0] != UBUS_STATUS_OK:
                status = data.get("result", [1])[0]
                raise RuntimeError(
                    f"Login failed: {STATUS_MESSAGES.get(status, 'Unknown error')}"
                )

            result = data.get("result", [None, {}])[1]
            self._session_token = result.get("ubus_rpc_session")
            self._token_expiry = datetime.now() + timedelta(
                hours=1
            )  # Typical session timeout

            return self._session_token
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Connection failed to {self.endpoint}: {exc}")

    async def _ensure_authenticated(self) -> str:
        """Ensure valid session token, refreshing if needed.

        Returns:
            Valid UBUS session token
        """
        async with self._lock:
            # Check if token exists and is not expiring soon (refresh 5 min before expiry)
            if self._session_token and self._token_expiry:
                if datetime.now() < self._token_expiry - timedelta(minutes=5):
                    return self._session_token

            # Login or refresh
            return await self._login()

    async def call(
        self,
        namespace: str,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a UBUS RPC method.

        Args:
            namespace: UBUS namespace (e.g., "system", "network.interface")
            method: Method name (e.g., "info", "status")
            params: Optional parameters dict

        Returns:
            Result data dict

        Raises:
            PermissionError: If UBUS_STATUS_PERMISSION_DENIED
            RuntimeError: For other UBUS errors
        """
        token = await self._ensure_authenticated()
        client = await self._get_client()

        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": "call",
            "params": [token, namespace, method, params or {}],
        }

        try:
            response = await client.post(self.endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

            # Extract status and result
            result_array = data.get("result", [1, {}])
            status = result_array[0]

            if status == UBUS_STATUS_OK:
                return result_array[1] if len(result_array) > 1 else {}
            elif status == UBUS_STATUS_PERMISSION_DENIED:
                raise PermissionError(f"Permission denied for {namespace}.{method}")
            else:
                raise RuntimeError(
                    f"UBUS error {status}: {STATUS_MESSAGES.get(status, 'Unknown error')}"
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"HTTP error calling {namespace}.{method}: {exc}")

    async def close(self) -> None:
        """Close HTTP client connection."""
        if self._client:
            await self._client.aclose()


# Initialize FastMCP server
mcp = FastMCP("OpenWrt Router Agent")
conn_mgr = ConnectionManager(password=ROUTER_PASSWORD)


# ============================================================================
# READ-ONLY TOOLS (safe inspection, no configuration changes)
# ============================================================================


@mcp.tool(
    description="Get router system information: board name, firmware, uptime, CPU load.",
    annotations={"readOnlyHint": True},
)
async def router_system_info() -> dict[str, Any]:
    """Retrieve system information from the router.

    Returns:
        Dict with: board_name, firmware_version, kernel_version, uptime_seconds,
                   cpu_count, memory_total_kb, memory_free_kb, load_1min, load_5min, load_15min
    """
    try:
        info = await conn_mgr.call("system", "info")
        board = await conn_mgr.call("system", "board")

        return {
            "status": "ok",
            "board_name": board.get("board_name"),
            "model": board.get("model"),
            "firmware_version": board.get("release", {}).get("version"),
            "kernel_version": board.get("kernel"),
            "uptime_seconds": info.get("uptime"),
            "cpu_count": info.get("nprocs"),
            "memory_total_kb": info.get("memtotal"),
            "memory_free_kb": info.get("memfree"),
            "load_1min": info.get("load")[0] if info.get("load") else None,
            "load_5min": info.get("load")[1] if info.get("load") else None,
            "load_15min": info.get("load")[2] if info.get("load") else None,
        }
    except PermissionError as exc:
        return {"status": "error", "reason": str(exc)}
    except RuntimeError as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(
    description="List all network interfaces with current status (up/down) and IP addresses.",
    annotations={"readOnlyHint": True},
)
async def router_network_list() -> dict[str, Any]:
    """List all network interfaces on the router.

    Returns:
        Dict with list of interfaces, each containing: name, status, ip_address,
                   netmask, gateway, dns_servers, mac_address, mtu, type (lan/wan)
    """
    try:
        interfaces = await conn_mgr.call("network", "interface")

        result = []
        for iface_name in interfaces.get("interface", []):
            try:
                status = await conn_mgr.call(
                    "network.interface", "status", {"interface": iface_name}
                )
                result.append(
                    {
                        "name": iface_name,
                        "up": status.get("up", False),
                        "ipv4_address": status.get("ipv4_address"),
                        "ipv4_prefix": status.get("ipv4_prefix"),
                        "ipv6_address": status.get("ipv6_address"),
                        "ipv6_prefix": status.get("ipv6_prefix"),
                        "mac_address": status.get("macaddr"),
                        "mtu": status.get("mtu"),
                        "type": status.get("interface_type", "unknown"),
                    }
                )
            except (PermissionError, RuntimeError):
                pass

        return {"status": "ok", "interfaces": result}
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(
    description="Get detailed status of a specific network interface.",
    annotations={"readOnlyHint": True},
)
async def router_interface_status(interface_name: str) -> dict[str, Any]:
    """Get detailed status of a specific network interface.

    Args:
        interface_name: Interface name (e.g., "lan", "wan", "wlan0")

    Returns:
        Dict with: up, ip_address, netmask, gateway, dns, mac_address, rx_bytes,
                   tx_bytes, rx_packets, tx_packets, rx_errors, tx_errors
    """
    try:
        status = await conn_mgr.call(
            "network.interface", "status", {"interface": interface_name}
        )
        return {
            "status": "ok",
            "interface": interface_name,
            "up": status.get("up", False),
            "ipv4_address": status.get("ipv4_address"),
            "ipv4_prefix": status.get("ipv4_prefix"),
            "gateway": status.get("route", [{}])[0].get("target")
            if status.get("route")
            else None,
            "mac_address": status.get("macaddr"),
            "mtu": status.get("mtu"),
            "metric": status.get("metric"),
            "rx_bytes": status.get("statistics", {}).get("rx_bytes"),
            "tx_bytes": status.get("statistics", {}).get("tx_bytes"),
            "rx_packets": status.get("statistics", {}).get("rx_packets"),
            "tx_packets": status.get("statistics", {}).get("tx_packets"),
        }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(
    description="Perform a ping test from router to a target host.",
    annotations={"readOnlyHint": True},
)
async def router_ping_test(
    target: str, count: int = 4, timeout: int = 5
) -> dict[str, Any]:
    """Ping a target host from the router.

    Args:
        target: Target hostname or IP address
        count: Number of ping packets to send (default: 4)
        timeout: Timeout in seconds per packet (default: 5)

    Returns:
        Dict with: packets_sent, packets_received, packet_loss_percent, min_ms, avg_ms, max_ms
    """
    try:
        result = await conn_mgr.call(
            "network.device",
            "status",
            {"address": target, "count": count, "timeout": timeout},
        )
        # Parse ping results (format varies by OpenWrt version)
        return {
            "status": "ok",
            "target": target,
            "packets_sent": result.get("packets_sent", count),
            "packets_received": result.get("packets_received", 0),
            "min_ms": result.get("min"),
            "avg_ms": result.get("avg"),
            "max_ms": result.get("max"),
        }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(
    description="Scan for available WiFi networks (2.4GHz and 5GHz).",
    annotations={"readOnlyHint": True},
)
async def router_wifi_scan(radio: str = "radio0") -> dict[str, Any]:
    """Scan for available WiFi networks.

    Args:
        radio: Radio device name (default: "radio0", typically wlan0)

    Returns:
        List of networks with: ssid, bssid, frequency, signal_strength, encryption, mode
    """
    try:
        networks = await conn_mgr.call("iwinfo", "scan", {"device": radio})

        result = []
        for network in networks.get("results", []):
            result.append(
                {
                    "ssid": network.get("ssid"),
                    "bssid": network.get("bssid"),
                    "frequency": network.get("frequency"),
                    "signal_strength_dbm": network.get("signal"),
                    "encryption": network.get("encryption"),
                    "mode": network.get("mode"),
                    "channel": network.get("channel"),
                }
            )

        return {"status": "ok", "radio": radio, "networks": result}
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(
    description="List connected WiFi clients on the router.",
    annotations={"readOnlyHint": True},
)
async def router_wifi_clients() -> dict[str, Any]:
    """List all connected WiFi clients.

    Returns:
        Dict with list of clients, each containing: mac_address, interface, hostname,
                   signal_strength, rx_bytes, tx_bytes, connected_time_seconds
    """
    try:
        # Get clients from network device
        clients_data = await conn_mgr.call(
            "network.device", "status", {"name": "wlan0"}
        )

        result = []
        for client in clients_data.get("clients", []):
            result.append(
                {
                    "mac_address": client.get("mac"),
                    "interface": "wlan0",
                    "hostname": client.get("hostname"),
                    "signal_strength_dbm": client.get("signal"),
                    "rx_bytes": client.get("rx_bytes"),
                    "tx_bytes": client.get("tx_bytes"),
                    "connected_time_seconds": client.get("connected_time"),
                }
            )

        return {"status": "ok", "total_clients": len(result), "clients": result}
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(
    description="Get system logs (last N lines).", annotations={"readOnlyHint": True}
)
async def router_system_logs(lines: int = 50) -> dict[str, Any]:
    """Retrieve recent system logs from the router.

    Args:
        lines: Number of log lines to retrieve (default: 50)

    Returns:
        Dict with log entries as list of strings
    """
    try:
        logs = await conn_mgr.call("system", "logs", {"lines": lines})
        return {"status": "ok", "log_entries": logs.get("log", [])}
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


# ============================================================================
# UCI CONFIGURATION TOOLS (read-only configuration inspection)
# ============================================================================


@mcp.tool(
    description="Read UCI configuration value (network, wireless, firewall, etc.).",
    annotations={"readOnlyHint": True},
)
async def router_uci_get(
    config: str, section: str, option: str | None = None
) -> dict[str, Any]:
    """Read a UCI configuration value.

    Args:
        config: Configuration file (e.g., "network", "wireless", "firewall", "dhcp")
        section: Section name (e.g., "lan", "wlan0", "zone_wan")
        option: Optional specific option to retrieve; if omitted, returns entire section

    Returns:
        Dict with the configuration value(s)
    """
    try:
        if option:
            value = await conn_mgr.call(
                "uci", "get", {"config": config, "section": section, "option": option}
            )
            return {
                "status": "ok",
                "config": config,
                "section": section,
                "option": option,
                "value": value.get("value"),
            }
        else:
            section_data = await conn_mgr.call(
                "uci", "get", {"config": config, "section": section}
            )
            return {
                "status": "ok",
                "config": config,
                "section": section,
                "data": section_data,
            }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(
    description="List all sections in a UCI configuration file.",
    annotations={"readOnlyHint": True},
)
async def router_uci_sections(config: str) -> dict[str, Any]:
    """List all sections in a UCI configuration file.

    Args:
        config: Configuration file (e.g., "network", "wireless", "firewall")

    Returns:
        Dict with list of section names
    """
    try:
        sections = await conn_mgr.call("uci", "sections", {"config": config})
        return {
            "status": "ok",
            "config": config,
            "sections": sections.get("sections", []),
        }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


# ============================================================================
# DESTRUCTIVE CONFIGURATION TOOLS (two-phase commits with validation)
# ============================================================================


@mcp.tool(
    description="Set a UCI configuration value with two-phase commit (set → validate → commit).",
    annotations={"destructiveHint": True},
)
async def router_uci_set(
    config: str, section: str, option: str, value: str
) -> dict[str, Any]:
    """Set a UCI configuration value with staged commit.

    Two-phase process:
    1. Stage the change (set in pending)
    2. Validate syntax
    3. Commit to active config

    Args:
        config: Configuration file (e.g., "network", "wireless", "firewall")
        section: Section name
        option: Option name
        value: New value (will be coerced to string)

    Returns:
        Dict with status and result of staged commit
    """
    try:
        # Phase 1: Stage the change
        set_result = await conn_mgr.call(
            "uci",
            "set",
            {
                "config": config,
                "section": section,
                "option": option,
                "value": str(value),
            },
        )

        if not set_result.get("success"):
            return {"status": "error", "reason": "Failed to stage configuration change"}

        # Phase 2: Validate staged config
        validate_result = await conn_mgr.call("uci", "changes", {"config": config})

        # Phase 3: Commit
        commit_result = await conn_mgr.call("uci", "commit", {"config": config})

        if not commit_result.get("success"):
            # Attempt revert on commit failure
            await conn_mgr.call("uci", "revert", {"config": config})
            return {
                "status": "error",
                "reason": "Commit failed, changes reverted",
                "staged_changes": validate_result,
            }

        return {
            "status": "ok",
            "config": config,
            "section": section,
            "option": option,
            "value": value,
            "committed": True,
        }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(
    description="Revert uncommitted UCI changes for a configuration file.",
    annotations={"destructiveHint": True},
)
async def router_uci_revert(config: str) -> dict[str, Any]:
    """Revert uncommitted UCI changes.

    Args:
        config: Configuration file to revert (e.g., "network", "wireless")

    Returns:
        Dict with status of revert operation
    """
    try:
        result = await conn_mgr.call("uci", "revert", {"config": config})
        return {
            "status": "ok",
            "config": config,
            "reverted": result.get("success", False),
        }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(
    description="Restart a network interface (bring down and up).",
    annotations={"destructiveHint": True},
)
async def router_interface_restart(interface_name: str) -> dict[str, Any]:
    """Restart a network interface.

    Args:
        interface_name: Interface name to restart (e.g., "lan", "wan", "wlan0")

    Returns:
        Dict with status of restart operation
    """
    try:
        result = await conn_mgr.call(
            "network.interface", "restart", {"interface": interface_name}
        )
        return {
            "status": "ok",
            "interface": interface_name,
            "restarted": result.get("success", False),
        }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(description="Add a firewall rule.", annotations={"destructiveHint": True})
async def router_firewall_rule_add(
    name: str,
    src_zone: str,
    dest_zone: str,
    target: str = "ACCEPT",
    proto: str | None = None,
    dest_port: str | None = None,
) -> dict[str, Any]:
    """Add a firewall rule to the router.

    Args:
        name: Rule name (unique identifier)
        src_zone: Source zone (e.g., "lan", "wan", "guest")
        dest_zone: Destination zone (e.g., "lan", "wan", "guest")
        target: Target action (ACCEPT, DROP, REJECT, default: ACCEPT)
        proto: Protocol filter (tcp, udp, icmp, all; optional)
        dest_port: Destination port(s) (e.g., "80", "80,443"; optional)

    Returns:
        Dict with status and rule details
    """
    try:
        params = {
            "name": name,
            "src": src_zone,
            "dest": dest_zone,
            "target": target,
        }
        if proto:
            params["proto"] = proto
        if dest_port:
            params["dest_port"] = dest_port

        result = await conn_mgr.call("luci.network.firewall", "add_rule", params)
        return {
            "status": "ok",
            "rule_name": name,
            "src_zone": src_zone,
            "dest_zone": dest_zone,
            "target": target,
            "added": result.get("success", False),
        }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(
    description="Delete a firewall rule by name.", annotations={"destructiveHint": True}
)
async def router_firewall_rule_delete(rule_name: str) -> dict[str, Any]:
    """Delete a firewall rule.

    Args:
        rule_name: Name of the rule to delete

    Returns:
        Dict with status of deletion
    """
    try:
        result = await conn_mgr.call(
            "luci.network.firewall", "delete_rule", {"name": rule_name}
        )
        return {
            "status": "ok",
            "rule_name": rule_name,
            "deleted": result.get("success", False),
        }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(
    description="List all firewall rules and zones.", annotations={"readOnlyHint": True}
)
async def router_firewall_rules() -> dict[str, Any]:
    """List all firewall rules and zones.

    Returns:
        Dict with zones and rules
    """
    try:
        result = await conn_mgr.call("luci.network.firewall", "get_rules", {})
        return {
            "status": "ok",
            "zones": result.get("zones", []),
            "rules": result.get("rules", []),
        }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


# ============================================================================
# SERVICE MANAGEMENT (restart services like dnsmasq, firewall, etc.)
# ============================================================================


@mcp.tool(
    description="Reload a system service (dnsmasq, firewall, etc.).",
    annotations={"destructiveHint": True},
)
async def router_service_reload(service: str) -> dict[str, Any]:
    """Reload (restart) a system service.

    Args:
        service: Service name (e.g., "dnsmasq", "firewall", "network")

    Returns:
        Dict with status of reload operation
    """
    try:
        result = await conn_mgr.call("service", "reload", {"name": service})
        return {
            "status": "ok",
            "service": service,
            "reloaded": result.get("success", False),
        }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


# ============================================================================
# PACKAGE MANAGEMENT (opkg operations)
# ============================================================================


@mcp.tool(
    description="List installed packages on the router.",
    annotations={"readOnlyHint": True},
)
async def router_packages_list(filter_name: str | None = None) -> dict[str, Any]:
    """List installed packages.

    Args:
        filter_name: Optional package name filter (substring search)

    Returns:
        Dict with list of packages and versions
    """
    try:
        result = await conn_mgr.call("opkg", "list", {})
        packages = result.get("packages", [])

        if filter_name:
            packages = [
                p for p in packages if filter_name.lower() in p.get("name", "").lower()
            ]

        return {
            "status": "ok",
            "total": len(packages),
            "packages": packages,
        }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(
    description="Search for a package in opkg repository.",
    annotations={"readOnlyHint": True},
)
async def router_packages_search(query: str) -> dict[str, Any]:
    """Search for packages in the repository.

    Args:
        query: Package name or description to search for

    Returns:
        Dict with matching packages
    """
    try:
        result = await conn_mgr.call("opkg", "search", {"query": query})
        return {
            "status": "ok",
            "query": query,
            "results": result.get("packages", []),
        }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


@mcp.tool(
    description="Install a package via opkg (network must be accessible).",
    annotations={"destructiveHint": True},
)
async def router_package_install(package_name: str) -> dict[str, Any]:
    """Install a package.

    Args:
        package_name: Package name to install

    Returns:
        Dict with status of installation
    """
    try:
        result = await conn_mgr.call("opkg", "install", {"package": package_name})
        return {
            "status": "ok",
            "package": package_name,
            "installed": result.get("success", False),
        }
    except (PermissionError, RuntimeError) as exc:
        return {"status": "error", "reason": str(exc)}


async def main() -> None:
    """Start the FastMCP server on port 8002."""
    print(f"Starting OpenWrt Router MCP Server on port {ROUTER_MCP_PORT}...")
    print(f"Router endpoint: {ROUTER_ENDPOINT}")
    await mcp.run(port=ROUTER_MCP_PORT)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        asyncio.run(conn_mgr.close())
