"""WCCA 计算数据结构定义。"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ResistorDef:
    """单个电阻的完整参数定义。

    这些参数应从 datasheet 中提取。
    """
    ref: str                # 位号，如 "R39"
    description: str        # 功能描述，如 "主放电电阻"
    mpn: str                # 物料编号 (MPN)
    manufacturer: str       # 制造商
    package: str            # 封装，如 "1206"
    R_typ: float            # 标称阻值 (Ohm)
    TOL_max: float          # 精度上限 (小数，如 0.01 = 1%)
    TOL_min: float          # 精度下限 (小数，如 -0.01 = -1%)
    TCR: float              # 温度系数 (ppm/degC, 正值)
    P_rated: float          # 额定功率 (W)
    V_max: float            # 最大工作电压 (V)
    EOL_max: float          # 寿命末期漂移上限 (小数)
    EOL_min: float          # 寿命末期漂移下限 (小数)


@dataclass
class CapacitorDef:
    """电容参数定义。"""
    ref: str                # 位号
    Cap_typ: float          # 典型电容值 (F)，0 表示需要反推
    TOL_max: float          # 精度上限
    TOL_min: float          # 精度下限
    TCR_max: float          # 温度系数上限 (ppm/degC 或小数)
    TCR_min: float          # 温度系数下限
    V_rated: float          # 额定电压 (V)


@dataclass
class Configuration:
    """一种电路配置方案。"""
    name: str               # 显示名称，如 "情况一: 7串6并"
    n_serial: int           # 串联电阻数
    n_parallel: int         # 并联支路数
    t_typ_known: Optional[float] = None  # 已知典型放电时间 (s)，用于反推电容


@dataclass
class ResistorWCResult:
    """单个电阻的最坏情况计算结果。"""
    ref: str
    R_typ: float
    R_max_Tmax: float       # 高温下最大值
    R_max_Tmin: float       # 低温下最大值
    R_min_Tmax: float       # 高温下最小值
    R_min_Tmin: float       # 低温下最小值


@dataclass
class ConfigResult:
    """单个配置方案的计算结果。"""
    config_name: str
    n_serial: int
    n_parallel: int
    R_parallel_typ: float   # 标称并联等效电阻 (Ohm)
    R_parallel_max: float   # 最大并联等效电阻 (Ohm)
    R_parallel_min: float   # 最小并联等效电阻 (Ohm)
    C_max: float            # 母线电容最大值 (F) — 考虑偏差
    V_HVDC_max: float       # 母线电压最大值 (V) — 考虑偏差
    t_discharge_typ: float  # 典型放电时间 (s)
    t_discharge_max: float  # 最坏情况放电时间 (s)
    P_all_max: float        # 总功耗最大值 (W)
    P_single_max: float     # 单颗功耗最大值 (W)
    P_derate_target: float  # 降额目标 (W)
    t_passed: bool          # 放电时间判定
    P_passed: bool          # 功率判定


@dataclass
class CircuitParams:
    """电路计算输入参数（每次计算由 AI 从原理图+BOM+datasheet 中提取填入）。"""

    circuit_id: str                          # 电路标识
    circuit_name: str                        # 电路名称

    # 工作条件
    T_max: float                             # 最高温度 (degC)
    T_min: float                             # 最低温度 (degC)
    T_typ: float = 25.0                      # 典型温度 (degC)

    # 输入条件 (均由工程师提供)
    V_HVDC_typ: float = 500.0                # 母线电压典型值 (V)
    V_HVDC_tol: float = 0.0                  # 母线电压偏差 (小数, 如 0.05 = ±5%)
    V_Safety: float = 60.0                   # 安全电压 (V)

    # 器件
    resistors: Dict[str, ResistorDef] = field(default_factory=dict)
    capacitors: Dict[str, CapacitorDef] = field(default_factory=dict)

    # 拓扑函数 (由电路 skill 提供)
    # 签名: fn(r_dict, config_dict) -> float (等效并联电阻)
    topology_fn: Optional[callable] = None

    # 配置方案
    configurations: List[Configuration] = field(default_factory=list)


@dataclass
class CalculationResults:
    """完整的 WCCA 计算结果。"""

    circuit_id: str
    circuit_name: str

    # 温度
    T_max: float
    T_min: float

    # 输入
    V_HVDC_typ: float
    V_Safety: float

    # 电阻最坏情况值
    resistors_wc: Dict[str, ResistorWCResult] = field(default_factory=dict)

    # 电容
    Cap_HVDC_typ: float = 0.0
    ln_ratio: float = 0.0

    # 各配置结果
    config_results: List[ConfigResult] = field(default_factory=list)

    # 汇总
    all_t_pass: bool = True
    all_P_pass: bool = True
