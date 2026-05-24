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
    result = await registry.execute(tool_name, arguments)
    return {
        "role": "tool",
        "tool_call_id": tool_call.get("id"),
        "name": tool_name,
        "content": json.dumps(result),
    }


async def run_agent_loop(
    session_messages: list[dict[str, Any]],
    inference: InferenceService | None = None,
    model: str | None = None,
) -> list[dict[str, Any]]:
    inference_service = inference or InferenceService()
    state: dict[str, Any] = {"messages": list(session_messages), "rag_results": []}

    started_at = time.monotonic()
    for _ in range(15):
        if (time.monotonic() - started_at) > 300:
            break

        ctx = await context_node(state)
        response = await inference_service.chat(messages=ctx["messages"], tools=ctx["tools"], model=model)
        state["messages"].append(response)

        tool_calls = response.get("tool_calls") or []
        if not tool_calls:
            break

        for call in tool_calls:
            tool_message = await tool_node(call)
            state["messages"].append(tool_message)

        await asyncio.sleep(0)

    return state["messages"]
