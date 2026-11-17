# 技术架构

## 总体数据流

```text
OpenStreetMap PBF
  ├─ Valhalla build tools ──> 路由 tiles + config ──> Valhalla HTTP :8002
  ├─ pyosmium ──────────────> osm_idx.sqlite (ways/signals)
  └─ GDAL/OGR + Tippecanoe ─> roads_cn.mbtiles (MVT)
                                                │
Vue 3 + MapLibre ──HTTP──> FastAPI :8004 ──────┤
       │                    ├─ /api/* 分析 API   │
       │                    ├─ /api/road_info ───┤──> Valhalla + SQLite
       │                    ├─ /mvt/* 瓦片 API ──┤
       └─ driving.html <────┴─ 静态资源         │
              └─ Three.js 3D 自动导航场景
```

## 组件边界

### 数据层

- 原始输入为 OSM PBF；本仓库带香港小区域快照用于复现。
- `build_valhalla.sh` 生成 Valhalla 路由数据，`build_mvt.sh` 生成可视化矢量路网。
- `na_app/build_osm_idx.py` 只抽取仿真与导航所需属性，避免运行时扫描 PBF。
- 大型派生数据写入 `data/generated/`，运行态写入 `data/runtime/`，均由 `.gitignore` 排除。

### FastAPI 服务

- `na_app/main.py`：应用装配、CORS 和路由注册。
- `na_app/routes_api.py`：路径规划、等时圈、最近设施、选址、VRP、2SFCA API 编排。
- `na_app/routes_road.py`：请求 Valhalla `/trace_attributes`，关联 OSM way 索引并投影交通信号灯到路线里程。
- `na_app/routes_static.py`：Vue `dist`、样例、驾驶页、车模及 MBTiles 服务。
- `na_app/runs.py`：分析请求与结果落盘为 GeoJSON/JSON 历史记录。
- `na_app/paths.py`：集中管理 `NA_DATA_DIR`、`NA_RUNS_DIR`、`NA_WEB_DIST`、`OSM_INDEX_PATH` 和 `VALHALLA_URL`。
- `na_tool.py`：Valhalla 网络矩阵与分析算法，采用批量矩阵请求，结果按需缓存。

### 前端

- Vue 3 + Vite：`webapp/src/` 内含分析状态、地图、底图、点集、结果历史和 UI 组件。
- MapLibre GL JS：绘制 CARTO 底图、OSM MVT、结果 GeoJSON、设施点和分析图层；无天地图 key 时不注册天地图注记源，若后端有 `roads_cn.mbtiles` 则自动启用本地 OSM 道路层。
- 地图范围由 `scripts/prepare_region.py` 从输入 PBF 自动推导，写入 `webapp/public/regions/region.json`；分析页和自动驾驶页读取该文件设置初始视野与 `maxBounds`，未提供时回退到内置香港范围。
- Vite 发布包将 MapLibre 6 的 worker 复制到 `/assets/maplibre-gl-worker.mjs`；FastAPI 对 `.mjs` 返回 JavaScript MIME，保证本地 worker 能启动。
- `webapp/public/driving.html`：独立自动模拟驾驶页面；从 `localStorage.na_drive_route` 读取被选路线，未提供时展示香港示例线路。
- Three.js 自定义 MapLibre layer：绘制玩家车、NPC 车和行人模型；路线进度和场景位置共享同一参考线。
- 本仓库不发布手动驾驶独立页，也不从结果卡提供手动驾驶入口。

## API 和请求过程

### 一般网络分析

1. 前端准备点集、costing 和分析参数。
2. `POST /api/{op}` 调用 `na_tool.py`。
3. `na_tool.py` 根据 Valhalla 的 `/route`、`/isochrone`、`/sources_to_targets` 计算路网成本。
4. 结果标准化为 GeoJSON，记录到 `data/runtime/runs/<id>/` 并返回统计值。

### 路线到驾驶场景

1. 路线 API 返回经纬度 LineString 和 maneuver 数据。
2. 前端驾驶页面调用 `/api/road_info`。
3. 后端 Valhalla `/trace_attributes` 将采样点 map-match 到 OSM edges，得到 way id、道路等级、速度和长度。
4. SQLite way 属性补充车道数、车道宽、限速、单行和道路名称；信号灯按路线 bbox 查询后投影到路线里程。
5. 浏览器对路线平滑、重采样、曲线拟合、构造车道面和边界；同一几何用于渲染及 OpenDRIVE / Lanelet2 导出。
6. 自动驾驶按路线距离推进，读取道路段限速、车道和信号灯；Three.js 负责车体、NPC 与行人渲染。

## 道路索引

`osm_idx.sqlite` 由 `na_app/build_osm_idx.py` 生成：

- `ways`：OSM way id、`lanes`、`lanes:forward/backward`、`width`、`maxspeed`、`oneway`、`highway`、`name`。
- `signals`：信号灯节点坐标，以及转向、右转规则、车道、方向等可选标签。
- 索引使用 SQLite 本地读取；数据库路径可由 `OSM_INDEX_PATH` 覆盖。

## 运行态目录和配置

| 环境变量 | 默认值 | 作用 |
|---|---|---|
| `VALHALLA_URL` | `http://127.0.0.1:8002` | Valhalla HTTP endpoint |
| `NA_DATA_DIR` | `data/generated` | MBTiles 和 Valhalla build 输出目录 |
| `OSM_INDEX_PATH` | `$NA_DATA_DIR/osm_idx.sqlite` | OSM 道路属性数据库 |
| `NA_RUNS_DIR` | `data/runtime/runs` | 分析历史 |
| `NA_CACHE_DIR` | `data/runtime/cache` | Valhalla 矩阵缓存 |
| `NA_WEB_DIST` | `webapp/dist` | FastAPI 托管的 Vite build |
| `NA_CORS_ORIGINS` | 本地 Vite 地址 | 开发跨域白名单 |

## 安全边界

- 默认仅监听 `127.0.0.1`。CORS 默认允许本地 Vite 开发地址；部署时应显式设置白名单、反向代理和认证。
- API 没有用户认证、配额或多租户隔离，适合本机演示，不适合直接暴露公网。
- Provider key 放在未跟踪的 `webapp/.env.local`，不要硬编码到源文件或提交。
- 历史点集和分析结果保存在本地 `data/runtime`，不可提交到仓库。
