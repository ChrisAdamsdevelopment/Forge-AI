# Contributing to Forge-AI

Thank you for helping improve Forge-AI. This project provides powerful local
system automation and authorized security-assessment capabilities, so changes
must be reviewed carefully.

## Before You Start

1. Read [SECURITY.md](SECURITY.md) and only contribute functionality intended
   for lawful, authorized use.
2. Open an issue or draft PR for significant design changes before investing
   substantial implementation time.
3. Never commit secrets, tokens, passwords, `.env` files, generated runtime
   data, or private assessment output.

## Development Setup

```bash
git clone https://github.com/ChrisAdamsdevelopment/Forge-AI.git
cd Forge-AI
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r implementation/backend/requirements.txt
playwright install chromium
cp .env.example .env
```

## Code Style

- Follow PEP 8 and keep functions small, typed, and testable.
- Use `pathlib` for filesystem paths.
- Load configuration from environment variables or `.env`; do not hardcode
  user-specific paths, credentials, domains, tokens, or router details.
- Use ruff for linting and formatting-compatible cleanup.
- Avoid broad exception swallowing. Return structured errors where tool calls
  can fail due to environment limitations.

## Tests and Checks

Run these from `implementation/backend` before submitting a PR:

```bash
python -m compileall forge/
ruff check forge/
pytest tests/ -v
python -c "from forge.agent.tools import registry; print(len(registry.list_tools()))"
```

If a check cannot run because of a missing local dependency such as WSL, OpenWrt,
Ollama, or a display server, document that limitation in the PR.

## Pull Request Process

1. Keep PRs focused on one feature, fix, or documentation update.
2. Include a clear summary, testing performed, and any security implications.
3. Link related issues.
4. Update README, SECURITY, THREAT_MODEL, and `.env.example` when behavior or
   configuration changes.
5. Maintainers may request additional review for changes touching tool execution,
   filesystem access, router control, pentest workflows, or persistent memory.

## Security Contributions

Report vulnerabilities privately using the process in [SECURITY.md](SECURITY.md).
Do not open public issues containing exploit details, secrets, or reproduction
steps that could put users at risk.
