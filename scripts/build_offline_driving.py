#!/usr/bin/env python3
"""Bundle the real automatic-driving page into one self-contained HTML file.

All page assets (MapLibre JS/CSS/worker, three.js + GLTFLoader, GLB car
models, route data) are inlined as data/blob URLs, so the file can be opened
directly with file:// and needs no local server. The basemap still uses the
online tile services configured in the page.
"""
import base64
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'webapp' / 'public'
PAGE = PUBLIC / 'driving.html'
OUT = ROOT / 'docs' / 'driving-offline.html'
URBAN_ROUTE = ROOT / 'data' / 'samples' / 'urban-demo-route.geojson'
URBAN_INFO = ROOT / 'data' / 'samples' / 'urban-demo-roadinfo.json'

ASSETS = {
    'css': PUBLIC / 'vendor' / 'maplibre-gl.css',
    'maplibre': PUBLIC / 'vendor' / 'maplibre-gl.mjs',
    'worker': PUBLIC / 'vendor' / 'maplibre-gl-worker.mjs',
    'three': PUBLIC / 'vendor' / 'three' / 'three.module.js',
    'gltf': PUBLIC / 'vendor' / 'three' / 'addons' / 'loaders' / 'GLTFLoader.js',
    'bgu': PUBLIC / 'vendor' / 'three' / 'addons' / 'utils' / 'BufferGeometryUtils.js',
}
MODELS = {'sedan': PUBLIC / 'models' / 'sedan.glb',
          'sedan-sports': PUBLIC / 'models' / 'sedan-sports.glb'}
TEXTURES = {'colormap': PUBLIC / 'models' / 'Textures' / 'colormap.png'}
SPRITES = {'car_top': PUBLIC / 'car_top.png', 'car_rear': PUBLIC / 'car_rear.png'}


def b64(path):
    return base64.b64encode(path.read_bytes()).decode('ascii')


def extract_block(html, start, marker):
    i = html.index(start, marker)
    j = html.index('</script>', i)
    body = html[i + len(start):j]
    return body, j + len('</script>')


