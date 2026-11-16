"""na_tool.py — 本地 Valhalla 之上的 ArcGIS 风格网络分析。

功能:
  locate-alloc  6 种选址: min_impedance / max_coverage / cap_coverage /
                min_facilities / max_attendance / market_share
  closest       最近设施分配
  service       批量等时圈服务区
  vrp           车辆配送(容量/单程限时/时间窗/服务时长)
矩阵磁盘缓存: ./na_tool_cache/ (环境变量 NA_CACHE=0 关闭)
核心函数同时也是 na_server.py 的 HTTP 后端(见 analyze_*)。
"""
import argparse
import hashlib
import json
import math
import os
import urllib.request
import urllib.parse

API = os.environ.get('VALHALLA_URL', 'http://127.0.0.1:8002').rstrip('/')
INF = 10 ** 9
CACHE_DIR = os.environ.get(
    'NA_CACHE_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'runtime', 'cache')
)

PROBLEMS = ('min_impedance', 'max_coverage', 'cap_coverage', 'min_facilities',
            'max_attendance', 'market_share')


def api(path, body, timeout=300):
    url = API + path + '?json=' + urllib.parse.quote(json.dumps(body))
    return json.load(urllib.request.urlopen(url, timeout=timeout))


def norm_points(pts):
    out = []
    for p in pts:
        q = {'name': str(p.get('name') or p.get('NAME') or len(out) + 1),
             'lat': round(float(p['lat']), 6),
             'lon': round(float(p['lon']), 6),
             'weight': float(p.get('weight', 1))}
        for k in ('tw_start', 'tw_end', 'service_time'):
            if p.get(k) is not None:
                q[k] = float(p[k])
        out.append(q)
    return out


def load_points(path):
    with open(path, encoding='utf-8') as f:
        g = json.load(f)
    pts = []
    for ft in g.get('features', []):
        gm = ft.get('geometry') or {}
        if gm.get('type') != 'Point':
            continue
        lon, lat = gm['coordinates'][:2]
        pr = ft.get('properties') or {}
        p = {'name': str(pr.get('name') or pr.get('NAME') or len(pts) + 1),
             'lat': lat, 'lon': lon,
             'weight': float(pr.get('weight', pr.get('Weight', 1)))}
        for k in ('tw_start', 'tw_end', 'service_time'):
            if pr.get(k) is not None:
                p[k] = float(pr[k])
        pts.append(p)
    return norm_points(pts)


def write_fc(path, feats):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'type': 'FeatureCollection', 'features': feats}, f, ensure_ascii=False, indent=1)


def time_matrix(sources, targets, costing='auto', costing_options=None):
    S = [{'lat': p['lat'], 'lon': p['lon'], 'type': 'break'} for p in sources]
    T = [{'lat': p['lat'], 'lon': p['lon'], 'type': 'break'} for p in targets]
    os.makedirs(CACHE_DIR, exist_ok=True)
    raw = json.dumps([S, T, costing, costing_options], sort_keys=True)
    key = os.path.join(CACHE_DIR, hashlib.md5(raw.encode()).hexdigest() + '.json')
    if os.environ.get('NA_CACHE', '1') != '0' and os.path.exists(key):
        with open(key, encoding='utf-8') as f:
            return json.load(f)
    mat = [[INF] * len(T) for _ in S]
    CH = 12
    for i0 in range(0, len(S), CH):
        for j0 in range(0, len(T), CH):
            req = {'sources': S[i0:i0 + CH], 'targets': T[j0:j0 + CH], 'costing': costing}
            if costing_options:
                req['costing_options'] = costing_options
            d = api('/sources_to_targets', req)
            for ri, row in enumerate(d.get('sources_to_targets', [])):
                for ci, cell in enumerate(row):
                    t = cell.get('time')
                    mat[i0 + ri][j0 + ci] = t if t is not None else INF
    if os.environ.get('NA_CACHE', '1') != '0':
        with open(key, 'w', encoding='utf-8') as f:
            json.dump(mat, f)
    return mat


