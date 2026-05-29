from __future__ import annotations

from typing import Any

from forge.agent.template_loader import TemplateLoader


class ChatTemplateEngine:
    """Format and trim OpenAI-style chat history with model-native templates."""

    def __init__(self, template_loader: TemplateLoader) -> None:
        self.template_loader = template_loader

    async def format_messages(
        self,
        model_name: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        add_generation_prompt: bool = True,
    ) -> str:
        """Render conversation history into the model's native prompt string."""
        return await self.template_loader.apply_template(
            model_name=model_name,
            messages=messages,
            tools=tools,
            add_generation_prompt=add_generation_prompt,
        )

    async def estimate_tokens(self, text: str) -> int:
        """Estimate token count when the model tokenizer is unavailable."""
        return max(1, len(text) // 4)

    async def truncate_messages(
        self,
        model_name: str,
        messages: list[dict],
        max_tokens: int,
        system_prompt: str = "",
    ) -> list[dict]:
        """Preserve system/RAG context and newest turns while fitting a token budget."""
        if not messages:
            return []

        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        non_system = [msg for msg in messages if msg.get("role") != "system"]
        last_user = next(
            (msg for msg in reversed(non_system) if msg.get("role") == "user"), None
        )

        kept: list[dict[str, Any]] = list(system_messages)
        if system_prompt and not system_messages:
            kept.append({"role": "system", "content": system_prompt})

        budget_text = await self.format_messages(
            model_name, kept, tools=None, add_generation_prompt=False
        )
        budget_used = await self.estimate_tokens(budget_text)
        remaining_budget = max_tokens - budget_used

        newest_first = list(reversed(non_system))
        selected: list[dict] = []
        for message in newest_first:
            candidate_text = await self.format_messages(
                model_name, [message], tools=None, add_generation_prompt=False
            )
            candidate_tokens = await self.estimate_tokens(candidate_text)
            if candidate_tokens <= remaining_budget or message is last_user:
                selected.append(message)
                remaining_budget -= candidate_tokens
            if remaining_budget <= 0 and last_user in selected:
                break

        selected.reverse()
        if last_user and last_user not in selected:
            selected.append(last_user)
        return kept + selected
