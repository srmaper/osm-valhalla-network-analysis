#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PBF="${OSM_PBF:-$ROOT/data/input/hong-kong-261113.osm.pbf}"
DATA_DIR="${NA_DATA_DIR:-$ROOT/data/generated}"
OSMCONF="${OSM_CONFIG_FILE:-$ROOT/configs/osmconf.ini}"
OUT="$DATA_DIR/roads_cn.mbtiles"

for tool in ogr2ogr tippecanoe; do
  command -v "$tool" >/dev/null || { echo "Missing tool: $tool (GDAL/OGR and Tippecanoe required)" >&2; exit 1; }
done
[[ -f "$PBF" ]] || { echo "PBF not found: $PBF" >&2; exit 1; }
[[ -f "$OSMCONF" ]] || { echo "OSM config not found: $OSMCONF" >&2; exit 1; }
mkdir -p "$DATA_DIR"
if [[ -e "$OUT" ]]; then
  echo "Refusing to overwrite existing output: $OUT" >&2
  exit 1
fi

TMP="$(mktemp -d "$DATA_DIR/.mvt-build.XXXXXX")"
trap 'rm -rf -- "$TMP"' EXIT

echo "[1/2] Exporting OSM road lines"
ogr2ogr --config OSM_CONFIG_FILE "$OSMCONF" \
  -f GeoJSONSeq "$TMP/roads.geojsonseq" "$PBF" lines \
  -where "highway IS NOT NULL" \
  -select highway,bridge,tunnel,oneway,maxspeed,lanes,name,ref \
  -lco COORDINATE_PRECISION=7 -nlt LINESTRING

echo "[2/2] Building vector tiles"
tippecanoe -o "$TMP/roads_cn.mbtiles" -l roads_cn -Z5 -z14 \
  --drop-densest-as-needed --extend-zooms-if-still-dropping \
  --read-parallel --no-feature-limit --no-tile-size-limit \
  "$TMP/roads.geojsonseq"
mv -- "$TMP/roads_cn.mbtiles" "$OUT"
echo "MVT data is ready at $OUT"