def _polyline_decode(s, prec=1e6):
    coords = []
    lat = lon = 0
    i = 0
    while i < len(s):
        out = []
        for ref in (0, 0):
            result = 0
            shift2 = 0
            while True:
                b = ord(s[i]) - 63
                i += 1
                result |= (b & 0x1F) << shift2
                shift2 += 5
                if b < 0x20:
                    break
            out.append(~(result >> 1) if result & 1 else (result >> 1))
        lat += out[0]
        lon += out[1]
        coords.append([round(lon / prec, 6), round(lat / prec, 6)])
    return coords


def route_shape(pts, costing='auto', costing_options=None):
    """沿路网的实际路径坐标([lon,lat])。pts: 按顺序的节点字典列表。"""
    if len(pts) < 2:
        return None
    req = {'locations': [{'lat': p['lat'], 'lon': p['lon'], 'type': 'break'} for p in pts],
           'costing': costing, 'units': 'km'}
    if costing_options:
        req['costing_options'] = costing_options
    r = api('/route', req)
    seg = []
    for leg in r.get('trip', {}).get('legs', []):
        shape = leg.get('shape') or ''
        seg += _polyline_decode(shape)
    return seg if len(seg) >= 2 else None


# ------------------------------------------------------------------ 可达性 (2SFCA族)

def _sfca_g(kind, t, rad_s, beta):
    if t is None or t >= INF or t > rad_s:
        return 0.0
    if kind == 'binary':
        return 1.0
    if kind == 'gaussian':
        return (math.exp(-0.5 * (t / rad_s) ** 2) - math.exp(-0.5)) / (1 - math.exp(-0.5))
    if kind == 'e2sfca':
        x = t / rad_s
        return 1.0 if x <= 1 / 3 else (0.68 if x <= 2 / 3 else 0.36)
    if kind == 'power':
        return (max(t, 60.0) / rad_s) ** (-beta)
    return 1.0


def _gini(vals):
    v = sorted(x for x in vals if x is not None and x >= 0)
    n = len(v)
    if n == 0 or v[-1] == 0:
        return 0.0
    cum = 0.0
    for i, x in enumerate(v, 1):
        cum += x
    return round((2.0 * sum((i + 1) * x for i, x in enumerate(v)) / (n * cum) - (n + 1) / n), 4)


def analyze_2sfca(demand, fac, radius_min=15.0, decay='gaussian', beta=1.0,
                  costing='auto', costing_options=None):
    """两步移动搜索法。demand: 需求点(weight=人口); fac: 设施点(weight=容量)。
    decay: binary=E2SFCA前的经典 | e2sfca=增强分段 | gaussian=高斯 | power=重力(beta)。
    返回 (features, stats): features 含 demand 打分点 + facility 供需比点。"""
    demand = norm_points(demand)
    fac = norm_points(fac)
    if not demand or not fac:
        raise ValueError('需要 demands(需求点,权重=人口) 与 facilities(设施点,权重=容量)')
    if len(fac) > 60 or len(demand) > 300:
        raise ValueError('样例规模过大:facilities<=60, demands<=300(公共 API 限制)')
    rad_s = radius_min * 60.0
    m_fd = time_matrix(fac, demand, costing, costing_options)   # [facility][demand]
    m_df = time_matrix(demand, fac, costing, costing_options)   # demand×facility(常命中缓存)
    R = []
    for k in range(len(fac)):
        den = 0.0
        for j in range(len(demand)):
            g = _sfca_g(decay, m_fd[k][j], rad_s, beta)
            if g:
                den += g * demand[j]['weight']
        R.append(fac[k]['weight'] / den if den > 0 else 0.0)
    feats = []
    scores = []
    for j, dj in enumerate(demand):
        s = 0.0
        for k in range(len(fac)):
            g = _sfca_g(decay, m_df[j][k], rad_s, beta)
            if g:
                s += g * R[k]
        s = round(s, 6)
        scores.append(s)
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [dj['lon'], dj['lat']]},
                      'properties': {'kind': 'demand', 'name': dj['name'],
                                     'weight': dj['weight'], 'score': s}})
        fi = min(range(len(fac)), key=lambda kk: m_df[j][kk])
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'LineString',
                                   'coordinates': [[fac[fi]['lon'], fac[fi]['lat']],
                                                   [dj['lon'], dj['lat']]]},
                      'properties': {'kind': 'assignment', 'demand': dj['name'],
                                     'facility': fac[fi]['name'],
                                     'time_min': round(m_df[j][fi] / 60, 1),
                                     'weight': dj['weight']}})
    for k, fk in enumerate(fac):
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point', 'coordinates': [fk['lon'], fk['lat']]},
                      'properties': {'kind': 'facility', 'name': fk['name'],
                                     'weight': fk['weight'], 'ratio': round(R[k], 6)}})
    sv = sorted(scores)
    n = len(sv)
    thr = sv[int(n * 0.25)] if n else 0
    low_n = sum(1 for s in scores if s <= thr)
    wsum = sum(dj['weight'] for dj in demand) or 1
    wmean = sum(scores[j] * demand[j]['weight'] for j in range(n)) / wsum
    stats = {'n_demand': n, 'n_facility': len(fac), 'radius_min': radius_min,
             'decay': decay, 'mean': round(sum(scores) / n, 4) if n else 0,
             'pop_mean': round(wmean, 4),
             'min': min(scores) if scores else 0, 'max': max(scores) if scores else 0,
             'p25': thr, 'gini': _gini(scores), 'n_low': low_n,
             'low_pct': round(100.0 * low_n / n, 1) if n else 0}
    return feats, stats


