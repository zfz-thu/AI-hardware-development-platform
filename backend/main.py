# -*- coding: utf-8 -*-
"""
AI 硬件开发平台 —— 后端主程序
"""
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from agents.registry import list_agents, list_categories
from wcca_api import router as wcca_router

app = FastAPI(
    title="AI 硬件开发平台",
    description="一站式硬件开发平台，集成多个硬件相关 agent，为硬件工程师提效。",
    version="0.2.0",
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# WCCA 相关 API（chat / upload / calculate）
app.include_router(wcca_router)


@app.get("/api/categories")
def get_categories():
    return {"categories": list_categories()}


@app.get("/api/agents")
def get_agents(
    category: str | None = Query(None, description="按分类筛选"),
    keyword: str | None = Query(None, description="按关键词搜索"),
):
    agents = list_agents(category=category, keyword=keyword)
    return {"agents": agents}


@app.get("/api/agents/{agent_id}")
def get_agent(agent_id: str):
    agents = list_agents()
    for a in agents:
        if a["id"] == agent_id:
            return {"agent": a}
    return {"agent": None}, 404


@app.get("/agent/wcca-circuit")
def wcca_page():
    """WCCA 电路类型选择页。"""
    return FileResponse(FRONTEND_DIR / "wcca.html")


@app.get("/agent/passive-discharge")
def passive_discharge_page():
    """WCCA 被动放电分析 —— 专家对话页。"""
    return FileResponse(FRONTEND_DIR / "passive-discharge.html")


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


# 静态文件挂载（必须在最后，避免覆盖上面的路由）
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
