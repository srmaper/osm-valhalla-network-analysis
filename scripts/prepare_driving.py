#!/usr/bin/env python3
"""Refresh the embedded auto-drive fallback route from the OSM sample fixture."""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'webapp' / 'public' / 'driving.html'
ROUTE = Path(os.environ.get('DEMO_ROUTE_OUT', ROOT / 'data' / 'samples' / 'demo-route.geojson'))


def main():
    page = PAGE.read_text(encoding='utf-8')
    route = json.loads(ROUTE.read_text(encoding='utf-8'))
    encoded = json.dumps(route, ensure_ascii=False, separators=(',', ':'))
    old_tags = '<script src="vendor/maplibre-gl.js"></script>\n<script>'
    module_tag = ('<script type="module">\n'
                  "import * as maplibregl from './vendor/maplibre-gl.mjs';\n"
                  'window.maplibregl = maplibregl;')
    if old_tags in page:
        page = page.replace(old_tags, module_tag, 1)
    elif "import * as maplibregl from './vendor/maplibre-gl.mjs';" not in page:
        raise SystemExit('Could not convert the automatic-driving page to the MapLibre ESM build')
    page, count = re.subn(r'^const ROUTE = .*?;$', 'const ROUTE = ' + encoded + ';',
                          page, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit('Could not locate exactly one embedded ROUTE in driving.html')
    if 'driving_manual.html' in page:
        raise SystemExit('Manual-driving page reference found in auto-drive page')
    PAGE.write_text(page, encoding='utf-8', newline='')
    print(f'Updated auto-drive sample with {len(route["features"][0]["geometry"]["coordinates"])} points')


if __name__ == '__main__':
    main()
