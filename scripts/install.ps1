# Create venv and install dependencies (Windows workshop)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (-not (Test-Path $py)) {
    $py = "python"
}

if (-not (Test-Path .venv)) {
    & $py -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -r requirements.txt
& .\.venv\Scripts\pip.exe install -e .

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env — add your ANTHROPIC_API_KEY before chatting."
}

Write-Host "Done. PowerShell often blocks Activate.ps1 — skip it and use:"
Write-Host "  .\scripts\run.cmd"
Write-Host "  .\scripts\test.cmd"
Write-Host "TTS smoke: .\scripts\run.cmd speak `"Yes, sir?`""
Write-Host "Optional mic/STT: .\.venv\Scripts\pip.exe install -e `".[voice]`""
