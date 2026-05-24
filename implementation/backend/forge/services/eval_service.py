from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import yaml

from forge.agent.graph import run_agent_loop
from forge.core.config import settings


class EvalService:
    def __init__(self, tasks_file: Path | None = None, results_file: Path | None = None) -> None:
        self._tasks_file = tasks_file or Path("eval/golden_tasks.yaml")
        self._results_file = results_file or (settings.data_dir / "eval_results.json")

    def _load_tasks(self) -> list[dict[str, Any]]:
        if not self._tasks_file.exists():
            raise FileNotFoundError(f"Golden tasks file not found: {self._tasks_file}")
        data = yaml.safe_load(self._tasks_file.read_text(encoding="utf-8")) or {}
        return data.get("tasks", [])

    async def run_eval_suite(self) -> dict[str, Any]:
        tasks = self._load_tasks()
        results: list[dict[str, Any]] = []

        for task in tasks:
            user_message = task.get("input", {}).get("user_message", "")
            started = time.monotonic()
            messages = await run_agent_loop(
                session_messages=[
                    {"role": "system", "content": settings.load_system_prompt()},
                    {"role": "user", "content": user_message},
                ],
                model=task.get("model") or settings.default_model,
            )
            duration = time.monotonic() - started

            assistant_messages = [m for m in messages if m.get("role") == "assistant"]
            final_assistant = assistant_messages[-1] if assistant_messages else {"content": ""}
            response_text = (final_assistant.get("content") or "").strip()

            all_tool_names: list[str] = []
            for m in messages:
                for tool_call in (m.get("tool_calls") or []):
                    fn = tool_call.get("function", {})
                    name = fn.get("name")
                    if name:
                        all_tool_names.append(name)

            assertions: list[dict[str, Any]] = []
            expected = task.get("expected", {})

            for needle in expected.get("contains", []) or []:
                passed = needle.lower() in response_text.lower()
                assertions.append({"type": "contains", "expected": needle, "actual": response_text, "passed": passed})

            for needle in expected.get("not_contains", []) or []:
                passed = needle.lower() not in response_text.lower()
                assertions.append({"type": "not_contains", "expected": needle, "actual": response_text, "passed": passed})

            for tool_name in expected.get("tool_calls_include", []) or []:
                passed = tool_name in all_tool_names
                assertions.append({"type": "tool_calls_include", "expected": tool_name, "actual": all_tool_names, "passed": passed})

            max_duration = expected.get("max_duration_seconds")
            if max_duration is not None:
                passed = duration <= float(max_duration)
                assertions.append({"type": "max_duration_seconds", "expected": max_duration, "actual": round(duration, 4), "passed": passed})

            task_passed = all(a["passed"] for a in assertions) if assertions else True
            results.append(
                {
                    "task_id": task.get("id"),
                    "description": task.get("description", ""),
                    "passed": task_passed,
                    "assertions": assertions,
                }
            )

        report = {
            "total_tasks": len(results),
            "passed": sum(1 for r in results if r["passed"]),
            "failed": sum(1 for r in results if not r["passed"]),
            "results": results,
        }

        self._results_file.parent.mkdir(parents=True, exist_ok=True)
        self._results_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    def get_last_results(self) -> dict[str, Any]:
        if not self._results_file.exists():
            return {"total_tasks": 0, "passed": 0, "failed": 0, "results": []}
        return json.loads(self._results_file.read_text(encoding="utf-8"))


def run_eval_suite_sync() -> dict[str, Any]:
    return asyncio.run(EvalService().run_eval_suite())
