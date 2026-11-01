#!/usr/bin/env bash
# Opens the tracker full-screen on the Pi's touch screen. Started by the desktop autostart
# entry that install.sh creates (~/.config/autostart/tvatt-kiosk.desktop).
# Chromium is restarted automatically if it crashes or is closed.
set -u

URL="${TVATT_URL:-http://localhost/?kiosk=1}"
PROFILE="$HOME/.config/tvatt-kiosk"

# Wait (up to two minutes) for the server to answer.
for _ in $(seq 1 120); do
  curl -fs http://localhost/api/health >/dev/null 2>&1 && break
  sleep 1
done

BROWSER="$(command -v chromium || command -v chromium-browser || true)"
if [ -z "$BROWSER" ]; then
  echo "kiosk.sh: Chromium is not installed" >&2
  exit 1
fi

while true; do
  "$BROWSER" \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-features=Translate \
    --password-store=basic \
    --overscroll-history-navigation=0 \
    --disable-pinch \
    --check-for-update-interval=31536000 \
    --ozone-platform-hint=auto \
    --user-data-dir="$PROFILE" \
    "$URL"
  sleep 3
done
