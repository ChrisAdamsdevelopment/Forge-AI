from __future__ import annotations

import inspect
import json
from typing import Any

from forge.agent.tools.apps import app_focus, app_list_windows, app_open
from forge.agent.tools.browser import browser_click, browser_get_content, browser_navigate, browser_screenshot, browser_type
from forge.agent.tools.filesystem import file_delete, file_list, file_mkdir, file_read, file_search, file_write
from forge.agent.tools.memory import memory_retrieve, memory_store
from forge.agent.tools.screen import keyboard_press, keyboard_type, mouse_click, mouse_move, mouse_position, screen_capture
from forge.agent.tools.terminal import terminal_execute
from forge.agent.tools.thinking import sequential_thinking
from forge.agent.tools.web import web_fetch

TOOLS: dict[str, Any] = {
    fn.__name__: fn
    for fn in [
        browser_navigate,
        browser_screenshot,
        browser_click,
        browser_type,
        browser_get_content,
        screen_capture,
        mouse_position,
        mouse_move,
        mouse_click,
        keyboard_type,
        keyboard_press,
        terminal_execute,
        file_read,
        file_write,
        file_delete,
        file_list,
        file_search,
        file_mkdir,
        app_open,
        app_focus,
        app_list_windows,
        web_fetch,
        memory_store,
        memory_retrieve,
        sequential_thinking,
    ]
}


def get_tool(name: str):
    return TOOLS.get(name)


def _to_json_schema(annotation: Any) -> dict[str, Any]:
    if annotation in (int,):
        return {"type": "integer"}
    if annotation in (float,):
        return {"type": "number"}
    if annotation in (bool,):
        return {"type": "boolean"}
    return {"type": "string"}


def list_tools() -> list[dict[str, Any]]:
    schemas: list[dict[str, Any]] = []
    for name, fn in TOOLS.items():
        sig = inspect.signature(fn)
        properties: dict[str, Any] = {}
        required: list[str] = []
        for param_name, param in sig.parameters.items():
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            annotation = param.annotation if param.annotation is not inspect._empty else str
            prop = _to_json_schema(annotation)
            if param.default is not inspect._empty:
                prop["default"] = param.default
            else:
                required.append(param_name)
            properties[param_name] = prop

        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": (inspect.getdoc(fn) or "").strip(),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return schemas


async def execute(name: str, arguments: dict[str, Any] | str | None = None) -> dict[str, Any]:
    fn = get_tool(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}

    args = arguments or {}
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except json.JSONDecodeError as exc:
            return {"error": f"Invalid tool arguments JSON: {exc}"}

    try:
        return await fn(**args)
    except Exception as exc:
        return {"error": str(exc)}
