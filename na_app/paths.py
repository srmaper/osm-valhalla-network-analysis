"""Project paths shared by the API modules; generated data stays outside source files."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get('NA_DATA_DIR', ROOT / 'data' / 'generated')).resolve()
SAMPLES_DIR = Path(os.environ.get('NA_SAMPLES_DIR', ROOT / 'data' / 'samples')).resolve()
WEB_DIST = Path(os.environ.get('NA_WEB_DIST', ROOT / 'webapp' / 'dist')).resolve()
RUNS_DIR = Path(os.environ.get('NA_RUNS_DIR', ROOT / 'data' / 'runtime' / 'runs')).resolve()
CACHE_DIR = Path(os.environ.get('NA_CACHE_DIR', ROOT / 'data' / 'runtime' / 'cache')).resolve()
OSM_INDEX_PATH = Path(os.environ.get('OSM_INDEX_PATH', DATA_DIR / 'osm_idx.sqlite')).resolve()
VALHALLA_URL = os.environ.get('VALHALLA_URL', 'http://127.0.0.1:8002').rstrip('/')