# ------------------------------------------------------------------ 选址服务



def decay_value(t, cut_s, decay, imp):
    if t is None or t >= INF or t > cut_s:
        return 0.0
    x = t / max(cut_s, 1e-9)
    d = {'linear': 1 - x, 'power': max(0.0, (1 - x)) ** imp,
         'exponential': math.exp(-4 * x)}.get(decay, 1 - x)
    return d if d > 0 else 0.0


def p_median_cost(mat, sel, weights):
    return sum(min(mat[j][ci] for ci in sel) * (weights[j] or 1) for j in range(len(mat)))


def p_median(mat, weights, P):
    n = len(mat)
    m = len(mat[0])
    if m <= P:
        return list(range(m)), p_median_cost(mat, list(range(m)), weights)
    sel, _ = greedy_max(P, m, n, lambda s: -p_median_cost(mat, s, weights))
    return sel, p_median_cost(mat, sel, weights)


def greedy_max(P, m, n, score):
    sel = [max(range(m), key=lambda ci: score([ci]))]
    while len(sel) < P:
        best = None
        for ci in range(m):
            if ci in sel:
                continue
            s = score(sel + [ci])
            if best is None or s > best[0]:
                best = (s, ci)
        if best is None:
            break
        sel.append(best[1])
    cur = score(sel)
    for _ in range(300):
        imp = False
        for oi in list(sel):
            for ni in range(m):
                if ni in sel:
                    continue
                cand = [ci for ci in sel if ci != oi] + [ni]
                s = score(cand)
                if s > cur + 1e-9:
                    sel = cand
                    cur = s
                    imp = True
        if not imp:
            break
    return sel, cur


def build_score(mat, weights, problem, decay, imp_param, cut_s, comp_vec=None, attract=None):
    n, m = len(mat), len(mat[0])
    att = attract if attract is not None else [1.0] * m
    if problem == 'max_coverage':
        def score(sel):
            tot = 0.0
            for j in range(n):
                if any(mat[j][ci] <= cut_s for ci in sel):
                    tot += weights[j] or 1
            return tot
        return score

    if problem == 'max_attendance':
        def score(sel):
            tot = 0.0
            for j in range(n):
                g = max((att[ci] * decay_value(mat[j][ci], cut_s, decay, imp_param)) for ci in sel)
                tot += (weights[j] or 1) * g
            return tot
        return score

    if problem == 'market_share':
        def score(sel):
            tot = 0.0
            for j in range(n):
                g_ours = max((att[ci] * decay_value(mat[j][ci], cut_s, decay, imp_param)) for ci in sel)
                g_comp = comp_vec[j] if comp_vec else 0.0
                share = g_ours / (g_ours + g_comp) if (g_ours + g_comp) > 0 else 0.0
                tot += (weights[j] or 1) * share
            return tot
        return score
    raise ValueError(problem)


