"""电路拓扑计算。

拓扑由数据描述（engine.models.Topology），AI 从原理图识别后填入，
引擎不写死任何位号或支路数量。

求值规则：
  - 一个 BranchElement = r_dict[ref] * n_serial / n_parallel
  - 一条 Branch = 其所有 element 串联相加
  - 多条 Branch 按 Topology.combine 合并（parallel / series）
"""

from typing import Dict

from .models import Topology, Branch, BranchElement


def _eval_element(el: BranchElement, r_dict: Dict[str, float]) -> float:
    """单个元件项的等效电阻：R * n_serial / n_parallel。"""
    if el.ref not in r_dict:
        raise KeyError(
            f"拓扑引用了位号 '{el.ref}'，但电阻参数里没有它"
            f"（已知位号: {sorted(r_dict.keys())}）"
        )
    n_parallel = el.n_parallel if el.n_parallel else 1
    return r_dict[el.ref] * el.n_serial / n_parallel


def _eval_branch(branch: Branch, r_dict: Dict[str, float]) -> float:
    """一条支路的等效电阻：各 element 串联相加。"""
    if not branch.elements:
        raise ValueError(f"支路 '{branch.name}' 没有任何元件")
    return sum(_eval_element(el, r_dict) for el in branch.elements)


def evaluate_topology(topo: Topology, r_dict: Dict[str, float]) -> float:
    """按拓扑描述计算总等效电阻。

    Args:
        topo: 拓扑结构（支路列表 + 合并方式）
        r_dict: {ref: resistance_value} 各位号当前阻值

    Returns:
        总等效电阻 (Ohm)
    """
    if not topo or not topo.branches:
        raise ValueError("拓扑为空，无法计算等效电阻")

    branch_values = [_eval_branch(b, r_dict) for b in topo.branches]

    if topo.combine == "series":
        return sum(branch_values)

    # 默认并联
    inv = 0.0
    for rv in branch_values:
        if rv <= 0:
            raise ValueError("支路等效电阻必须为正值")
        inv += 1.0 / rv
    if inv == 0:
        raise ValueError("并联等效电阻计算异常（分母为 0）")
    return 1.0 / inv


def build_r_dict(wc_results, key: str) -> Dict[str, float]:
    """从 ResistorWCResult 字典中提取指定 key 的阻值。

    Args:
        wc_results: {ref: ResistorWCResult}
        key: 字段名，如 "R_typ", "R_max_Tmax", "R_min_Tmax"

    Returns:
        {ref: resistance_value}
    """
    return {ref: getattr(wc, key) for ref, wc in wc_results.items()}
