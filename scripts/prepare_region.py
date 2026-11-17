#!/usr/bin/env python3
"""Derive the map region (bounds, center, zoom) from any OSM PBF extract."""
import json
import os
import sys
from pathlib import Path

import osmium

ROOT = Path(__file__).resolve().parents[1]
PBF = Path(os.environ.get('OSM_PBF', ROOT / 'data' / 'input' / 'region.osm.pbf')).resolve()
OUT = Path(os.environ.get(
    'REGION_OUT', ROOT / 'webapp' / 'public' / 'regions' / 'region.json'
)).resolve()


def header_bounds(path):
    try:
        with osmium.io.Reader(str(path)) as reader:
            box = reader.header().box()
            if box.valid():
                west, south, east, north = box.bottom_left.lon, box.bottom_left.lat, \
                    box.top_right.lon, box.top_right.lat
                if west < east and south < north:
                    return west, south, east, north
    except Exception:
        pass
    return None


class Extent(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.west = self.south = 180.0
        self.east = self.north = -180.0
        self.count = 0

    def node(self, node):
        if not node.location.valid():
            return
        lon, lat = node.location.lon, node.location.lat
        self.count += 1
        self.west = min(self.west, lon)
        self.east = max(self.east, lon)
        self.south = min(self.south, lat)
        self.north = max(self.north, lat)


def scan_bounds(path):
    handler = Extent()
    handler.apply_file(str(path), locations=False)
    if not handler.count:
        raise SystemExit(f'No located nodes found in {path}')
    return handler.west, handler.south, handler.east, handler.north


def derive_name(path):
    stem = path.name
    for suffix in ('.osm.pbf', '.osm.bz2', '.osm.gz', '.pbf', '.osm'):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem.replace('_', ' ').replace('-', ' ').strip() or 'OSM region'


def main():
    if len(sys.argv) > 1:
        PBF = Path(sys.argv[1]).resolve()
    if not PBF.is_file():
        raise SystemExit(f'OSM PBF not found: {PBF}')

    bounds = header_bounds(PBF) or scan_bounds(PBF)
    west, south, east, north = bounds
    center = [(west + east) / 2.0, (south + north) / 2.0]
    span = max(east - west, north - south)
    zoom = 8.5 if span > 6 else 9.5 if span > 2 else 10.5 if span > 0.6 else 11.5

    region = {
        'name': derive_name(PBF),
        'bounds': [[west, south], [east, north]],
        'center': center,
        'zoom': zoom,
        'source': PBF.name,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(region, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, OUT)
    print(f'Region "{region["name"]}" bounds={bounds} zoom={zoom} -> {OUT}')


if __name__ == '__main__':
    main()
