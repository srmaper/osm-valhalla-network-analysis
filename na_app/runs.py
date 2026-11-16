"""分析结果持久化:每次运行写入 na_runs/<run_id>/(result.geojson + meta.json)。"""
import json
import os
import time
from datetime import datetime, timezone, timedelta
from .paths import RUNS_DIR as RUNS_PATH

TZ_CN = timezone(timedelta(hours=8))

RUNS = str(RUNS_PATH)

MODE_NAME = {'2sfca': '可达性', 'loc-alloc': '选址', 'closest': '最近设施', 'service': '等时圈',
             'vrp': 'VRP 配送', 'route': '路径规划'}

POINT_KEYS = (('locations', 'wp'), ('demands', 'dem'), ('candidates', 'fac'),
              ('facilities', 'fac'), ('competitors', 'comp'), ('points', 'fac'),
              ('depot', 'dep'), ('stops', 'stop'))


def points_geojson(body):
    fs = []
    for key, setid in POINT_KEYS:
        norm = lambda s: SET_OF.get(s, s) if False else s
        for i, p in enumerate(body.get(key) or []):
            try:
                lat, lon = float(p['lat']), float(p['lon'])
            except (KeyError, TypeError, ValueError):
                continue
            fs.append({'type': 'Feature',
                       'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                       'properties': {'kind': setid, 'seq': i + 1,
                                      'name': p.get('name', f'P{i+1}'),
                                      'weight': p.get('weight', 1)}})
    return {'type': 'FeatureCollection', 'features': fs}


def _now(fmt):
    return datetime.now(TZ_CN).strftime(fmt)

def save_run(op, mode_name, body, feats, stats):
    ts = _now('%Y%m%d-%H%M%S')
    rid = f'{ts}-{op}'
    d = os.path.join(RUNS_DIR(), rid)
    os.makedirs(d, exist_ok=True)
    meta = {'id': rid, 'op': op, 'mode_name': mode_name,
            'ts': _now('%Y-%m-%d %H:%M:%S'),
            'params': {k: v for k, v in body.items() if k != 'costing_options'},
            'stats': stats, 'n_features': len(feats)}
    with open(os.path.join(d, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    with open(os.path.join(d, 'result.geojson'), 'w', encoding='utf-8') as f:
        json.dump({'type': 'FeatureCollection', 'features': feats},
                  f, ensure_ascii=False)
    pts = points_geojson(body)
    if pts['features']:
        with open(os.path.join(d, 'params.geojson'), 'w', encoding='utf-8') as f:
            json.dump(pts, f, ensure_ascii=False)
    return rid


def RUNS_DIR():
    return RUNS


def list_runs():
    if not os.path.isdir(RUNS):
        return []
    out = []
    for rid in sorted(os.listdir(RUNS), reverse=True):
        mp = os.path.join(RUNS, rid, 'meta.json')
        if os.path.exists(mp):
            try:
                with open(mp, encoding='utf-8') as f:
                    out.append(json.load(f))
            except Exception:
                pass
    return out


def load_meta(rid):
    mp = os.path.join(RUNS, _safe(rid), 'meta.json')
    if not os.path.exists(mp):
        return None
    with open(mp, encoding='utf-8') as f:
        return json.load(f)


def load_result(rid):
    rp = os.path.join(RUNS, _safe(rid), 'result.geojson')
    if not os.path.exists(rp):
        return None
    with open(rp, encoding='utf-8') as f:
        return json.load(f)


def load_params(rid):
    pp = os.path.join(RUNS, _safe(rid), 'params.geojson')
    if not os.path.exists(pp):
        return {'type': 'FeatureCollection', 'features': []}
    with open(pp, encoding='utf-8') as f:
        return json.load(f)


def _safe(rid):
    return os.path.basename(rid)


def delete_run(rid):
    import shutil
    rid = _safe(rid)
    d = os.path.join(RUNS, rid)
    if not os.path.isdir(d):
        return False
    shutil.rmtree(d)
    return True

MODE_NAME_OR_DEFAULT = MODE_NAME.get
