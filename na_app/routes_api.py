"""分析端点:六类分析。算法在 na_tool.py,此处 HTTP 编排 + 结果落盘(na_runs)。"""
from fastapi import APIRouter, Body
from fastapi.responses import FileResponse

import na_tool as na
from .runs import save_run

router = APIRouter(prefix='/api')

TYPE_ZH = {
    1: '出发', 2: '靠右出发', 3: '靠左出发',
    4: '到达目的地', 5: '到达目的地（右侧）', 6: '到达目的地（左侧）',
    7: '继续沿道路行驶', 8: '继续直行',
    9: '稍向右转', 10: '右转', 11: '急右转',
    12: '掉头', 13: '掉头',
    14: '急左转', 15: '左转', 16: '稍向左转',
    17: '沿匝道直行', 18: '走右侧匝道', 19: '走左侧匝道',
    20: '从右侧出口驶出', 21: '从左侧出口驶出',
    22: '保持直行', 23: '靠右保持直行', 24: '靠左保持直行',
    25: '汇入主路', 26: '进入环岛', 27: '驶出环岛',
    28: '乘坐轮渡', 29: '驶离轮渡', 30: '乘坐公共交通', 31: '换乘',
}


def _zh_instruction(m):
    t = m.get('type')
    base = TYPE_ZH.get(t, '')
    street = ', '.join(m.get('street_names') or []).strip()
    if not base:
        return (m.get('instruction') or '').strip()
    if street and t not in (4, 5, 6):
        return base + '进入' + street
    return base


def _decode_polyline(s, prec=1e6):
    """Valhalla shape 编码线 → [[lng,lat],...]"""
    idx = lat = lng = 0
    coords = []
    fac = 10 ** prec if prec < 10 else prec
    while idx < len(s):
        for which in (0, 1):
            shift = result = 0
            while True:
                ch = ord(s[idx]) - 63
                idx += 1
                result |= (ch & 0x1f) << shift
                shift += 5
                if ch < 0x20:
                    break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if which == 0:
                lat += delta
            else:
                lng += delta
        coords.append([lng / fac, lat / fac])
    return coords


def _route(b):
    body = {'locations': b['locations'], 'costing': b.get('costing', 'auto')}
    if b.get('costing_options'):
        body['costing_options'] = b['costing_options']
    if b.get('alternates'):
        body['alternates'] = int(b['alternates'])
    body['directions_options'] = {'units': 'kilometers', 'language': 'zh-CN'}
    r = na.api('/route', body)
    trips = [('最优', r['trip'])]
    for i, alt in enumerate(r.get('alternates') or []):
        trips.append(('备选' + str(i + 1), alt['trip']))
    feats = []
    for name, trip in trips:
        coords = []
        mans = []
        for leg in trip.get('legs', []):
            pts = _decode_polyline(leg['shape'])
            dedup = bool(coords and pts and coords[-1] == pts[0])
            if dedup:
                pts = pts[1:]
            off = len(coords)
            for m in leg.get('maneuvers') or []:
                bg = max(0, int(m.get('begin_shape_index', 0)) - (1 if dedup else 0))
                en = max(0, int(m.get('end_shape_index', 0)) - (1 if dedup else 0))
                mans.append({
                    'instruction': (m.get('instruction') or '').strip(),
                    'instruction_zh': _zh_instruction(m),
                    'verbal': (m.get('verbal_pre_transition_instruction') or '').strip(),
                    'street': ', '.join(m.get('street_names') or []),
                    'length_km': round(float(m.get('length', 0) or 0), 3),
                    'time_s': int(round(float(m.get('time', 0) or 0))),
                    'begin': off + bg,
                    'end': off + en,
                    'type': m.get('type'),
                })
            coords.extend(pts)
        if not coords:
            continue
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'LineString', 'coordinates': coords},
                      'properties': {'kind': 'route', 'name': name,
                                     'maneuvers': mans if name == '最优' else []}})
    s = r.get('trip', {}).get('summary', {})
    stats = {'routes': len(feats),
             'distance_km': round(s.get('length', 0), 2),
             'time_min': round(s.get('time', 0) / 60.0, 1),
             'maneuvers': len(feats[0]['properties']['maneuvers']) if feats else 0}
    return feats, stats


