#!/usr/bin/env bash
# Downloads the image model used to recognise pantry items (MobileNetV2 from OpenCV Zoo, Apache-2.0)
# into <data dir>/models. Safe to run again: does nothing when the file is there with the right checksum.
# Usage: deploy/get-model.sh [data dir]
set -euo pipefail
DATA_DIR="${1:-${TVATT_DATA:-$HOME/tvatt-data}}"
URL="${TVATT_MODEL_URL:-https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/image_classification_mobilenet/image_classification_mobilenetv2_2022apr.onnx}"
SHA256="${TVATT_MODEL_SHA256:-c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5}"
DEST="$DATA_DIR/models/mobilenetv2.onnx"

mkdir -p "$DATA_DIR/models"
if [ -f "$DEST" ] && echo "$SHA256  $DEST" | sha256sum -c --status; then
  echo "Bildmodellen finns redan."
  exit 0
fi
TMP="$(mktemp "$DATA_DIR/models/.download.XXXXXX")"
trap 'rm -f "$TMP"' EXIT
echo "Hämtar bildmodellen (14 MB)…"
curl -fsSL --retry 3 --connect-timeout 20 -o "$TMP" "$URL"
if ! echo "$SHA256  $TMP" | sha256sum -c --status; then
  echo "Bildmodellen som hämtades hade fel kontrollsumma och sparades inte." >&2
  exit 1
fi
mv "$TMP" "$DEST"
trap - EXIT
echo "Bildmodellen sparades i $DEST"
