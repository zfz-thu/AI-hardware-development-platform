# -*- coding: utf-8 -*-
"""
AI 硬件开发平台 —— 后端主程序（网站的"大脑"）
====================================================

这个文件是整个网站后端的入口。它做两件事：
  1. 提供一个 API 接口 /api/agents，把"当前有哪些 agent"用数据形式返回给前端；
  2. 把 frontend/ 文件夹里的网页（GUI）显示给用户。

技术栈：FastAPI（一个轻量、好上手的 Python 网站框架）。

【怎么运行】（在项目根目录打开终端，依次执行）
  1. 安装依赖：   pip install -r requirements.txt
  2. 启动网站：   python backend/main.py
  3. 打开浏览器访问： http://127.0.0.1:8000
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 导入"agent 注册表"——以后新增 agent，只需要去 agents/registry.py 里登记
from agents.registry import list_agents

# 创建网站应用对象
app = FastAPI(
    title="AI 硬件开发平台",
    description="一站式硬件开发平台，集成多个硬件相关 agent，为硬件工程师提效。",
    version="0.1.0",
)

# 计算前端文件夹的绝对路径（不管在哪个目录启动都能找到）
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/api/agents")
def get_agents():
    """
    API 接口：返回当前平台上所有可用的 agent 列表。
    前端的网页会调用这个接口，把每个 agent 显示成一张可点击的卡片。
    """
    return {"agents": list_agents()}


@app.get("/")
def index():
    """把首页（前端的 index.html）返回给浏览器。"""
    return FileResponse(FRONTEND_DIR / "index.html")


# 把整个 frontend 文件夹作为"静态资源"挂载，这样网页里的图片、样式等都能访问到。
# 注意：这一行要放在最后，避免覆盖上面的 /api 接口。
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# 当直接用 `python backend/main.py` 运行时，自动启动网站服务
if __name__ == "__main__":
    import uvicorn

    # host="127.0.0.1" 表示只在本机访问；reload=True 表示改了代码会自动重启，方便开发
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
