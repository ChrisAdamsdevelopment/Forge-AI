#!/usr/bin/env bash
set -euo pipefail

MODEL_NAME="${1:-forge-qwen}"
MODEFILE_PATH="${2:-../../runtime/Modelfile}"

ollama create "$MODEL_NAME" -f "$MODEFILE_PATH"
ollama list
