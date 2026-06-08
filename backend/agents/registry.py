# -*- coding: utf-8 -*-
"""
Agent 注册表（registry）
========================
这里是整个平台的"目录册"——记录当前有哪些 agent 可以用。

前端网页会读取这份名单，把每个 agent 显示成一张卡片，
工程师在界面上看到、点击，就能使用对应的功能。

【以后新增一个 agent，只需要在下面的 AGENTS 列表里加一段就行】
每个 agent 用一个字典描述，包含这些字段：
  - id：       英文短名，唯一标识（不要重复），例如 "wcca-passive-discharge"
  - name：     中文显示名，工程师在界面上看到的标题
  - description：一句话说明这个 agent 干什么
  - category： 分类（用于以后给界面做分组/筛选），例如 "电路分析"
  - status：   状态，"available"=可用，"coming_soon"=即将上线
"""

# ===== 平台上的 agent 名单 =====
# 下面先放了两个示例（一个可用、一个即将上线），方便你看到效果。
# 你可以照着格式继续往下加。
AGENTS = [
    {
        "id": "wcca-passive-discharge",
        "name": "WCCA 被动放电分析",
        "description": "汽车电子被动放电电路最坏情况分析：放电时间验证、功率降额、母线放电计算，并生成报告。",
        "category": "电路分析",
        "status": "available",
    },
    {
        "id": "desat-protection",
        "name": "DESAT 保护电路分析",
        "description": "IGBT/SiC 退饱和（DESAT）保护电路参数计算与时序验证。",
        "category": "电路分析",
        "status": "coming_soon",
    },
]


def list_agents():
    """返回 agent 名单，供后端 API 调用。"""
    return AGENTS
