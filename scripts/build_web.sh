#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/webapp"
npm ci
cd "$ROOT"
python3 scripts/sync_driving_vendor.py
python3 scripts/prepare_driving.py
python3 scripts/build_offline_driving.py
cd "$ROOT/webapp"
npm run build
