#!/usr/bin/env bash
# One entry point: give it an OSM PBF file (local path or Geofabrik URL) and it
# builds all data, builds the web app, and starts Valhalla + the API.
#
#   bash scripts/oneclick.sh /path/to/region.osm.pbf
#   bash scripts/oneclick.sh https://download.geofabrik.de/.../region-latest.osm.pbf
#   bash scripts/oneclick.sh --check          # environment diagnostics only
#   bash scripts/oneclick.sh region.pbf --build-only
#
# Environment overrides: OSM_PBF, NA_DATA_DIR, NA_PORT, VALHALLA_PORT,
# VALHALLA_THREADS, VALHALLA_CONFIG, VALHALLA_BIN_DIR, PYTHON, NPM, SKIP_WEB.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Load local overrides (gitignored): VALHALLA_CONFIG, SKIP_WEB, ports, etc.
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

NA_PORT="${NA_PORT:-8004}"
VALHALLA_PORT="${VALHALLA_PORT:-8002}"
DATA_DIR="${NA_DATA_DIR:-$ROOT/data/generated}"
RUN_DIR="$ROOT/.run"
BUILD_ONLY=0
CHECK_ONLY=0
NO_SETUP=0
ARG_PBF=""

for arg in "$@"; do
  case "$arg" in
    --build-only) BUILD_ONLY=1 ;;
    --check) CHECK_ONLY=1 ;;
    --no-setup) NO_SETUP=1 ;;
    --setup) NO_SETUP=0 ;;
    -h|--help) sed -n '1,14p' "$0"; exit 0 ;;
    *) ARG_PBF="$arg" ;;
  esac
done

step() { printf '\n==> %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
fail() {
  printf '\nERROR: %s\n\n' "$*" >&2
  cat >&2 <<'TIPS'
排查提示：
  1) 本项目需要 Linux / WSL2 环境；
  2) 需要 Valhalla 命令行工具、Python 3.11+、GDAL/OGR(ogr2ogr)、Tippecanoe；
  3) 首次运行可先执行:  bash scripts/oneclick.sh --check
  4) 自动补全依赖:      bash scripts/oneclick.sh --setup（默认已自动执行）
TIPS
  exit 1
}

if [[ -z "${VALHALLA_BIN_DIR:-}" ]] && ! command -v valhalla_service >/dev/null 2>&1 \
   && [[ -x /opt/valhalla-venv/bin/valhalla_service ]]; then
  VALHALLA_BIN_DIR=/opt/valhalla-venv/bin
  echo "Using local Valhalla tools: $VALHALLA_BIN_DIR"
fi
if [[ -n "${VALHALLA_BIN_DIR:-}" ]]; then
  PATH="$VALHALLA_BIN_DIR:$PATH"
  export PATH
fi

# ---------- environment detection / completion ----------
if [[ "$CHECK_ONLY" == "0" && "$NO_SETUP" != "1" ]]; then
  bash "$ROOT/scripts/setup_env.sh" || warn "环境自动补全未全部成功，将继续尝试已有工具"
  hash -r
fi

# ---------- python ----------
# A venv inside a Windows drive (/mnt/c) can produce unusable symlinks, so the
# managed environment lives in WSL's home directory.
VENV_DIR="${NA_VENV:-$HOME/.cache/osm-valhalla/venv}"
PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]] && "$ROOT/.venv/bin/python" -c 'import osmium' >/dev/null 2>&1; then
    PY="$ROOT/.venv/bin/python"
  elif [[ -x "$VENV_DIR/bin/python" ]] && "$VENV_DIR/bin/python" -c 'import osmium' >/dev/null 2>&1; then
    PY="$VENV_DIR/bin/python"
  elif python3 -c 'import osmium' >/dev/null 2>&1; then
    PY=python3
  else
    PY=python3
  fi
fi

