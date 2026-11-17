#!/usr/bin/env python3
"""Copy the pinned MapLibre ESM runtime used by the standalone drive page."""
from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'webapp' / 'node_modules' / 'maplibre-gl' / 'dist'
VENDOR = ROOT / 'webapp' / 'public' / 'vendor'
ASSETS = ROOT / 'webapp' / 'public' / 'assets'
FILES = ('maplibre-gl.mjs', 'maplibre-gl-worker.mjs', 'maplibre-gl.css')


def main():
    missing = [name for name in FILES if not (DIST / name).is_file()]
    if missing:
        raise SystemExit(f'MapLibre distribution files missing: {missing}; run npm ci first')
    VENDOR.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy2(DIST / name, VENDOR / name)
    # The application bundle resolves its module worker next to /assets/*.js.
    shutil.copy2(DIST / 'maplibre-gl-worker.mjs', ASSETS / 'maplibre-gl-worker.mjs')
    legacy = VENDOR / 'maplibre-gl.js'
    if legacy.exists():
        legacy.unlink()
    package = json.loads((ROOT / 'webapp' / 'node_modules' / 'maplibre-gl' / 'package.json').read_text())
    print('Synced MapLibre', package['version'])


if __name__ == '__main__':
    main()
