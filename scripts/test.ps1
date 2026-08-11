# Run unit tests (Windows workshop)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$python = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "No .venv found. Run .\scripts\install.cmd first."
    exit 1
}

& $python -m unittest discover -s tests -v @args
