# Run Jarvis text chat
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$python = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "No .venv found. Run .\scripts\install.ps1 first."
    exit 1
}

if (-not (Test-Path .env)) {
    Write-Host "Missing .env — copy .env.example and set ANTHROPIC_API_KEY."
    exit 1
}

& $python -m jarvis @args
