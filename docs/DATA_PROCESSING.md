# OSM 数据处理说明

示例输入：`data/input/hong-kong-261113.osm.pbf`。这是 OSM PBF 快照，不是 Valhalla 路由图或前端瓦片。数据生成默认落在 `data/generated/`，处理时不会改写原始 PBF。

## 输入约定

所有原始数据放在 `data/input/`，扩展名为 `.osm.pbf`。仓库默认带一份香港快照；放入其他地区文件后，`scripts/oneclick.sh` 会自动以新文件为基准重建范围、道路索引、矢量瓦片和路由图，并更新 `webapp/public/regions/region.json`。PBF 哈希记录在 `data/generated/source.sha256`，用于判断是否需要重建旧产物。

## 流水线

```text
hong-kong-261113.osm.pbf
  ├─ valhalla_build_admins ──> 行政区域边界
  ├─ valhalla_build_tiles ───> valhalla/tiles/
  ├─ valhalla_build_extract ─> valhalla/tiles.tar
  ├─ pyosmium ───────────────> osm_idx.sqlite
  ├─ ogr2ogr ────────────────> GeoJSONSeq 道路中间文件
  └─ tippecanoe ─────────────> roads_cn.mbtiles
```

### 1. Valhalla 图

`scripts/build_valhalla.sh` 为数据目录写入 Valhalla config，并将 admin SQLite 路径显式设到同一生成目录，然后依次运行 admin、tile 和 extract 构建器。脚本要求输出目录尚不存在，避免覆盖旧数据。Valhalla 的版本、可执行程序路径和并发参数可通过 `PATH`、`VALHALLA_BIN_DIR`、`VALHALLA_JOBS` 配置。使用容器或 chroot 包装的 Valhalla 时，输入 PBF 和生成路径必须挂载到引擎进程可见的路径。

在香港区域 PBF 上生成的是区域路由图；行政边界与部分跨边界路线的完整性取决于 PBF 覆盖范围。全国或跨境部署应提供范围完整的源 PBF 后重建。

### 2. 道路属性 / 信号灯索引

`python -m na_app.build_osm_idx [pbf] [sqlite]` 由 pyosmium 顺序扫描 PBF，只保留有相关标签的道路 way 和 `highway=traffic_signals` 节点。

- 建表字段：way id、车道数、宽度、限速、单行、道路等级、名称；信号灯附带可用的转向标签。
- 输出先写入旁路临时 SQLite，成功后原子替换目标文件，失败会保留旧目标。
- 默认 PBF 为仓库香港样例；默认输出服从 `OSM_INDEX_PATH` / `NA_DATA_DIR`。

### 3. MVT 路网

`scripts/build_mvt.sh` 使用 `configs/osmconf.ini` 配置 GDAL/OGR 的 OSM PBF `lines` 图层字段，筛选 `highway` 要素并保留道路分类、桥隧、单行、限速、车道、名称与 ref 标签；Tippecanoe 将其压缩为 z5–14 的 `roads_cn.mbtiles`。FastAPI 从 MBTiles 的 SQLite 表按瓦片坐标读取压缩 PBF。

### 4. 演示路线

`scripts/prepare_region.py` 读取 PBF 头部 bbox（缺失时扫描节点）生成地图范围 `webapp/public/regions/region.json`。

`scripts/prepare_demo.py` 在 PBF 中挑选最长的可行驶道路作为自动驾驶演示线路，并沿线生成合成需求点、设施点、配送中心和 stops；这些只是开发用虚构位置，不代表真实客户或机构。`scripts/prepare_driving.py` 将线路写入自动驾驶页面。这些步骤不参与 Valhalla 图的构建。

### 5. 构建顺序与运行

```bash
# 一条命令：解析 PBF → Valhalla 图 → 道路索引 → MVT → 前端 → 启动服务
bash scripts/oneclick.sh /path/to/region.osm.pbf

# 只构建不启动
bash scripts/oneclick.sh region.osm.pbf --build-only
```

`oneclick.sh` 会自动检测已有产物并跳过重复构建，日志与 PID 写入 `.run/`。

处理完成后分别运行：

```bash
bash scripts/run_valhalla.sh              # 8002
bash scripts/run_api.sh                   # 8004
```

前端开发服务器：

```bash
bash scripts/build_web.sh                 # 安装依赖并构建发布版
cd webapp && npm run dev                  # 5173，API 代理到 8004
```

前端静态构建由 `scripts/build_web.sh` 完成，输出 `webapp/dist/`，并同步自动驾驶页使用的 MapLibre ESM 资源。

## 常见问题与容量

- PBF 文件仅为原始输入；Valhalla tiles、MVT 和 SQLite 索引必须本地生成，且不纳入 Git。
- Valhalla 与 MVT 输出体积取决于 PBF 覆盖范围、工具版本和瓦片层级；构建前应为临时数据和数据库预留数倍于 PBF 的空间。
- Tippecanoe 为提高可显示性可能丢弃过密瓦片要素；它是地图显示瓦片，不应用作分析数据源。
- 道路车道、信号灯标签的 OSM 覆盖度不均，仿真车道和右转规则是基于标签的近似推断。
