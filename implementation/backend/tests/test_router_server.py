"""Tests for the OpenWrt router MCP server.

Covers ConnectionManager auth/retry semantics, input validators, and the
two-phase + confirmed-commit UCI flow.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from forge import router_server as rs
from forge.router_server import (
    ANONYMOUS_SESSION,
    ConnectionManager,
    ERR_CONFIG_INCOMPATIBLE,
    ERR_CONFIRMED_COMMIT_TIMEOUT,
    ERR_INVALID_PARAM,
    ERR_PERMISSION_DENIED,
    UBUS_STATUS_OK,
    UBUS_STATUS_PERMISSION_DENIED,
    UbusError,
    UbusPermissionError,
    ValidationError,
    _require,
    _require_host,
    _require_int_range,
    _UCI_NAME_RE,
)


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class StubConn:
    """Drop-in replacement for ConnectionManager used by tool tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.responses: dict[tuple[str, str], Any] = {}
        self.raise_for: dict[tuple[str, str], Exception] = {}

    async def call(
        self, namespace: str, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.calls.append((namespace, method, params))
        key = (namespace, method)
        if key in self.raise_for:
            raise self.raise_for[key]
        return self.responses.get(key, {})

    async def close(self) -> None:
        return None


@pytest.fixture
def stub_conn(monkeypatch: pytest.MonkeyPatch) -> StubConn:
    stub = StubConn()
    monkeypatch.setattr(rs, "_conn_mgr", stub)
    return stub


@pytest.fixture(autouse=True)
def _clear_pending_commits() -> None:
    rs._pending_commits.clear()


# ---------------------------------------------------------------------------
# Mock HTTP transport for ConnectionManager
# ---------------------------------------------------------------------------


def _mock_client(handler):
    """Build an httpx.AsyncClient backed by a callable that takes a request and returns (status_code, json_body)."""

    def transport_handler(request: httpx.Request) -> httpx.Response:
        status, body = handler(request)
        return httpx.Response(status, json=body)

    transport = httpx.MockTransport(transport_handler)
    return httpx.AsyncClient(transport=transport)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


class TestValidators:
    def test_uci_name_accepts_letters_digits_underscore(self) -> None:
        for ok in ["network", "wlan0", "zone_wan", "rule_42"]:
            assert _require(_UCI_NAME_RE, ok, "config") == ok

    @pytest.mark.parametrize(
        "bad",
        ["", "../etc", "name with space", "a" * 33, "rm; rf", "name\nlinefeed", 'a"b'],
    )
    def test_uci_name_rejects_shell_metacharacters(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            _require(_UCI_NAME_RE, bad, "config")

    def test_require_int_range_accepts_within(self) -> None:
        assert _require_int_range(5, 1, 10, "n") == 5

    def test_require_int_range_rejects_bool(self) -> None:
        # bool is a subclass of int — guarded against to avoid True/False sneaking through.
        with pytest.raises(ValidationError):
            _require_int_range(True, 0, 10, "n")  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad", [0, 11, -1, 9999])
    def test_require_int_range_rejects_outside(self, bad: int) -> None:
        with pytest.raises(ValidationError):
            _require_int_range(bad, 1, 10, "n")

    @pytest.mark.parametrize("ok", ["1.1.1.1", "::1", "example.com", "router.local"])
    def test_require_host_accepts(self, ok: str) -> None:
        assert _require_host(ok) == ok

    @pytest.mark.parametrize(
        "bad", ["", "a; rm -rf /", "8.8.8.8 && id", "-leadingdash", "trailingdash-", "x" * 254]
    )
    def test_require_host_rejects(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            _require_host(bad)


# ---------------------------------------------------------------------------
# ConnectionManager
# ---------------------------------------------------------------------------


class TestConnectionManager:
    def _login_response(self, token: str = "a" * 32, timeout: int = 600) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "result": [UBUS_STATUS_OK, {"ubus_rpc_session": token, "timeout": timeout, "acls": {}}],
        }

    @pytest.mark.asyncio
    async def test_login_success_caches_token(self) -> None:
        def handler(request: httpx.Request):
            body = request.read()
            assert b"session" in body
            assert b"login" in body
            return 200, self._login_response()

        cm = ConnectionManager(password="pw", client=_mock_client(handler))
        token = await cm._login()
        assert token == "a" * 32
        assert cm._session_token == "a" * 32
        assert cm._token_expiry is not None
        await cm.close()

    @pytest.mark.asyncio
    async def test_login_without_password_raises(self) -> None:
        cm = ConnectionManager(password=None, client=_mock_client(lambda r: (200, {"result": [0, {}]})))
        with pytest.raises(UbusError):
            await cm._login()
        await cm.close()

    @pytest.mark.asyncio
    async def test_login_rejects_bad_status(self) -> None:
        cm = ConnectionManager(
            password="pw",
            client=_mock_client(lambda r: (200, {"result": [UBUS_STATUS_PERMISSION_DENIED, {}]})),
        )
        with pytest.raises(UbusError):
            await cm._login()
        await cm.close()

    @pytest.mark.asyncio
    async def test_call_reuses_cached_token(self) -> None:
        login_count = 0
        call_count = 0

        def handler(request: httpx.Request):
            nonlocal login_count, call_count
            body = request.read()
            if b'"login"' in body:
                login_count += 1
                return 200, self._login_response()
            call_count += 1
            return 200, {"result": [UBUS_STATUS_OK, {"value": "x"}]}

        cm = ConnectionManager(password="pw", client=_mock_client(handler))
        await cm.call("system", "info")
        await cm.call("system", "info")
        assert login_count == 1
        assert call_count == 2
        await cm.close()

    @pytest.mark.asyncio
    async def test_call_retries_once_on_stale_session(self) -> None:
        login_count = 0
        attempt_count = 0

        def handler(request: httpx.Request):
            nonlocal login_count, attempt_count
            body = request.read()
            if b'"login"' in body:
                login_count += 1
                return 200, self._login_response(token=("b" * 32 if login_count > 1 else "a" * 32))
            attempt_count += 1
            # First call: simulate expired session → PERMISSION_DENIED.
            # Second call (post-relogin): succeed.
            status = UBUS_STATUS_PERMISSION_DENIED if attempt_count == 1 else UBUS_STATUS_OK
            return 200, {"result": [status, {"ok": attempt_count > 1}]}

        cm = ConnectionManager(password="pw", client=_mock_client(handler))
        result = await cm.call("system", "info")
        assert result == {"ok": True}
        assert login_count == 2  # initial + re-login after denial
        assert attempt_count == 2
        await cm.close()

    @pytest.mark.asyncio
    async def test_call_permission_denied_twice_raises(self) -> None:
        def handler(request: httpx.Request):
            body = request.read()
            if b'"login"' in body:
                return 200, self._login_response()
            return 200, {"result": [UBUS_STATUS_PERMISSION_DENIED, {}]}

        cm = ConnectionManager(password="pw", client=_mock_client(handler))
        with pytest.raises(UbusPermissionError):
            await cm.call("system", "info")
        await cm.close()

    @pytest.mark.asyncio
    async def test_call_transport_error_raises_ubus_error(self) -> None:
        def handler(request: httpx.Request):
            return 503, {"error": "down"}

        cm = ConnectionManager(password="pw", client=_mock_client(handler))
        with pytest.raises(UbusError):
            await cm._login()
        await cm.close()

    @pytest.mark.asyncio
    async def test_call_malformed_response_raises(self) -> None:
        def handler(request: httpx.Request):
            body = request.read()
            if b'"login"' in body:
                return 200, self._login_response()
            return 200, {"not_result": "garbage"}

        cm = ConnectionManager(password="pw", client=_mock_client(handler))
        with pytest.raises(UbusError):
            await cm.call("system", "info")
        await cm.close()

    @pytest.mark.asyncio
    async def test_anonymous_session_used_for_login(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request):
            import json

            payload = json.loads(request.read())
            captured["params"] = payload["params"]
            return 200, self._login_response()

        cm = ConnectionManager(password="pw", client=_mock_client(handler))
        await cm._login()
        assert captured["params"][0] == ANONYMOUS_SESSION
        await cm.close()

    def test_invalid_scheme_rejected(self) -> None:
        with pytest.raises(ValueError):
            ConnectionManager(scheme="ftp", password="pw")


# ---------------------------------------------------------------------------
# Tool: router_uci_get / set with validation
# ---------------------------------------------------------------------------


class TestUciTools:
    @pytest.mark.asyncio
    async def test_uci_get_validates_config_name(self, stub_conn: StubConn) -> None:
        result = await rs.router_uci_get("../etc/passwd", "section")
        assert result["status"] == "error"
        assert result["code"] == ERR_INVALID_PARAM
        # validator runs before any network call
        assert stub_conn.calls == []

    @pytest.mark.asyncio
    async def test_uci_get_with_option_returns_value(self, stub_conn: StubConn) -> None:
        stub_conn.responses[("uci", "get")] = {"value": "192.168.1.1"}
        result = await rs.router_uci_get("network", "lan", "ipaddr")
        assert result == {
            "status": "ok",
            "config": "network",
            "section": "lan",
            "option": "ipaddr",
            "value": "192.168.1.1",
        }
        assert stub_conn.calls[0][:2] == ("uci", "get")
        assert stub_conn.calls[0][2] == {"config": "network", "section": "lan", "option": "ipaddr"}

    @pytest.mark.asyncio
    async def test_uci_set_stages_and_returns_next_step(self, stub_conn: StubConn) -> None:
        result = await rs.router_uci_set("network", "lan", "ipaddr", "10.0.0.1")
        assert result["status"] == "ok"
        assert result["staged"] is True
        assert result["next_step"] == "router_uci_commit"
        assert stub_conn.calls == [
            (
                "uci",
                "set",
                {
                    "config": "network",
                    "section": "lan",
                    "values": {"ipaddr": "10.0.0.1"},
                },
            )
        ]

    @pytest.mark.asyncio
    async def test_uci_set_propagates_permission_error(self, stub_conn: StubConn) -> None:
        stub_conn.raise_for[("uci", "set")] = UbusPermissionError("denied")
        result = await rs.router_uci_set("network", "lan", "ipaddr", "10.0.0.1")
        assert result["status"] == "error"
        assert result["code"] == ERR_PERMISSION_DENIED

    @pytest.mark.asyncio
    async def test_uci_set_oversized_value_rejected(self, stub_conn: StubConn) -> None:
        result = await rs.router_uci_set("network", "lan", "ipaddr", "x" * 2000)
        assert result["status"] == "error"
        assert result["code"] == ERR_INVALID_PARAM
        assert stub_conn.calls == []

    @pytest.mark.asyncio
    async def test_uci_set_invalid_section(self, stub_conn: StubConn) -> None:
        result = await rs.router_uci_set("network", "../oops", "ipaddr", "v")
        assert result["status"] == "error"
        assert result["code"] == ERR_INVALID_PARAM


# ---------------------------------------------------------------------------
# Confirmed-commit flow
# ---------------------------------------------------------------------------


class TestConfirmedCommit:
    @pytest.mark.asyncio
    async def test_commit_without_timeout_is_immediately_confirmed(
        self, stub_conn: StubConn
    ) -> None:
        stub_conn.responses[("uci", "changes")] = {"changes": [["set", "lan", "ipaddr", "10.0.0.1"]]}
        result = await rs.router_uci_commit("network")
        assert result["status"] == "ok"
        assert result["committed"] is True
        assert result["confirmed"] is True
        assert "commit_id" not in result
        # changes + commit, in that order
        assert [(ns, m) for ns, m, _ in stub_conn.calls] == [("uci", "changes"), ("uci", "commit")]

    @pytest.mark.asyncio
    async def test_commit_with_timeout_schedules_auto_revert(self, stub_conn: StubConn) -> None:
        stub_conn.responses[("uci", "changes")] = {"changes": []}
        result = await rs.router_uci_commit("network", confirm_timeout_seconds=10)
        assert result["confirmed"] is False
        commit_id = result["commit_id"]
        assert commit_id in rs._pending_commits
        # Cleanup so the scheduled revert doesn't fire after the test.
        rs._pending_commits[commit_id].task.cancel()
        try:
            await rs._pending_commits[commit_id].task
        except asyncio.CancelledError:
            pass
        rs._pending_commits.pop(commit_id, None)

    @pytest.mark.asyncio
    async def test_confirm_cancels_auto_revert(self, stub_conn: StubConn) -> None:
        stub_conn.responses[("uci", "changes")] = {"changes": []}
        commit = await rs.router_uci_commit("network", confirm_timeout_seconds=60)
        commit_id = commit["commit_id"]
        confirm = await rs.router_uci_confirm(commit_id)
        assert confirm == {
            "status": "ok",
            "commit_id": commit_id,
            "config": "network",
            "confirmed": True,
        }
        assert commit_id not in rs._pending_commits
        # No revert should ever have been issued.
        assert ("uci", "revert", {"config": "network"}) not in stub_conn.calls

    @pytest.mark.asyncio
    async def test_confirm_unknown_id_returns_timeout_error(self, stub_conn: StubConn) -> None:
        result = await rs.router_uci_confirm("commit-9999")
        assert result["status"] == "error"
        assert result["code"] == ERR_CONFIRMED_COMMIT_TIMEOUT

    @pytest.mark.asyncio
    async def test_confirm_bad_id_format_rejected(self, stub_conn: StubConn) -> None:
        result = await rs.router_uci_confirm("not-a-commit-id")
        assert result["status"] == "error"
        assert result["code"] == ERR_INVALID_PARAM

    @pytest.mark.asyncio
    async def test_auto_revert_fires_after_timeout(self, stub_conn: StubConn) -> None:
        stub_conn.responses[("uci", "changes")] = {"changes": []}
        commit = await rs.router_uci_commit("network", confirm_timeout_seconds=1)
        commit_id = commit["commit_id"]
        # Drive the event loop forward until the scheduled task completes.
        await rs._pending_commits[commit_id].task
        # After the timeout the pending entry is cleared and revert+commit were called.
        assert commit_id not in rs._pending_commits
        invoked = [(ns, m) for ns, m, _ in stub_conn.calls]
        assert ("uci", "revert") in invoked
        # The second commit (post-revert) is what makes the rollback durable.
        assert invoked.count(("uci", "commit")) >= 2


# ---------------------------------------------------------------------------
# Tool: error mapping
# ---------------------------------------------------------------------------


class TestErrorMapping:
    @pytest.mark.asyncio
    async def test_ubus_error_maps_to_config_incompatible(self, stub_conn: StubConn) -> None:
        stub_conn.raise_for[("system", "info")] = UbusError(9, "unknown")
        result = await rs.router_system_info()
        assert result["status"] == "error"
        assert result["code"] == ERR_CONFIG_INCOMPATIBLE
        assert result["ubus_status"] == 9

    @pytest.mark.asyncio
    async def test_invalid_argument_maps_to_invalid_param(self, stub_conn: StubConn) -> None:
        stub_conn.raise_for[("system", "info")] = UbusError(2, "bad arg")
        result = await rs.router_system_info()
        assert result["code"] == ERR_INVALID_PARAM


# ---------------------------------------------------------------------------
# Read tools: ping, wifi_scan, system_info, network_list
# ---------------------------------------------------------------------------


class TestReadTools:
    @pytest.mark.asyncio
    async def test_ping_parses_stdout(self, stub_conn: StubConn) -> None:
        stub_conn.responses[("file", "exec")] = {
            "code": 0,
            "stdout": (
                "PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.\n"
                "64 bytes from 1.1.1.1: icmp_seq=1 ttl=58 time=12.3 ms\n"
                "\n--- 1.1.1.1 ping statistics ---\n"
                "4 packets transmitted, 4 received, 0% packet loss, time 3005ms\n"
                "rtt min/avg/max/mdev = 12.300/14.500/17.100/1.234 ms\n"
            ),
        }
        result = await rs.router_ping_test("1.1.1.1", count=4)
        assert result["status"] == "ok"
        assert result["packet_loss_percent"] == 0
        assert result["min_ms"] == 12.300
        assert result["avg_ms"] == 14.500
        assert result["max_ms"] == 17.100

    @pytest.mark.asyncio
    async def test_ping_rejects_shell_metacharacters(self, stub_conn: StubConn) -> None:
        result = await rs.router_ping_test("1.1.1.1; rm -rf /", count=1)
        assert result["status"] == "error"
        assert result["code"] == ERR_INVALID_PARAM
        assert stub_conn.calls == []

    @pytest.mark.asyncio
    async def test_ping_rejects_oversized_count(self, stub_conn: StubConn) -> None:
        result = await rs.router_ping_test("1.1.1.1", count=10_000)
        assert result["status"] == "error"
        assert result["code"] == ERR_INVALID_PARAM

    @pytest.mark.asyncio
    async def test_wifi_scan_sorts_and_limits(self, stub_conn: StubConn) -> None:
        stub_conn.responses[("iwinfo", "scan")] = {
            "results": [
                {"ssid": "weak", "signal": -90, "channel": 1, "encryption": {"description": "WPA2"}},
                {"ssid": "strong", "signal": -40, "channel": 6, "encryption": {"description": "WPA2"}},
                {"ssid": "mid", "signal": -65, "channel": 11, "encryption": {"description": "WPA2"}},
            ]
        }
        result = await rs.router_wifi_scan("radio0", limit=2)
        assert result["status"] == "ok"
        assert result["returned"] == 2
        assert [n["ssid"] for n in result["networks"]] == ["strong", "mid"]
        assert result["total_visible"] == 3

    @pytest.mark.asyncio
    async def test_wifi_scan_rejects_bad_radio(self, stub_conn: StubConn) -> None:
        result = await rs.router_wifi_scan("eth0", limit=10)
        assert result["status"] == "error"
        assert result["code"] == ERR_INVALID_PARAM

    @pytest.mark.asyncio
    async def test_system_info_assembles_fields(self, stub_conn: StubConn) -> None:
        stub_conn.responses[("system", "info")] = {
            "uptime": 12345,
            "nprocs": 4,
            "memtotal": 524288,
            "memfree": 131072,
            "load": [0.1, 0.2, 0.3],
        }
        stub_conn.responses[("system", "board")] = {
            "board_name": "openwrt-one",
            "model": "OpenWrt One",
            "release": {"version": "23.05.0"},
            "kernel": "5.15.0",
        }
        result = await rs.router_system_info()
        assert result["status"] == "ok"
        assert result["board_name"] == "openwrt-one"
        assert result["firmware_version"] == "23.05.0"
        assert result["load_1min"] == 0.1
        assert result["load_15min"] == 0.3

    @pytest.mark.asyncio
    async def test_network_list_flattens_dump(self, stub_conn: StubConn) -> None:
        stub_conn.responses[("network.interface", "dump")] = {
            "interface": [
                {
                    "interface": "lan",
                    "up": True,
                    "proto": "static",
                    "ipv4-address": [{"address": "192.168.1.1", "mask": 24}],
                    "l3_device": "br-lan",
                    "uptime": 100,
                },
                {
                    "interface": "wan",
                    "up": False,
                    "proto": "dhcp",
                    "l3_device": "eth0",
                },
            ]
        }
        result = await rs.router_network_list()
        assert result["status"] == "ok"
        names = [iface["name"] for iface in result["interfaces"]]
        assert names == ["lan", "wan"]
        assert result["interfaces"][0]["ipv4_address"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_system_logs_bounds_lines(self, stub_conn: StubConn) -> None:
        result = await rs.router_system_logs(lines=10_000)
        assert result["status"] == "error"
        assert result["code"] == ERR_INVALID_PARAM


# ---------------------------------------------------------------------------
# Firewall tool: validators
# ---------------------------------------------------------------------------


class TestFirewallTools:
    @pytest.mark.asyncio
    async def test_firewall_rule_add_rejects_bad_target(self, stub_conn: StubConn) -> None:
        result = await rs.router_firewall_rule_add(
            name="allow_ssh",
            src_zone="lan",
            dest_zone="wan",
            target="LOGGING",
        )
        assert result["status"] == "error"
        assert result["code"] == ERR_INVALID_PARAM

    @pytest.mark.asyncio
    async def test_firewall_rule_add_happy_path(self, stub_conn: StubConn) -> None:
        stub_conn.responses[("uci", "add")] = {"section": "cfg01234"}
        result = await rs.router_firewall_rule_add(
            name="allow_ssh",
            src_zone="lan",
            dest_zone="wan",
            target="ACCEPT",
            proto="tcp",
            dest_port="22",
        )
        assert result["status"] == "ok"
        assert result["staged"] is True
        # add then set
        assert [(ns, m) for ns, m, _ in stub_conn.calls] == [("uci", "add"), ("uci", "set")]

    @pytest.mark.asyncio
    async def test_firewall_rule_add_rejects_bad_port(self, stub_conn: StubConn) -> None:
        result = await rs.router_firewall_rule_add(
            name="r",
            src_zone="lan",
            dest_zone="wan",
            target="ACCEPT",
            proto="tcp",
            dest_port="22; DROP",
        )
        assert result["status"] == "error"
        assert result["code"] == ERR_INVALID_PARAM


# ---------------------------------------------------------------------------
# Interface restart
# ---------------------------------------------------------------------------


class TestInterfaceRestart:
    @pytest.mark.asyncio
    async def test_restart_calls_down_then_up(self, stub_conn: StubConn) -> None:
        result = await rs.router_interface_restart("wan")
        assert result == {"status": "ok", "interface": "wan", "restarted": True}
        assert [(ns, m) for ns, m, _ in stub_conn.calls] == [
            ("network.interface", "down"),
            ("network.interface", "up"),
        ]

    @pytest.mark.asyncio
    async def test_restart_rejects_bad_name(self, stub_conn: StubConn) -> None:
        result = await rs.router_interface_restart("eth0; reboot")
        assert result["status"] == "error"
        assert result["code"] == ERR_INVALID_PARAM
