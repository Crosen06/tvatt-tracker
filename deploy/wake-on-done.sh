#!/usr/bin/env bash
# Turns the Pi's screen on when a wash is finished, so "Tvätten är klar!" is actually seen
# even if the screen has blanked. Started in the background by kiosk.sh.
# While the notice is waiting for someone, the screen is kept on (checked every 30 s).
#
#   wake-on-done.sh          run forever
#   wake-on-done.sh --once   check once (used by tests)
set -u
BASE="${TVATT_BASE:-http://localhost}"
INTERVAL="${TVATT_WAKE_INTERVAL:-30}"

screen_on() {
  if command -v wlopm >/dev/null 2>&1; then
    wlopm --on '*' >/dev/null 2>&1
  elif command -v xset >/dev/null 2>&1; then
    DISPLAY="${DISPLAY:-:0}" xset dpms force on >/dev/null 2>&1
  fi
}

check() {
  local json
  json="$(curl -fs --max-time 5 "$BASE/api/washes/current" 2>/dev/null)" || return 0
  if printf '%s' "$json" | grep -q '"is_done": *true'; then
    screen_on
  fi
}

if [ "${1:-}" = "--once" ]; then
  check
  exit 0
fi

while true; do
  check
  sleep "$INTERVAL"
done
