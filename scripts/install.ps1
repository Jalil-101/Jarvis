# Create venv and install dependencies (Windows)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -r requirements.txt
& .\.venv\Scripts\pip.exe install -e .

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env — add your ANTHROPIC_API_KEY before chatting."
}

Write-Host "Done. Activate with: .\.venv\Scripts\Activate.ps1"
Write-Host "Then run: python -m jarvis"
