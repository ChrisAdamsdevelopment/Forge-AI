from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ModuleLoader:
    def __init__(self, modules_dir: str | None = None):
        repo_root = Path(__file__).resolve().parents[4]
        self.modules_dir = Path(modules_dir) if modules_dir else repo_root / "modules"

    async def discover(self) -> list[dict]:
        manifests: list[dict] = []
        if not self.modules_dir.exists():
            return manifests

        for child in self.modules_dir.iterdir():
            if not child.is_dir():
                continue
            manifest_path = child / "module.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning("Invalid module manifest JSON: %s", manifest_path)
                continue
            manifest["_path"] = str(child)
            manifests.append(manifest)
        return manifests

    async def load_module(
        self, module_name: str, target: Any, force: bool = False
    ) -> bool:
        module_dir = self.modules_dir / module_name
        manifest_path = module_dir / "module.json"
        module_path = module_dir / "module.py"

        if not manifest_path.exists() or not module_path.exists():
            return False

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False

        if not force and not manifest.get("enabled", False):
            return False

        spec = importlib.util.spec_from_file_location(
            f"forge_dynamic_module_{module_name}", module_path
        )
        if spec is None or spec.loader is None:
            return False

        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)

        register = getattr(loaded, "register", None)
        if not callable(register):
            return False

        register(target)
        return True

    async def load_all(self, target: Any) -> list[str]:
        manifests = await self.discover()
        loaded_names: list[str] = []
        for manifest in manifests:
            module_name = manifest.get("name", "")
            if not module_name:
                continue
            module_dir_name = module_name.replace("-", "_")
            if await self.load_module(module_dir_name, target):
                loaded_names.append(module_name)
        return loaded_names

    async def enable_module(self, module_name: str) -> bool:
        return self._set_enabled(module_name, True)

    async def disable_module(self, module_name: str) -> bool:
        return self._set_enabled(module_name, False)

    def _set_enabled(self, module_name: str, enabled: bool) -> bool:
        manifest_path = self.modules_dir / module_name / "module.json"
        if not manifest_path.exists():
            return False
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        manifest["enabled"] = enabled
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return True
