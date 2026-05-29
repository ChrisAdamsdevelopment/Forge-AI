"""FastMCP server for OpenWrt router automation via rpcd JSON-RPC API.

Connects to an OpenWrt router (default 192.168.1.1) over the ubus HTTP
JSON-RPC interface. Provides tools for system inspection, network status,
WiFi diagnostics, firewall management, and UCI configuration with
NETCONF-style confirmed-commit semantics so an autonomous agent that
breaks connectivity auto-recovers.

Configuration via environment:
    FORGE_ROUTER_HOST       - router IP/hostname (default: 192.168.1.1)
    FORGE_ROUTER_PORT       - router HTTP port (default: 80)
    FORGE_ROUTER_SCHEME     - "http" or "https" (default: http)
    FORGE_ROUTER_USERNAME   - rpcd username (default: mcp_ai_agent)
    FORGE_ROUTER_PASSWORD   - rpcd password (required to authenticate)
    FORGE_ROUTER_VERIFY_TLS - "true"/"false" (default: true for https)
    FORGE_ROUTER_MCP_PORT   - port the FastMCP server binds (default: 8002)

The companion ACL (acl_mcp_ai_agent.json) must be deployed to
/usr/share/rpcd/acl.d/ on the router so rpcd enforces least-privilege
on the server side. Forge-side validators provide defence in depth.
"""

from __future__ import annotations

import asyncio
import ipaddress
import itertools
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from fastmcp import FastMCP

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer for %s=%r; using default %d", name, raw, default)
        return default


ROUTER_HOST = os.environ.get("FORGE_ROUTER_HOST", "192.168.1.1")
ROUTER_PORT = _env_int("FORGE_ROUTER_PORT", 80)
ROUTER_SCHEME = os.environ.get("FORGE_ROUTER_SCHEME", "http").lower()
ROUTER_USERNAME = os.environ.get("FORGE_ROUTER_USERNAME", "mcp_ai_agent")
ROUTER_PASSWORD = os.environ.get("FORGE_ROUTER_PASSWORD")
ROUTER_VERIFY_TLS = _env_bool("FORGE_ROUTER_VERIFY_TLS", True)
ROUTER_MCP_PORT = _env_int("FORGE_ROUTER_MCP_PORT", 8002)
REQUEST_TIMEOUT = float(os.environ.get("FORGE_ROUTER_TIMEOUT", "30"))

# ubus status codes — these come from the OpenWrt project.
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

# IETF AINETOPS error codes (draft-zw-opsawg-mcp-network-mgmt).
ERR_CONFIG_INCOMPATIBLE = -32084
ERR_CONFIRMED_COMMIT_TIMEOUT = -32086
ERR_PERMISSION_DENIED = -32088
ERR_TRANSPORT = -32090
ERR_INVALID_PARAM = -32602  # JSON-RPC standard "invalid params"

ANONYMOUS_SESSION = "00000000000000000000000000000000"

# Defensive validators. The router-side ACL is the real authority, but the
# OpenWrt rpcd parsers have a history of CVEs, so we don't forward
# arbitrary LLM-generated strings to the wire.
_UCI_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")
_INTERFACE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,16}$")
_SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_PACKAGE_NAME_RE = re.compile(r"^[A-Za-z0-9_.+-]{1,64}$")
_RULE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_RADIO_NAME_RE = re.compile(r"^radio[0-9]{1,2}$")
_PORT_LIST_RE = re.compile(r"^\d{1,5}(?:[,-]\d{1,5})*$")
_FIREWALL_TARGETS = frozenset({"ACCEPT", "DROP", "REJECT"})
_FIREWALL_PROTOS = frozenset({"tcp", "udp", "icmp", "all"})


class ValidationError(ValueError):
    """Raised by tool validators when an argument fails an allowlist check."""


