#!/usr/bin/env python3
"""Extract a stable public-road demo line from the bundled Hong Kong OSM PBF."""
import json
import os
from pathlib import Path

import osmium

ROOT = Path(__file__).resolve().parents[1]
PBF = Path(os.environ.get(
    'OSM_PBF', ROOT / 'data' / 'input' / 'hong-kong-261113.osm.pbf'
)).resolve()
OUT = Path(os.environ.get(
    'DEMO_ROUTE_OUT', ROOT / 'data' / 'samples' / 'hong-kong-demo-route.geojson'
)).resolve()
WAY_ID = 103001305  # 西貢萬宜路 / Sai Kung Man Yee Road, from this extract


class RouteHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.coordinates = None
        self.name = None

    def way(self, way):
        if way.id != WAY_ID:
            return
        coordinates = []
        for node in way.nodes:
            if node.location.valid():
                coordinates.append([node.location.lon, node.location.lat])
        if len(coordinates) >= 2:
            # Keep a manageable fixture while retaining both endpoints and the road shape.
            stride = max(1, len(coordinates) // 350)
            reduced = coordinates[::stride]
            if reduced[-1] != coordinates[-1]:
                reduced.append(coordinates[-1])
            self.coordinates = reduced
            self.name = way.tags.get('name') or 'Sai Kung Man Yee Road'


def main():
    if not PBF.is_file():
        raise SystemExit(f'OSM PBF not found: {PBF}')
    handler = RouteHandler()
    handler.apply_file(str(PBF), locations=True)
    if not handler.coordinates:
        raise SystemExit(f'OSM way {WAY_ID} was not found in {PBF}')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    feature = {
        'type': 'Feature',
        'geometry': {'type': 'LineString', 'coordinates': handler.coordinates},
        'properties': {'kind': 'route', 'name': handler.name,
                       'source': 'OpenStreetMap', 'osm_way_id': WAY_ID,
                       'maneuvers': []},
    }
    payload = {'type': 'FeatureCollection', 'features': [feature]}
    tmp = OUT.with_suffix(OUT.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
                   encoding='utf-8')
    tmp.replace(OUT)
    print(f'Wrote {len(handler.coordinates)} route points to {OUT}')


if __name__ == '__main__':
    main()
