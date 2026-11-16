#!/usr/bin/env python3
"""Create non-personal synthetic analysis point sets along the public HK demo road."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'data' / 'samples'
ROUTE = SAMPLES / 'hong-kong-demo-route.geojson'


def point_set(name, indices, weights=None):
    coords = json.loads(ROUTE.read_text(encoding='utf-8'))['features'][0]['geometry']['coordinates']
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


def main():
    SAMPLES.mkdir(parents=True, exist_ok=True)
    n = len(json.loads(ROUTE.read_text(encoding='utf-8'))['features'][0]['geometry']['coordinates'])
    specs = {
        'sample_demands.geojson': point_set('D', [int((n - 1) * i / 9) for i in range(10)], [1, 2, 3, 1]),
        'sample_facilities.geojson': point_set('F', [int((n - 1) * i / 3) for i in range(4)], [1]),
        'sample_depot.geojson': point_set('DC', [0], [1]),
        'sample_stops.geojson': point_set('S', [int((n - 1) * i / 7) for i in range(8)], [1, 2, 1]),
    }
    for name, data in specs.items():
        (SAMPLES / name).write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')),
                                    encoding='utf-8')
    print(f'Wrote {len(specs)} synthetic Hong Kong point sets')


if __name__ == '__main__':
    main()
