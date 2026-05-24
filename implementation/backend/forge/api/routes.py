"""
forge/api/routes.py

All v1 REST + WebSocket routes.

Route map
─────────
GET  /health               → liveness + backend health
POST /chat                 → non-streaming chat (full response)
WS   /ws/chat/{session_id} → streaming chat with tool-call events
GET  /models               → list available Ollama models
GET  /modules              → list installed modules
POST /modules/validate     → validate a manifest dict
POST /modules/{id}/run     → execute a module
GET  /config               → current effective config (no secrets)
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from forge.core.config import settings
from forge.core.security import verify_api_key
from forge.services.inference_service import InferenceService
from forge.services.module_service import ModuleService
from forge.services.rag_service import rag_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared service instances (stateless; safe to reuse across requests)
_inference = InferenceService()
_modules = ModuleService()


# ── Health ─────────────────────────────────────────────────────────────────────

@router.get("/health", tags=["system"])
async def health():
    backend_health = await _inference.health()
    return {
        "status": "ok",
        "service": "forge-api",
        "version": "0.1.0",
        "backends": backend_health,
    }


# ── Chat (non-streaming) ───────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    temperature: float | None = None
    tools: list[dict] | None = None
    prefer_remote: bool = False


class ChatResponse(BaseModel):
    role: str
    content: str
    tool_calls: list[dict] | None = None
    model: str


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(
    request: ChatRequest,
    _key: str = Depends(verify_api_key),
):
    """
    Single-turn non-streaming chat.  For multi-turn conversations with
    streaming and tool execution, use the WebSocket endpoint instead.
    """
    messages = [m.model_dump(exclude_none=True) for m in request.messages]

    # Prepend system prompt if first message is not already a system message
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {
            "role": "system",
            "content": settings.load_system_prompt(),
        })

    try:
        response = await _inference.chat(
            messages=messages,
            tools=request.tools,
            model=request.model,
            temperature=request.temperature,
            prefer_remote=request.prefer_remote,
        )
    except Exception as exc:
        logger.exception("Inference error in /chat")
        raise HTTPException(status_code=502, detail=f"Inference backend error: {exc}")

    return ChatResponse(
        role=response.get("role", "assistant"),
        content=response.get("content", ""),
        tool_calls=response.get("tool_calls"),
        model=request.model or settings.default_model,
    )


# ── Chat WebSocket (streaming) ─────────────────────────────────────────────────

@router.websocket("/ws/chat/{session_id}")
async def ws_chat(websocket: WebSocket, session_id: str):
    """
    Streaming chat WebSocket.

    Client → server messages (JSON)::

        {"type": "user_message", "content": "...", "model": null}
        {"type": "approval_response", "tool_call_id": "...", "approved": true}
        {"type": "cancel"}

    Server → client messages (JSON)::

        {"type": "token", "content": "..."}
        {"type": "tool_call_start", "tool_name": "...", "tool_call_id": "...", "arguments": {...}}
        {"type": "tool_call_result", "tool_call_id": "...", "result": "..."}
        {"type": "approval_required", "tool_name": "...", "tool_call_id": "...", "arguments": {...}}
        {"type": "error", "message": "..."}
        {"type": "done", "session_id": "...", "token_count": 0}
    """
    await websocket.accept()
    logger.info("WebSocket connected: session=%s", session_id)

    system_prompt = settings.load_system_prompt()
    history: list[dict] = [{"role": "system", "content": system_prompt}]

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            event_type = event.get("type")

            if event_type == "user_message":
                content = event.get("content", "").strip()
                if not content:
                    continue
                history.append({"role": "user", "content": content})

                full_response = ""
                token_count = 0

                try:
                    stream = await _inference.stream(
                        messages=history,
                        model=event.get("model"),
                    )
                    async for token in stream:
                        full_response += token
                        token_count += 1
                        await websocket.send_json({"type": "token", "content": token})
                except Exception as exc:
                    logger.exception("Streaming error in WebSocket")
                    await websocket.send_json({"type": "error", "message": str(exc)})
                    continue

                history.append({"role": "assistant", "content": full_response})
                await websocket.send_json({
                    "type": "done",
                    "session_id": session_id,
                    "token_count": token_count,
                })

            elif event_type == "cancel":
                await websocket.send_json({"type": "error", "message": "Cancelled by client"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session=%s", session_id)


# ── Models ─────────────────────────────────────────────────────────────────────

@router.get("/models", tags=["models"])
async def list_models(_key: str = Depends(verify_api_key)):
    """List all models available in the local Ollama instance."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cannot reach Ollama: {exc}")


# ── Modules ─────────────────────────────────────────────────────────────────────

@router.get("/modules", tags=["modules"])
async def list_modules(_key: str = Depends(verify_api_key)):
    return {"modules": _modules.list_modules()}


@router.post("/modules/validate", tags=["modules"])
async def validate_module(
    manifest: dict[str, Any],
    _key: str = Depends(verify_api_key),
):
    return _modules.validate_manifest(manifest)


class ModuleRunRequest(BaseModel):
    input_data: dict[str, Any] = Field(default_factory=dict)
    system_prompt: str | None = None


@router.post("/modules/{module_id}/run", tags=["modules"])
async def run_module(
    module_id: str,
    request: ModuleRunRequest,
    _key: str = Depends(verify_api_key),
):
    system_prompt = request.system_prompt or settings.load_system_prompt()
    try:
        result = await _modules.run_module(
            module_id_or_path=module_id,
            input_data=request.input_data,
            inference_service=_inference,
            system_prompt=system_prompt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Module run failed: %s", module_id)
        raise HTTPException(status_code=500, detail=str(exc))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return {
        "module_id": result.module_id,
        "response": result.response,
        "output_path": result.output_path,
        "risk": result.risk,
    }


# ── Config (read-only, no secrets) ────────────────────────────────────────────

@router.get("/config", tags=["system"])
async def get_config(_key: str = Depends(verify_api_key)):
    return {
        "default_model": settings.default_model,
        "embed_model": settings.embed_model,
        "num_ctx": settings.num_ctx,
        "temperature": settings.temperature,
        "rag_top_k": settings.rag_top_k,
        "rag_rerank_top_n": settings.rag_rerank_top_n,
        "enable_modules": settings.enable_modules,
        "enable_eval": settings.enable_eval,
        "enable_training": settings.enable_training,
        "has_remote_inference": settings.remote_inference_url is not None,
    }


class RagIngestFileRequest(BaseModel):
    file_path: str


class RagIngestDirectoryRequest(BaseModel):
    dir_path: str
    pattern: str = "*"


class RagDeleteRequest(BaseModel):
    filename: str


@router.post("/rag/ingest/file", tags=["rag"])
async def rag_ingest_file(request: RagIngestFileRequest, _key: str = Depends(verify_api_key)):
    return await rag_service.ingest_file(request.file_path)


@router.post("/rag/ingest/directory", tags=["rag"])
async def rag_ingest_directory(request: RagIngestDirectoryRequest, _key: str = Depends(verify_api_key)):
    return await rag_service.ingest_directory(request.dir_path, request.pattern)


@router.get("/rag/search", tags=["rag"])
async def rag_search(q: str, top_k: int = 5, _key: str = Depends(verify_api_key)):
    return await rag_service.search(query=q, top_k=top_k)


@router.delete("/rag/document", tags=["rag"])
async def rag_delete_document(request: RagDeleteRequest, _key: str = Depends(verify_api_key)):
    return await rag_service.delete_from_index(request.filename)
