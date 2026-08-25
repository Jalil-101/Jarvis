@echo off
REM Install optional mic / STT / wake-word deps for always-on listen.
cd /d "%~dp0\.."
if not exist ".venv\Scripts\pip.exe" (
  echo No .venv found. Run scripts\install.cmd first.
  exit /b 1
)
echo Installing voice extras (sounddevice, faster-whisper, openWakeWord)...
".venv\Scripts\pip.exe" install -e ".[voice]"
if errorlevel 1 exit /b 1
echo.
echo Done. Always-on:
echo   .\scripts\run.cmd listen
echo Push-to-talk:
echo   .\scripts\run.cmd voice
echo Leave this terminal open while listening.
