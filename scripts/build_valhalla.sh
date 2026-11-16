#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PBF="${OSM_PBF:-$ROOT/data/input/hong-kong-261113.osm.pbf}"
DATA_DIR="${NA_DATA_DIR:-$ROOT/data/generated}"
TARGET="$DATA_DIR/valhalla"
BIN="${VALHALLA_BIN_DIR:-}"

if [[ -n "$BIN" ]]; then PATH="$BIN:$PATH"; fi
for tool in valhalla_build_config valhalla_build_admins valhalla_build_tiles valhalla_build_extract; do
  command -v "$tool" >/dev/null || { echo "Missing Valhalla tool: $tool" >&2; exit 1; }
done
[[ -f "$PBF" ]] || { echo "PBF not found: $PBF" >&2; exit 1; }

if [[ -e "$TARGET" ]]; then
  echo "Refusing to overwrite existing output: $TARGET" >&2
  echo "Move it aside yourself before rebuilding." >&2
  exit 1
fi
mkdir -p "$DATA_DIR"
mkdir "$TARGET"
mkdir "$TARGET/tiles"

args=(--mjolnir-tile-dir "$TARGET/tiles"
      --mjolnir-tile-extract "$TARGET/tiles.tar"
      --mjolnir-concurrency "${VALHALLA_JOBS:-$(nproc)}"
      --mjolnir-max-cache-size "${VALHALLA_CACHE_MB:-2048}")
if valhalla_build_config --help 2>&1 | grep -qE '^[[:space:]]+(-o|--output) '; then
  valhalla_build_config "${args[@]}" -o "$TARGET/valhalla.json"
else
  valhalla_build_config "${args[@]}" > "$TARGET/valhalla.json"
fi
python3 "$ROOT/scripts/configure_valhalla.py" "$TARGET/valhalla.json" "$TARGET"

echo "[1/3] Building administrative areas"
valhalla_build_admins -c "$TARGET/valhalla.json" "$PBF"
echo "[2/3] Building routing tiles"
valhalla_build_tiles -c "$TARGET/valhalla.json" "$PBF"
echo "[3/3] Building tile extract"
valhalla_build_extract -c "$TARGET/valhalla.json" -v
echo "Valhalla data is ready at $TARGET"
