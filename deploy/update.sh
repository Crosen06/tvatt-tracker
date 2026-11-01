#!/usr/bin/env bash
# Fetches the latest version from GitHub and restarts the app and the kiosk browser.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
git pull --ff-only
"$REPO/.venv/bin/pip" install -q -r backend/requirements.txt
sudo systemctl restart tvatt.service
# kiosk.sh restarts Chromium by itself, so closing it loads the new interface.
pkill -f "user-data-dir=$HOME/.config/tvatt-kiosk" >/dev/null 2>&1 || true
echo "Uppdaterat till $(git log -1 --format='%h %s')"
