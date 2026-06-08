# -*- coding: utf-8 -*-
"""
Agent 注册表（registry）
========================
每个 agent 的完整信息：基本信息 + 详情面板内容 + 分类筛选用。
新增 agent 只需在 AGENTS 列表里加一条。
"""
import re

AGENTS: list[dict] = [
    {
        "id": "wcca-passive-discharge",
        "name": "WCCA 被动放电分析",
        "description": "汽车电子被动放电电路最坏情况分析",
        "category": "电路分析",
        "status": "available",
        "icon": "⚡",
        "detail": """
<h3>WCCA 被动放电分析</h3>
<p>对汽车电子中的<strong>被动放电电路</strong>进行最坏情况分析（Worst Case Circuit Analysis），
覆盖放电时间验证、功率降额验证、母线放电计算等关键指标。</p>

<h4>功能亮点</h4>
<ul>
  <li>自动识别原理图中的被动放电回路</li>
  <li>基于 BOM + Datasheet 交叉计算最坏情况参数</li>
  <li>放电时间 vs. 安全阈值自动对比</li>
  <li>功率电阻降额裕度验证</li>
  <li>一键生成 WCCA 分析报告</li>
</ul>

<h4>适用场景</h4>
<p>D11-B0 / IPU 母线放电电路、新能源车主驱逆变器被动放电设计验证。</p>

<h4>输入要求</h4>
<ul>
  <li>放电回路原理图（PDF / 图片）</li>
  <li>BOM 表（Excel）</li>
  <li>关键器件 Datasheet</li>
</ul>
""",
        "url": "/agent/wcca-passive-discharge",
        "urlText": "🚀 启动 WCCA 被动放电分析",
    },
    {
        "id": "desat-protection",
        "name": "DESAT 保护电路分析",
        "description": "IGBT/SiC 退饱和保护电路参数计算与时序验证",
        "category": "电路分析",
        "status": "available",
        "icon": "🛡️",
        "detail": """
<h3>DESAT 保护电路分析</h3>
<p>针对 IGBT / SiC MOSFET 栅极驱动中的<strong>退饱和（DESAT）保护电路</strong>，
进行参数计算与时序验证，确保短路工况下器件安全关断。</p>

<h4>功能亮点</h4>
<ul>
  <li>DESAT 检测阈值电压计算</li>
  <li>消隐时间（Blanking Time）配置验证</li>
  <li>软关断（Soft Turn-off）参数推荐</li>
  <li>STGAP4HX 等驱动芯片适配</li>
</ul>

<h4>适用场景</h4>
<p>电机控制器栅极驱动电路设计、SiC 功率模块保护策略验证。</p>
""",
        "url": "/agent/desat-protection",
        "urlText": "🚀 启动 DESAT 分析",
    },
    {
        "id": "dc-dc-power-stage",
        "name": "DC-DC 功率级计算",
        "description": "Buck/Boost/Flyback 功率级参数快速选型与损耗估算",
        "category": "电源设计",
        "status": "available",
        "icon": "🔌",
        "detail": """
<h3>DC-DC 功率级计算</h3>
<p>支持 Buck、Boost、Buck-Boost、Flyback 等常见拓扑的<strong>功率级参数计算</strong>，
一键完成电感选型、电容选型、开关损耗估算。</p>

<h4>功能亮点</h4>
<ul>
  <li>输入电压 / 输出电压 / 输出电流 → 自动推荐电感 & 电容</li>
  <li>开关频率可调，实时更新损耗估算</li>
  <li>支持电流纹波率 & 电压纹波约束</li>
  <li>MOSFET 导通损耗 + 开关损耗 + 二极管损耗分项展示</li>
</ul>
""",
        "url": "/agent/dc-dc-power-stage",
        "urlText": "🚀 启动 DC-DC 计算",
    },
    {
        "id": "pcb-trace-capacity",
        "name": "PCB 走线载流计算",
        "description": "根据 IPC-2152 / IPC-2221 计算 PCB 走线载流能力与温升",
        "category": "PCB 设计",
        "status": "available",
        "icon": "📐",
        "detail": """
<h3>PCB 走线载流计算</h3>
<p>基于 <strong>IPC-2152</strong> 标准，计算 PCB 走线（外层/内层）的载流能力、
温升、压降和功率损耗，支持多铜厚和多温度场景。</p>

<h4>功能亮点</h4>
<ul>
  <li>IPC-2152 通用曲线 + 修正系数</li>
  <li>输入电流 / 铜厚 / 允许温升 → 推荐线宽</li>
  <li>多走线并联方案对比</li>
  <li>过孔载流能力辅助计算</li>
</ul>
""",
        "url": "/agent/pcb-trace-capacity",
        "urlText": "🚀 启动 PCB 载流计算",
    },
    {
        "id": "transformer-design",
        "name": "变压器设计工具",
        "description": "反激变压器参数设计与磁芯选型",
        "category": "电源设计",
        "status": "coming_soon",
        "icon": "🧲",
        "detail": """
<h3>变压器设计工具</h3>
<p>针对<strong>反激变换器（Flyback）</strong>的变压器进行参数设计和磁芯选型，
覆盖电感量、匝数比、气隙长度、绕组线径等关键参数。</p>

<h4>功能亮点（开发中）</h4>
<ul>
  <li>输入规格参数 → 自动计算变压器关键参数</li>
  <li>磁芯数据库选型推荐</li>
  <li>绕组损耗 & 磁芯损耗估算</li>
</ul>
""",
        "url": "/agent/transformer-design",
        "urlText": "🚀 启动变压器设计",
    },
    {
        "id": "wcca-signal-chain",
        "name": "WCCA 信号链分析",
        "description": "模拟信号链最坏情况误差分析与精度预算",
        "category": "电路分析",
        "status": "coming_soon",
        "icon": "📊",
        "detail": """
<h3>WCCA 信号链分析</h3>
<p>对模拟信号调理链进行<strong>最坏情况误差分析</strong>，
包含运放失调、电阻容差、温漂等误差源的 RSS 与极值合成。</p>

<h4>功能亮点（开发中）</h4>
<ul>
  <li>多级运放链误差传播建模</li>
  <li>电阻分压网络 Monte Carlo 仿真</li>
  <li>ADC 量化误差 & 基准漂移计入</li>
</ul>
""",
        "url": "/agent/wcca-signal-chain",
        "urlText": "🚀 启动信号链分析",
    },
    {
        "id": "eeprom-durability",
        "name": "EEPROM 耐久计算",
        "description": "EEPROM 写入寿命估算与磨损均衡策略建议",
        "category": "嵌入式",
        "status": "coming_soon",
        "icon": "💾",
        "detail": """
<h3>EEPROM 耐久计算</h3>
<p>根据写入频率、数据量和 EEPROM 规格书参数，<strong>估算器件使用寿命</strong>
并推荐磨损均衡策略。</p>

<h4>功能亮点（开发中）</h4>
<ul>
  <li>写入周期 → 年寿命换算</li>
  <li>磨损均衡算法对比（静态 vs 动态）</li>
  <li>多分区策略容量开销评估</li>
</ul>
""",
        "url": "/agent/eeprom-durability",
        "urlText": "🚀 启动 EEPROM 计算",
    },
]


# 收集所有分类（保持添加顺序、去重）
_all_categories: list[str] = []
for _a in AGENTS:
    if _a["category"] not in _all_categories:
        _all_categories.append(_a["category"])


def list_agents(category: str | None = None, keyword: str | None = None) -> list[dict]:
    """返回 agent 列表，支持按分类和关键词筛选。"""
    result = AGENTS
    if category:
        result = [a for a in result if a["category"] == category]
    if keyword:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        result = [a for a in result if pattern.search(a["name"]) or pattern.search(a["description"])]
    return result


def list_categories() -> list[str]:
    """返回所有分类名。"""
    return _all_categories
