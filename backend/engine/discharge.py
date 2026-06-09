"""放电时间计算。

RC 放电: V(t) = V0 x exp(-t / (R x C))
放电至安全电压: t = -R x C x ln(V_safety / V_HVDC)
"""

import math


def ln_ratio(V_safety: float, V_HVDC: float) -> float:
    """计算 ln(V_safety / V_HVDC)。"""
    return math.log(V_safety / V_HVDC)


def t_discharge(R_parallel: float, C: float,
                V_safety: float, V_HVDC: float) -> float:
    """计算 RC 放电至安全电压所需时间。

    Args:
        R_parallel: 并联等效电阻 (Ohm)
        C: 电容 (F)
        V_safety: 安全电压 (V)
        V_HVDC: 母线电压 (V)

    Returns:
        放电时间 (s)
    """
    return -R_parallel * C * math.log(V_safety / V_HVDC)


def derive_capacitance(t_typ: float, R_parallel_typ: float,
                       V_safety: float, V_HVDC: float) -> float:
    """由已知典型放电时间反推电容值。

    C = t_typ / (-R_parallel_typ x ln(V_safety / V_HVDC))

    Args:
        t_typ: 已知的典型放电时间 (s)
        R_parallel_typ: 标称条件下的并联等效电阻 (Ohm)
        V_safety: 安全电压 (V)
        V_HVDC: 母线电压 (V)

    Returns:
        反推电容值 (F)
    """
    return t_typ / (-R_parallel_typ * math.log(V_safety / V_HVDC))
