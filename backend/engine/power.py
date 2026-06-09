"""功率降额验证计算。

汽车电子常用规范: 电阻实际功耗 ≤ 额定功率 x 25%
"""


def P_derate_target(P_rated: float, derating_factor: float = 0.25) -> float:
    """计算降额目标功率。

    Args:
        P_rated: 电阻额定功率 (W)
        derating_factor: 降额系数 (默认 0.25 = 25%)
    """
    return P_rated * derating_factor


def P_all_max(V_HVDC: float, R_min_total: float) -> float:
    """总功耗最大值 (全部电阻取最小阻值)。

    P = V^2 / R

    Args:
        V_HVDC: 母线电压 (V)
        R_min_total: 支路总电阻最小值 (Ohm)
    """
    return V_HVDC ** 2 / R_min_total


def P_single_max(V_HVDC: float, R_min: float, R_max: float,
                 n_serial: int) -> float:
    """单颗电阻最大功耗 (1颗取最大值，其余取最小值)。

    设 n_serial 颗串联: 其中 n_serial-1 颗取 R_min, 1 颗取 R_max
    总电阻 = R_min x (n_serial-1) + R_max
    电流 = V / 总电阻
    该颗功率 = 电流^2 x R_max = V^2 / 总电阻^2 x R_max

    Args:
        V_HVDC: 母线电压 (V)
        R_min: 单颗电阻最小值 (Ohm)
        R_max: 单颗电阻最大值 (Ohm)
        n_serial: 串联数量
    """
    r_total = R_min * (n_serial - 1) + R_max
    return V_HVDC ** 2 / r_total ** 2 * R_max
