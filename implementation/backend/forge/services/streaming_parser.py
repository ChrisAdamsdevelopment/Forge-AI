from __future__ import annotations

import json
from enum import Enum
from typing import Any


class ParserState(str, Enum):
    TEXT_MODE = "TEXT_MODE"
    TOOL_CALL_NAME = "TOOL_CALL_NAME"
    TOOL_CALL_ARGUMENTS = "TOOL_CALL_ARGUMENTS"
    DONE = "DONE"


class StreamingResponseParser:
    """Accumulate streaming text and tool-call deltas into complete events."""

    TEXT_MODE = ParserState.TEXT_MODE
    TOOL_CALL_NAME = ParserState.TOOL_CALL_NAME
    TOOL_CALL_ARGUMENTS = ParserState.TOOL_CALL_ARGUMENTS
    DONE = ParserState.DONE

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset parser state for a new response."""
        self._state: ParserState = self.TEXT_MODE
        self._current_tool_id: str | None = None
        self._current_tool_name: str | None = None
        self._arguments_buffer: str = ""
        self._events: list[dict] = []
        self._bracket_depth: int = 0
        self._in_string: bool = False
        self._escape_next: bool = False
        self._seen_open_brace: bool = False
        self._seen_close_brace: bool = False
        self._tool_states: dict[int, dict[str, Any]] = {}

    def feed(self, delta: dict) -> list[dict]:
        """Consume one normalized OpenAI-compatible delta chunk."""
        self._events = []

        content = delta.get("content")
        if content:
            self._state = self.TEXT_MODE
            self._events.append({"type": "text", "content": content})

        for tool_delta in delta.get("tool_calls") or []:
            index = int(tool_delta.get("index") or 0)
            state = self._tool_states.setdefault(index, self._new_tool_state())

            tool_id = tool_delta.get("id")
            if tool_id and not state["id"]:
                state["id"] = tool_id
                self._current_tool_id = tool_id

            function = tool_delta.get("function") or {}
            name = function.get("name")
            if name:
                state["name"] = (state["name"] or "") + name
                self._current_tool_name = state["name"]
                self._state = self.TOOL_CALL_NAME

            arguments = function.get("arguments")
            if arguments is not None:
                self._state = self.TOOL_CALL_ARGUMENTS
                for char in str(arguments):
                    self._feed_argument_char(state, char)
                    if self._tool_call_complete(state):
                        self._emit_tool_call(index, state)
                        state = self._tool_states.setdefault(
                            index, self._new_tool_state()
                        )
                        break

            self._sync_public_state(state)

        return list(self._events)

    def flush(self) -> list[dict]:
        """Emit any remaining complete tool calls or an error for malformed partial JSON."""
        self._events = []
        for index, state in list(self._tool_states.items()):
            buffer = state["arguments_buffer"].strip()
            if not buffer:
                continue
            try:
                json.loads(buffer)
            except json.JSONDecodeError:
                self._events.append(
                    {"type": "error", "message": "Incomplete tool call arguments JSON"}
                )
                continue
            self._emit_tool_call(index, state)
        self._state = self.DONE
        return list(self._events)

    def _new_tool_state(self) -> dict[str, Any]:
        return {
            "id": None,
            "name": None,
            "arguments_buffer": "",
            "bracket_depth": 0,
            "in_string": False,
            "escape_next": False,
            "seen_open_brace": False,
            "seen_close_brace": False,
        }

    def _feed_argument_char(self, state: dict[str, Any], char: str) -> None:
        state["arguments_buffer"] += char

        if state["escape_next"]:
            state["escape_next"] = False
            return
        if char == "\\" and state["in_string"]:
            state["escape_next"] = True
            return
        if char == '"':
            state["in_string"] = not state["in_string"]
            return
        if state["in_string"]:
            return
        if char == "{":
            state["bracket_depth"] += 1
            state["seen_open_brace"] = True
        elif char == "}":
            state["bracket_depth"] = max(0, state["bracket_depth"] - 1)
            state["seen_close_brace"] = True

    def _tool_call_complete(self, state: dict[str, Any]) -> bool:
        if not (
            state["seen_open_brace"]
            and state["seen_close_brace"]
            and state["bracket_depth"] == 0
        ):
            return False
        try:
            json.loads(state["arguments_buffer"])
        except json.JSONDecodeError:
            return False
        return bool(state["name"])

    def _emit_tool_call(self, index: int, state: dict[str, Any]) -> None:
        self._events.append(
            {
                "type": "tool_call",
                "id": state["id"] or f"tool_call_{index}",
                "name": state["name"] or "",
                "arguments": state["arguments_buffer"],
            }
        )
        self._tool_states[index] = self._new_tool_state()
        self._arguments_buffer = ""
        self._bracket_depth = 0
        self._in_string = False
        self._escape_next = False
        self._seen_open_brace = False
        self._seen_close_brace = False

    def _sync_public_state(self, state: dict[str, Any]) -> None:
        self._current_tool_id = state["id"]
        self._current_tool_name = state["name"]
        self._arguments_buffer = state["arguments_buffer"]
        self._bracket_depth = state["bracket_depth"]
        self._in_string = state["in_string"]
        self._escape_next = state["escape_next"]
        self._seen_open_brace = state["seen_open_brace"]
        self._seen_close_brace = state["seen_close_brace"]


def _run_inline_tests() -> None:
    parser = StreamingResponseParser()
    assert parser.feed({"content": "hello"}) == [{"type": "text", "content": "hello"}]
    assert parser.flush() == []

    parser.reset()
    events = parser.feed(
        {
            "tool_calls": [
                {
                    "index": 0,
                    "id": "call_ollama",
                    "function": {
                        "name": "file_read",
                        "arguments": '{"path": "/tmp/a.txt"}',
                    },
                }
            ]
        }
    )
    assert events == [
        {
            "type": "tool_call",
            "id": "call_ollama",
            "name": "file_read",
            "arguments": '{"path": "/tmp/a.txt"}',
        }
    ]

    parser.reset()
    assert (
        parser.feed(
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call_vllm",
                        "function": {"name": "file_", "arguments": None},
                    }
                ]
            }
        )
        == []
    )
    assert (
        parser.feed(
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "function": {"name": "write", "arguments": '{"path": "'},
                    }
                ]
            }
        )
        == []
    )
    events = parser.feed(
        {
            "tool_calls": [
                {"index": 0, "function": {"arguments": '/tmp/a.txt", "content": "ok"}'}}
            ]
        }
    )
    assert events == [
        {
            "type": "tool_call",
            "id": "call_vllm",
            "name": "file_write",
            "arguments": '{"path": "/tmp/a.txt", "content": "ok"}',
        }
    ]

    parser.reset()
    assert parser.feed({"content": "Let me check. "}) == [
        {"type": "text", "content": "Let me check. "}
    ]
    events = parser.feed(
        {
            "tool_calls": [
                {
                    "index": 0,
                    "id": "call_mixed",
                    "function": {
                        "name": "web_fetch",
                        "arguments": '{"url": "https://example.com/a|b"}',
                    },
                }
            ]
        }
    )
    assert events == [
        {
            "type": "tool_call",
            "id": "call_mixed",
            "name": "web_fetch",
            "arguments": '{"url": "https://example.com/a|b"}',
        }
    ]

    print("StreamingResponseParser inline tests passed.")


if __name__ == "__main__":
    _run_inline_tests()
