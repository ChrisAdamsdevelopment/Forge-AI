# Forge Backend

Minimal backend scaffold for the Forge API.

## Setup

```bash
cd implementation/backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Run

```bash
cd implementation/backend
uvicorn forge.main:app --host 127.0.0.1 --port 9147 --reload
```

## Tests

```bash
cd implementation/backend
python -m pytest -q
```

## Protected API example

```bash
curl -X POST http://127.0.0.1:9147/api/v1/chat \
  -H "Authorization: Bearer $(cat ~/.forge/auth.key)" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Say Forge is online."}]}'
```
