from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from forge.agent.tools import registry
from forge.core.config import settings
from forge.services.rag_service import rag_service

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "system_prompt.md"


def _load_system_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return settings.load_system_prompt()


async def context_node(state: dict[str, Any]) -> dict[str, Any]:
    history = state.get("messages", [])
    user_message = ""
    for msg in reversed(history):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    rag_context = ""
    if user_message:
        try:
            rag_result = await rag_service.search(query=user_message, top_k=5)
            rag_context = rag_result.get("context", "")
        except Exception as exc:
            logger.warning("RAG search failed; continuing without RAG context: %s", exc)

    messages: list[dict[str, Any]] = [{"role": "system", "content": _load_system_prompt()}]
    if rag_context:
        messages.append({"role": "system", "content": f"Relevant document context:\n\n{rag_context}"})

    messages.extend(history)

    return {
        "messages": messages,
        "tools": registry.list_tools(),
    }
