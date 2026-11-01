#!/usr/bin/env bash
# Renders deploy/tvatt.service and installs it when it differs from the installed unit.
# Used by install.sh and update.sh. Prints "changed" or "unchanged".
#
#   deploy/install-service.sh DATA_DIR
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${1:?usage: install-service.sh DATA_DIR}"
UNIT="${TVATT_UNIT_PATH:-/etc/systemd/system/tvatt.service}"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
sed -e "s|@USER@|$(id -un)|g" -e "s|@REPO@|$REPO|g" -e "s|@DATA@|$DATA_DIR|g" "$REPO/deploy/tvatt.service" > "$tmp"

if [ -f "$UNIT" ] && cmp -s "$tmp" "$UNIT"; then
  echo unchanged
  exit 0
fi
sudo install -m 644 "$tmp" "$UNIT"
sudo systemctl daemon-reload
echo changed