ANALYZERS = {
    'route': _route,
    'loc-alloc': lambda b: na.analyze_loc_alloc(
        b['demands'], b['candidates'], int(b.get('p', 3)),
        b.get('problem', 'min_impedance'), b.get('cutoff'), b.get('capacity'),
        b.get('decay', 'linear'), b.get('imp_param', 1.0),
        b.get('competitors'), b.get('costing', 'auto'),
        b.get('costing_options')),
    'closest': lambda b: na.analyze_closest(
        b['demands'], b['facilities'], b.get('costing', 'auto'),
        b.get('costing_options')),
    'service': lambda b: na.analyze_service(
        b['points'], b.get('minutes', 10), b.get('costing', 'auto'),
        b.get('costing_options')),
    'vrp': lambda b: na.analyze_vrp(
        b.get('depot') or [], b.get('stops', []),
        int(b.get('vehicles', 0)), float(b.get('capacity', 999999)),
        float(b.get('time_limit_min', 480)), b.get('costing', 'auto'),
        b.get('costing_options')),
    '2sfca': lambda b: na.analyze_2sfca(
        b['demands'], b['facilities'], float(b.get('radius_min', 15)),
        b.get('decay', 'gaussian'), float(b.get('beta', 1.0)),
        b.get('costing', 'auto'), b.get('costing_options')),
}

@router.post('/{op}')
def analyze(op: str, body: dict = Body(...)):
    fn = ANALYZERS.get(op)
    if fn is None:
        return {'error': 'unknown endpoint', 'op': op}
    try:
        feats, stats = fn(body)
        rid = save_run(op, mode_name(op), body, feats, stats) if feats else None
        from .runs import points_geojson
        return {'features': feats, 'stats': stats, 'run_id': rid, 'params': points_geojson(body)}
    except Exception as e:
        return {'error': str(e)}


def mode_name(op):
    from .runs import MODE_NAME
    return MODE_NAME.get(op, op)


@router.get('/runs')
def runs_list():
    from .runs import list_runs
    return {'runs': list_runs()}


@router.get('/runs/{rid}/result')
def runs_result(rid: str):
    from .runs import load_result
    r = load_result(rid)
    if r is None:
        return {'error': 'not found'}
    return r


@router.get('/runs/{rid}/params')
def runs_params(rid: str):
    from .runs import load_params
    return load_params(rid)


@router.get('/runs/{rid}/meta')
def runs_meta(rid: str):
    from .runs import load_meta
    m = load_meta(rid)
    if m is None:
        return {'error': 'not found'}
    return m


@router.get('/runs/{rid}/download')
def runs_download(rid: str):
    """该任务文件夹(zip:meta.json + result.geojson)整包下载。"""
    import os
    import tempfile
    import shutil
    import zipfile
    from .runs import RUNS_DIR
    d = os.path.join(RUNS_DIR(), rid)
    if not os.path.isdir(d):
        return {'error': 'not found'}
    tmp = os.path.join(tempfile.gettempdir(), 'na_' + rid + '.zip')
    if os.path.exists(tmp):
        os.remove(tmp)
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in os.listdir(d):
            fp = os.path.join(d, name)
            if os.path.isfile(fp):
                z.write(fp, arcname=os.path.join(rid, name))
    return FileResponse(tmp, media_type='application/zip',
                        filename='na_' + rid + '.zip')


@router.delete('/runs/{rid}')
def runs_delete(rid: str):
    """删除该任务(na_runs/<rid> 整目录),前端卡片删除时调用。"""
    from .runs import delete_run
    ok = delete_run(rid)
    return {'deleted': bool(ok)}
