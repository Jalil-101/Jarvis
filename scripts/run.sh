#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo "Run ./scripts/install.sh first."
  exit 1
fi
exec .venv/bin/python -m jarvis "$@"
