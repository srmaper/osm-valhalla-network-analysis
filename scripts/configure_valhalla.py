#!/usr/bin/env python3
"""Keep Valhalla's generated admin DB inside the selected data directory."""
import json
import os
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: configure_valhalla.py CONFIG.json DATA_DIR')
    config_path = Path(sys.argv[1]).resolve()
    data_dir = Path(sys.argv[2]).resolve()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    mjolnir = config.setdefault('mjolnir', {})
    mjolnir['admin'] = str(data_dir / 'admin.sqlite')
    tmp = config_path.with_suffix(config_path.suffix + '.tmp')
    tmp.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, config_path)
    print(f'Valhalla admin DB path: {mjolnir["admin"]}')


if __name__ == '__main__':
    main()
