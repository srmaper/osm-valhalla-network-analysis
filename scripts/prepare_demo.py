#!/usr/bin/env python3
"""Build a demo route and synthetic sample points from any OSM PBF extract.

The longest drivable road segment in the extract becomes the automatic-driving
demo line. Analysis samples are synthetic points placed along that line; they
are development fixtures, not real customers or facilities.
"""
import json
import math
import os
import sys
from pathlib import Path

import osmium

ROOT = Path(__file__).resolve().parents[1]
PBF = Path(os.environ.get('OSM_PBF', ROOT / 'data' / 'input' / 'region.osm.pbf')).resolve()
SAMPLES = Path(os.environ.get('NA_SAMPLES_DIR', ROOT / 'data' / 'samples')).resolve()
ROUTE = SAMPLES / 'demo-route.geojson'
ROAD_CLASSES = {
    'motorway', 'trunk', 'primary', 'secondary', 'tertiary',
    'unclassified', 'residential', 'living_street',
}


def haversine(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + \
        math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


class LongestRoad(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.best = None
        self.best_len = 0.0

    def way(self, way):
        if (way.tags.get('highway') or '') not in ROAD_CLASSES:
            return
        if way.tags.get('area') in ('yes', '1'):
            return
        coords = [[n.location.lon, n.location.lat] for n in way.nodes if n.location.valid()]
        if len(coords) < 12:
            return
        length = sum(haversine(coords[i - 1], coords[i]) for i in range(1, len(coords)))
        if length > self.best_len:
            self.best_len = length
            self.best = (way.id, way.tags.get('name') or '', coords)


def reduce_points(coords, limit=350):
    stride = max(1, len(coords) // limit)
    out = coords[::stride]
    if out[-1] != coords[-1]:
        out.append(coords[-1])
    return out


def point_set(coords, name, indices, weights=None):
    features = []
    for i, idx in enumerate(indices):
        props = {'name': f'{name}{i + 1}'}
        if weights:
            props['weight'] = weights[i % len(weights)]
        features.append({
            'type': 'Feature', 'properties': props,
            'geometry': {'type': 'Point', 'coordinates': coords[idx]},
        })
    return {'type': 'FeatureCollection', 'features': features}


def write_json(path, payload):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
                   encoding='utf-8')
    os.replace(tmp, path)


def main():
    if len(sys.argv) > 1:
        PBF = Path(sys.argv[1]).resolve()
    if not PBF.is_file():
        raise SystemExit(f'OSM PBF not found: {PBF}')
    handler = LongestRoad()
    handler.apply_file(str(PBF), locations=True)
    if not handler.best:
        raise SystemExit('No suitable drivable road found for the demo route')
    way_id, name, coords = handler.best
    line = reduce_points(coords)
    SAMPLES.mkdir(parents=True, exist_ok=True)
    write_json(ROUTE, {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'geometry': {'type': 'LineString', 'coordinates': line},
            'properties': {'kind': 'route', 'name': name or f'OSM way {way_id}',
                           'source': 'OpenStreetMap', 'osm_way_id': way_id,
                           'maneuvers': []},
        }],
    })
    n = len(line)
    pick = lambda count: [int((n - 1) * i / max(1, count - 1)) for i in range(count)]
    write_json(SAMPLES / 'sample_demands.geojson',
               point_set(line, 'D', pick(10), [1, 2, 3, 1]))
    write_json(SAMPLES / 'sample_facilities.geojson',
               point_set(line, 'F', pick(4), [1]))
    write_json(SAMPLES / 'sample_depot.geojson', point_set(line, 'DC', [0], [1]))
    write_json(SAMPLES / 'sample_stops.geojson',
               point_set(line, 'S', pick(8), [1, 2, 1]))
    print(f'Demo route: {name or way_id} ({handler.best_len / 1000:.2f} km, '
          f'{len(line)} points) -> {ROUTE}')


if __name__ == '__main__':
    main()