def main():
    for path in list(ASSETS.values()) + list(MODELS.values()):
        if not path.is_file():
            raise SystemExit(f'Missing asset: {path}')
    html = PAGE.read_text(encoding='utf-8')

    # Prefer the signal-rich urban demo route when it is present.
    road_info_script = ''
    if URBAN_ROUTE.is_file():
        urban = json.loads(URBAN_ROUTE.read_text(encoding='utf-8'))
        encoded = json.dumps(urban, ensure_ascii=False, separators=(',', ':'))
        html, n = re.subn(r'^const ROUTE = .*?;$', 'const ROUTE = ' + encoded + ';',
                          html, count=1, flags=re.MULTILINE)
        if n != 1:
            raise SystemExit('Could not replace ROUTE with the urban demo route')
    if URBAN_INFO.is_file():
        info = URBAN_INFO.read_text(encoding='utf-8')
        road_info_script = ('<script>window.__ROAD_INFO__ = ' + info + ';</script>')

    # inline the MapLibre stylesheet
    link = '<link rel="stylesheet" href="vendor/maplibre-gl.css">'
    if link not in html:
        raise SystemExit('MapLibre stylesheet link not found')
    html = html.replace(link, '<style>\n' + ASSETS['css'].read_text(encoding='utf-8') + '\n</style>', 1)

    # --- first module block: main app (imports maplibre) ---
    app_body, after_app = extract_block(html, '<script type="module">', 0)
    import_line = "import * as maplibregl from './vendor/maplibre-gl.mjs';"
    if import_line not in app_body:
        raise SystemExit('Main app maplibre import not found')
    app_body = app_body.replace(import_line, '/* maplibre injected by bundle */', 1)

    # --- import map + second module block: three.js car layer ---
    im_start = html.index('<script type="importmap">', after_app)
    im_end = html.index('</script>', im_start) + len('</script>')
    car_body, after_car = extract_block(html, '<script type="module">', im_end)
    for old in ("import * as THREE from 'three';",
                "import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';"):
        if old not in car_body:
            raise SystemExit(f'Car layer import not found: {old}')
        car_body = car_body.replace(old, '', 1)

    head = html[:html.index('<script type="module">')]
    tail = html[after_car:]
    payload = {
        'app': base64.b64encode(app_body.encode('utf-8')).decode('ascii'),
        'car': base64.b64encode(car_body.encode('utf-8')).decode('ascii'),
    }
    for key, path in ASSETS.items():
        if key != 'css':
            payload[key] = b64(path)
    for key, path in MODELS.items():
        payload['model:' + key] = b64(path)
    for key, path in TEXTURES.items():
        payload['tex:' + key] = b64(path)
    for key, path in SPRITES.items():
        payload['sprite:' + key] = b64(path)

    data_script = ('<script type="application/json" id="assets">'
                   + json.dumps(payload) + '</script>')

    bootstrap = r'''
<script>
(async () => {
  const payload = JSON.parse(document.getElementById('assets').textContent);
  const bin = s => { const b = atob(s); const u = new Uint8Array(b.length);
    for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; };
  const url = (s, type) => URL.createObjectURL(new Blob([bin(s)], { type }));
  const text = s => new TextDecoder().decode(bin(s));
  const textUrl = (s, type) => URL.createObjectURL(new Blob([s], { type }));

  const threeUrl = url(payload.three, 'text/javascript');
  const bguUrl = url(payload.bgu, 'text/javascript');
  const gltfSource = text(payload.gltf)
    .replace("'../utils/BufferGeometryUtils.js'", JSON.stringify(bguUrl));
  const gltfUrl = textUrl(gltfSource, 'text/javascript');
  const maplibreUrl = url(payload.maplibre, 'text/javascript');
  const workerUrl = url(payload.worker, 'text/javascript');

  const map = document.createElement('script');
  map.type = 'importmap';
  map.textContent = JSON.stringify({ imports: { 'three': threeUrl } });
  document.head.appendChild(map);

  const spriteTop = url(payload['sprite:car_top'], 'image/png');
  const spriteRear = url(payload['sprite:car_rear'], 'image/png');
  let appSource = text(payload.app)
    .replace("'car_top.png'", JSON.stringify(spriteTop))
    .replace("'car_rear.png'", JSON.stringify(spriteRear))
    .replace('/* maplibre injected by bundle */',
    'import * as maplibregl from ' + JSON.stringify(maplibreUrl) + ';\n'
    + 'try { maplibregl.setWorkerUrl(' + JSON.stringify(workerUrl) + '); } catch (e) {}');
  let carSource = text(payload.car)
    .replace('/* THREE_PLACEHOLDER */', '')
    .replace(/THREE_IMPORT_PLACEHOLDER/g, '');
  carSource = 'import * as THREE from ' + JSON.stringify(threeUrl) + ';\n'
    + 'import { GLTFLoader } from ' + JSON.stringify(gltfUrl) + ';\n' + carSource;
  const colormapUrl = url(payload['tex:colormap'], 'image/png');
  carSource = carSource.replace('const loader = new GLTFLoader();',
    'const loader = new GLTFLoader();\n'
    + 'try { loader.manager.setURLModifier(u => /colormap\\.png$/i.test(u) ? '
    + JSON.stringify(colormapUrl) + ' : u); } catch (e) {}');
  carSource = carSource.replace("./models/sedan.glb", url(payload['model:sedan'], 'model/gltf-binary'));
  carSource = carSource.replace("./models/sedan-sports.glb", url(payload['model:sedan-sports'], 'model/gltf-binary'));

  const boot = (src) => new Promise(res => {
    const el = document.createElement('script');
    el.type = 'module';
    el.src = textUrl(src, 'text/javascript');
    el.onload = res; el.onerror = res;
    document.body.appendChild(el);
  });
  await boot(appSource);
  await boot(carSource);
})();
</script>
'''

    if road_info_script:
        head = head.replace('</head>', road_info_script + '\n</head>', 1)
    out = head + data_script + bootstrap + tail
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(out, encoding='utf-8', newline='')
    print(f'Wrote {OUT} ({OUT.stat().st_size / 1048576:.2f} MB)')


if __name__ == '__main__':
    main()