def capacity_assign(mat, sel, weights, cut_s, caps=None, capacity=None):
    n = len(mat)
    assigned = {}
    orders = sorted(range(n), key=lambda j: min(mat[j][ci] for ci in sel))
    loads = {ci: 0.0 for ci in sel}
    for j in orders:
        covered = []
        for ci in sorted(sel, key=lambda k: mat[j][k]):
            if mat[j][ci] <= cut_s:
                covered.append(ci)
        for ci in covered:
            lim = caps[ci] if caps is not None else capacity
            if lim is None or loads[ci] + (weights[j] or 1) <= lim:
                assigned[j] = ci
                loads[ci] += weights[j] or 1
                break
    covered = sum((weights[j] or 1) for j in assigned)
    return assigned, covered, loads


def solve_loc_alloc(mat, weights, P, problem, cutoff_min=None, capacity=None,
                    decay='linear', imp_param=1.0, comp_vec=None, cand_caps=None,
                    attract=None):
    cut_s = (cutoff_min * 60) if cutoff_min is not None else INF
    if problem == 'min_impedance':
        sel, score = p_median(mat, weights, P)
        return sel, score
    if problem == 'max_coverage':
        score = build_score(mat, weights, 'max_coverage', decay, imp_param, cut_s)
        return greedy_max(P, len(mat[0]), len(mat), score)
    if problem == 'max_attendance':
        score = build_score(mat, weights, 'max_attendance', decay, imp_param, cut_s, attract=attract)
        return greedy_max(P, len(mat[0]), len(mat), score)
    if problem == 'market_share':
        score = build_score(mat, weights, 'market_share', decay, imp_param, cut_s, comp_vec, attract=attract)
        sel, score = greedy_max(P, len(mat[0]), len(mat), score)
        return sel, score
    if problem == 'cap_coverage':
        sel = [min(range(len(mat[0])),
                   key=lambda ci: sum(mat[j][ci] * (weights[j] or 1) for j in range(len(mat))))]
        best_cov = -1
        while len(sel) < P:
            best = None
            for ci in range(len(mat[0])):
                if ci in sel:
                    continue
                assigned, cov, _ = capacity_assign(mat, sel + [ci], weights, cut_s, cand_caps, capacity)
                if not best or cov > best[0]:
                    best = (cov, ci)
            if best is None or best[0] <= best_cov:
                break
            sel.append(best[1])
            best_cov = best[0]
        assigned, cov, loads = capacity_assign(mat, sel, weights, cut_s, cand_caps, capacity)
        return sel, cov
    if problem == 'min_facilities':
        sel = []
        covered = set()
        best_cov_len = 0
        while len(covered) < len(mat):
            gains = []
            for ci in range(len(mat[0])):
                cov_now = {j for j in range(len(mat)) if mat[j][ci] <= cut_s}
                gains.append((len(covered | cov_now), ci))
            gains.sort(reverse=True)
            top = gains[0]
            if top[0] <= len(covered):
                break
            sel.append(top[1])
            covered |= {j for j in range(len(mat)) if mat[j][top[1]] <= cut_s}
        if len(covered) < len(mat):
            return None, None
        return sel, len(sel)
    raise ValueError('unknown problem: ' + str(problem))


