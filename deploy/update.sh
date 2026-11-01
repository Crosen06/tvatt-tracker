#!/usr/bin/env bash
# Fetches the latest version from GitHub and restarts the app and the kiosk browser.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT="${TVATT_UNIT_PATH:-/etc/systemd/system/tvatt.service}"
PIP="${TVATT_PIP:-$REPO/.venv/bin/pip}"
cd "$REPO"
git pull --ff-only
"$PIP" install -q -r backend/requirements.txt
# Optional, better barcode reader. Scanning still works with OpenCV if it cannot be installed.
"$PIP" install -q zxing-cpp || echo "zxing-cpp kunde inte installeras; streckkoder läses med OpenCV i stället."

# Keep the data folder the app was installed with, then refresh the systemd unit if it changed.
DATA_DIR="$(sed -n 's/^Environment=TVATT_DATA=//p' "$UNIT" 2>/dev/null | head -n1 || true)"
DATA_DIR="${DATA_DIR:-${TVATT_DATA:-$HOME/tvatt-data}}"
"$REPO/deploy/install-service.sh" "$DATA_DIR" >/dev/null
# Image model for recognising pantry items. Optional: barcodes work without it.
"$REPO/deploy/get-model.sh" "$DATA_DIR" || echo "Bildmodellen kunde inte hämtas; bildigenkänningen i köket är avstängd tills den finns."

sudo systemctl restart tvatt.service
# kiosk.sh restarts Chromium by itself, so closing it loads the new interface.
pkill -f "user-data-dir=$HOME/.config/tvatt-kiosk" >/dev/null 2>&1 || true
echo "Uppdaterat till $(git log -1 --format='%h %s' 2>/dev/null || echo 'senaste versionen')"
