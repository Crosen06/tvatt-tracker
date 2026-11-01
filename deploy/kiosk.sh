#!/usr/bin/env bash
# Opens the tracker full-screen on the Pi's touch screen. Started by the desktop autostart
# entry that install.sh creates (~/.config/autostart/tvatt-kiosk.desktop).
# Chromium is restarted automatically if it crashes or is closed.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="${TVATT_BASE:-http://localhost}"
URL="${TVATT_URL:-$BASE/?kiosk=1}"
PROFILE="$HOME/.config/tvatt-kiosk"
WAIT_SECONDS="${TVATT_WAIT_SECONDS:-120}"

# Wait for the server to answer.
for _ in $(seq 1 "$WAIT_SECONDS"); do
  curl -fs --max-time 2 "$BASE/api/health" >/dev/null 2>&1 && break
  sleep 1
done

BROWSER="$(command -v chromium || command -v chromium-browser || true)"
if [ -z "$BROWSER" ]; then
  echo "kiosk.sh: Chromium is not installed" >&2
  exit 1
fi

# After a power cut Chromium thinks it crashed and offers to restore pages. Tell it all is well.
clear_crash_flag() {
  local prefs="$PROFILE/Default/Preferences"
  [ -f "$prefs" ] || return 0
  sed -i -e 's/"exit_type":"[A-Za-z]*"/"exit_type":"Normal"/' \
         -e 's/"exited_cleanly":false/"exited_cleanly":true/' "$prefs"
}

launch() {
  clear_crash_flag
  "$BROWSER" \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --no-default-browser-check \
    --disable-session-crashed-bubble \
    --disable-features=Translate \
    --password-store=basic \
    --overscroll-history-navigation=0 \
    --disable-pinch \
    --check-for-update-interval=31536000 \
    --ozone-platform-hint=auto \
    --user-data-dir="$PROFILE" \
    "$URL"
}

if [ -n "${TVATT_KIOSK_ONCE:-}" ]; then
  launch
  exit 0
fi

"$HERE/wake-on-done.sh" &
trap 'kill $! 2>/dev/null' EXIT

while true; do
  launch
  sleep 3
done
