from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.agent.tools import registry
from forge.core.config import settings


PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "system_prompt.md"


def _load_system_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return settings.load_system_prompt()


async def context_node(state: dict[str, Any]) -> dict[str, Any]:
    history = state.get("messages", [])
    rag_results = state.get("rag_results", [])

    messages: list[dict[str, Any]] = [{"role": "system", "content": _load_system_prompt()}]
    messages.extend(history)

    if rag_results:
        rag_blob = "\n\n".join(str(item) for item in rag_results)
        messages.append({"role": "system", "content": f"RAG context:\n{rag_blob}"})

    return {
        "messages": messages,
        "tools": registry.list_tools(),
    }
