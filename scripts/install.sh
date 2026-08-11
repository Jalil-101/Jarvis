#!/usr/bin/env bash
# Ubuntu/Debian install for the Jarvis body.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v python3 >/dev/null; then
  echo "Install Python 3.12+: sudo apt install python3 python3-venv python3-pip"
  exit 1
fi

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .
# Optional voice extras (uncomment when the mic/speakers are attached):
# .venv/bin/pip install -e ".[voice]"

DATA="${XDG_DATA_HOME:-$HOME/.local/share}/jarvis"
mkdir -p "$DATA/sandbox"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env — set ANTHROPIC_API_KEY before running."
fi

echo "Installed. Data dir: $DATA"
echo "Run:  source .venv/bin/activate && python -m jarvis"
echo "Linux service: ./scripts/setup-linux.sh"
