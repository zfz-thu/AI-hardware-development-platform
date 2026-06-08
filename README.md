# AI-hardware-development-platform

第二个项目：开发一站式硬件开发平台网站，内部集成多个硬件工作常用 agent，为硬件工作提效。

工程师打开网站后，可以通过直观的图形界面（GUI）浏览并选择自己需要的 agent / skill 来完成工作。

---

## 📁 项目结构

```
ai-hardware-platform/
├─ backend/                后端（网站的"大脑"，用 Python 写）
│  ├─ main.py              ★ 网站服务入口，启动它就能跑起来
│  └─ agents/              所有硬件 agent 都放这里
│     ├─ __init__.py       （让 Python 把本文件夹识别为"包"）
│     └─ registry.py       ★ Agent 注册表 —— 新增 agent 在这里登记
├─ frontend/               前端（工程师在浏览器里看到的界面）
│  └─ index.html           ★ 首页：显示 agent 卡片，可点击选择
├─ requirements.txt        Python 依赖清单
├─ .gitignore             Git 忽略清单
└─ README.md             本说明文件
```

> 标 ★ 的是你以后最常打交道的文件。

---

## 🚀 如何运行（本地预览）

> 前提：电脑已安装 [Python](https://www.python.org/)（3.9 或更新版本）。

在项目根目录打开终端，依次执行：

```bash
# 1. 安装依赖（只需第一次运行）
pip install -r requirements.txt

# 2. 启动网站
python backend/main.py

# 3. 打开浏览器访问
#    http://127.0.0.1:8000
```

打开后，你会看到平台首页，上面以卡片形式列出当前所有 agent。

---

## ➕ 如何添加一个新的 Agent

整个平台的设计目标，就是让"加新 agent"变得简单。三步即可：

1. 在 `backend/agents/` 文件夹里，新建一个 Python 文件（例如 `my_agent.py`），写好这个 agent 的功能逻辑；
2. 打开 `backend/agents/registry.py`，仿照里面的示例，在 `AGENTS` 列表中加一段登记信息；
3. 刷新网页 —— 新 agent 会自动出现在界面上，**无需改动前端代码**。

每个 agent 的登记信息长这样：

```python
{
    "id": "my-agent",            # 英文唯一标识
    "name": "我的新 Agent",       # 界面上显示的中文名
    "description": "一句话说明它干什么",
    "category": "电路分析",       # 分类
    "status": "available",       # available=可用, coming_soon=即将上线
}
```

---

## 🛠️ 技术栈说明（给非软件背景的你）

| 部分 | 用的技术 | 通俗解释 |
|------|----------|----------|
| 后端 | Python + FastAPI | 在服务器上真正"干活"的大脑 |
| 前端 | HTML + CSS + JavaScript | 工程师在浏览器里看到、点击的界面 |
| 版本管理 | Git + GitHub | 记录每次修改、多人协作、云端备份 |

---

## 📌 后续规划（建议）

- [ ] 接入第一个真实 agent（如 WCCA 被动放电分析）
- [ ] 点击卡片后，进入该 agent 的具体操作页面
- [ ] 增加 agent 分类筛选、搜索功能
- [ ] 用户登录与权限管理
