# OSM Network Analysis & Automatic Drive Simulation

基于 OpenStreetMap 的网络分析与自动驾驶路线回放示例。项目包含 OSM PBF 数据处理、Valhalla 路由、FastAPI 服务、Vue 3 地图前端，以及**仅自动巡航**的 3D 路线模拟。

> 这是本地开发 / 研究示例，不是面向公网开放的生产部署。不要将未加认证的 API 直接暴露到互联网。

## 能力

- 路径规划（可选备选路线）、最近设施、等时圈、选址、VRP 配送、2SFCA 可达性。
- 从 OSM 路段提取车道、限速、道路方向和信号灯属性，生成 OpenDRIVE / Lanelet2 导出。
- 浏览器自动模拟导航：路线巡航、中文转向提示、路网与 3D 车道场景、交通车辆 / 行人、碰撞计分和天气效果。
- 自动驾驶入口独立为 `webapp/public/driving.html`；本仓库不包含手动驾驶页面或手动驾驶入口。

## 技术组成

| 层 | 技术 | 输入 / 输出 |
|---|---|---|
| OSM 数据处理 | OSM PBF、Valhalla tools、pyosmium、GDAL/OGR、Tippecanoe | PBF → 路由 tiles、道路属性 SQLite、MVT MBTiles |
| 后端 | Python 3.11+、FastAPI、Uvicorn | 分析 API、Valhalla 代理、历史记录、静态文件/MVT |
| 路由引擎 | Valhalla | route、sources-to-targets、isochrone、trace attributes |
| 前端 | Vue 3、Vite、MapLibre GL JS、Three.js | 交互分析地图、自动驾驶仿真 |
| 持久化 | SQLite / GeoJSON | OSM 道路索引、运行历史、矩阵缓存 |

完整系统架构、API 契约和数据处理说明：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)、[`docs/DATA_PROCESSING.md`](docs/DATA_PROCESSING.md)。

## 仓库数据

- `data/input/hong-kong-261113.osm.pbf`：香港 OSM 示例快照（约 36 MiB），用于复现处理流程。
- `data/samples/`：小型分析点集和从示例 PBF 提取的路线 GeoJSON。
- `data/generated/`：构建生成的 Valhalla tiles、MVT 和道路属性索引；不提交。
- `data/runtime/`：运行历史、临时结果和缓存；不提交。

OSM 数据署名与数据许可证见 [`docs/OSM_ATTRIBUTION.md`](docs/OSM_ATTRIBUTION.md)。代码使用 MIT；这不改变 OSM 数据自身的 ODbL 条款。

## 从 PBF 重建数据

推荐在 Ubuntu / WSL2 中运行。需要安装 Valhalla 命令行工具、Python 3.11+、GDAL/OGR、Tippecanoe 和 `requirements.txt` 中的依赖。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 默认处理仓库内的香港 PBF；数据输出到 data/generated/
bash scripts/build_all.sh
```

`build_all.sh` 会执行：

1. `build_valhalla.sh`：生成 Valhalla 配置、行政区域、路由 tiles 和 extract。
2. `na_app.build_osm_idx`：扫描道路 way / traffic signals，生成 `osm_idx.sqlite`。
3. `build_mvt.sh`：使用仓库内 `configs/osmconf.ini` 配置 OGR 道路字段，再用 Tippecanoe 构建 `roads_cn.mbtiles`。
4. `extract_hk_demo_route.py`：从示例 PBF 生成自动驾驶演示路线；`generate_hk_samples.py` 生成沿线的合成分析点集；`prepare_driving.py` 更新页面内置路线。

构建脚本不会覆盖已有的 Valhalla 输出或 MBTiles；如果想重建，请先自行备份并移走对应输出目录。详情、产物结构和限制见数据处理文档。

## 启动

先在终端 A 启动 Valhalla（数据处理完成后）：

```bash
bash scripts/run_valhalla.sh
```

终端 B 启动后端：

```bash
pip install -r requirements.txt
bash scripts/run_api.sh
```

终端 C 构建和启动前端：

```bash
bash scripts/build_web.sh
cd webapp
npm run dev
```

打开 `http://127.0.0.1:5173`。Vite 将 `/api` 和 `/samples` 代理到本机 FastAPI。自动驾驶静态页依赖同版本 MapLibre ESM 文件，可用 `bash scripts/build_web.sh` 做完整发布构建（安装依赖、同步资源并构建 `dist/`）。

环境变量可在仓库根目录 `.env` 设置，参考 [`.env.example`](.env.example)。如需天地图注记，在 `webapp/.env.local` 设置 `VITE_TDT_KEY`；密钥不要提交。没有密钥时仍可使用 CARTO / Esri 底图。

## API 速览

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/route` | 路线与中文 maneuver |
| `POST` | `/api/road_info` | 路线道路属性、车道和信号灯 |
| `POST` | `/api/closest`、`/api/service`、`/api/vrp`、`/api/loc-alloc`、`/api/2sfca` | 网络分析 |
| `GET` | `/api/runs`、`/api/runs/{id}/result` | 历史运行记录 |
| `GET` | `/mvt/cn/{z}/{x}/{y}.mvt` | OSM 矢量路网瓦片 |
| `GET` | `/health` | 服务状态 |

交互式 API 文档：`http://127.0.0.1:8004/docs`。

## 自动驾驶演示

分析一条路线后，在结果卡点击 🚗，页面读取路线结果并打开自动模拟驾驶。也可以直接打开 `/driving.html` 载入随仓库提供的香港示例路线。车辆、车道、路口和仿真规则均由浏览器页面驱动；Valhalla 负责规划和网络成本，不负责实时物理仿真。

## 开发与验证

```bash
cd webapp && npm ci && npm run build
cd .. && python -m compileall -q na_app na_tool.py scripts
```

更完整的本地端到端验证依赖生成的 Valhalla tiles、道路索引和 MVT 文件。

## License

代码：MIT（见 [`LICENSE`](LICENSE)）。OSM 数据：ODbL；底图和第三方 JS/3D 资产按各自条款使用，见 [`docs/OSM_ATTRIBUTION.md`](docs/OSM_ATTRIBUTION.md) 与 [`docs/THIRD_PARTY_NOTICES.md`](docs/THIRD_PARTY_NOTICES.md)。
