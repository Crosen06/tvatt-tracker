#!/usr/bin/env bash
# Downloads the image models used to recognise pantry items into <data dir>/models:
#   - MobileNetV2 (OpenCV Zoo, Apache-2.0): fingerprints of the item. Required for recognition.
#   - YuNet face detector (OpenCV Zoo, MIT): keeps faces out of the item's outline. Optional.
# Safe to run again: a file already there with the right checksum is not downloaded again.
# Exits 1 only when MobileNetV2 could not be fetched.
# Usage: deploy/get-model.sh [data dir]
set -euo pipefail
DATA_DIR="${1:-${TVATT_DATA:-$HOME/tvatt-data}}"
ZOO="https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"
URL="${TVATT_MODEL_URL:-$ZOO/image_classification_mobilenet/image_classification_mobilenetv2_2022apr.onnx}"
SHA256="${TVATT_MODEL_SHA256:-c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5}"
FACE_URL="${TVATT_FACE_URL:-$ZOO/face_detection_yunet/face_detection_yunet_2023mar.onnx}"
FACE_SHA256="${TVATT_FACE_SHA256:-8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4}"

mkdir -p "$DATA_DIR/models"

# fetch <name for messages> <size text> <url> <sha256> <destination>
fetch() {
  local name="$1" size="$2" url="$3" sha="$4" dest="$5" tmp
  if [ -f "$dest" ] && echo "$sha  $dest" | sha256sum -c --status; then
    echo "$name finns redan."
    return 0
  fi
  tmp="$(mktemp "$DATA_DIR/models/.download.XXXXXX")"
  echo "Hämtar ${name,,} ($size)…"
  if ! curl -fsSL --retry 3 --connect-timeout 20 -o "$tmp" "$url"; then
    rm -f "$tmp"
    return 1
  fi
  if ! echo "$sha  $tmp" | sha256sum -c --status; then
    rm -f "$tmp"
    echo "$name som hämtades hade fel kontrollsumma och sparades inte." >&2
    return 1
  fi
  mv "$tmp" "$dest"
  echo "$name sparades i $dest"
}

status=0
fetch "Bildmodellen" "14 MB" "$URL" "$SHA256" "$DATA_DIR/models/mobilenetv2.onnx" || status=1
fetch "Ansiktsmodellen" "0,2 MB" "$FACE_URL" "$FACE_SHA256" "$DATA_DIR/models/face_yunet.onnx" \
  || echo "Ansiktsmodellen kunde inte hämtas; ansikten filtreras inte bort." >&2
exit "$status"
