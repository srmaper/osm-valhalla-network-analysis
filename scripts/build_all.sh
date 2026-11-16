#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export OSM_PBF="${OSM_PBF:-$ROOT/data/input/hong-kong-261113.osm.pbf}"
export NA_DATA_DIR="${NA_DATA_DIR:-$ROOT/data/generated}"
bash "$ROOT/scripts/build_valhalla.sh"
python3 -m na_app.build_osm_idx "$OSM_PBF" "$NA_DATA_DIR/osm_idx.sqlite"
bash "$ROOT/scripts/build_mvt.sh"
python3 "$ROOT/scripts/extract_hk_demo_route.py"
python3 "$ROOT/scripts/generate_hk_samples.py"
python3 "$ROOT/scripts/prepare_driving.py"
