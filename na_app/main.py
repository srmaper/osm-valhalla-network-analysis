"""na_app 的 FastAPI 服务层（与算法脚本分离）。

结构:
  main.py           app 实例 / CORS / 挂载路由与静态
  routes_api.py     /api/* 分析端点(转 na_tool 纯算法)
  routes_road.py    /api/road_info 道路属性(OSM way + 信号灯)
  routes_static.py  / dist 前端产物 / samples 样例 / info / health
  schemas.py        请求体模型
启动: uvicorn na_app.main:app --host 0.0.0.0 --port 8004  (cwd=/opt/valhalla/data)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes_api import router as api_router
from .routes_road import router as road_router
from .routes_static import router as static_router

app = FastAPI(title='OSM Network Analysis', version='2.0', docs_url='/docs')
origins = [x.strip() for x in os.environ.get(
    'NA_CORS_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173'
).split(',') if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Content-Type'],
)
app.include_router(road_router)
app.include_router(api_router)
app.include_router(static_router)

# /network 前缀镜像(与根路径完整一致,便于挂到反代/子路径)
app.include_router(road_router, prefix='/network')
app.include_router(api_router, prefix='/network')
app.include_router(static_router, prefix='/network')
