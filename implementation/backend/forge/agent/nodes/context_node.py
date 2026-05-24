from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from forge.agent.chat_template_engine import ChatTemplateEngine
from forge.agent.template_loader import TemplateLoader
from forge.agent.tools import registry
from forge.core.config import settings
from forge.services.rag_service import rag_service

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "system_prompt.md"
_template_loader = TemplateLoader(settings.ollama_base_url)
_chat_template_engine = ChatTemplateEngine(_template_loader)


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

    tools = registry.list_tools()
    model_name = state.get("model") or settings.default_model
    formatted_prompt = None
    try:
        formatted_prompt = await _chat_template_engine.format_messages(
            model_name=model_name,
            messages=messages,
            tools=tools,
            add_generation_prompt=True,
        )
    except Exception as exc:
        logger.warning("Chat template formatting failed; continuing with raw messages: %s", exc)

    return {
        "messages": messages,
        "tools": tools,
        "formatted_prompt": formatted_prompt,
        "model": model_name,
    }
