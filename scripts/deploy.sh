#!/usr/bin/env bash
# Pull latest from Git and restart the Linux body. Run on the Ubuntu machine.
set -euo pipefail
cd "$(dirname "$0")/.."

git pull --ff-only
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .

if systemctl --user is-enabled jarvis.service >/dev/null 2>&1; then
  systemctl --user restart jarvis.service
  echo "Restarted jarvis.service"
fi
if systemctl --user is-enabled jarvis-autonomy.service >/dev/null 2>&1; then
  systemctl --user restart jarvis-autonomy.service
  echo "Restarted jarvis-autonomy.service"
fi

echo "Deploy complete. Memory is in ${XDG_DATA_HOME:-$HOME/.local/share}/jarvis"
