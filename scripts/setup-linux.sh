#!/usr/bin/env bash
# Install systemd --user units so Jarvis starts on login / reboot.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/jarvis"
mkdir -p "$DATA" "$HOME/.config/systemd/user"

if [[ ! -x .venv/bin/python ]]; then
  echo "Run ./scripts/install.sh first."
  exit 1
fi

render() {
  sed -e "s|@REPO@|$REPO|g" -e "s|@DATA@|$DATA|g" "$1"
}

render scripts/jarvis.service > "$HOME/.config/systemd/user/jarvis.service"
render scripts/jarvis-autonomy.service > "$HOME/.config/systemd/user/jarvis-autonomy.service"

systemctl --user daemon-reload
systemctl --user enable --now jarvis.service
echo "Jarvis listen service enabled."
echo "Optional autonomy: systemctl --user enable --now jarvis-autonomy.service"
echo "Logs: journalctl --user -u jarvis -f"
echo "Deploy later with: ./scripts/deploy.sh"
