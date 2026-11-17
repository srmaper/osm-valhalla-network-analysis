#!/usr/bin/env bash
# One entry point: give it an OSM PBF file (local path or Geofabrik URL) and it
# builds all data, builds the web app, and starts Valhalla + the API.
#
#   bash scripts/oneclick.sh /path/to/region.osm.pbf
#   bash scripts/oneclick.sh https://download.geofabrik.de/.../region-latest.osm.pbf
#   bash scripts/oneclick.sh region.osm.pbf --build-only
#
# Environment overrides:
#   OSM_PBF / NA_DATA_DIR / NA_PORT / VALHALLA_PORT / VALHALLA_THREADS
#   VALHALLA_BIN_DIR (directory holding valhalla_* executables)
#   SKIP_WEB=1 (reuse existing webapp/dist)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Load local overrides (gitignored): VALHALLA_CONFIG, SKIP_WEB, ports, etc.
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
PY="${PYTHON:-python3}"
if [[ -n "${VALHALLA_BIN_DIR:-}" ]]; then
  PATH="$VALHALLA_BIN_DIR:$PATH"
  export PATH
fi
NA_PORT="${NA_PORT:-8004}"
VALHALLA_PORT="${VALHALLA_PORT:-8002}"
DATA_DIR="${NA_DATA_DIR:-$ROOT/data/generated}"
RUN_DIR="$ROOT/.run"
BUILD_ONLY=0
ARG_PBF=""

for arg in "$@"; do
  case "$arg" in
    --build-only) BUILD_ONLY=1 ;;
    -h|--help) sed -n '1,18p' "$0"; exit 0 ;;
    *) ARG_PBF="$arg" ;;
  esac
done

