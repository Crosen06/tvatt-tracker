#!/usr/bin/env bash
# Fetches the latest version from GitHub and restarts the app and the kiosk browser.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT="${TVATT_UNIT_PATH:-/etc/systemd/system/tvatt.service}"
PIP="${TVATT_PIP:-$REPO/.venv/bin/pip}"
cd "$REPO"
git pull --ff-only
"$PIP" install -q -r backend/requirements.txt

# Keep the data folder the app was installed with, then refresh the systemd unit if it changed.
DATA_DIR="$(sed -n 's/^Environment=TVATT_DATA=//p' "$UNIT" 2>/dev/null | head -n1 || true)"
DATA_DIR="${DATA_DIR:-${TVATT_DATA:-$HOME/tvatt-data}}"
"$REPO/deploy/install-service.sh" "$DATA_DIR" >/dev/null

sudo systemctl restart tvatt.service
# kiosk.sh restarts Chromium by itself, so closing it loads the new interface.
pkill -f "user-data-dir=$HOME/.config/tvatt-kiosk" >/dev/null 2>&1 || true
echo "Uppdaterat till $(git log -1 --format='%h %s' 2>/dev/null || echo 'senaste versionen')"