def analyze_loc_alloc(demand, cand, p=3, problem='min_impedance', cutoff_min=None,
                      capacity=None, decay='linear', imp_param=1.0,
                      competitors=None, costing='auto', costing_options=None):
    demand = norm_points(demand)
    cand = norm_points(cand)
    mat = time_matrix(demand, cand, costing, costing_options)
    comp_vec = None
    cut_s = (cutoff_min * 60) if cutoff_min is not None else INF
    cand_caps = [c['weight'] for c in cand] if capacity == 'weight' else None
    if problem == 'market_share':
        if not competitors:
            raise ValueError('market_share 需要 competitors 参数(竞品设施点)')
        comps = norm_points(competitors)
        cmat = time_matrix(demand, comps, costing, costing_options)
        comp_vec = [sum((c['weight'] or 1) * decay_value(t, cut_s, decay, imp_param)
                        for t, c in zip(row, comps)) for row in cmat]
    sel, score = solve_loc_alloc(mat, [d['weight'] for d in demand], p,
                                 problem, cutoff_min, capacity, decay,
                                 imp_param, comp_vec,
                                 cand_caps, [c['weight'] for c in cand])
    if sel is None:
        raise ValueError('无解: P 上限内无法覆盖全部需求 (增大 --p 或放宽 --cutoff)')
    opened = [cand[ci] for ci in sel]
    feats = []
    for fi, fc in enumerate(opened):
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'Point',
                                   'coordinates': [fc['lon'], fc['lat']]},
                      'properties': {'kind': 'selected_facility',
                                     'name': fc['name'], 'problem': problem,
                                     'weight': fc['weight']}})
    for j, d in enumerate(demand):
        fi = min(range(len(opened)), key=lambda k: mat[j][sel[k]])
        fc = opened[fi]
        t = mat[j][sel[fi]]
        covered = (t <= cutoff_min * 60) if cutoff_min else True
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'LineString',
                                   'coordinates': [[fc['lon'], fc['lat']],
                                                   [d['lon'], d['lat']]]},
                      'properties': {'kind': 'assignment',
                                     'demand': d['name'],
                                     'facility': fc['name'],
                                     'time_min': round(t / 60, 1),
                                     'weight': d['weight'],
                                     'covered': covered}})
    stats = {'problem': problem,
             'facilities': [f['name'] for f in opened],
             'score': round(score, 3)}
    if problem == 'cap_coverage':
        _a, _c, loads = capacity_assign(mat, sel, [d['weight'] for d in demand], cut_s, cand_caps,
                                        capacity if cand_caps is None else None)
        stats['loads'] = {f['name']: round(loads[ci], 1) for ci, f in zip(sel, opened)}
        if cand_caps is None and capacity is not None:
            stats['capacity'] = capacity
    if problem in ('min_impedance', 'max_coverage'):
        stats['avg_time_min'] = round(score / max(1, sum(d['weight'] for d in demand)) / 60, 1)
    return feats, stats


def analyze_closest(demand, fac, costing='auto', costing_options=None):
    demand = norm_points(demand)
    fac = norm_points(fac)
    mat = time_matrix(demand, fac, costing, costing_options)
    feats = []
    for j, d in enumerate(demand):
        fi = min(range(len(fac)), key=lambda k: mat[j][k])
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'LineString',
                                   'coordinates': [[fac[fi]['lon'], fac[fi]['lat']],
                                                   [d['lon'], d['lat']]]},
                      'properties': {'kind': 'assignment',
                                     'demand': d['name'],
                                     'facility': fac[fi]['name'],
                                     'time_min': round(mat[j][fi], 1),
                                     'weight': d['weight']}})
    return feats, {'n': len(feats)}


def analyze_service(points, minutes=10, costing='auto', costing_options=None):
    """minutes: int 或 [m1, m2, ...](多圈层等时圈)。"""
    pts = norm_points(points)
    if isinstance(minutes, str):
        minutes = [x for x in minutes.replace(',', ',').split(',') if x.strip()]
    if not isinstance(minutes, (list, tuple)):
        minutes = [minutes]
    contours = [{'time': int(round(float(m)))} for m in minutes]
    feats = []
    for fi, f in enumerate(pts):
        try:
            r = api('/isochrone', {
                'locations': [{'lat': f['lat'], 'lon': f['lon'], 'type': 'break'}],
                'costing': costing,
                'costing_options': costing_options,
                'contours': contours,
                'polygons': True, 'generalize': 10, 'denoise': 0.5})
            for fc in r.get('features', []):
                if fc.get('geometry', {}).get('type') in ('Polygon', 'MultiPolygon'):
                    fc.setdefault('properties', {})['facility'] = f['name']
                    fc['properties']['minutes'] = ','.join(str(int(round(float(m)))) for m in minutes)
                    feats.append(fc)
        except Exception as e:
            print('isochrone failed for', f['name'], e)
    return feats, {'polygons': len(feats), 'minutes': ','.join(str(int(round(float(m)))) for m in minutes)}


