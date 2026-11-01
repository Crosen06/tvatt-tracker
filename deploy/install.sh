#!/usr/bin/env bash
# Installs Tvätt-tracker on Raspberry Pi OS (desktop). Safe to run again.
#
#   ./deploy/install.sh              full install
#   ./deploy/install.sh --no-hostname   keep the current hostname
#   ./deploy/install.sh --no-kiosk      server only (no full-screen browser on boot)
#
# Decisions (researched November 2026):
# - Desktop autostart uses an XDG .desktop file (~/.config/autostart). Raspberry Pi OS's
#   labwc session runs these, and unlike ~/.config/labwc/autostart it does not replace the
#   system autostart (panel, screen blanking).
# - The browser package is "chromium" on current Pi OS, "chromium-browser" on older images.
# - raspi-config nonint: do_hostname sets the mDNS name (tvatt.local), do_boot_behaviour B4
#   boots to the desktop with auto-login, do_blanking 0 turns screen blanking on.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${TVATT_DATA:-$HOME/tvatt-data}"
HOSTNAME_WANTED="tvatt"
SET_HOSTNAME=1
SET_KIOSK=1

for arg in "$@"; do
  case "$arg" in
    --no-hostname) SET_HOSTNAME=0 ;;
    --no-kiosk) SET_KIOSK=0 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "Okänt val: $arg" >&2; exit 2 ;;
  esac
done

if [ "$(id -u)" -eq 0 ]; then
  echo "Kör skriptet som din vanliga användare (utan sudo). Det frågar efter lösenord när det behövs." >&2
  exit 1
fi

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }

step "Installerar systempaket"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip avahi-daemon curl
if [ "$SET_KIOSK" -eq 1 ] && ! command -v chromium >/dev/null && ! command -v chromium-browser >/dev/null; then
  sudo apt-get install -y chromium || sudo apt-get install -y chromium-browser
fi
if [ "$SET_KIOSK" -eq 1 ]; then
  # wlopm turns the screen on when a wash is done (Wayland). Optional: skip if unavailable.
  sudo apt-get install -y wlopm || echo "wlopm saknas; skärmen tänds inte automatiskt när tvätten är klar."
fi

step "Skapar Python-miljö"
python3 -m venv "$REPO/.venv"
"$REPO/.venv/bin/pip" install --upgrade pip
"$REPO/.venv/bin/pip" install -r "$REPO/backend/requirements.txt"
# Optional, better barcode reader. Scanning still works with OpenCV if it cannot be installed.
"$REPO/.venv/bin/pip" install -q zxing-cpp || echo "zxing-cpp kunde inte installeras; streckkoder läses med OpenCV i stället."
mkdir -p "$DATA_DIR"
# Image model for recognising pantry items. Optional: barcodes work without it.
chmod +x "$REPO/deploy/get-model.sh"
"$REPO/deploy/get-model.sh" "$DATA_DIR" || echo "Bildmodellen kunde inte hämtas; bildigenkänningen i köket är avstängd tills den finns."

step "Installerar tjänsten tvatt"
chmod +x "$REPO/deploy/install-service.sh"
"$REPO/deploy/install-service.sh" "$DATA_DIR" >/dev/null
sudo systemctl enable tvatt.service
sudo systemctl restart tvatt.service
for _ in $(seq 1 30); do
  curl -fs http://localhost/api/health >/dev/null 2>&1 && break
  sleep 1
done
if curl -fs http://localhost/api/health >/dev/null 2>&1; then
  echo "Servern svarar på http://localhost"
else
  echo "Servern svarar inte. Se loggen med: journalctl -u tvatt -n 50" >&2
  exit 1
fi

if [ "$SET_HOSTNAME" -eq 1 ] && [ "$(hostname)" != "$HOSTNAME_WANTED" ]; then
  step "Byter värdnamn till $HOSTNAME_WANTED (nås som http://$HOSTNAME_WANTED.local)"
  if command -v raspi-config >/dev/null; then
    sudo raspi-config nonint do_hostname "$HOSTNAME_WANTED"
  else
    old="$(hostname)"
    sudo hostnamectl set-hostname "$HOSTNAME_WANTED"
    sudo sed -i "s/\b$old\b/$HOSTNAME_WANTED/g" /etc/hosts
  fi
  NEEDS_REBOOT=1
fi

if [ "$SET_KIOSK" -eq 1 ]; then
  step "Ställer in helskärm på touchskärmen"
  if command -v raspi-config >/dev/null; then
    sudo raspi-config nonint do_boot_behaviour B4
    sudo raspi-config nonint do_blanking 0
  fi
  mkdir -p "$HOME/.config/autostart"
  chmod +x "$REPO/deploy/kiosk.sh" "$REPO/deploy/wake-on-done.sh"
  cat > "$HOME/.config/autostart/tvatt-kiosk.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Tvätt-tracker
Comment=Visar tvätt-trackern i helskärm
Exec=$REPO/deploy/kiosk.sh
Terminal=false
X-GNOME-Autostart-enabled=true
DESKTOP
  NEEDS_REBOOT=1
fi

tz="$(timedatectl show -p Timezone --value 2>/dev/null || echo unknown)"
if [ "$tz" = "Etc/UTC" ] || [ "$tz" = "UTC" ]; then
  echo
  echo "Obs: tidszonen är $tz. Klockan på skärmen visar då fel tid. Ändra med:"
  echo "  sudo timedatectl set-timezone Europe/Stockholm"
fi

step "Klart"
echo "Öppna http://$HOSTNAME_WANTED.local i mobilen (samma wifi) för att lägga till plagg."
echo "Data sparas i $DATA_DIR"
if [ "${NEEDS_REBOOT:-0}" -eq 1 ]; then
  echo "Starta om Pi:n för att allt ska slå igenom:  sudo reboot"
fi
