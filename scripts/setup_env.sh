#!/usr/bin/env bash
# Detect and (when possible) install the toolchain needed by oneclick.sh.
# Safe to run repeatedly. Requires root/sudo for package installation.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUDO=""
if [[ "$(id -u)" -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  fi
fi
APT_UPDATED=0
FAILED=0

log()  { printf '[setup] %s\n' "$*"; }
warn() { printf '[setup] WARN: %s\n' "$*" >&2; }

have() { command -v "$1" >/dev/null 2>&1; }

apt_ready() { have apt-get; }

apt_update_once() {
  if [[ "$APT_UPDATED" == "0" ]]; then
    log "apt-get update"
    $SUDO apt-get update -qq || warn "apt-get update failed"
    APT_UPDATED=1
  fi
}

apt_install() {
  [[ -n "$SUDO" || "$(id -u)" -eq 0 ]] || { warn "需要 root 权限安装: $*"; FAILED=1; return 1; }
  apt_ready || { warn "非 Debian/Ubuntu 系统，请手动安装: $*"; FAILED=1; return 1; }
  apt_update_once
  log "apt-get install -y $*"
  DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq "$@" || { warn "安装失败: $*"; FAILED=1; return 1; }
}

# ---------- Python 3.11+ ----------
python_ok() {
  have python3 || return 1
  python3 - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}
if ! python_ok; then
  log "Python 3.11+ 缺失或版本过低，尝试安装"
  apt_install python3 python3-venv python3-pip || true
fi
if python_ok; then
  log "Python: $(python3 -V 2>&1)"
else
  warn "Python 3.11+ 仍不可用；可安装 python3.11 或设置 PYTHON=/path/to/python"
  FAILED=1
fi
python3 -c 'import venv' >/dev/null 2>&1 || apt_install python3-venv || true

# ---------- GDAL / OGR ----------
if have ogr2ogr; then
  log "GDAL: $(ogr2ogr --version 2>&1 | head -n 1)"
else
  log "ogr2ogr 缺失，尝试安装 gdal-bin"
  apt_install gdal-bin || true
  have ogr2ogr && log "GDAL 已就绪" || warn "GDAL 仍缺失"
fi

# ---------- Tippecanoe ----------
if have tippecanoe; then
  log "Tippecanoe: $(tippecanoe --version 2>&1 | head -n 1)"
else
  log "Tippecanoe 缺失，尝试从源码构建（需要几分钟）"
  apt_install build-essential libsqlite3-dev zlib1g-dev git || true
  if have git && have make && have g++; then
    tmp="$(mktemp -d)"
    if git clone --depth 1 https://github.com/felt/tippecanoe.git "$tmp/tippecanoe" 2>/dev/null; then
      ( cd "$tmp/tippecanoe" && make -j"$(nproc)" && $SUDO make install ) \
        || warn "Tippecanoe 构建失败"
    else
      warn "无法克隆 tippecanoe 仓库（网络受限）"
    fi
    rm -rf "$tmp" 2>/dev/null || true
  fi
  have tippecanoe && log "Tippecanoe 已就绪" || { warn "Tippecanoe 仍缺失"; FAILED=1; }
fi

# ---------- Node / npm ----------
if have npm; then
  log "Node: $(node -v 2>/dev/null) / npm $(npm -v 2>/dev/null)"
elif [[ -x "/mnt/c/Program Files/nodejs/node.exe" ]]; then
  log "Node: 使用 Windows 侧 Node（WSL 回退）"
else
  log "Node/npm 缺失，尝试安装 nodejs npm"
  apt_install nodejs npm || true
  if have npm; then
    log "Node 已就绪: $(node -v 2>/dev/null)"
  else
    warn "Node/npm 仍缺失；可安装 Node 18+ 或在 Windows 侧安装 Node"
    FAILED=1
  fi
fi

# ---------- Valhalla ----------
if have valhalla_service; then
  log "Valhalla: $(valhalla_service --version 2>&1 | head -n 1)"
elif [[ -x /opt/valhalla-venv/bin/valhalla_service ]]; then
  log "Valhalla: 使用 /opt/valhalla-venv/bin"
elif apt_ready && apt-cache show valhalla-bin >/dev/null 2>&1; then
  log "Valhalla 缺失，尝试安装 valhalla-bin"
  apt_install valhalla-bin || true
  have valhalla_service && log "Valhalla 已就绪" || warn "Valhalla 仍缺失"
else
  warn "未找到 Valhalla 命令行工具。可选用："
  warn "  - Ubuntu: sudo apt install valhalla-bin（若仓库提供）"
  warn "  - 或使用 Valhalla Docker 镜像，并设置 VALHALLA_BIN_DIR / VALHALLA_CONFIG"
  warn "  - 或构建 https://github.com/valhalla/valhalla"
  FAILED=1
fi

if [[ "$FAILED" == "1" ]]; then
  warn "部分依赖未就绪；仍可先运行 --check 查看细节。"
  exit 1
fi
log "环境自检通过"