def _vrp_dispatch(dep, sts, nveh, capacity, limit, costing, costing_options):
    """Clarke-Wright on one depot. Returns (feats, n_routes)."""
    nodes = [dep] + sts
    mat = time_matrix(nodes, nodes, costing, costing_options)

    def route_time(rt):
        c = 0
        prev = 0
        for i in rt:
            c += mat[prev][i]
            prev = i
        return c + mat[prev][0]

    def route_ok(rt):
        t = 0.0
        prev = 0
        for i in rt:
            t += mat[prev][i]
            nd = nodes[i]
            if nd.get('tw_start') is not None and t < nd['tw_start']:
                t = nd['tw_start']
            if nd.get('tw_end') is not None and t > nd.get('tw_end', INF):
                return -1
            t += nd.get('service_time', 0)
            prev = i
        return t + mat[prev][0]

    routes = [[i + 1] for i in range(len(sts))]
    while True:
        best = None
        for ri in range(len(routes)):
            for rj in range(ri + 1, len(routes)):
                a, b = routes[ri], routes[rj]
                la = sum(sts[k - 1]['weight'] for k in a)
                lb = sum(sts[k - 1]['weight'] for k in b)
                if la + lb > (capacity or INF):
                    continue
                merges = [a + b, b + a, list(reversed(b)) + a, list(reversed(a)) + b]
                for cand in merges:
                    t = route_ok(cand)
                    if t < 0 or t > limit:
                        continue
                    saving = route_time(a) + route_time(b) - t
                    if saving > 1e-9 and (best is None or saving > best[0]):
                        best = (saving, ri, rj, cand)
        if best is None:
            break
        _, ri, rj, cand = best
        routes = [r for k, r in enumerate(routes) if k not in (ri, rj)] + [cand]
    used = routes[:nveh] if nveh else routes
    feats = []
    total_min = 0.0
    for ri, rt in enumerate(used):
        seq = [0] + rt + [0]
        coords = []
        prev = 0
        elapsed = 0.0
        for i in seq:
            if prev != i:
                elapsed += mat[prev][i]
                prev = i
            nd = nodes[i]
            coords.append([nd['lon'], nd['lat']])
        total_min += elapsed / 60
        props = {'vehicle': ri + 1,
                 'depot': dep['name'],
                 'stops': [sts[k - 1]['name'] for k in rt],
                 'load': round(sum(sts[k - 1]['weight'] for k in rt), 2),
                 'time_min': round(elapsed / 60, 1)}
        real = None
        try:
            real = route_shape([nodes[i] for i in seq], costing, costing_options)
        except Exception as e:
            print('vrp route shape failed', e)
        if real:
            feats.append({'type': 'Feature',
                          'geometry': {'type': 'LineString', 'coordinates': real},
                          'properties': dict(kind='vrp_path', **props)})
        feats.append({'type': 'Feature',
                      'geometry': {'type': 'LineString', 'coordinates': coords},
                      'properties': dict(kind='vrp_od', **props)})
    return feats, used, total_min


