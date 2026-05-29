REM Used for headless/development startup and as a companion to the Electron desktop shell process flow.
@echo off
setlocal

if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
)

call .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r implementation\backend\requirements.txt

REM Load .env file if present
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
  )
)

REM Start ngrok only if NGROK_DOMAIN is configured
if defined NGROK_DOMAIN (
  echo Starting ngrok tunnel for %NGROK_DOMAIN%...
  start /B ngrok http --domain=%NGROK_DOMAIN% 8000
  timeout /t 2 /nobreak >nul
) else (
  echo NGROK_DOMAIN not set - skipping ngrok tunnel. Set it in .env to enable remote access.
)

start /B python implementation\backend\forge\tool_server.py
start /B python implementation\backend\forge\main.py
start /B python implementation\backend\forge\pentest_server.py
start /B python implementation\backend\forge\router_server.py

echo Forge MCP, Pentest MCP, Router MCP, and FastAPI started.
endlocal
