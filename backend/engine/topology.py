"""电路拓扑计算。

拓扑函数签名: fn(r_dict, config) -> float
  r_dict: {ref: resistance_value} — 各电阻的阻值字典
  config: {"n_serial": int, "n_parallel": int, ...} — 配置参数字典
"""

from typing import Dict, Any, Callable


# ---- 拓扑函数类型 ----
TopologyFn = Callable[[Dict[str, float], Dict[str, Any]], float]


# ---- 被动放电电路拓扑 (D11-B0) ----

def passive_discharge_branch1_r39(r_dict: Dict[str, float],
                                   config: Dict[str, Any]) -> float:
    """支路1: R39 x (n_serial / n_parallel)。"""
    n_serial = config["n_serial"]
    n_parallel = config["n_parallel"]
    return r_dict["R39"] * n_serial / n_parallel


def passive_discharge_branch2_sample(r_dict: Dict[str, float],
                                      config: Dict[str, Any]) -> float:
    """支路2: R749 x 10 + R1151 / 2 (母线电压采样回路)。"""
    return r_dict["R749"] * 10.0 + r_dict["R1151"] / 2.0


def passive_discharge_r_parallel(r_dict: Dict[str, float],
                                  config: Dict[str, Any]) -> float:
    """被动放电电路总并联等效电阻。

    两支路并联:
      branch1 = R39 x (7 / n)
      branch2 = R749 x 10 + R1151 / 2
      R_total = 1 / (1/branch1 + 1/branch2)
    """
    b1 = passive_discharge_branch1_r39(r_dict, config)
    b2 = passive_discharge_branch2_sample(r_dict, config)
    return 1.0 / (1.0 / b1 + 1.0 / b2)


def build_r_dict(wc_results, key: str) -> Dict[str, float]:
    """从 ResistorWCResult 字典中提取指定 key 的阻值。

    Args:
        wc_results: {ref: ResistorWCResult}
        key: 字段名，如 "R_typ", "R_max_Tmax", "R_min_Tmax"

    Returns:
        {ref: resistance_value}
    """
    return {ref: getattr(wc, key) for ref, wc in wc_results.items()}
