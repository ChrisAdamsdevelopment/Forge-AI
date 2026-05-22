#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

export FORGE_HOST="${FORGE_HOST:-127.0.0.1}"
export FORGE_PORT="${FORGE_PORT:-9147}"
export FORGE_OLLAMA_BASE_URL="${FORGE_OLLAMA_BASE_URL:-http://127.0.0.1:11434}"

uvicorn forge.main:app --host "$FORGE_HOST" --port "$FORGE_PORT" --reload
