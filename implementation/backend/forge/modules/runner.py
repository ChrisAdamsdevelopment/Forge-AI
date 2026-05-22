"""
forge/modules/runner.py

Loads, validates, and executes Forge modules — the Tasker-style reusable
workflow packages.

A module folder layout::

    my_module/
        module.yaml              ← manifest
        prompts/main.md          ← Jinja2 prompt template
        prompts/critique.md      ← optional self-critique template
        schemas/input.schema.json
        schemas/output.schema.json
        policy/tool_policy.yaml
        examples/example_input.json
        examples/example_output.md
        tests/golden_tasks.yaml

Usage::

    runner = ModuleRunner()
    result = await runner.run(
        module_path="modules/repo_inspector",
        input_data={"repo_path": "/srv/forge/workspace/myproject"},
        inference=InferenceService(),
    )
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

logger = logging.getLogger(__name__)


# ── Risk classification ───────────────────────────────────────────────────────

_CRITICAL_KEYWORDS = {"delete", "secrets", "credentials", "rm ", "drop "}
_HIGH_KEYWORDS = {"terminal", "execute", "shell", "sudo"}
_MEDIUM_KEYWORDS = {"network", "fetch", "web", "http", "browser"}


def classify_risk(manifest: dict) -> str:
    """
    Inspect a manifest's permissions block and return a risk level:
    'low' | 'medium' | 'high' | 'critical'
    """
    perms = manifest.get("permissions", {})
    tools: list[str] = [t.lower() for t in perms.get("tools", [])]
    tool_str = " ".join(tools)

    if any(kw in tool_str for kw in _CRITICAL_KEYWORDS) or perms.get("reads_secrets"):
        return "critical"
    if (
        perms.get("terminal") is True
        or any(kw in tool_str for kw in _HIGH_KEYWORDS)
    ):
        return "high"
    if perms.get("network") or any(kw in tool_str for kw in _MEDIUM_KEYWORDS):
        return "medium"
    return "low"


# ── Manifest validation ───────────────────────────────────────────────────────

REQUIRED_FIELDS = (
    "id", "name", "version", "author", "description",
    "category", "entrypoint", "input_schema", "output_schema",
    "permissions", "safety",
)

ALLOWED_CATEGORIES = {
    "research", "coding", "file_ops", "media", "security",
    "writing", "monitoring", "utility",
}


def validate_manifest(manifest: dict) -> dict:
    """
    Returns::

        {
            "valid": bool,
            "missing": [...],       # required keys absent
            "invalid": [...],       # keys present but wrong value
            "risk": "low|medium|high|critical",
            "requires_review": bool,
            "approval_required": [...],  # tools that need user approval
        }
    """
    missing = [f for f in REQUIRED_FIELDS if f not in manifest]
    invalid: list[str] = []

    category = manifest.get("category", "")
    if category and category not in ALLOWED_CATEGORIES:
        invalid.append(f"category must be one of: {sorted(ALLOWED_CATEGORIES)}")

    risk = classify_risk(manifest)
    approval_required: list[str] = list(
        manifest.get("safety", {}).get("approval_required", [])
    )

    return {
        "valid": not missing and not invalid,
        "missing": missing,
        "invalid": invalid,
        "risk": risk,
        "requires_review": risk in ("high", "critical"),
        "approval_required": approval_required,
    }


# ── Run result ────────────────────────────────────────────────────────────────

@dataclass
class ModuleRunResult:
    module_id: str
    rendered_prompt: str
    response: str = ""
    output_path: str | None = None
    risk: str = "low"
    tool_calls: list[dict] = field(default_factory=list)
    error: str | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.error is None


# ── Runner ────────────────────────────────────────────────────────────────────

class ModuleRunner:
    """
    Loads modules, renders their prompts via Jinja2, and executes them
    through the inference service.
    """

    def __init__(self, modules_root: str | Path = "modules") -> None:
        self.root = Path(modules_root)

    # ── Loading ───────────────────────────────────────────────────────────────

    def load_manifest(self, module_path: str | Path) -> dict:
        path = self.root / module_path if not Path(module_path).is_absolute() else Path(module_path)
        manifest_file = path / "module.yaml"
        if not manifest_file.exists():
            raise FileNotFoundError(f"No module.yaml in {path}")
        return yaml.safe_load(manifest_file.read_text(encoding="utf-8"))

    def list_modules(self) -> list[dict]:
        """Return validated manifests for every module.yaml found under root."""
        results: list[dict] = []
        for manifest_path in sorted(self.root.rglob("module.yaml")):
            try:
                raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                validation = validate_manifest(raw)
                results.append({**raw, "_validation": validation, "_path": str(manifest_path.parent)})
            except Exception as exc:
                results.append({"_path": str(manifest_path), "_error": str(exc)})
        return results

    # ── Input validation ──────────────────────────────────────────────────────

    def validate_input(self, module_path: str | Path, input_data: dict) -> dict:
        """
        Validate input_data against the module's input JSON Schema.
        Returns {"valid": bool, "missing": [...], "errors": [...]}.
        """
        path = self.root / module_path if not Path(module_path).is_absolute() else Path(module_path)
        manifest = self.load_manifest(path)
        schema_file = path / manifest["input_schema"]

        if not schema_file.exists():
            return {"valid": True, "missing": [], "errors": [], "warning": "No input schema found"}

        schema = json.loads(schema_file.read_text(encoding="utf-8"))
        required = schema.get("required", [])
        missing = [f for f in required if f not in input_data]

        # Basic type checking
        errors: list[str] = []
        props = schema.get("properties", {})
        for key, value in input_data.items():
            if key in props:
                expected_type = props[key].get("type")
                if expected_type == "string" and not isinstance(value, str):
                    errors.append(f"'{key}' must be a string")
                elif expected_type == "integer" and not isinstance(value, int):
                    errors.append(f"'{key}' must be an integer")

        return {"valid": not missing and not errors, "missing": missing, "errors": errors}

    # ── Prompt rendering ──────────────────────────────────────────────────────

    def render_prompt(self, module_path: str | Path, input_data: dict) -> str:
        """
        Render the module's entrypoint prompt template with Jinja2,
        substituting input_data variables.
        """
        path = self.root / module_path if not Path(module_path).is_absolute() else Path(module_path)
        manifest = self.load_manifest(path)
        entrypoint = manifest["entrypoint"]

        env = Environment(
            loader=FileSystemLoader(str(path)),
            undefined=StrictUndefined,
            autoescape=False,
        )
        try:
            template = env.get_template(entrypoint)
        except TemplateNotFound:
            raise FileNotFoundError(f"Entrypoint '{entrypoint}' not found in {path}")

        return template.render(**input_data)

    # ── Execution ─────────────────────────────────────────────────────────────

    async def run(
        self,
        module_path: str | Path,
        input_data: dict,
        inference: Any,          # InferenceService — typed loosely to avoid circular imports
        system_prompt: str = "",
        output_root: str | Path = "",
    ) -> ModuleRunResult:
        """
        Full module execution pipeline:
        1. Load + validate manifest
        2. Validate input
        3. Check risk / approval (caller must have pre-approved high-risk modules)
        4. Render prompt
        5. Call inference
        6. Return result

        Raises ValueError for invalid manifests.
        Does NOT automatically execute high-risk tools — the caller is
        responsible for enforcing the tool policy.
        """
        path = self.root / module_path if not Path(module_path).is_absolute() else Path(module_path)

        # 1. Manifest
        manifest = self.load_manifest(path)
        validation = validate_manifest(manifest)
        if not validation["valid"]:
            raise ValueError(
                f"Invalid module manifest for {manifest.get('id', '?')}: "
                f"missing={validation['missing']}"
            )

        module_id = manifest["id"]
        risk = validation["risk"]
        logger.info("Running module %s (risk=%s)", module_id, risk)

        # 2. Input validation
        input_check = self.validate_input(path, input_data)
        if not input_check["valid"]:
            raise ValueError(
                f"Module input validation failed: missing={input_check['missing']} "
                f"errors={input_check['errors']}"
            )

        # 3. Render prompt
        try:
            rendered = self.render_prompt(path, input_data)
        except Exception as exc:
            return ModuleRunResult(
                module_id=module_id,
                rendered_prompt="",
                risk=risk,
                error=f"Prompt rendering failed: {exc}",
            )

        # 4. Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": rendered})

        # 5. Inference
        try:
            response_msg = await inference.chat(messages)
            response_text = response_msg.get("content", "")
        except Exception as exc:
            logger.exception("Inference failed for module %s", module_id)
            return ModuleRunResult(
                module_id=module_id,
                rendered_prompt=rendered,
                risk=risk,
                error=f"Inference error: {exc}",
            )

        # 6. Optional output write
        output_path: str | None = None
        if output_root:
            out_dir = Path(output_root) / module_id
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "output.md"
            out_file.write_text(response_text, encoding="utf-8")
            output_path = str(out_file)
            logger.info("Module output written to %s", output_path)

        return ModuleRunResult(
            module_id=module_id,
            rendered_prompt=rendered,
            response=response_text,
            output_path=output_path,
            risk=risk,
        )
