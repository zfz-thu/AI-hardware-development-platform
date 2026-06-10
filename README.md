# AI-hardware-development-platform

第二个项目：开发一站式硬件开发平台网站，内部集成多个硬件工作常用 agent，为硬件工作提效。

工程师打开网站后，可以通过直观的图形界面（GUI）浏览并选择自己需要的 agent / skill 来完成工作。

---

## 📁 项目结构

```
ai-hardware-platform/
├─ backend/                后端（网站的"大脑"，用 Python 写）
│  ├─ main.py              ★ 网站服务入口，启动它就能跑起来
│  ├─ wcca_api.py          ★ WCCA 分析接口：专家对话 / 文件上传 / 计算
│  ├─ agents/              所有硬件 agent 的注册信息
│  │  ├─ __init__.py       （让 Python 把本文件夹识别为"包"）
│  │  └─ registry.py       ★ Agent 注册表 —— 新增 agent 在这里登记
│  └─ engine/              WCCA 计算引擎（纯数学，不依赖网络）
│     ├─ models.py         数据结构：电路参数、拓扑、计算结果
│     ├─ calculator.py     ★ 计算编排器：串起整个 WCCA 流程
│     ├─ topology.py       拓扑求值：按支路描述算等效电阻（数据驱动）
│     ├─ resistor.py       电阻最坏情况值（温漂 + 公差 + 寿命漂移）
│     ├─ discharge.py      RC 放电时间 / 电容反推
│     └─ power.py          功率降额验证
├─ frontend/               前端（工程师在浏览器里看到的界面）
│  ├─ index.html           ★ 首页：分类边栏 + agent 卡片 + 详情面板
│  ├─ wcca.html            WCCA 电路类型选择页
│  └─ passive-discharge.html  WCCA 被动放电分析 —— 专家对话页
├─ uploads/                上传的 BOM / 原理图文件
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

## 📌 后续规划

已完成：
- [x] 接入第一个真实 agent —— WCCA 被动放电分析（专家对话引导 + 计算引擎）
- [x] 点击卡片后跳转到对应 agent 的操作页面
- [x] agent 分类筛选 / 关键词搜索
- [x] 计算引擎拓扑数据驱动（位号、支路结构由原理图识别后传入，不再写死）

待办：
- [ ] 从原理图图片中**自动识别拓扑结构**（目前依赖 AI 在对话中描述）
- [ ] 扩展更多 WCCA 类型（主动放电、降额分析、热分析等）
- [ ] BOM 表与 datasheet 参数的自动提取与校验
- [ ] 用户登录与权限管理
