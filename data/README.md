# Data layout

- `input/`: put `.osm.pbf` extracts here. A Hong Kong extract is included by default;
  drop another region's file in this folder (or pass a path/URL to `scripts/oneclick.sh`)
  and everything is regenerated for it.

Replacing the data: one-click autodetects the newest `.osm.pbf`, rebuilds the road index,
MVT tiles and (if the file hash changed) the Valhalla graph, and rewrites
`webapp/public/regions/region.json` so the map bounds follow the new extract.
- `香港特别行政区.geojson`: optional local boundary input used to derive the fixed HK viewport bounds; this user-provided file is not included in the public repository.
- `samples/`: generated demo route (`demo-route.geojson`) and synthetic point sets used by the UI.
- `../webapp/public/regions/region.json`: auto-generated map bounds/center/zoom for the current OSM input.
- `generated/`: Valhalla graph/config, OSM road index, and MVT tiles. Created by the data pipeline; ignored by Git.
- `runtime/`: analysis run history and matrix cache. Created at runtime; ignored by Git.

The source PBF is OpenStreetMap data, © OpenStreetMap contributors, licensed under the Open Database License (ODbL). See `docs/OSM_ATTRIBUTION.md`.

Sample PBF SHA-256: `CA3ED60DEDACCBD87CF703B13D560719ED76A665A59D623B9E3566680564E7D0`.
