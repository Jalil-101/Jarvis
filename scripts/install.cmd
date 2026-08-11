@echo off
setlocal
cd /d "%~dp0\.."

set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
  echo Python 3.12 not found at %PY%
  echo Install Python 3.12+ from python.org and tick "Add python.exe to PATH".
  exit /b 1
)

if not exist .venv (
  "%PY%" -m venv .venv
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\pip.exe" install -r requirements.txt
".venv\Scripts\pip.exe" install -e .

if not exist .env (
  copy .env.example .env >nul
  echo Created .env — add your ANTHROPIC_API_KEY before chatting.
)

echo.
echo Done. Do not type "python" or "jarvis" in PowerShell — use these:
echo   .\scripts\test.cmd
echo   .\scripts\run.cmd
echo   .\scripts\run.cmd speak "Yes, sir?"
echo   .\scripts\run.cmd --once "Good evening."
endlocal