def _require(pattern: re.Pattern[str], value: str, field_name: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValidationError(f"Invalid {field_name}: {value!r}")
    return value


def _require_in(allowed: frozenset[str], value: str, field_name: str) -> str:
    if value not in allowed:
        raise ValidationError(f"Invalid {field_name}: {value!r} (allowed: {sorted(allowed)})")
    return value


def _require_int_range(value: int, low: int, high: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < low or value > high:
        raise ValidationError(f"{field_name} must be int in [{low},{high}], got {value!r}")
    return value


def _require_host(value: str, field_name: str = "target") -> str:
    if not isinstance(value, str) or not value or len(value) > 253:
        raise ValidationError(f"Invalid {field_name}: empty or too long")
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        pass
    # Hostname: RFC 1123 label, no shell metacharacters.
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*", value):
        raise ValidationError(f"Invalid {field_name}: {value!r}")
    return value


def _error_response(code: int, reason: str, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"status": "error", "code": code, "reason": reason}
    out.update(extra)
    return out


def _map_ubus_status(status: int) -> int:
    if status == UBUS_STATUS_PERMISSION_DENIED:
        return ERR_PERMISSION_DENIED
    if status in (UBUS_STATUS_INVALID_ARGUMENT, UBUS_STATUS_INVALID_COMMAND):
        return ERR_INVALID_PARAM
    return ERR_CONFIG_INCOMPATIBLE


# ---------------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------------


class UbusError(RuntimeError):
    """Generic UBUS-side failure (non-permission)."""

    def __init__(self, status: int, message: str | None = None) -> None:
        self.status = status
        super().__init__(message or STATUS_MESSAGES.get(status, f"ubus status {status}"))


class UbusPermissionError(PermissionError):
    """rpcd rejected the call with PERMISSION_DENIED."""


class ConnectionManager:
    """Authenticated ubus JSON-RPC client.

    - Caches the session token until ~5 minutes before the router-reported
      expiry, then transparently re-logs in.
    - One global lock guards the login flow; concurrent ``call()`` requests
      are otherwise unserialised and reuse the cached token.
    - On PERMISSION_DENIED the call is retried exactly once after a forced
      re-login so we don't spuriously fail when a session times out under us.
    """

    def __init__(
        self,
        host: str = ROUTER_HOST,
        port: int = ROUTER_PORT,
        scheme: str = ROUTER_SCHEME,
        username: str = ROUTER_USERNAME,
        password: str | None = ROUTER_PASSWORD,
        timeout: float = REQUEST_TIMEOUT,
        verify_tls: bool = ROUTER_VERIFY_TLS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if scheme not in ("http", "https"):
            raise ValueError(f"scheme must be http or https, got {scheme!r}")
        self.host = host
        self.port = port
        self.scheme = scheme
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.endpoint = f"{scheme}://{host}:{port}/ubus"

        self._session_token: str | None = None
        self._token_expiry: datetime | None = None
        self._client = client
        self._lock = asyncio.Lock()
        self._id_counter = itertools.count(1)

    def _next_id(self) -> int:
        return next(self._id_counter)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            verify = self.verify_tls if self.scheme == "https" else True
            self._client = httpx.AsyncClient(timeout=self.timeout, verify=verify)
        return self._client

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = await self._get_client()
        try:
            response = await client.post(self.endpoint, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise UbusError(UBUS_STATUS_CONNECTION_FAILED, f"transport: {exc}") from exc

    async def _login(self) -> str:
        if not self.password:
            raise UbusError(
                UBUS_STATUS_PERMISSION_DENIED,
                "FORGE_ROUTER_PASSWORD not set; cannot authenticate",
            )

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "call",
            "params": [
                ANONYMOUS_SESSION,
                "session",
                "login",
                {"username": self.username, "password": self.password},
            ],
        }
        data = await self._post(payload)

        result = data.get("result")
        if not isinstance(result, list) or not result:
            raise UbusError(UBUS_STATUS_UNKNOWN_ERROR, f"malformed login response: {data!r}")

        status = result[0]
        if status != UBUS_STATUS_OK:
            raise UbusError(status, f"login failed: {STATUS_MESSAGES.get(status, status)}")

        body = result[1] if len(result) > 1 else {}
        if not isinstance(body, dict):
            raise UbusError(UBUS_STATUS_UNKNOWN_ERROR, "login result missing session body")

        token = body.get("ubus_rpc_session")
        if not isinstance(token, str) or len(token) != 32:
            raise UbusError(UBUS_STATUS_UNKNOWN_ERROR, "login result missing ubus_rpc_session")

        timeout_s = body.get("timeout")
        if not isinstance(timeout_s, int) or timeout_s <= 0:
            timeout_s = 300  # rpcd's documented default
        self._session_token = token
        self._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=timeout_s)
        logger.info("ubus session established (expires in %ds)", timeout_s)
        return token

    async def _ensure_authenticated(self, force: bool = False) -> str:
        async with self._lock:
            if not force and self._session_token and self._token_expiry:
                # Refresh five minutes before the router will drop us.
                if datetime.now(timezone.utc) < self._token_expiry - timedelta(minutes=5):
                    return self._session_token
            return await self._login()

    async def call(
        self,
        namespace: str,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invoke a ubus method, transparently retrying once on stale session."""

        attempts_left = 2
        force_login = False
        while attempts_left > 0:
            attempts_left -= 1
            token = await self._ensure_authenticated(force=force_login)

            payload = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "call",
                "params": [token, namespace, method, params or {}],
            }
            data = await self._post(payload)

            result = data.get("result")
            if not isinstance(result, list) or not result:
                raise UbusError(
                    UBUS_STATUS_UNKNOWN_ERROR, f"malformed response for {namespace}.{method}"
                )

            status = result[0]
            if status == UBUS_STATUS_OK:
                body = result[1] if len(result) > 1 else {}
                return body if isinstance(body, dict) else {"value": body}

            if status == UBUS_STATUS_PERMISSION_DENIED and attempts_left > 0:
                # Could be expired session — drop the token and retry once.
                logger.info("ubus permission denied for %s.%s; re-authenticating", namespace, method)
                self._session_token = None
                self._token_expiry = None
                force_login = True
                continue

            if status == UBUS_STATUS_PERMISSION_DENIED:
                raise UbusPermissionError(f"{namespace}.{method}: permission denied")

            raise UbusError(status, f"{namespace}.{method}: {STATUS_MESSAGES.get(status, status)}")

        # Unreachable: loop either returns or raises.
        raise UbusError(UBUS_STATUS_UNKNOWN_ERROR, "exhausted retries")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# ---------------------------------------------------------------------------
# Confirmed-commit registry
# ---------------------------------------------------------------------------


@dataclass
class _PendingCommit:
    commit_id: str
    config: str
    revert_at: datetime
    task: asyncio.Task[Any] = field(repr=False)


_pending_commits: dict[str, _PendingCommit] = {}
_pending_commits_lock = asyncio.Lock()
_commit_id_counter = itertools.count(1)


async def _schedule_auto_revert(
    conn: ConnectionManager, commit_id: str, config: str, timeout_seconds: int
) -> None:
    try:
        await asyncio.sleep(timeout_seconds)
    except asyncio.CancelledError:
        return
    async with _pending_commits_lock:
        pending = _pending_commits.pop(commit_id, None)
    if pending is None:
        return
    logger.warning(
        "Confirmed-commit timeout reached for %s (config=%s); reverting",
        commit_id,
        config,
    )
    try:
        await conn.call("uci", "revert", {"config": config})
        await conn.call("uci", "commit", {"config": config})
    except (UbusError, UbusPermissionError) as exc:
        logger.exception("auto-revert for %s failed: %s", commit_id, exc)


# ---------------------------------------------------------------------------
# FastMCP server + tools
# ---------------------------------------------------------------------------


mcp = FastMCP("OpenWrt Router Agent")
_conn_mgr = ConnectionManager()


def _conn() -> ConnectionManager:
    """Indirection so tests can swap in a stub."""
    return _conn_mgr


def _handle(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ValidationError):
        return _error_response(ERR_INVALID_PARAM, str(exc))
    if isinstance(exc, UbusPermissionError):
        return _error_response(ERR_PERMISSION_DENIED, str(exc))
    if isinstance(exc, UbusError):
        return _error_response(_map_ubus_status(exc.status), str(exc), ubus_status=exc.status)
    return _error_response(ERR_TRANSPORT, f"{type(exc).__name__}: {exc}")


# ============================================================================
# READ-ONLY TOOLS
# ============================================================================


@mcp.tool(description="Get router system information: board name, firmware, uptime, CPU load.")
async def router_system_info() -> dict[str, Any]:
    try:
        info = await _conn().call("system", "info")
        board = await _conn().call("system", "board")
        load = info.get("load") or []
        return {
            "status": "ok",
            "board_name": board.get("board_name"),
            "model": board.get("model"),
            "firmware_version": (board.get("release") or {}).get("version"),
            "kernel_version": board.get("kernel"),
            "uptime_seconds": info.get("uptime"),
            "cpu_count": info.get("nprocs"),
            "memory_total_kb": info.get("memtotal"),
            "memory_free_kb": info.get("memfree"),
            "load_1min": load[0] if len(load) > 0 else None,
            "load_5min": load[1] if len(load) > 1 else None,
            "load_15min": load[2] if len(load) > 2 else None,
        }
    except Exception as exc:  # noqa: BLE001 — handled below
        return _handle(exc)


@mcp.tool(description="List all network interfaces with up/down status and IP addresses.")
async def router_network_list() -> dict[str, Any]:
    try:
        dump = await _conn().call("network.interface", "dump")
        interfaces = dump.get("interface", []) if isinstance(dump, dict) else []
        result = []
        for entry in interfaces:
            if not isinstance(entry, dict):
                continue
            v4 = (entry.get("ipv4-address") or [{}])[0]
            v6 = (entry.get("ipv6-address") or [{}])[0]
            result.append(
                {
                    "name": entry.get("interface"),
                    "up": bool(entry.get("up")),
                    "proto": entry.get("proto"),
                    "ipv4_address": v4.get("address"),
                    "ipv4_mask": v4.get("mask"),
                    "ipv6_address": v6.get("address"),
                    "ipv6_mask": v6.get("mask"),
                    "device": entry.get("l3_device"),
                    "uptime": entry.get("uptime"),
                }
            )
        return {"status": "ok", "interfaces": result}
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="Get detailed status for one network interface.")
async def router_interface_status(interface_name: str) -> dict[str, Any]:
    try:
        _require(_INTERFACE_NAME_RE, interface_name, "interface_name")
        status = await _conn().call(
            "network.interface", "status", {"interface": interface_name}
        )
        v4 = (status.get("ipv4-address") or [{}])[0]
        route0 = (status.get("route") or [{}])[0]
        stats = status.get("statistics") or {}
        return {
            "status": "ok",
            "interface": interface_name,
            "up": bool(status.get("up")),
            "proto": status.get("proto"),
            "ipv4_address": v4.get("address"),
            "ipv4_mask": v4.get("mask"),
            "gateway": route0.get("nexthop") or route0.get("target"),
            "device": status.get("l3_device"),
            "uptime": status.get("uptime"),
            "rx_bytes": stats.get("rx_bytes"),
            "tx_bytes": stats.get("tx_bytes"),
            "rx_packets": stats.get("rx_packets"),
            "tx_packets": stats.get("tx_packets"),
        }
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="Ping a host from the router (count bounded 1-20).")
async def router_ping_test(target: str, count: int = 4) -> dict[str, Any]:
    """ICMP ping via rpcd's file.exec.

    Requires the rpcd ACL to grant the agent ``file.exec`` for ``/bin/ping``.
    Output is parsed to extract loss and RTT stats; full stdout is returned
    truncated for context efficiency.
    """
    try:
        _require_host(target)
        _require_int_range(count, 1, 20, "count")
        result = await _conn().call(
            "file",
            "exec",
            {"command": "/bin/ping", "params": ["-c", str(count), "-w", "10", target]},
        )
        stdout = (result.get("stdout") or "")[:4096]
        loss_match = re.search(r"(\d+)% packet loss", stdout)
        rtt_match = re.search(
            r"min/avg/max(?:/mdev)? = ([\d.]+)/([\d.]+)/([\d.]+)", stdout
        )
        return {
            "status": "ok",
            "target": target,
            "packets_sent": count,
            "packet_loss_percent": int(loss_match.group(1)) if loss_match else None,
            "min_ms": float(rtt_match.group(1)) if rtt_match else None,
            "avg_ms": float(rtt_match.group(2)) if rtt_match else None,
            "max_ms": float(rtt_match.group(3)) if rtt_match else None,
            "exit_code": result.get("code"),
        }
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="Scan for available WiFi networks on a radio.")
async def router_wifi_scan(radio: str = "radio0", limit: int = 50) -> dict[str, Any]:
    try:
        _require(_RADIO_NAME_RE, radio, "radio")
        _require_int_range(limit, 1, 200, "limit")
        scan = await _conn().call("iwinfo", "scan", {"device": radio})
        results = scan.get("results") or []
        # Sort by signal strength (best first) and truncate for token budget.
        results.sort(key=lambda n: n.get("signal", -200), reverse=True)
        networks = [
            {
                "ssid": n.get("ssid"),
                "bssid": n.get("bssid"),
                "channel": n.get("channel"),
                "signal_dbm": n.get("signal"),
                "quality": n.get("quality"),
                "encryption": (n.get("encryption") or {}).get("description"),
                "mode": n.get("mode"),
            }
            for n in results[:limit]
        ]
        return {
            "status": "ok",
            "radio": radio,
            "total_visible": len(results),
            "returned": len(networks),
            "networks": networks,
        }
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="List currently associated WiFi clients across all radios.")
async def router_wifi_clients() -> dict[str, Any]:
    try:
        devices = await _conn().call("iwinfo", "devices")
        names = devices.get("devices") or []
        clients: list[dict[str, Any]] = []
        for dev in names:
            if not isinstance(dev, str) or not _INTERFACE_NAME_RE.fullmatch(dev):
                continue
            try:
                assoc = await _conn().call("iwinfo", "assoclist", {"device": dev})
            except (UbusError, UbusPermissionError):
                continue
            for entry in assoc.get("results") or []:
                clients.append(
                    {
                        "mac_address": entry.get("mac"),
                        "device": dev,
                        "signal_dbm": entry.get("signal"),
                        "noise_dbm": entry.get("noise"),
                        "inactive_ms": entry.get("inactive"),
                        "rx_bytes": (entry.get("rx") or {}).get("bytes"),
                        "tx_bytes": (entry.get("tx") or {}).get("bytes"),
                    }
                )
        return {"status": "ok", "total_clients": len(clients), "clients": clients}
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="Read recent system log entries (lines bounded 1-500).")
async def router_system_logs(lines: int = 50) -> dict[str, Any]:
    try:
        _require_int_range(lines, 1, 500, "lines")
        logs = await _conn().call("log", "read", {"lines": lines})
        entries = logs.get("log") or []
        if isinstance(entries, str):
            # Some OpenWrt builds return a single newline-joined blob.
            entries = entries.splitlines()
        return {"status": "ok", "log_entries": entries[-lines:]}
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


# ============================================================================
# UCI INSPECTION
# ============================================================================


@mcp.tool(description="Read a UCI configuration value (entire section or single option).")
async def router_uci_get(
    config: str, section: str, option: str | None = None
) -> dict[str, Any]:
    try:
        _require(_UCI_NAME_RE, config, "config")
        _require(_UCI_NAME_RE, section, "section")
        params: dict[str, Any] = {"config": config, "section": section}
        if option is not None:
            _require(_UCI_NAME_RE, option, "option")
            params["option"] = option
        data = await _conn().call("uci", "get", params)
        if option is not None:
            return {
                "status": "ok",
                "config": config,
                "section": section,
                "option": option,
                "value": data.get("value"),
            }
        return {"status": "ok", "config": config, "section": section, "data": data}
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="List section names in a UCI configuration file.")
async def router_uci_sections(config: str) -> dict[str, Any]:
    try:
        _require(_UCI_NAME_RE, config, "config")
        data = await _conn().call("uci", "get", {"config": config})
        sections = data.get("values") if isinstance(data.get("values"), dict) else data
        names = list(sections.keys()) if isinstance(sections, dict) else []
        return {"status": "ok", "config": config, "sections": names}
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


# ============================================================================
# UCI MUTATION (two-phase + confirmed commit)
# ============================================================================


@mcp.tool(
    description=(
        "Stage a UCI option change (does NOT apply). Call router_uci_commit to "
        "persist, or router_uci_revert to discard."
    )
)
async def router_uci_set(
    config: str, section: str, option: str, value: str
) -> dict[str, Any]:
    try:
        _require(_UCI_NAME_RE, config, "config")
        _require(_UCI_NAME_RE, section, "section")
        _require(_UCI_NAME_RE, option, "option")
        if not isinstance(value, str) or len(value) > 1024:
            raise ValidationError("value must be a string of <=1024 chars")
        await _conn().call(
            "uci",
            "set",
            {
                "config": config,
                "section": section,
                "values": {option: value},
            },
        )
        # uci.set returns an empty dict on success — absence of an exception
        # is the success signal.
        return {
            "status": "ok",
            "config": config,
            "section": section,
            "option": option,
            "value": value,
            "staged": True,
            "next_step": "router_uci_commit",
        }
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="List staged UCI changes for a configuration file.")
async def router_uci_changes(config: str) -> dict[str, Any]:
    try:
        _require(_UCI_NAME_RE, config, "config")
        data = await _conn().call("uci", "changes", {"config": config})
        return {"status": "ok", "config": config, "changes": data.get("changes", [])}
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(
    description=(
        "Commit staged UCI changes. If confirm_timeout_seconds > 0, an auto-revert "
        "is scheduled and you must call router_uci_confirm with the returned commit_id "
        "before the timeout to make the change permanent. This protects against an "
        "agent severing its own connectivity."
    )
)
async def router_uci_commit(
    config: str, confirm_timeout_seconds: int = 0
) -> dict[str, Any]:
    try:
        _require(_UCI_NAME_RE, config, "config")
        _require_int_range(confirm_timeout_seconds, 0, 600, "confirm_timeout_seconds")

        # Snapshot the changes before commit so we can echo them back.
        try:
            changes_data = await _conn().call("uci", "changes", {"config": config})
        except UbusError:
            changes_data = {}

        await _conn().call("uci", "commit", {"config": config})

        if confirm_timeout_seconds == 0:
            return {
                "status": "ok",
                "config": config,
                "committed": True,
                "confirmed": True,
                "changes": changes_data.get("changes", []),
            }

        commit_id = f"commit-{next(_commit_id_counter)}"
        revert_at = datetime.now(timezone.utc) + timedelta(seconds=confirm_timeout_seconds)
        task = asyncio.create_task(
            _schedule_auto_revert(_conn(), commit_id, config, confirm_timeout_seconds)
        )
        async with _pending_commits_lock:
            _pending_commits[commit_id] = _PendingCommit(
                commit_id=commit_id, config=config, revert_at=revert_at, task=task
            )
        return {
            "status": "ok",
            "config": config,
            "committed": True,
            "confirmed": False,
            "commit_id": commit_id,
            "confirm_by": revert_at.isoformat(),
            "changes": changes_data.get("changes", []),
            "next_step": "router_uci_confirm",
        }
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="Confirm a pending commit before its auto-revert timeout fires.")
async def router_uci_confirm(commit_id: str) -> dict[str, Any]:
    try:
        if not isinstance(commit_id, str) or not commit_id.startswith("commit-"):
            raise ValidationError("commit_id must be returned by router_uci_commit")
        async with _pending_commits_lock:
            pending = _pending_commits.pop(commit_id, None)
        if pending is None:
            return _error_response(
                ERR_CONFIRMED_COMMIT_TIMEOUT,
                f"commit_id {commit_id} not found (may have expired and reverted)",
            )
        pending.task.cancel()
        return {
            "status": "ok",
            "commit_id": commit_id,
            "config": pending.config,
            "confirmed": True,
        }
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="Discard staged UCI changes that have not yet been committed.")
async def router_uci_revert(config: str) -> dict[str, Any]:
    try:
        _require(_UCI_NAME_RE, config, "config")
        await _conn().call("uci", "revert", {"config": config})
        return {"status": "ok", "config": config, "reverted": True}
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


# ============================================================================
# NETWORK / FIREWALL / SERVICE OPERATIONS
# ============================================================================


@mcp.tool(description="Restart a network interface (brings it down then up).")
async def router_interface_restart(interface_name: str) -> dict[str, Any]:
    try:
        _require(_INTERFACE_NAME_RE, interface_name, "interface_name")
        await _conn().call("network.interface", "down", {"interface": interface_name})
        await _conn().call("network.interface", "up", {"interface": interface_name})
        return {"status": "ok", "interface": interface_name, "restarted": True}
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="Add a firewall rule via UCI (stages; commit firewall separately).")
async def router_firewall_rule_add(
    name: str,
    src_zone: str,
    dest_zone: str,
    target: str = "ACCEPT",
    proto: str | None = None,
    dest_port: str | None = None,
) -> dict[str, Any]:
    try:
        _require(_RULE_NAME_RE, name, "name")
        _require(_UCI_NAME_RE, src_zone, "src_zone")
        _require(_UCI_NAME_RE, dest_zone, "dest_zone")
        _require_in(_FIREWALL_TARGETS, target, "target")
        values: dict[str, Any] = {
            "name": name,
            "src": src_zone,
            "dest": dest_zone,
            "target": target,
        }
        if proto is not None:
            values["proto"] = _require_in(_FIREWALL_PROTOS, proto, "proto")
        if dest_port is not None:
            _require(_PORT_LIST_RE, dest_port, "dest_port")
            values["dest_port"] = dest_port

        # Use UCI add+set rather than the LuCI namespace (which is not part of
        # core rpcd and is gated by additional ACLs).
        added = await _conn().call("uci", "add", {"config": "firewall", "type": "rule", "name": name})
        section = added.get("section") or name
        await _conn().call(
            "uci",
            "set",
            {"config": "firewall", "section": section, "values": values},
        )
        return {
            "status": "ok",
            "rule_name": name,
            "section": section,
            "staged": True,
            "next_step": "router_uci_commit(config='firewall')",
        }
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="Delete a firewall rule section by name.")
async def router_firewall_rule_delete(rule_name: str) -> dict[str, Any]:
    try:
        _require(_RULE_NAME_RE, rule_name, "rule_name")
        await _conn().call(
            "uci", "delete", {"config": "firewall", "section": rule_name}
        )
        return {
            "status": "ok",
            "rule_name": rule_name,
            "staged": True,
            "next_step": "router_uci_commit(config='firewall')",
        }
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="List firewall zones and rules from the active configuration.")
async def router_firewall_rules() -> dict[str, Any]:
    try:
        data = await _conn().call("uci", "get", {"config": "firewall"})
        sections = data.get("values") if isinstance(data.get("values"), dict) else data
        zones = []
        rules = []
        if isinstance(sections, dict):
            for name, section in sections.items():
                if not isinstance(section, dict):
                    continue
                stype = section.get(".type")
                if stype == "zone":
                    zones.append({"name": name, **{k: v for k, v in section.items() if not k.startswith(".")}})
                elif stype == "rule":
                    rules.append({"name": name, **{k: v for k, v in section.items() if not k.startswith(".")}})
        return {"status": "ok", "zones": zones, "rules": rules}
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="Reload (signal) a system service.")
async def router_service_reload(service: str) -> dict[str, Any]:
    try:
        _require(_SERVICE_NAME_RE, service, "service")
        await _conn().call("service", "event", {"type": "reload", "data": {"name": service}})
        return {"status": "ok", "service": service, "reloaded": True}
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


# ============================================================================
# PACKAGE MANAGEMENT (read-mostly, install gated to ACL)
# ============================================================================


@mcp.tool(
    description="List installed packages with pagination (offset, limit bounded 1-500)."
)
async def router_packages_list(
    filter_name: str | None = None, offset: int = 0, limit: int = 100
) -> dict[str, Any]:
    try:
        _require_int_range(offset, 0, 10_000, "offset")
        _require_int_range(limit, 1, 500, "limit")
        if filter_name is not None:
            _require(_PACKAGE_NAME_RE, filter_name, "filter_name")
        data = await _conn().call("opkg", "list_installed", {})
        packages = data.get("packages") or []
        if filter_name:
            packages = [
                p for p in packages if filter_name.lower() in (p.get("name") or "").lower()
            ]
        total = len(packages)
        window = packages[offset : offset + limit]
        return {
            "status": "ok",
            "total": total,
            "offset": offset,
            "returned": len(window),
            "packages": window,
        }
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="Search the opkg repository for matching package names.")
async def router_packages_search(query: str, limit: int = 50) -> dict[str, Any]:
    try:
        _require(_PACKAGE_NAME_RE, query, "query")
        _require_int_range(limit, 1, 200, "limit")
        data = await _conn().call("opkg", "find", {"pattern": query})
        packages = (data.get("packages") or [])[:limit]
        return {"status": "ok", "query": query, "results": packages}
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@mcp.tool(description="Install a package via opkg (requires ACL write.ubus.opkg).")
async def router_package_install(package_name: str) -> dict[str, Any]:
    try:
        _require(_PACKAGE_NAME_RE, package_name, "package_name")
        await _conn().call("opkg", "install", {"package": package_name})
        return {"status": "ok", "package": package_name, "installed": True}
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


# ============================================================================
# Entrypoint
# ============================================================================


async def _serve() -> None:
    logger.info("Starting OpenWrt Router MCP server on port %d", ROUTER_MCP_PORT)
    logger.info("Router endpoint: %s://%s:%d/ubus", ROUTER_SCHEME, ROUTER_HOST, ROUTER_PORT)
    try:
        await mcp.run_async(transport="http", host="0.0.0.0", port=ROUTER_MCP_PORT)
    finally:
        await _conn_mgr.close()


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("FORGE_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        logger.info("Router MCP server stopped by user.")


if __name__ == "__main__":
    main()
