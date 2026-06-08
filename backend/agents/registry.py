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
        "id": "wcca-circuit",
        "name": "电路WCCA计算",
        "description": "最坏情况电路分析（WCCA）：覆盖被动放电、信号链、功率电路等场景",
        "category": "电路分析",
        "status": "available",
        "icon": "⚡",
        "detail": """
<h3>电路WCCA计算</h3>
<p>对汽车电子电路进行<strong>最坏情况分析（Worst Case Circuit Analysis）</strong>，
覆盖被动放电、信号调理链、功率电路等关键场景，自动生成分析报告。</p>

<h4>功能亮点</h4>
<ul>
  <li>支持被动放电 / 信号链 / 功率电路多种分析模板</li>
  <li>基于 BOM + Datasheet 交叉计算最坏情况参数</li>
  <li>极值分析（EVA）与 RSS 合成双模式</li>
  <li>功率降额裕度自动验证</li>
  <li>一键生成 WCCA 分析报告</li>
</ul>

<h4>适用场景</h4>
<p>新能源车主驱逆变器、OBC、DCDC 等汽车电子关键电路的设计验证。</p>
""",
        "url": "/agent/wcca-circuit",
        "urlText": "🚀 启动 WCCA 计算",
    },
    {
        "id": "monte-carlo",
        "name": "蒙特卡洛分析",
        "description": "基于 Monte Carlo 方法的电路容差分析与良率预测",
        "category": "电路分析",
        "status": "available",
        "icon": "🎲",
        "detail": """
<h3>蒙特卡洛分析</h3>
<p>基于<strong>蒙特卡洛（Monte Carlo）方法</strong>对电路进行容差分析与良率预测，
考虑器件参数分布、温度漂移、老化效应等因素，评估量产一致性。</p>

<h4>功能亮点</h4>
<ul>
  <li>电阻 / 电容 / 运放等关键器件容差建模</li>
  <li>支持的分布类型：正态、均匀、三角分布</li>
  <li>支持自定义仿真次数（1k ~ 100k）</li>
  <li>输出直方图 & Cpk / Ppk 统计量</li>
  <li>敏感度分析：识别对输出影响最大的器件</li>
</ul>

<h4>适用场景</h4>
<p>电压基准精度评估、滤波器截止频率分布、放大器增益一致性验证。</p>
""",
        "url": "/agent/monte-carlo",
        "urlText": "🚀 启动蒙特卡洛分析",
    },
    {
        "id": "circuit-design-assistant",
        "name": "电路设计助手",
        "description": "AI 辅助电路设计：拓扑推荐、器件选型、原理图审查",
        "category": "电路设计",
        "status": "available",
        "icon": "🤖",
        "detail": """
<h3>电路设计助手</h3>
<p>基于 AI 大模型的<strong>电路设计智能助手</strong>，辅助工程师完成拓扑推荐、
器件选型、原理图审查等设计任务。</p>

<h4>功能亮点</h4>
<ul>
  <li>根据设计规格自动推荐电路拓扑</li>
  <li>关键器件（MOSFET / 运放 / LDO 等）参数选型建议</li>
  <li>原理图规范性审查（命名、网络、封装检查）</li>
  <li>常见设计缺陷自动识别</li>
  <li>支持自然语言交互式问答</li>
</ul>

<h4>适用场景</h4>
<p>电源电路设计、模拟信号链设计、功率驱动电路方案评估。</p>
""",
        "url": "/agent/circuit-design-assistant",
        "urlText": "🚀 启动电路设计助手",
    },
    {
        "id": "functional-safety",
        "name": "功能安全FMEDA和DFMEA分析",
        "description": "FMEDA / DFMEA 分析工具：失效模式、影响及诊断覆盖率计算",
        "category": "功能安全",
        "status": "available",
        "icon": "🛡️",
        "detail": """
<h3>功能安全 FMEDA & DFMEA 分析</h3>
<p>面向 ISO 26262 功能安全开发流程的<strong>FMEDA / DFMEA 分析工具</strong>，
辅助完成失效模式识别、影响分析、诊断覆盖率计算和安全指标评估。</p>

<h4>功能亮点</h4>
<ul>
  <li>FMEDA：元器件级失效模式 & 失效率库（SN 29500 / IEC 62380）</li>
  <li>自动计算 SPFM / LFM / PMHF 安全指标</li>
  <li>DFMEA：结构化失效链建模（失效模式 → 失效影响 → 失效原因）</li>
  <li>RPN / AP（Action Priority）风险评估与排序</li>
  <li>导出符合 ISO 26262 模板的分析报告</li>
</ul>

<h4>适用场景</h4>
<p>新能源汽车电驱 / 电池管理 / 自动驾驶域控制器的功能安全分析。</p>
""",
        "url": "/agent/functional-safety",
        "urlText": "🚀 启动功能安全分析",
    },
    {
        "id": "bom-compare",
        "name": "BOM比对及价格分析助手",
        "description": "BOM 差异比对、价格趋势分析与替代料推荐",
        "category": "物料管理",
        "status": "available",
        "icon": "📋",
        "detail": """
<h3>BOM 比对及价格分析助手</h3>
<p>面向硬件物料管理的<strong>BOM 比对与成本分析工具</strong>，
支持多版本 BOM 差异比对、元器件价格趋势分析、替代料智能推荐。</p>

<h4>功能亮点</h4>
<ul>
  <li>双 BOM 差异比对：高亮新增 / 删除 / 变更的物料行</li>
  <li>器件价格历史趋势图（支持主流供应商数据导入）</li>
  <li>基于规格参数的替代料推荐（Pin-to-Pin / 功能等效）</li>
  <li>BOM 成本汇总 & 分类占比饼图</li>
  <li>缺货风险预警 & 交货周期查询</li>
</ul>

<h4>适用场景</h4>
<p>硬件改版 BOM 变更评审、量产前物料成本优化、器件 EOL 替代方案评估。</p>
""",
        "url": "/agent/bom-compare",
        "urlText": "🚀 启动 BOM 分析",
    },
    {
        "id": "circuit-efficiency",
        "name": "电路效率仿真",
        "description": "功率电路效率仿真：导通损耗、开关损耗与系统效率曲线",
        "category": "电路分析",
        "status": "coming_soon",
        "icon": "📈",
        "detail": """
<h3>电路效率仿真</h3>
<p>对功率变换电路进行<strong>效率仿真分析</strong>，分解导通损耗、开关损耗、
磁芯损耗等关键损耗源，绘制全工况效率曲线。</p>

<h4>功能亮点（开发中）</h4>
<ul>
  <li>支持 Buck / Boost / LLC / PSFB 等常见拓扑</li>
  <li>MOSFET / IGBT / GaN / SiC 器件损耗模型</li>
  <li>磁件损耗估算（Steinmetz 方程）</li>
  <li>全负载范围效率曲线 & 损耗分布瀑布图</li>
</ul>

<h4>适用场景</h4>
<p>车载 DCDC / OBC 功率级效率评估、散热设计输入。</p>
""",
        "url": "/agent/circuit-efficiency",
        "urlText": "🚀 启动效率仿真",
    },
    {
        "id": "film-capacitor",
        "name": "膜电容选型分析",
        "description": "DC-Link 膜电容参数计算、纹波电流校核与寿命评估",
        "category": "元器件选型",
        "status": "coming_soon",
        "icon": "🔋",
        "detail": """
<h3>膜电容选型分析</h3>
<p>针对电机控制器 DC-Link 应用的<strong>薄膜电容选型工具</strong>，
覆盖容值计算、纹波电流校核、热点温度与寿命评估。</p>

<h4>功能亮点（开发中）</h4>
<ul>
  <li>根据母线电压 / 开关频率 / 功率等级计算最小容值</li>
  <li>纹波电流频谱分解与等效校核</li>
  <li>ESR 热损耗 & 热点温度估算</li>
  <li>薄膜电容寿命模型（温度 / 电压加速因子）</li>
  <li>主流供应商（TDK / Vishay / 法拉）型号库查询</li>
</ul>

<h4>适用场景</h4>
<p>新能源车主驱逆变器 DC-Link 电容选型、薄膜电容替代电解电容方案评估。</p>
""",
        "url": "/agent/film-capacitor",
        "urlText": "🚀 启动膜电容选型",
    },
    {
        "id": "pcb-utilization",
        "name": "PCB利用率及价格评估",
        "description": "PCB 拼板利用率优化与制板成本快速估价",
        "category": "PCB 设计",
        "status": "available",
        "icon": "🧩",
        "detail": """
<h3>PCB 利用率及价格评估</h3>
<p>针对 PCB 制板阶段的<strong>拼板利用率优化与成本估价工具</strong>，
自动计算拼板利用率、推荐最优拼板方案，并基于工艺参数估算制板价格。</p>

<h4>功能亮点</h4>
<ul>
  <li>单板尺寸 → 自动拼接最优拼板方案（0° / 90° / 180° 旋转）</li>
  <li>拼板利用率实时计算 & 可视化预览</li>
  <li>基于层数 / 铜厚 / 表面工艺 / 阻焊颜色估算单价</li>
  <li>V-Cut / 邮票孔工艺选择 & 工艺边宽度设置</li>
  <li>支持多家 PCB 厂商价格模型对比</li>
</ul>

<h4>适用场景</h4>
<p>硬件量产前 PCB 拼板方案评审、制板成本预算评估、多供应商比价。</p>
""",
        "url": "/agent/pcb-utilization",
        "urlText": "🚀 启动 PCB 估价",
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
