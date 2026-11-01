#!/usr/bin/env bash
# Run the backend locally on port 8000 with a throwaway data dir.
set -euo pipefail
cd "$(dirname "$0")/../backend"
export TVATT_DATA="${TVATT_DATA:-/tmp/tvatt-dev}"
exec "${PYTHON:-python3}" -m uvicorn --factory app.main:create_app --host 0.0.0.0 --port "${PORT:-8000}" --reload
