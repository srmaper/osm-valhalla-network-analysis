#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${NA_DATA_DIR:-$ROOT/data/generated}"
CONFIG="$DATA_DIR/valhalla/valhalla.json"
[[ -f "$CONFIG" ]] || { echo "Build Valhalla data first: $CONFIG not found" >&2; exit 1; }
exec valhalla_service "$CONFIG" "${VALHALLA_THREADS:-2}"
