"""
forge/services/inference_service.py

Strategy-pattern inference abstraction.
Supports Ollama (local) and any OpenAI-compatible remote endpoint (vLLM, LM Studio, etc.).
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import httpx

from forge.core.config import settings
from forge.services.streaming_parser import StreamingResponseParser

logger = logging.getLogger(__name__)

type ChatMessage = dict[str, Any]
type ToolSchema = dict[str, Any]


class BaseInferenceBackend(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
        prompt: str | None = None,
    ) -> ChatMessage: ...

    @abstractmethod
    async def stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
        prompt: str | None = None,
    ) -> AsyncIterator[dict]: ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    async def health(self) -> bool: ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> ChatMessage: ...


class OllamaBackend(BaseInferenceBackend):
    def __init__(self, base_url: str | None = None) -> None:
        self._base = (base_url or settings.ollama_base_url).rstrip("/")

    def _default_model(self, model: str | None) -> str:
        return model or settings.default_model

    def _default_temp(self, t: float | None) -> float:
        return t if t is not None else settings.temperature

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
        prompt: str | None = None,
    ) -> ChatMessage:
        if prompt is not None:
            payload: dict[str, Any] = {
                "model": self._default_model(model),
                "prompt": prompt,
                "stream": False,
                "raw": True,
                "options": {
                    "temperature": self._default_temp(temperature),
                    "num_ctx": settings.num_ctx,
                },
            }
            async with httpx.AsyncClient(timeout=settings.inference_timeout) as client:
                resp = await client.post(f"{self._base}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
            return {"role": "assistant", "content": data.get("response", "")}

        payload: dict[str, Any] = {
            "model": self._default_model(model),
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self._default_temp(temperature),
                "num_ctx": settings.num_ctx,
            },
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=settings.inference_timeout) as client:
            resp = await client.post(f"{self._base}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        msg = data.get("message", {})
        logger.debug(
            "Ollama response: role=%s tool_calls=%s",
            msg.get("role"),
            bool(msg.get("tool_calls")),
        )
        return msg

    async def stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
        prompt: str | None = None,
    ) -> AsyncIterator[dict]:
        if prompt is not None:
            payload: dict[str, Any] = {
                "model": self._default_model(model),
                "prompt": prompt,
                "stream": True,
                "raw": True,
                "options": {
                    "temperature": self._default_temp(temperature),
                    "num_ctx": settings.num_ctx,
                },
            }
            parser = StreamingResponseParser()
            async with httpx.AsyncClient(timeout=settings.inference_timeout) as client:
                async with client.stream(
                    "POST", f"{self._base}/api/generate", json=payload
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        for event in parser.feed(
                            normalize_ollama_generate_chunk(chunk)
                        ):
                            yield event
                        if chunk.get("done"):
                            break
            for event in parser.flush():
                yield event
            return

        payload: dict[str, Any] = {
            "model": self._default_model(model),
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": self._default_temp(temperature),
                "num_ctx": settings.num_ctx,
            },
        }
        if tools:
            payload["tools"] = tools
        parser = StreamingResponseParser()
        async with httpx.AsyncClient(timeout=settings.inference_timeout) as client:
            async with client.stream(
                "POST", f"{self._base}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    for event in parser.feed(normalize_ollama_chunk(chunk)):
                        yield event
                    if chunk.get("done"):
                        break
        for event in parser.flush():
            yield event

    async def embed(self, text: str) -> list[float]:
        payload = {"model": settings.embed_model, "input": text}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{self._base}/api/embed", json=payload)
            resp.raise_for_status()
            data = resp.json()
        embeddings = data.get("embeddings", data.get("embedding", []))
        if isinstance(embeddings[0], list):
            return embeddings[0]
        return embeddings

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> ChatMessage:
        """Generate from a pre-formatted raw prompt via Ollama /api/generate."""
        return await self.chat(
            [],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt=prompt,
        )


class RemoteOpenAIBackend(BaseInferenceBackend):
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._base = (base_url or settings.remote_inference_url or "").rstrip("/")
        self._key = api_key or settings.remote_inference_key or "local"
        self._model = model or settings.remote_model or "default"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
        prompt: str | None = None,
    ) -> ChatMessage:
        payload: dict[str, Any] = {
            "model": model or self._model,
            "messages": [{"role": "user", "content": prompt}]
            if prompt is not None
            else messages,
            "temperature": temperature
            if temperature is not None
            else settings.temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=settings.inference_timeout) as client:
            resp = await client.post(
                f"{self._base}/v1/chat/completions",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]

    async def stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
        prompt: str | None = None,
    ) -> AsyncIterator[dict]:
        payload: dict[str, Any] = {
            "model": model or self._model,
            "messages": [{"role": "user", "content": prompt}]
            if prompt is not None
            else messages,
            "temperature": temperature
            if temperature is not None
            else settings.temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        parser = StreamingResponseParser()
        async with httpx.AsyncClient(timeout=settings.inference_timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base}/v1/chat/completions",
                json=payload,
                headers=self._headers(),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:]
                    if raw.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    for event in parser.feed(normalize_openai_chunk(chunk)):
                        yield event
        for event in parser.flush():
            yield event

    async def embed(self, text: str) -> list[float]:
        payload = {"model": self._model, "input": text}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._base}/v1/embeddings", json=payload, headers=self._headers()
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self._base}/v1/models", headers=self._headers()
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> ChatMessage:
        """Generate from a raw prompt by sending it as a single user message."""
        return await self.chat(
            [],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt=prompt,
        )


class InferenceService:
    def __init__(self) -> None:
        self._local = OllamaBackend()
        self._remote: RemoteOpenAIBackend | None = (
            RemoteOpenAIBackend() if settings.remote_inference_url else None
        )

    def _backend(self, prefer_remote: bool = False) -> BaseInferenceBackend:
        if prefer_remote and self._remote:
            return self._remote
        return self._local

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
        prefer_remote: bool = False,
        prompt: str | None = None,
    ) -> ChatMessage:
        return await self._backend(prefer_remote).chat(
            messages, tools, model=model, temperature=temperature, prompt=prompt
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
        prefer_remote: bool = False,
        prompt: str | None = None,
    ) -> AsyncIterator[dict]:
        return self._backend(prefer_remote).stream(
            messages, tools=tools, model=model, temperature=temperature, prompt=prompt
        )

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        prefer_remote: bool = False,
    ) -> ChatMessage:
        return await self._backend(prefer_remote).generate(
            prompt, model=model, temperature=temperature
        )

    async def embed(self, text: str) -> list[float]:
        return await self._local.embed(text)

    async def health(self) -> dict[str, bool]:
        local_ok = await self._local.health()
        remote_ok = await self._remote.health() if self._remote else None
        return {"local": local_ok, "remote": remote_ok}


def normalize_ollama_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    """Normalize Ollama /api/chat stream chunks to OpenAI-compatible deltas."""
    message = chunk.get("message") or {}
    delta: dict[str, Any] = {"content": message.get("content")}
    tool_calls = []
    for index, tool_call in enumerate(message.get("tool_calls") or []):
        function = tool_call.get("function") or {}
        arguments = function.get("arguments", tool_call.get("arguments"))
        if arguments is not None and not isinstance(arguments, str):
            arguments = json.dumps(arguments)
        tool_calls.append(
            {
                "index": tool_call.get("index", index),
                "id": tool_call.get("id") or f"ollama_tool_call_{index}",
                "function": {
                    "name": function.get("name")
                    or tool_call.get("name")
                    or tool_call.get("function_name"),
                    "arguments": arguments,
                },
            }
        )
    if tool_calls:
        delta["tool_calls"] = tool_calls
    return delta


def normalize_ollama_generate_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    """Normalize Ollama /api/generate stream chunks to parser deltas."""
    return {
        "content": chunk.get("response"),
        "raw_prompt": True,
    }


def normalize_openai_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    """Normalize OpenAI-compatible, vLLM, and llama.cpp chunks to parser deltas."""
    choices = chunk.get("choices") or []
    delta = (choices[0].get("delta") if choices else chunk.get("delta")) or chunk
    normalized: dict[str, Any] = {"content": delta.get("content")}
    tool_calls = []
    for index, tool_call in enumerate(delta.get("tool_calls") or []):
        function = tool_call.get("function") or {}
        arguments = function.get("arguments", tool_call.get("arguments"))
        if arguments is not None and not isinstance(arguments, str):
            arguments = json.dumps(arguments)
        tool_calls.append(
            {
                "index": tool_call.get("index", index),
                "id": tool_call.get("id"),
                "function": {
                    "name": function.get("name")
                    or tool_call.get("name")
                    or tool_call.get("function_name"),
                    "arguments": arguments,
                },
            }
        )
    if tool_calls:
        normalized["tool_calls"] = tool_calls
    return normalized
