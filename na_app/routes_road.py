"""道路属性端点:把 Valhalla 路线匹配到 OSM way, 附带车道数/宽度/限速/真实信号灯。

POST /api/road_info  {"shape": [[lon,lat], ...] | [{"lat":..,"lon":..}, ...]}
"""
import json
import math
import os
import re
import sqlite3
import urllib.request

from fastapi import APIRouter, Body
from .paths import OSM_INDEX_PATH, VALHALLA_URL

router = APIRouter(prefix='/api')

DB_PATH = str(OSM_INDEX_PATH)
VALHALLA = VALHALLA_URL

ONE_WAY = {'yes', 'true', '1', '-1', 'reverse'}


def _num(v):
    if v is None:
        return None
    m = re.search(r'[-+]?\d+(\.\d+)?', str(v))
    return float(m.group()) if m else None


def _speed_kmh(v):
    if v is None:
        return None
    s = str(v).lower()
    x = _num(s)
    if x is None:
        return None
    if 'mph' in s:
        x *= 1.60934
    elif 'knot' in s:
        x *= 1.852
    return max(5.0, min(160.0, round(x)))


def _parse_way(row):
    wid, lanes, lf, lb, width, maxspeed, oneway, highway, name = row
    n_tot = _num(lanes)
    fwd = _num(lf)
    bak = _num(lb)
    ow = (oneway or '').lower() in ONE_WAY
    if fwd is None and bak is None and n_tot:
        if ow:
            fwd, bak = n_tot, 0
        else:
            fwd = max(1.0, round(n_tot / 2))
            bak = max(0.0, n_tot - fwd)
    n_fwd = int(min(4, max(1, fwd))) if fwd else None
    w = _num(width)
    lane_w = None
    if w and n_tot and 2.5 <= w / max(1, n_tot) <= 5.0:
        lane_w = round(w / max(1, n_tot), 2)
    return {
        'way_id': wid, 'lanes': int(n_tot) if n_tot else None,
        'lanes_fwd': n_fwd, 'lanes_bak': int(bak) if bak is not None else None,
        'lane_w': lane_w, 'maxspeed': _speed_kmh(maxspeed),
        'oneway': ow, 'highway': highway, 'name': name,
    }


def _ways(ids):
    if not ids:
        return {}
    c = sqlite3.connect(DB_PATH)
    try:
        q = 'SELECT way_id,lanes,lanes_fwd,lanes_bak,width,maxspeed,oneway,highway,name FROM ways WHERE way_id IN (%s)' % ','.join('?' * len(ids))
        out = {}
        for row in c.execute(q, list(ids)):
            out[row[0]] = _parse_way(row)
        return out
    finally:
        c.close()


def _to_ll(shape):
    pts = []
    for p in shape:
        if isinstance(p, dict):
            pts.append((float(p['lat']), float(p['lon'])))
        else:
            pts.append((float(p[1]), float(p[0])))
    return pts


def _trace(pts):
    body = {
        'shape': [{'lat': la, 'lon': lo} for la, lo in pts],
        'costing': 'auto',
        'shape_match': 'map_snap',
        'filters': {'action': 'include',
                    'attributes': ['edge.way_id', 'edge.speed', 'edge.length',
                                   'edge.names', 'edge.road_class']},
    }
    req = urllib.request.Request(VALHALLA + '/trace_attributes',
                                 data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _havg(a, b):
    R = 6371008.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _project(pts, cum, total):
    kx = 111320.0 * math.cos(math.radians(pts[0][0]))

    def xy(p):
        return ((p[1] - pts[0][1]) * kx, (p[0] - pts[0][0]) * 110540.0)

    seg = [xy(p) for p in pts]
    out = []
    for i in range(1, len(seg)):
        out.append((seg[i - 1], seg[i], cum[i - 1], _havg(pts[i - 1], pts[i])))

    def project(p):
        px, py = xy((p[0], p[1]))
        best = (1e18, 0.0)
        for (ax, ay), (bx, by), c0, L in out:
            vx, vy = bx - ax, by - ay
            ll = vx * vx + vy * vy
            t = 0.0 if ll < 1e-9 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / ll))
            dx, dy = ax + vx * t - px, ay + vy * t - py
            d = math.hypot(dx, dy)
            if d < best[0]:
                best = (d, c0 + t * L)
        return best

    return project


def _signals(pts, cum, total):
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    pad = 0.003
    q = ('SELECT lat,lon,turn,red_turn_right,lanes,direction FROM signals'
         ' WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?')
    c = sqlite3.connect(DB_PATH)
    try:
        try:
            rows = c.execute(q, (min(lats) - pad, max(lats) + pad,
                                 min(lons) - pad, max(lons) + pad)).fetchall()
        except sqlite3.OperationalError:      # 旧版索引没有这些列
            rows = [(la, lo, None, None, None, None) for la, lo in c.execute(
                'SELECT lat,lon FROM signals WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?',
                (min(lats) - pad, max(lats) + pad, min(lons) - pad, max(lons) + pad))]
    finally:
        c.close()
    project = _project(pts, cum, total)
    out = []
    for lat, lon, turn, red, lanes, direction in rows:
        d, m = project((lat, lon))
        if d <= 22.0:
            out.append({'lat': lat, 'lon': lon, 'm': round(m, 1), 'd': round(d, 1),
                        'turn': turn, 'red_turn_right': red, 'lanes': lanes,
                        'direction': direction})
    out.sort(key=lambda x: x['m'])
    return out


@router.post('/road_info')
def road_info(shape=Body(...)):
    pts = _to_ll(shape.get('shape') if isinstance(shape, dict) else shape)
    if len(pts) < 2:
        return {'error': 'shape too short'}
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + _havg(pts[i - 1], pts[i]))
    total = cum[-1]

    step = max(1, len(pts) // 220)
    sub = pts[::step]
    if sub[-1] != pts[-1]:
        sub.append(pts[-1])

    try:
        tr = _trace(sub)
        edges = tr.get('edges') or []
    except Exception as e:
        return {'error': 'trace failed: %s' % e, 'total_m': round(total, 1)}

    out_edges = []
    acc = 0.0
    for e in edges:
        L = (e.get('length') or 0.0) * 1000.0
        out_edges.append({
            'way_id': e.get('way_id'), 'from_m': round(acc, 1), 'to_m': round(acc + L, 1),
            'speed': e.get('speed'), 'name': (e.get('names') or [None])[0],
            'road_class': e.get('road_class'),
        })
        acc += L

    ids = sorted({e['way_id'] for e in out_edges if e.get('way_id')})
    ways = _ways(ids)

    try:
        sig = _signals(pts, cum, total)
    except Exception:
        sig = []

    return {'total_m': round(total, 1), 'edges': out_edges,
            'ways': {str(k): v for k, v in ways.items()}, 'signals': sig}
