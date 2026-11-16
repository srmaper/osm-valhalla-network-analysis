"""从 OSM PBF 构建道路属性 / 信号灯索引(一次性,约 2-4 分钟)。

用法: python -m na_app.build_osm_idx [pbf] [sqlite]
"""
import os
import sqlite3
import sys
import time
from pathlib import Path

import osmium
from .paths import OSM_INDEX_PATH, ROOT

DEFAULT_PBF = ROOT / 'data' / 'input' / 'hong-kong-261113.osm.pbf'

KEEP = ('lanes', 'lanes:forward', 'lanes:backward', 'width', 'maxspeed',
        'oneway', 'highway', 'name')


class Handler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.n_ways = 0
        self.n_rows = 0
        self.n_sig = 0

    def way(self, w):
        self.n_ways += 1
        t = w.tags
        if not t.get('highway'):
            return
        if not any(k in t for k in KEEP):
            return
        self.n_rows += 1
        self.conn.execute(
            'INSERT OR REPLACE INTO ways(way_id,lanes,lanes_fwd,lanes_bak,width,maxspeed,oneway,highway,name)'
            ' VALUES(?,?,?,?,?,?,?,?,?)',
            (w.id, t.get('lanes'), t.get('lanes:forward'), t.get('lanes:backward'),
             t.get('width'), t.get('maxspeed'), t.get('oneway'), t.get('highway'), t.get('name')))
        if self.n_rows % 50000 == 0:
            self.conn.commit()
            print('ways', self.n_ways, 'rows', self.n_rows, flush=True)

    def node(self, n):
        t = n.tags
        if t.get('highway') != 'traffic_signals':
            return
        self.n_sig += 1
        self.conn.execute(
            'INSERT OR REPLACE INTO signals(node_id,lat,lon,turn,red_turn_right,lanes,direction)'
            ' VALUES(?,?,?,?,?,?,?)',
            (n.id, n.location.lat, n.location.lon,
             t.get('traffic_signals:turn'), t.get('red_turn:right'),
             t.get('traffic_signals:lanes'), t.get('traffic_signals:direction')))


def main():
    pbf = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PBF).resolve()
    db = Path(sys.argv[2] if len(sys.argv) > 2 else OSM_INDEX_PATH).resolve()
    if not pbf.is_file():
        raise SystemExit(f'PBF not found: {pbf}')
    db.parent.mkdir(parents=True, exist_ok=True)
    tmp = db.with_name(db.name + '.building')
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(tmp)
    conn.execute('PRAGMA journal_mode=OFF')
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('CREATE TABLE ways(way_id INTEGER PRIMARY KEY, lanes TEXT, lanes_fwd TEXT,'
                 ' lanes_bak TEXT, width TEXT, maxspeed TEXT, oneway TEXT, highway TEXT, name TEXT)')
    conn.execute('CREATE TABLE signals(node_id INTEGER PRIMARY KEY, lat REAL, lon REAL,'
                 ' turn TEXT, red_turn_right TEXT, lanes TEXT, direction TEXT)')
    t0 = time.time()
    h = Handler()
    h.conn = conn
    try:
        h.apply_file(str(pbf), locations=False)
        conn.commit()
        conn.execute('CREATE INDEX idx_signals_latlon ON signals(lat,lon)')
        conn.commit()
        conn.close()
        os.replace(tmp, db)
    except Exception:
        conn.close()
        if tmp.exists():
            tmp.unlink()
        raise
    print('done ways=%d rows=%d signals=%d %.1fs -> %s' %
          (h.n_ways, h.n_rows, h.n_sig, time.time() - t0, db))


if __name__ == '__main__':
    main()