step() { printf '\n==> %s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || fail "missing required tool: $1"; }
need curl
need "$PY"
"$PY" -c 'import osmium' >/dev/null 2>&1 || fail "pyosmium missing: $PY -m pip install osmium"
need valhalla_service

# ---------- 1. input ----------
mkdir -p "$ROOT/data/input" "$DATA_DIR" "$RUN_DIR"
if [[ -n "$ARG_PBF" && "$ARG_PBF" =~ ^https?:// ]]; then
  name="$(basename "${ARG_PBF%%\?*}")"
  PBF="${OSM_PBF:-$ROOT/data/input/$name}"
  if [[ ! -s "$PBF" ]]; then
    step "Downloading $name"
    curl -fL --retry 3 --progress-bar -o "$PBF.part" "$ARG_PBF"
    mv "$PBF.part" "$PBF"
  else
    echo "Using cached download: $PBF"
  fi
elif [[ -n "$ARG_PBF" ]]; then
  PBF="$(cd "$(dirname "$ARG_PBF")" && pwd)/$(basename "$ARG_PBF")"
elif [[ -n "${OSM_PBF:-}" ]]; then
  PBF="$OSM_PBF"
else
  fail "usage: bash scripts/oneclick.sh <region.osm.pbf|url> [--build-only]"
fi
[[ -s "$PBF" ]] || fail "OSM file is empty or missing: $PBF"
export OSM_PBF="$PBF"
echo "OSM input: $PBF"

# ---------- 2. region + demo data (cheap, always refresh) ----------
step "Deriving region bounds and demo fixtures"
"$PY" scripts/prepare_region.py "$PBF"
"$PY" scripts/prepare_demo.py "$PBF"

# ---------- 3. Valhalla routing graph ----------
OWN_VALHALLA=0
VALHALLA_CONFIG="${VALHALLA_CONFIG:-}"
if [[ -n "$VALHALLA_CONFIG" ]]; then
  [[ -f "$VALHALLA_CONFIG" ]] || fail "VALHALLA_CONFIG not found: $VALHALLA_CONFIG"
  echo "Using existing Valhalla config: $VALHALLA_CONFIG (graph build skipped)"
elif [[ -f "$DATA_DIR/valhalla/valhalla.json" && -s "$DATA_DIR/valhalla/tiles.tar" ]]; then
  echo "Valhalla graph already present, skipping rebuild (remove $DATA_DIR/valhalla to rebuild)"
  VALHALLA_CONFIG="$DATA_DIR/valhalla/valhalla.json"
  OWN_VALHALLA=1
else
  step "Building Valhalla routing graph"
  for tool in valhalla_build_config valhalla_build_admins valhalla_build_tiles \
              valhalla_build_extract; do
    command -v "$tool" >/dev/null 2>&1 || fail "missing Valhalla tool: $tool (set VALHALLA_BIN_DIR or PATH)"
  done
  bash scripts/build_valhalla.sh
  VALHALLA_CONFIG="$DATA_DIR/valhalla/valhalla.json"
  OWN_VALHALLA=1
fi

# ---------- 4. road attribute index ----------
step "Building OSM road index"
"$PY" -m na_app.build_osm_idx "$PBF" "$DATA_DIR/osm_idx.sqlite"

# ---------- 5. vector road tiles ----------
if [[ -s "$DATA_DIR/roads_cn.mbtiles" ]]; then
  echo "Road tiles already present, skipping rebuild (remove $DATA_DIR/roads_cn.mbtiles to rebuild)"
else
  step "Building vector road tiles"
  need ogr2ogr
  need tippecanoe
  bash scripts/build_mvt.sh
fi

# ---------- 6. web bundle ----------
if [[ "${SKIP_WEB:-0}" != "1" ]]; then
  step "Building web app"
  need npm
  bash scripts/build_web.sh
else
  echo "SKIP_WEB=1: reusing webapp/dist"
fi

if [[ "$BUILD_ONLY" == "1" ]]; then
  step "Build complete (services not started)"
  echo "Valhalla data:  $DATA_DIR/valhalla"
  echo "Road index:     $DATA_DIR/osm_idx.sqlite"
  echo "Road tiles:     $DATA_DIR/roads_cn.mbtiles"
  echo "Web bundle:     $ROOT/webapp/dist"
  exit 0
fi

# ---------- 7. services ----------
stop_pidfile() {
  local f="$1"
  [[ -s "$f" ]] || return 0
  local pid; pid="$(cat "$f")"
  kill "$pid" 2>/dev/null || true
  rm -f "$f"
}

step "Starting services"
stop_pidfile "$RUN_DIR/valhalla.pid"
stop_pidfile "$RUN_DIR/api.pid"

if [[ "$OWN_VALHALLA" == "1" ]]; then
  export VALHALLA_PORT
  "$PY" scripts/configure_valhalla.py "$VALHALLA_CONFIG" "$(dirname "$VALHALLA_CONFIG")"
fi
setsid nohup valhalla_service "$VALHALLA_CONFIG" "${VALHALLA_THREADS:-2}" \
  >"$RUN_DIR/valhalla.log" 2>&1 </dev/null &
echo $! > "$RUN_DIR/valhalla.pid"

export VALHALLA_URL="${VALHALLA_URL:-http://127.0.0.1:$VALHALLA_PORT}"
export NA_HOST="${NA_HOST:-127.0.0.1}"
export NA_PORT
export NA_DATA_DIR="$DATA_DIR"
setsid nohup uvicorn na_app.main:app --host "$NA_HOST" --port "$NA_PORT" \
  >"$RUN_DIR/api.log" 2>&1 </dev/null &
echo $! > "$RUN_DIR/api.pid"

for _ in $(seq 1 40); do
  if curl -fsS -m 1 "$VALHALLA_URL/status" >/dev/null 2>&1 \
     && curl -fsS -m 1 "http://$NA_HOST:$NA_PORT/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

step "Ready"
echo "Analyzer:  http://$NA_HOST:$NA_PORT/network/"
echo "API docs:  http://$NA_HOST:$NA_PORT/docs"
echo "Valhalla:  $VALHALLA_URL/status"
echo "Logs:      $RUN_DIR/valhalla.log  $RUN_DIR/api.log"
echo "Stop:      kill \$(cat $RUN_DIR/valhalla.pid) \$(cat $RUN_DIR/api.pid)"
