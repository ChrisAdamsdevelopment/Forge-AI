from __future__ import annotations

from pathlib import Path

import pytest

from forge.services.eval_service import EvalService
from forge.services.module_service import ModuleService
from forge.services.rag_service import RagService
from forge.services.session_service import SessionService, _estimate_tokens


def test_estimate_tokens_has_lower_bound():
    assert _estimate_tokens("") == 1
    assert _estimate_tokens("abcd") == 1
    assert _estimate_tokens("a" * 40) >= 10


def test_build_context_includes_system_and_recent_messages():
    svc = SessionService(db=None)  # type: ignore[arg-type]

    async def fake_get_messages(_session_id: str):
        class Msg:
            def __init__(self, role: str, content: str, token_count: int):
                self.role = role
                self.content = content
                self.token_count = token_count
                self.tool_calls = None
                self.tool_call_id = None
                self.tool_name = None

        return [
            Msg("user", "old", 200),
            Msg("assistant", "new", 1),
        ]

    svc.get_messages = fake_get_messages  # type: ignore[method-assign]
    import asyncio
    context = asyncio.run(svc.build_context("s1", system_prompt="sys", max_tokens=10))

    assert context[0] == {"role": "system", "content": "sys"}
    assert any(m.get("content") == "new" for m in context)


def test_module_service_get_module_by_id(tmp_path: Path):
    class DummyRunner:
        def list_modules(self) -> list[dict]:
            return [{"id": "alpha"}, {"id": "beta"}]

    svc = ModuleService(module_dir=tmp_path)
    svc._runner = DummyRunner()  # type: ignore[attr-defined]

    assert svc.get_module("beta") == {"id": "beta"}
    assert svc.get_module("missing") is None


def test_eval_service_loads_tasks_from_yaml(tmp_path: Path):
    tasks_file = tmp_path / "golden_tasks.yaml"
    tasks_file.write_text("tasks:\n  - id: test-1\n    input:\n      user_message: hi\n", encoding="utf-8")
    svc = EvalService(tasks_file=tasks_file, results_file=tmp_path / "out.json")

    tasks = svc._load_tasks()
    assert len(tasks) == 1
    assert tasks[0]["id"] == "test-1"


def test_rag_service_ingest_directory_empty(tmp_path: Path):
    svc = RagService()
    import asyncio
    result = asyncio.run(svc.ingest_directory(str(tmp_path), pattern="*.md"))

    assert result["status"] == "ok"
    assert result["results"] == []
