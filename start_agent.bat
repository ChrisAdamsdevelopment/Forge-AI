REM Used for headless/development startup and as a companion to the Electron desktop shell process flow.
@echo off
setlocal

if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
)

call .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r implementation\backend\requirements.txt

set NGROK_DOMAIN=fossil-unicorn-defuse.ngrok-free.dev

start /B ngrok http --domain=fossil-unicorn-defuse.ngrok-free.dev 8000

timeout /t 2 /nobreak >nul

start /B python implementation\backend\forge\tool_server.py
start /B python implementation\backend\forge\main.py

echo Forge MCP, FastAPI, and ngrok started.
endlocal