# ---------- node / npm (WSL may not have Node; fall back to Windows Node) ----------
WIN_NODE="/mnt/c/Program Files/nodejs/node.exe"
WIN_NPM_CLI="/mnt/c/Program Files/nodejs/node_modules/npm/bin/npm-cli.js"
NPM_MODE=""
NPM_FOUND="$(command -v npm 2>/dev/null || true)"
if [[ -n "${NPM:-}" ]]; then
  NPM_MODE="custom"
elif [[ -n "$NPM_FOUND" && "$NPM_FOUND" != /mnt/* ]]; then
  NPM_MODE="native"
elif [[ -x "$WIN_NODE" && -f "$WIN_NPM_CLI" ]]; then
  # A /mnt/* npm is a Windows shim; run Windows Node with npm-cli.js instead.
  NPM_MODE="win-node"
elif [[ -n "$NPM_FOUND" ]]; then
  NPM_MODE="native"
elif [[ -x "/mnt/c/Program Files/nodejs/npm.cmd" ]]; then
  NPM_MODE="win-cmd"
fi
if [[ "$NPM_MODE" == "native" ]]; then
  NPM_BIN="$(command -v npm)"
  NPM_SHIM_CMD="$NPM_BIN"
elif [[ "$NPM_MODE" == "custom" ]]; then
  NPM_BIN="$NPM"
  NPM_SHIM_CMD="$NPM"
elif [[ "$NPM_MODE" == "win-node" ]]; then
  WIN_NPM_CLI="$(wslpath -w "$WIN_NPM_CLI")"
  NPM_BIN="node + npm-cli (Windows)"
  NPM_SHIM_CMD="\"$WIN_NODE\" \"$WIN_NPM_CLI\""
elif [[ "$NPM_MODE" == "win-cmd" ]]; then
  NPM_BIN="npm.cmd (Windows)"
  NPM_SHIM_CMD="cmd.exe /c npm"
fi
if [[ -n "${NPM_SHIM_CMD:-}" ]]; then
  mkdir -p "$RUN_DIR/bin"
  cat > "$RUN_DIR/bin/npm" <<SHIM
#!/usr/bin/env bash
exec $NPM_SHIM_CMD "\$@"
SHIM
  chmod +x "$RUN_DIR/bin/npm"
  PATH="$RUN_DIR/bin:$PATH"
  export PATH
  echo "npm: $NPM_BIN"
fi

check_env() {
  local ok=0
  printf '%-28s %s\n' '检查项' '状态'
  printf '%-28s %s\n' '----------------------------' '----'
  if [[ -x "$PY" ]] && "$PY" -c 'import osmium' >/dev/null 2>&1; then
    printf '%-28s %s\n' "Python + pyosmium" "OK ($PY)"
  else
    printf '%-28s %s\n' "Python + pyosmium" "MISSING ($PY)"; ok=1
  fi
  if command -v ogr2ogr >/dev/null 2>&1; then
    printf '%-28s %s\n' 'GDAL / ogr2ogr' "OK"
  else
    printf '%-28s %s\n' 'GDAL / ogr2ogr' 'MISSING'; ok=1
  fi
  if command -v tippecanoe >/dev/null 2>&1; then
    printf '%-28s %s\n' 'Tippecanoe' 'OK'
  else
    printf '%-28s %s\n' 'Tippecanoe' 'MISSING'; ok=1
  fi
  if command -v valhalla_service >/dev/null 2>&1; then
    printf '%-28s %s\n' 'Valhalla (service+build)' 'OK'
  else
    printf '%-28s %s\n' 'Valhalla (service+build)' 'MISSING (set VALHALLA_BIN_DIR)'; ok=1
  fi
  if [[ -n "${NPM_BIN:-}" ]]; then
    printf '%-28s %s\n' 'Node / npm' "OK ($NPM_BIN)"
  else
    printf '%-28s %s\n' 'Node / npm' 'MISSING'; ok=1
  fi
  if [[ -x "$VENV_DIR/bin/python" ]] && "$VENV_DIR/bin/python" -c 'import osmium' >/dev/null 2>&1; then
    printf '%-28s %s\n' 'Managed venv' "OK ($VENV_DIR)"
  fi
  if [[ -f "$VALHALLA_CONFIG_EFFECTIVE" ]]; then
    printf '%-28s %s\n' 'Valhalla graph' "OK ($VALHALLA_CONFIG_EFFECTIVE)"
  else
    printf '%-28s %s\n' 'Valhalla graph' 'will be built'
  fi
  return "$ok"
}

# ---------- resolve Valhalla config up front (for --check too) ----------
VALHALLA_CONFIG_EFFECTIVE="${VALHALLA_CONFIG:-}"
if [[ -z "$VALHALLA_CONFIG_EFFECTIVE" ]]; then
  if [[ -f "$DATA_DIR/valhalla/valhalla.json" ]]; then
    VALHALLA_CONFIG_EFFECTIVE="$DATA_DIR/valhalla/valhalla.json"
  elif [[ -f /opt/valhalla/data/valhalla.json ]]; then
    VALHALLA_CONFIG_EFFECTIVE=/opt/valhalla/data/valhalla.json
  fi
fi

if [[ "$CHECK_ONLY" == "1" ]]; then
  check_env || true
  exit 0
fi

if [[ "$PY" == "python3" ]] && ! python3 -c 'import osmium' >/dev/null 2>&1; then
  step "Preparing Python environment ($VENV_DIR)"
  mkdir -p "$(dirname "$VENV_DIR")"
  python3 -m venv "$VENV_DIR" || fail "cannot create venv (install python3-venv)"
  "$VENV_DIR/bin/python" -m pip install -q --upgrade pip
  "$VENV_DIR/bin/python" -m pip install -q -r "$ROOT/requirements.txt" \
    || fail "pip install failed (check network / pip mirror)"
  PY="$VENV_DIR/bin/python"
fi
need() { command -v "$1" >/dev/null 2>&1 || fail "missing required tool: $1"; }
need curl
"$PY" -c 'import osmium' >/dev/null 2>&1 || fail "pyosmium missing for $PY"
need valhalla_service

# ---------- 1. input ----------
mkdir -p "$ROOT/data/input" "$DATA_DIR" "$RUN_DIR"
if [[ -n "$ARG_PBF" && "$ARG_PBF" =~ ^https?:// ]]; then
  name="$(basename "${ARG_PBF%%\?*}")"
  PBF="${OSM_PBF:-$ROOT/data/input/$name}"
  if [[ ! -s "$PBF" ]]; then
    step "Downloading $name"
    curl -fL --retry 3 --progress-bar -o "$PBF.part" "$ARG_PBF"
    mv "$PBF.part" "$PBF"
  else
    echo "Using cached download: $PBF"
  fi
elif [[ -n "$ARG_PBF" ]]; then
  PBF="$(cd "$(dirname "$ARG_PBF")" && pwd)/$(basename "$ARG_PBF")"
elif [[ -n "${OSM_PBF:-}" ]]; then
  PBF="$OSM_PBF"
else
  PBF="$(ls -t "$ROOT"/data/input/*.osm.pbf 2>/dev/null | head -n 1 || true)"
  [[ -n "$PBF" ]] || fail "没有找到 OSM 文件。用法: bash scripts/oneclick.sh <region.osm.pbf|geofabrik-url>"
  echo "No OSM argument; using data/input/$(basename "$PBF")"
fi
[[ -s "$PBF" ]] || fail "OSM file is empty or missing: $PBF"
export OSM_PBF="$PBF"
PBF_HASH="$(sha256sum "$PBF" | cut -d' ' -f1)"
STAMP="$DATA_DIR/source.sha256"
PREV_HASH=""
[[ -f "$STAMP" ]] && PREV_HASH="$(cat "$STAMP")"
echo "OSM input: $PBF"
if [[ "$PREV_HASH" != "$PBF_HASH" ]]; then
  if [[ -n "$PREV_HASH" ]]; then
    echo "检测到 OSM 数据已更换，旧的道路索引/瓦片/路由图将重建"
  fi
  # Derived artifacts belong to the previous extract; keep them out of the way.
  if [[ -f "$DATA_DIR/valhalla/valhalla.json" && -z "${VALHALLA_CONFIG:-}" ]]; then
    prev="$DATA_DIR/valhalla.prev-$(date +%Y%m%d-%H%M%S)"
    mv "$DATA_DIR/valhalla" "$prev"
    echo "旧 Valhalla 图已移到: $prev"
  fi
  rm -f "$DATA_DIR/roads_cn.mbtiles" "$DATA_DIR/osm_idx.sqlite"
  if [[ -n "${VALHALLA_CONFIG:-}" ]]; then
    warn "正在复用外部 Valhalla 图 ($VALHALLA_CONFIG)，无法校验它是否覆盖当前 OSM 范围；"
    warn "如果路径规划结果异常，请用本仓库构建路由图（去掉 VALHALLA_CONFIG）。"
  fi
fi

# ---------- 2. region + demo data ----------
step "Deriving region bounds and demo fixtures"
"$PY" scripts/prepare_region.py "$PBF"
"$PY" scripts/prepare_demo.py "$PBF"

# ---------- 3. Valhalla graph ----------
OWN_VALHALLA=0
if [[ -n "${VALHALLA_CONFIG:-}" ]]; then
  [[ -f "$VALHALLA_CONFIG" ]] || fail "VALHALLA_CONFIG not found: $VALHALLA_CONFIG"
  echo "Using configured Valhalla graph: $VALHALLA_CONFIG"
  warn "外部 Valhalla 图无法校验是否覆盖当前 OSM 范围；若路由异常请改用本仓库构建的图。"
elif [[ -f "$DATA_DIR/valhalla/valhalla.json" && -s "$DATA_DIR/valhalla/tiles.tar" ]]; then
  echo "Valhalla graph already present, reusing it"
  VALHALLA_CONFIG="$DATA_DIR/valhalla/valhalla.json"
  OWN_VALHALLA=1
elif [[ -f /opt/valhalla/data/valhalla.json && -s /opt/valhalla/data/tiles.tar ]]; then
  echo "Found local Valhalla install; reusing /opt/valhalla/data/valhalla.json"
  echo "(set VALHALLA_CONFIG to use a different graph)"
  warn "复用现有 Valhalla 图；请确认它覆盖当前 OSM 数据范围。"
  VALHALLA_CONFIG=/opt/valhalla/data/valhalla.json
else
  step "Building Valhalla routing graph"
  for tool in valhalla_build_config valhalla_build_admins valhalla_build_tiles \
              valhalla_build_extract; do
    command -v "$tool" >/dev/null 2>&1 || fail "missing Valhalla tool: $tool (set VALHALLA_BIN_DIR)"
  done
  bash scripts/build_valhalla.sh
  VALHALLA_CONFIG="$DATA_DIR/valhalla/valhalla.json"
  OWN_VALHALLA=1
fi

# ---------- 4. road index ----------
step "Building OSM road index"
"$PY" -m na_app.build_osm_idx "$PBF" "$DATA_DIR/osm_idx.sqlite"

# ---------- 5. vector tiles ----------
if [[ -s "$DATA_DIR/roads_cn.mbtiles" ]]; then
  echo "Road tiles already present, skipping rebuild"
else
  step "Building vector road tiles"
  need ogr2ogr
  need tippecanoe
  bash scripts/build_mvt.sh
fi

# ---------- 6. web ----------
if [[ "${SKIP_WEB:-0}" != "1" ]]; then
  step "Building web app"
  [[ -n "$NPM_BIN" ]] || fail "npm not found (install Node.js or set NPM=...)"
  bash scripts/build_web.sh
else
  echo "SKIP_WEB=1: reusing webapp/dist"
fi

printf '%s\n' "$PBF_HASH" > "$STAMP"

if [[ "$BUILD_ONLY" == "1" ]]; then
  step "Build complete (services not started)"
  echo "Valhalla:    $VALHALLA_CONFIG"
  echo "Road index:  $DATA_DIR/osm_idx.sqlite"
  echo "Road tiles:  $DATA_DIR/roads_cn.mbtiles"
  echo "Web bundle:  $ROOT/webapp/dist"
  exit 0
fi

# ---------- 7. services ----------
stop_pidfile() {
  local f="$1"
  [[ -s "$f" ]] || return 0
  kill "$(cat "$f")" 2>/dev/null || true
  rm -f "$f"
}

step "Starting services"
stop_pidfile "$RUN_DIR/valhalla.pid"
stop_pidfile "$RUN_DIR/api.pid"

if [[ "$OWN_VALHALLA" == "1" ]]; then
  export VALHALLA_PORT
  "$PY" scripts/configure_valhalla.py "$VALHALLA_CONFIG" "$(dirname "$VALHALLA_CONFIG")"
fi
export VALHALLA_URL="${VALHALLA_URL:-http://127.0.0.1:$VALHALLA_PORT}"
export NA_HOST="${NA_HOST:-127.0.0.1}"
export NA_PORT
export NA_DATA_DIR="$DATA_DIR"

port_pid() {
  ss -ltnp 2>/dev/null | grep ":$1 " | grep -o 'pid=[0-9]*' | head -n 1 | cut -d= -f2 || true
}

stop_port() {
  local port="$1" pid
  pid="$(port_pid "$port" || true)"
  [[ -n "$pid" ]] || return 0
  echo "端口 $port 已被进程 $pid 占用，先停止它"
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 40); do
    [[ -z "$(port_pid "$port")" ]] && return 0
    sleep 0.5
  done
  kill -9 "$pid" 2>/dev/null || true
  for _ in $(seq 1 10); do
    [[ -z "$(port_pid "$port")" ]] && return 0
    sleep 0.5
  done
  fail "端口 $port 仍被占用，请手动释放后重试"
}

VALHALLA_REUSED=0
if curl -fsS -m 2 "$VALHALLA_URL/status" >/dev/null 2>&1; then
  echo "Valhalla 已在 $VALHALLA_URL 运行，直接复用"
  VALHALLA_REUSED=1
else
  stop_port "$VALHALLA_PORT"
  setsid nohup valhalla_service "$VALHALLA_CONFIG" "${VALHALLA_THREADS:-2}" \
    >"$RUN_DIR/valhalla.log" 2>&1 </dev/null &
  echo $! > "$RUN_DIR/valhalla.pid"
fi

API_REUSED=0
if curl -fsS -m 2 "http://$NA_HOST:$NA_PORT/health" >/dev/null 2>&1; then
  echo "API 已在 http://$NA_HOST:$NA_PORT 运行，直接复用"
  API_REUSED=1
else
  stop_port "$NA_PORT"
  setsid nohup "$PY" -m uvicorn na_app.main:app --host "$NA_HOST" --port "$NA_PORT" \
    >"$RUN_DIR/api.log" 2>&1 </dev/null &
  echo $! > "$RUN_DIR/api.pid"
fi

ok=0
for _ in $(seq 1 120); do
  if curl -fsS -m 1 "$VALHALLA_URL/status" >/dev/null 2>&1 \
     && curl -fsS -m 1 "http://$NA_HOST:$NA_PORT/health" >/dev/null 2>&1; then
    ok=1; break
  fi
  sleep 0.5
done

if [[ "$ok" != "1" ]]; then
  echo "服务未在预期时间内就绪（60 秒）。常见原因：端口被占用、Valhalla 配置路径无效。"
  if grep -q "Address already in use" "$RUN_DIR/valhalla.log" 2>/dev/null; then
    echo "检测到 Valhalla 报错: Address already in use —— 请确认 $VALHALLA_PORT 端口已释放。"
  fi
  echo "日志："
  echo "  $RUN_DIR/valhalla.log"
  echo "  $RUN_DIR/api.log"
  exit 1
fi

step "Ready"
echo "Analyzer:  http://$NA_HOST:$NA_PORT/network/"
echo "API docs:  http://$NA_HOST:$NA_PORT/docs"
echo "Valhalla:  $VALHALLA_URL/status"
echo "Logs:      $RUN_DIR/valhalla.log  $RUN_DIR/api.log"
