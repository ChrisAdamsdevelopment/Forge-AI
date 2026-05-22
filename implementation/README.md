# Implementation Scaffold

This folder contains a minimal buildable starting point, not the finished application.

## First backend run

```bash
cd implementation/backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
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
  -H 'Content-Type: application/json' \
  -d '{"message":"Say Forge is online."}'
```
