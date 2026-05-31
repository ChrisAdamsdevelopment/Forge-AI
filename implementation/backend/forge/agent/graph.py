from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from forge.agent.nodes.context_node import context_node
from forge.agent.tools import registry
from forge.services.inference_service import InferenceService


async def tool_node(tool_call: dict[str, Any]) -> dict[str, Any]:
    fn = tool_call.get("function", {})
    tool_name = fn.get("name", "")
    arguments = fn.get("arguments", {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}
    result = await registry.execute(tool_name, arguments)
    return {
        "role": "tool",
        "tool_call_id": tool_call.get("id"),
        "name": tool_name,
        "content": json.dumps(result),
    }


async def _collect_streaming_response(stream: Any) -> dict[str, Any]:
    content_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []

    async for event in stream:
        if isinstance(event, str):
            content_parts.append(event)
            continue
        event_type = event.get("type")
        if event_type == "text":
            content_parts.append(event.get("content", ""))
        elif event_type == "tool_call":
            tool_calls.append(
                {
                    "id": event.get("id"),
                    "type": "function",
                    "function": {
                        "name": event.get("name", ""),
                        "arguments": event.get("arguments", "{}"),
                    },
                }
            )
        elif event_type == "error":
            continue

    response: dict[str, Any] = {"role": "assistant", "content": "".join(content_parts)}
    if tool_calls:
        response["tool_calls"] = tool_calls
    return response


async def run_agent_loop(
    session_messages: list[dict[str, Any]],
    inference: InferenceService | None = None,
    model: str | None = None,
    stream: bool = False,
) -> list[dict[str, Any]]:
    inference_service = inference or InferenceService()
    state: dict[str, Any] = {
        "messages": list(session_messages),
        "rag_results": [],
        "model": model,
    }

    started_at = time.monotonic()
    for _ in range(15):
        if (time.monotonic() - started_at) > 300:
            break

        ctx = await context_node(state)
        if stream:
            response = await _collect_streaming_response(
                await inference_service.stream(
                    messages=ctx["messages"],
                    tools=ctx["tools"],
                    model=model,
                    prompt=ctx.get("formatted_prompt"),
                )
            )
        else:
            response = await inference_service.chat(
                messages=ctx["messages"],
                tools=ctx["tools"],
                model=model,
                prompt=ctx.get("formatted_prompt"),
            )
        state["messages"].append(response)

        tool_calls = response.get("tool_calls") or []
        if not tool_calls:
            break

        for call in tool_calls:
            tool_message = await tool_node(call)
            state["messages"].append(tool_message)

        await asyncio.sleep(0)

    return state["messages"]
