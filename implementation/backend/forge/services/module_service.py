"""
forge/services/module_service.py

HTTP-facing service layer wrapping ModuleRunner.
Keeps the FastAPI routes thin and the business logic testable.
"""

from __future__ import annotations

from pathlib import Path

from forge.core.config import settings
from forge.modules.runner import ModuleRunner, ModuleRunResult, validate_manifest


class ModuleService:
    def __init__(self, module_dir: str | Path | None = None) -> None:
        root = Path(module_dir) if module_dir else settings.modules_dir
        self._runner = ModuleRunner(root)

    def list_modules(self) -> list[dict]:
        return self._runner.list_modules()

    def validate_manifest(self, manifest: dict) -> dict:
        return validate_manifest(manifest)

    def get_module(self, module_id: str) -> dict | None:
        for m in self.list_modules():
            if m.get("id") == module_id:
                return m
        return None

    async def run_module(
        self,
        module_id_or_path: str,
        input_data: dict,
        inference_service: object,
        system_prompt: str = "",
    ) -> ModuleRunResult:
        """
        Find a module by id or path and execute it.
        Raises ValueError if the module doesn't exist.
        """
        # Try as a direct path first
        candidate = settings.modules_dir / module_id_or_path
        if not (candidate / "module.yaml").exists():
            # Search by manifest id
            for m in self.list_modules():
                if m.get("id") == module_id_or_path:
                    candidate = Path(m["_path"])
                    break
            else:
                raise ValueError(f"Module not found: {module_id_or_path!r}")

        return await self._runner.run(
            module_path=candidate,
            input_data=input_data,
            inference=inference_service,
            system_prompt=system_prompt,
            output_root=settings.data_dir / "module_outputs",
        )
