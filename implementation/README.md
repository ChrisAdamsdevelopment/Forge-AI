# Implementation Scaffold

This folder contains a minimal buildable starting point, not the finished application.

## First backend run

```bash
cd implementation/backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
uvicorn forge.main:app --host 127.0.0.1 --port 9147 --reload
```

## Test health

```bash
curl http://127.0.0.1:9147/health
```

## Test chat

Make sure Ollama is running and a model exists.

```bash
curl -X POST http://127.0.0.1:9147/api/v1/chat \
  -H "Authorization: Bearer $(cat ~/.forge/auth.key)" \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Say Forge is online."}]}'
```