def analyze_vrp(depot, stops, vehicles=0, capacity=999999, time_limit_min=480,
                costing='auto', costing_options=None):
    depots = norm_points(depot if isinstance(depot, list) else [depot])
    stops = norm_points(stops)
    limit = (time_limit_min or 480) * 60
    total_veh = max(1, int(vehicles or 1)) if vehicles else 0  # 0 = 不限

    feats = []
    served = 0
    routes = 0
    total_min = 0.0
    missed = []
    veh_name = 0
    if len(depots) <= 1:
        sub, used, tmin = _vrp_dispatch(depots[0], stops, total_veh,
                                        capacity, limit, costing, costing_options)
        feats = sub
        served = sum(len(r) for r in used)
        routes = len(used)
        total_min = tmin
    else:
        # 多仓库:先算 仓库×停靠点 矩阵,按最近仓库分簇,再按簇规模分配载具
        nd_, ns = len(depots), len(stops)
        mat_ds = time_matrix(depots, stops, costing, costing_options)
        assign = {d: [] for d in range(nd_)}
        for s_i in range(ns):
            best_d = min(range(nd_), key=lambda d: (mat_ds[d][s_i], d))
            assign[best_d].append(s_i)
        quota = [total_veh // nd_] if total_veh else [0]  # placeholder
        # 分配载具: 每仓保底 1,余数按簇大小降序分
        base = max(1, total_veh // nd_) if total_veh else 1
        rem = (total_veh - base * nd_) if total_veh else 0
        order = sorted(range(nd_), key=lambda d: len(assign[d]), reverse=True)
        vquota = [base] * nd_
        for k in range(rem):
            vquota[order[k % nd_]] += 1
        if not total_veh:
            vquota = [0] * nd_
        for d_i in order:
            cluster = [stops[i] for i in assign[d_i]]
            if not cluster or (total_veh and vquota[d_i] <= 0):
                missed += [s['name'] for s in cluster]
                continue
            nveh = vquota[d_i] if total_veh else 0
            sub, used, tmin = _vrp_dispatch(depots[d_i], cluster, nveh,
                                            capacity, limit, costing, costing_options)
            for f in sub:
                f['properties']['vehicle'] += veh_name
            veh_name += len(used)
            feats += sub
            served += sum(len(r) for r in used)
            routes += len(used)
            total_min += tmin
            missed += [s['name'] for s in cluster if s['name'] not in
                       [s2 for r in used for s2 in [cluster[k - 1]['name'] for k in r]]]

    stats = {'served': served, 'total': len(stops), 'routes': routes,
             'total_time_min': round(total_min, 1)}
    if served < len(stops):
        stats['uncovered'] = missed
    return feats, stats


# ------------------------------------------------------------------ CLI

def parse_args():
    ap = argparse.ArgumentParser(
        prog='na_tool',
        description='ArcGIS-like network analysis atop local Valhalla')
    sub = ap.add_subparsers(dest='cmd', required=True)

    a = sub.add_parser('loc-alloc', help='位置分配(p_median / 最大化覆盖 / / | ...)')
    a.add_argument('--demands', required=True)
    a.add_argument('--candidates', required=True)
    a.add_argument('--p', type=int, default=3)
    a.add_argument('--problem', default='min_impedance', choices=PROBLEMS)
    a.add_argument('--cutoff', type=float, default=None,
                   help='覆盖/衰减上限(分钟), min_impedance 忽略')
    a.add_argument('--capacity', type=float, default=None)
    a.add_argument('--decay', default='linear', choices=('linear', 'power', 'exponential'))
    a.add_argument('--imp-param', type=float, default=1.0)
    a.add_argument('--competitors')
    a.add_argument('--costing', default='auto')
    a.add_argument('--out', required=True)
    a.set_defaults(fn=cli_loc_alloc)

    b = sub.add_parser('closest')
    b.add_argument('--demands', required=True)
    b.add_argument('--in', dest='inp', required=True)
    b.add_argument('--costing', default='auto')
    b.add_argument('--out', required=True)
    b.set_defaults(fn=cli_closest)

    c = sub.add_parser('service')
    c.add_argument('--in', dest='inp', required=True)
    c.add_argument('--minutes', type=int, default=10)
    c.add_argument('--costing', default='auto')
    c.add_argument('--out', required=True)
    c.set_defaults(fn=cli_service)

    d = sub.add_parser('vrp')
    d.add_argument('--depot', required=True)
    d.add_argument('--stops', required=True)
    d.add_argument('--vehicles', type=int, default=0)
    d.add_argument('--capacity', type=float, default=999999)
    d.add_argument('--time-limit', type=float, default=480)
    d.add_argument('--costing', default='auto')
    d.add_argument('--out', required=True)
    d.set_defaults(fn=cli_vrp)

    return ap


def cli_loc_alloc(args):
    feats, stats = analyze_loc_alloc(
        load_points(args.demands), load_points(args.candidates),
        args.p, args.problem, args.cutoff, args.capacity, args.decay,
        args.imp_param, load_points(args.competitors) if args.competitors else None,
        args.costing)
    write_fc(args.out, feats)
    print(json.dumps(stats, ensure_ascii=False))
    print('out:', args.out)


def cli_closest(args):
    feats, _ = analyze_closest(load_points(args.demands),
                               load_points(args.inp), args.costing)
    write_fc(args.out, feats)
    print(json.dumps({'n': len(feats)}))
    print('out:', args.out)


def cli_service(args):
    feats, stats = analyze_service(load_points(args.inp), args.minutes, args.costing)
    write_fc(args.out, feats)
    print(json.dumps(stats))
    print('out:', args.out)


def cli_vrp(args):
    feats, stats = analyze_vrp(load_points(args.depot), load_points(args.stops),
                               args.vehicles, args.capacity, args.time_limit,
                               args.costing)
    write_fc(args.out, feats)
    print(json.dumps(stats, ensure_ascii=False))
    print('out:', args.out)


def record_write():
    pass


if __name__ == '__main__':
    args = parse_args().parse_args()
    args.fn(args)
