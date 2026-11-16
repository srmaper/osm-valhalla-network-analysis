# Data layout

- `input/`: source PBF. The Hong Kong 2026-11-13 OSM extract is included as the reproducible sample.
- `samples/`: small GeoJSON point sets and a short route fixture used by the UI and automatic-drive demo.
- `generated/`: Valhalla graph/config, OSM road index, and MVT tiles. Created by the data pipeline; ignored by Git.
- `runtime/`: analysis run history and matrix cache. Created at runtime; ignored by Git.

The source PBF is OpenStreetMap data, © OpenStreetMap contributors, licensed under the Open Database License (ODbL). See `docs/OSM_ATTRIBUTION.md`.

Sample PBF SHA-256: `CA3ED60DEDACCBD87CF703B13D560719ED76A665A59D623B9E3566680564E7D0`.
