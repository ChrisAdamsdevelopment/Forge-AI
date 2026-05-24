from __future__ import annotations

import logging
from typing import Any

import httpx
from jinja2 import TemplateError
from jinja2.sandbox import SandboxedEnvironment

logger = logging.getLogger(__name__)


class TemplateLoader:
    """Fetch, cache, and render model-specific Jinja2 chat templates."""

    def __init__(self, ollama_base_url: str = "http://localhost:11434") -> None:
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self._templates: dict[str, str] = {}
        self._model_info: dict[str, dict[str, Any]] = {}
        self._env = SandboxedEnvironment(
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    async def fetch_template(self, model_name: str) -> str:
        """Return the cached, Ollama-provided, or inferred template for a model."""
        if model_name in self._templates:
            return self._templates[model_name]

        info = await self.get_model_info(model_name)
        template = info.get("template") or self._fallback_template(model_name)
        self._templates[model_name] = template
        return template

    async def apply_template(
        self,
        model_name: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        add_generation_prompt: bool = True,
    ) -> str:
        """Render messages and tools with the active model's chat template."""
        template_source = await self.fetch_template(model_name)
        normalized_messages = [self._normalize_message(message) for message in messages]
        try:
            template = self._env.from_string(template_source)
            return template.render(
                messages=normalized_messages,
                tools=tools or [],
                add_generation_prompt=add_generation_prompt,
                bos_token="",
                eos_token="",
            )
        except TemplateError as exc:
            logger.warning("Chat template rendering failed for %s; using simple fallback: %s", model_name, exc)
            return self._simple_format(normalized_messages, tools or [], add_generation_prompt)

    async def get_model_info(self, model_name: str) -> dict:
        """Fetch Ollama model metadata and cache the relevant template information."""
        if model_name in self._model_info:
            return self._model_info[model_name]

        data: dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.request("GET", f"{self.ollama_base_url}/api/show", json={"name": model_name})
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Unable to fetch Ollama template metadata for %s: %s", model_name, exc)

        info = {
            "model_name": model_name,
            "template": data.get("template") or self._fallback_template(model_name),
            "parameters": data.get("parameters") or {},
            "model_family": self._infer_family(model_name),
        }
        self._model_info[model_name] = info
        self._templates[model_name] = info["template"]
        return info

    def invalidate_cache(self, model_name: str | None = None) -> None:
        """Invalidate one model's cache entry or clear the entire template cache."""
        if model_name is None:
            self._templates.clear()
            self._model_info.clear()
            return
        self._templates.pop(model_name, None)
        self._model_info.pop(model_name, None)

    def _normalize_message(self, message: dict) -> dict[str, Any]:
        normalized = dict(message)
        if "content" not in normalized or normalized["content"] is None:
            normalized["content"] = ""
        if normalized.get("tool_calls"):
            normalized["tool_calls"] = [self._normalize_tool_call(call) for call in normalized["tool_calls"]]
        return normalized

    def _normalize_tool_call(self, tool_call: dict) -> dict[str, Any]:
        function = tool_call.get("function") or {}
        return {
            "id": tool_call.get("id", ""),
            "type": tool_call.get("type", "function"),
            "function": {
                "name": function.get("name", ""),
                "arguments": function.get("arguments", "{}"),
            },
        }

    def _simple_format(self, messages: list[dict], tools: list[dict], add_generation_prompt: bool) -> str:
        parts: list[str] = []
        if tools:
            parts.append("tools: " + repr(tools))
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            parts.append(f"{role}: {content}")
            for call in message.get("tool_calls") or []:
                fn = call.get("function", {})
                parts.append(f"assistant_tool_call: {fn.get('name', '')} {fn.get('arguments', '{}')}")
            if role == "tool":
                parts.append(f"tool_call_id: {message.get('tool_call_id', '')}")
        if add_generation_prompt:
            parts.append("assistant:")
        return "\n".join(parts)

    def _fallback_template(self, model_name: str) -> str:
        family = self._infer_family(model_name)
        if family == "qwen":
            return _QWEN_TEMPLATE
        if family == "mistral":
            return _MISTRAL_TEMPLATE
        if family == "llama":
            return _LLAMA3_TEMPLATE
        if family == "deepseek":
            return _DEEPSEEK_TEMPLATE
        return _OPENAI_COMPAT_TEMPLATE

    def _infer_family(self, model_name: str) -> str:
        lowered = model_name.lower()
        if "qwen" in lowered:
            return "qwen"
        if "mistral" in lowered or "mixtral" in lowered:
            return "mistral"
        if "llama" in lowered:
            return "llama"
        if "deepseek" in lowered:
            return "deepseek"
        return "openai"


_QWEN_TEMPLATE = """\
{%- for message in messages %}
<|im_start|>{{ message.role }}
{{ message.content }}
{%- if message.tool_calls %}
{%- for tool_call in message.tool_calls %}
<tool_call>{{ tool_call.function.name }} {{ tool_call.function.arguments }}</tool_call>
{%- endfor %}
{%- endif %}
{%- if message.role == "tool" %}
<tool_response id="{{ message.tool_call_id }}">{{ message.content }}</tool_response>
{%- endif %}
<|im_end|>
{%- endfor %}
{%- if tools %}
<|im_start|>system
Available tools: {{ tools | tojson }}<|im_end|>
{%- endif %}
{%- if add_generation_prompt %}
<|im_start|>assistant
{%- endif %}
"""

_MISTRAL_TEMPLATE = """\
{%- set system = messages | selectattr("role", "equalto", "system") | map(attribute="content") | join("\\n\\n") %}
{%- if system %}{{ system }}

{%- endif %}
{%- for message in messages if message.role != "system" %}
{%- if message.role == "user" %}
[INST] {{ message.content }} [/INST]
{%- elif message.role == "assistant" %}
{{ message.content }}
{%- if message.tool_calls %}{{ message.tool_calls | tojson }}{%- endif %}
{%- elif message.role == "tool" %}
[TOOL_RESULTS id="{{ message.tool_call_id }}"] {{ message.content }} [/TOOL_RESULTS]
{%- endif %}
{%- endfor %}
{%- if tools %}
[AVAILABLE_TOOLS] {{ tools | tojson }} [/AVAILABLE_TOOLS]
{%- endif %}
"""

_LLAMA3_TEMPLATE = """\
{%- for message in messages %}
<|start_header_id|>{{ message.role }}<|end_header_id|>

{{ message.content }}
{%- if message.tool_calls %}
{{ message.tool_calls | tojson }}
{%- endif %}<|eot_id|>
{%- endfor %}
{%- if tools %}
<|start_header_id|>system<|end_header_id|>

Available tools: {{ tools | tojson }}<|eot_id|>
{%- endif %}
{%- if add_generation_prompt %}
<|start_header_id|>assistant<|end_header_id|>

{%- endif %}
"""

_DEEPSEEK_TEMPLATE = """\
{%- for message in messages %}
{{ "<｜" ~ message.role ~ "▁begin｜>" }}
{{ message.content }}
{%- if message.tool_calls %}{{ message.tool_calls | tojson }}{%- endif %}
{{ "<｜" ~ message.role ~ "▁end｜>" }}
{%- endfor %}
{%- if tools %}
<｜system▁begin｜>Available tools: {{ tools | tojson }}<｜system▁end｜>
{%- endif %}
{%- if add_generation_prompt %}
<｜assistant▁begin｜>
{%- endif %}
"""

_OPENAI_COMPAT_TEMPLATE = """\
{%- for message in messages %}
{{ message.role }}: {{ message.content }}
{%- if message.tool_calls %}
tool_calls: {{ message.tool_calls | tojson }}
{%- endif %}
{%- if message.role == "tool" %}
tool_call_id: {{ message.tool_call_id }}
{%- endif %}

{%- endfor %}
{%- if tools %}
tools: {{ tools | tojson }}
{%- endif %}
{%- if add_generation_prompt %}
assistant:
{%- endif %}
"""
