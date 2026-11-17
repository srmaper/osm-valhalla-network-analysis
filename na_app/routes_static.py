"""静态托管:前端 dist(Vite 构建产物)、样例、服务信息、路网 MVT 瓦片。"""
import os
import sqlite3
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, Response
from .paths import DATA_DIR, SAMPLES_DIR, WEB_DIST

router = APIRouter()

BASE = str(DATA_DIR)
DIST = str(WEB_DIST)
SAMPLES = str(SAMPLES_DIR)

# ---- 路网 MVT(mbtiles 直读,统一走 8004,不再依赖独立的 :8003) ----
import threading

_MVT_TYPE = 'application/vnd.mapbox-vector-tile'
_TLS = threading.local()          # 每线程独立 sqlite 连接(FastAPI 线程池并发)


def _db(name):
    store = getattr(_TLS, 'dbs', None)
    if not store:
        store = _TLS.dbs = {}
    c = store.get(name)
    if c is not None:
        return c
    path = os.path.join(BASE, name + '.mbtiles')
    if not os.path.isfile(path):
        return None
    c = sqlite3.connect(path)
    ok = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='map'").fetchone()
    if ok:
        store[name] = c
        return c
    c.close()
    return None


def _load_tile(name, z, x, fy):
    c = _db(name)
    if not c:
        return None
    if name == 'roads':
        row = c.execute(
            'SELECT images.tile_data FROM map JOIN images ON images.tile_id = map.tile_id '
            'WHERE map.zoom_level=? AND map.tile_column=? AND map.tile_row=?',
            (z, x, fy)).fetchone()
    else:
        row = c.execute(
            'SELECT images.tile_data FROM map JOIN images ON images.tile_id = map.tile_id '
            'WHERE map.zoom_level=? AND map.tile_column=? AND map.tile_row=?',
            (z, x, fy)).fetchone()
    return row and row[0]


@router.get('/mvt/info')
def mvt_info():
    return {'sources': {name: name for name in ('roads', 'roads_cn')
                        if os.path.isfile(os.path.join(BASE, name + '.mbtiles'))}}


@router.get('/mvt/{src}/{z}/{x}/{y}.mvt')
def mvt_tile(src: str, z: int, x: int, y: int):
    name = {'cn': 'roads_cn', 'roads': 'roads'}.get(src)
    if not name or z > 14:
        return Response(status_code=404)
    data = _load_tile(name, z, x, (1 << z) - 1 - y)
    if not data:
        return Response(status_code=404)
    return Response(content=bytes(data), media_type=_MVT_TYPE,
                    headers={'Access-Control-Allow-Origin': '*',
                             'Content-Encoding': 'gzip'})


@router.get('/')
@router.get('/index.html')
@router.get('/access.html')
def index():
    fp = os.path.join(DIST, 'index.html')
    if os.path.exists(fp):
        return FileResponse(fp, media_type='text/html; charset=utf-8')
    legacy = os.path.join(BASE, 'access.html')
    if os.path.exists(legacy):
        return FileResponse(legacy, media_type='text/html; charset=utf-8')
    return JSONResponse({'error': '前端未部署'}, status_code=404)


@router.get('/assets/{name}')
def assets(name: str):
    fp = os.path.join(DIST, 'assets', os.path.basename(name))
    if not os.path.exists(fp):
        return JSONResponse({'error': 'not found'}, status_code=404)
    media = ('application/javascript' if fp.endswith(('.js', '.mjs'))
             else 'text/css' if fp.endswith('.css') else 'application/octet-stream')
    return FileResponse(fp, media_type=media)


@router.get('/driving.html')
def driving_page():
    fp = os.path.join(DIST, 'driving.html')
    if not os.path.exists(fp):
        return JSONResponse({'error': 'driving.html 未部署'}, status_code=404)
    return FileResponse(fp, media_type='text/html; charset=utf-8')


@router.get('/driving_odr.html')
def driving_odr_page():
    fp = os.path.join(DIST, 'driving_odr.html')
    if not os.path.exists(fp):
        return JSONResponse({'error': 'driving_odr.html 未部署'}, status_code=404)
    return FileResponse(fp, media_type='text/html; charset=utf-8')


@router.get('/vendor/{path:path}')
def vendor(path: str):
    safe = os.path.normpath(path).replace('..', '')
    fp = os.path.join(DIST, 'vendor', safe)
    if not os.path.exists(fp) or not os.path.isfile(fp):
        return JSONResponse({'error': 'not found'}, status_code=404)
    media = ('text/css' if fp.endswith('.css')
             else 'application/javascript' if fp.endswith(('.js', '.mjs'))
             else 'application/octet-stream')
    return FileResponse(fp, media_type=media)


@router.get('/models/{path:path}')
def model_file(path: str):
    safe = os.path.normpath(path).replace('..', '')
    fp = os.path.join(DIST, 'models', safe)
    if not os.path.exists(fp) or not os.path.isfile(fp):
        return JSONResponse({'error': 'not found'}, status_code=404)
    media = 'image/png' if fp.endswith('.png') else 'model/gltf-binary'
    return FileResponse(fp, media_type=media)


@router.get('/regions/{name}')
def region_file(name: str):
    fp = os.path.join(DIST, 'regions', os.path.basename(name))
    if not os.path.exists(fp):
        return JSONResponse({'error': 'not found'}, status_code=404)
    media = ('application/json' if fp.endswith('.json')
             else 'application/geo+json')
    return FileResponse(fp, media_type=media + '; charset=utf-8')


@router.get('/{name}.png')
def root_png(name: str):
    fp = os.path.join(DIST, os.path.basename(name) + '.png')
    if not os.path.exists(fp):
        return JSONResponse({'error': 'not found'}, status_code=404)
    return FileResponse(fp, media_type='image/png')


@router.get('/samples/{name}')
def samples(name: str):
    fp = os.path.join(SAMPLES, os.path.basename(name))
    if not os.path.exists(fp):
        return JSONResponse({'error': 'not found'}, status_code=404)
    return FileResponse(fp, media_type='application/json; charset=utf-8')


@router.get('/info')
@router.get('/health')
def info():
    return {'name': 'na_server', 'api': '2.0', 'engine': 'fastapi',
            'endpoints': ['/api/loc-alloc', '/api/closest', '/api/service',
                          '/api/vrp', '/api/2sfca'],
            'page': '/network/'}
