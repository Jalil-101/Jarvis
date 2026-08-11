@echo off
REM Run unit tests using the venv interpreter (no PowerShell execution policy needed).
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  echo No .venv found. Run scripts\install.cmd first.
  exit /b 1
)
".venv\Scripts\python.exe" -m unittest discover -s tests -v %*
