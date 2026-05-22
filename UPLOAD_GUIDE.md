# Upload Guide for the Forge Source Pack

Use this file to decide what belongs in project sources.

## Upload these as project sources

- `docs/project_brief.md`
- `docs/architecture_overview.md`
- `docs/architecture_layers.md`
- `docs/tasker_style_module_system.md`
- `docs/operating_rules.md`
- `docs/file_roots.md`
- `docs/rag_policy.md`
- `docs/source_manifest.yaml`
- `docs/glossary.md`
- `docs/style_guide.md`
- `docs/examples.md`
- `docs/sop_research.md`
- `docs/sop_coding.md`
- `docs/sop_file_ops.md`
- `docs/security_model.md`
- `docs/roadmap.md`
- `prompts/project_prime_prompt.md`
- `modules/specs/module_architecture.md`
- `modules/specs/module_manifest_spec.yaml`
- `modules/specs/module_safety_contract.md`
- `modules/specs/module_marketplace_model.md`

## Keep these out of RAG unless building code

- `runtime/Modelfile`
- `runtime/mcp.json`
- `runtime/docker-compose.yaml`
- `.env.example`
- `implementation/`
- `training/example_data/train.jsonl`
- `training/example_data/valid.jsonl`

## Never upload these when real values exist

- API keys
- SSH keys
- browser cookies
- password-manager exports
- full home directory listings
- `.env` files with secrets
- private legal/medical/financial records unless intentionally needed and isolated
