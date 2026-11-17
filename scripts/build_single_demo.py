#!/usr/bin/env python3
"""Build the dependency-free single-file automatic-driving demo.

Reads the demo route (data/samples/demo-route.geojson) and writes
docs/demo.html (open directly by double-click) plus a served copy at
webapp/public/demo.html.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'scripts' / 'templates' / 'auto_drive_single.html'
ROUTE = Path(__import__('os').environ.get('DEMO_ROUTE_OUT', ROOT / 'data' / 'samples' / 'demo-route.geojson'))
TARGETS = (ROOT / 'docs' / 'demo.html', ROOT / 'webapp' / 'public' / 'demo.html')


def main():
    if not TEMPLATE.is_file():
        raise SystemExit(f'Template not found: {TEMPLATE}')
    if not ROUTE.is_file():
        raise SystemExit(f'Demo route not found: {ROUTE}; run scripts/prepare_demo.py first')
    html = TEMPLATE.read_text(encoding='utf-8')
    route = json.loads(ROUTE.read_text(encoding='utf-8'))
    feature = route['features'][0]
    coords = feature['geometry']['coordinates']
    name = feature['properties'].get('name') or 'OSM demo route'
    html = html.replace('__ROUTE_COORDS__', json.dumps(coords, separators=(',', ':')))
    html = html.replace('__ROUTE_NAME__', json.dumps(name, ensure_ascii=False))
    if '__ROUTE_COORDS__' in html or '__ROUTE_NAME__' in html:
        raise SystemExit('Template placeholders were not fully replaced')
    for target in TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding='utf-8', newline='')
        print(f'Wrote {target} ({len(coords)} route points)')


if __name__ == '__main__':
    main()
