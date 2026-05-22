"""
forge/services/inference_service.py

Strategy-pattern inference abstraction.
Supports Ollama (local) and any OpenAI-compatible remote endpoint (vLLM, LM Studio, etc.).

Usage::

    service = InferenceService()
    # Non-streaming
    reply = await service.chat(messages=[...])

    # Streaming – yields text tokens
    async for token in service.stream(messages=[...]):
        print(token, end="", flush=True)
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import httpx

from forge.core.config import settings

logger = logging.getLogger(__name__)

# ── Shared types ─────────────────────────────────────────────────────────────

type ChatMessage = dict[str, Any]   # {"role": ..., "content": ...}
type ToolSchema  = dict[str, Any]   # OpenAI function-calling schema


# ── Abstract base ────────────────────────────────────────────────────────────

class BaseInferenceBackend(ABC):
    """Common interface every backend must implement."""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> ChatMessage:
        """Return the full assistant message (may contain tool_calls)."""

    @abstractmethod
    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Yield text tokens as they arrive."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return a dense embedding vector for the input text."""

    @abstractmethod
    async def health(self) -> bool:
        """Return True if the backend is reachable."""


# ── Ollama backend ────────────────────────────────────────────────────────────

class OllamaBackend(BaseInferenceBackend):
    """
    Communicates with a local Ollama instance via its HTTP API.
    Ollama exposes an OpenAI-compatible /v1/chat/completions endpoint
    as well as its native /api/chat; we use the native API for richer
    streaming and the v1 endpoint for tool-calling compatibility.
    """

    def __init__(self, base_url: str | None = None) -> None:
        self._base = (base_url or settings.ollama_base_url).rstrip("/")

    # ── helpers ──────────────────────────────────────────────────────────────

    def _default_model(self, model: str | None) -> str:
        return model or settings.default_model

    def _default_temp(self, t: float | None) -> float:
        return t if t is not None else settings.temperature

    # ── interface ────────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> ChatMessage:
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
        logger.debug("Ollama response: role=%s tool_calls=%s", msg.get("role"), bool(msg.get("tool_calls")))
        return msg

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self._default_model(model),
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": self._default_temp(temperature),
                "num_ctx": settings.num_ctx,
            },
        }
        async with httpx.AsyncClient(timeout=settings.inference_timeout) as client:
            async with client.stream("POST", f"{self._base}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        break

    async def embed(self, text: str) -> list[float]:
        payload = {"model": settings.embed_model, "input": text}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{self._base}/api/embed", json=payload)
            resp.raise_for_status()
            data = resp.json()
        # Ollama /api/embed returns {"embeddings": [[...]])}
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


# ── Remote OpenAI-compatible backend ─────────────────────────────────────────

class RemoteOpenAIBackend(BaseInferenceBackend):
    """
    Any server that speaks the OpenAI chat completions API:
    vLLM, SGLang, LM Studio, llama.cpp server, etc.
    """

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
        return {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> ChatMessage:
        payload: dict[str, Any] = {
            "model": model or self._model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.temperature,
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

        choice = data["choices"][0]["message"]
        return choice

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": model or self._model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
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
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content") or ""
                    if token:
                        yield token

    async def embed(self, text: str) -> list[float]:
        payload = {"model": self._model, "input": text}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._base}/v1/embeddings",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base}/v1/models", headers=self._headers())
                return resp.status_code == 200
        except Exception:
            return False


# ── Public facade ─────────────────────────────────────────────────────────────

class InferenceService:
    """
    Public entry point.  Picks the right backend based on config,
    with automatic fallback from remote → local Ollama.
    """

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
    ) -> ChatMessage:
        return await self._backend(prefer_remote).chat(
            messages, tools, model=model, temperature=temperature
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        prefer_remote: bool = False,
    ) -> AsyncIterator[str]:
        return self._backend(prefer_remote).stream(
            messages, model=model, temperature=temperature
        )

    async def embed(self, text: str) -> list[float]:
        return await self._local.embed(text)

    async def health(self) -> dict[str, bool]:
        local_ok = await self._local.health()
        remote_ok = await self._remote.health() if self._remote else None
        return {"local": local_ok, "remote": remote_ok}
