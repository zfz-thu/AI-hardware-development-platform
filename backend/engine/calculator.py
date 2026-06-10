"""WCCA 计算编排器。

输入: CircuitParams (从原理图+BOM+datasheet 提取的参数)
输出: CalculationResults (完整的计算结果)
"""

from typing import Dict, List, Optional

from .models import (
    CircuitParams, CalculationResults, ResistorWCResult,
    ConfigResult, Configuration, Topology, Branch, BranchElement,
)
from .resistor import calculate_resistor_wc
from .topology import build_r_dict, evaluate_topology
from .discharge import t_discharge, derive_capacitance, ln_ratio
from .power import P_all_max, P_single_max, P_derate_target


def _find_main_branch(topo: Topology) -> Branch:
    """定位主放电支路：优先 role=="main"，否则取第一条支路。"""
    for b in topo.branches:
        if b.role == "main":
            return b
    return topo.branches[0]


def _topology_for_config(topo: Topology, cfg: Configuration) -> Topology:
    """生成一份「主支路串并联数被 configuration 覆盖」的拓扑副本。

    Configuration 表示同一拓扑下的不同主支路串并联方案。覆盖只作用于
    主支路的第一个元件（主放电电阻），其余支路保持原样。
    """
    new_branches: List[Branch] = []
    main = _find_main_branch(topo)
    for b in topo.branches:
        if b is main and b.elements:
            first = b.elements[0]
            overridden = [
                BranchElement(
                    ref=first.ref,
                    n_serial=cfg.n_serial,
                    n_parallel=cfg.n_parallel,
                )
            ] + [
                BranchElement(ref=e.ref, n_serial=e.n_serial, n_parallel=e.n_parallel)
                for e in b.elements[1:]
            ]
            new_branches.append(Branch(name=b.name, elements=overridden, role=b.role))
        else:
            new_branches.append(b)
    return Topology(branches=new_branches, combine=topo.combine)


def calculate(params: CircuitParams) -> CalculationResults:
    """执行完整的 WCCA 计算流程。

    Args:
        params: 电路参数 (由 AI 从原理图+BOM+datasheet 提取后填入)

    Returns:
        CalculationResults 包含全部计算结果
    """
    # ---- Step 1: 计算各电阻的最坏情况值 ----
    resistors_wc: Dict[str, ResistorWCResult] = {}
    for ref, r in params.resistors.items():
        resistors_wc[ref] = calculate_resistor_wc(r, params.T_max, params.T_min)

    # ---- Step 2: 确定电容值 ----
    ln_r = ln_ratio(params.V_Safety, params.V_HVDC_typ)

    cap_def = list(params.capacitors.values())[0] if params.capacitors else None
    first_cfg = params.configurations[0] if params.configurations else None

    if not params.topology:
        raise ValueError("缺少拓扑结构（topology）—— 应由原理图识别后提供")

    if cap_def and cap_def.Cap_typ > 0:
        Cap_HVDC_typ = cap_def.Cap_typ
    elif first_cfg and first_cfg.t_typ_known:
        # 由典型放电时间反推电容值
        r_typ = build_r_dict(resistors_wc, "R_typ")
        topo_cfg = _topology_for_config(params.topology, first_cfg)
        R_par_typ = evaluate_topology(topo_cfg, r_typ)
        Cap_HVDC_typ = derive_capacitance(
            first_cfg.t_typ_known, R_par_typ,
            params.V_Safety, params.V_HVDC_typ,
        )
    else:
        Cap_HVDC_typ = 0.0

    # 母线电容最坏情况值 (考虑偏差)
    if cap_def and Cap_HVDC_typ > 0:
        C_max = Cap_HVDC_typ * (1 + cap_def.TOL_max)
    else:
        C_max = Cap_HVDC_typ

    # 母线电压最坏情况值 (考虑偏差)
    V_HVDC_max = params.V_HVDC_typ * (1 + abs(params.V_HVDC_tol))

    # ---- Step 3: 评估每种配置方案 ----
    if not params.resistors:
        raise ValueError("至少需要一个电阻定义")

    # 主放电电阻 = 主支路的第一个元件（用于功率降额）
    main_branch = _find_main_branch(params.topology)
    if not main_branch.elements:
        raise ValueError(f"主支路 '{main_branch.name}' 没有任何元件")
    main_ref = main_branch.elements[0].ref
    if main_ref not in params.resistors:
        raise ValueError(f"主放电电阻位号 '{main_ref}' 不在电阻参数中")
    P_rated_main = params.resistors[main_ref].P_rated
    P_derate = P_derate_target(P_rated_main, 0.25)

    config_results = []
    for cfg in params.configurations:
        cr = _evaluate_config(
            params, cfg, resistors_wc, Cap_HVDC_typ, C_max,
            V_HVDC_max, ln_r, P_derate,
        )
        config_results.append(cr)

    # ---- Step 4: 汇总 ----
    all_t_pass = all(c.t_passed for c in config_results)
    all_P_pass = all(c.P_passed for c in config_results)

    return CalculationResults(
        circuit_id=params.circuit_id,
        circuit_name=params.circuit_name,
        T_max=params.T_max,
        T_min=params.T_min,
        V_HVDC_typ=params.V_HVDC_typ,
        V_Safety=params.V_Safety,
        resistors_wc=resistors_wc,
        Cap_HVDC_typ=Cap_HVDC_typ,
        ln_ratio=ln_r,
        config_results=config_results,
        all_t_pass=all_t_pass,
        all_P_pass=all_P_pass,
    )


def _evaluate_config(
    params: CircuitParams,
    cfg: Configuration,
    resistors_wc: Dict[str, ResistorWCResult],
    Cap_typ: float,
    C_max: float,
    V_HVDC_max: float,
    ln_r: float,
    P_derate: float,
) -> ConfigResult:
    """评估单个配置方案。"""
    if params.topology is None:
        raise ValueError("缺少拓扑结构（topology）—— 应由原理图识别后提供")

    # 该方案对应的拓扑（主支路串并联数被 configuration 覆盖）
    topo_cfg = _topology_for_config(params.topology, cfg)

    # 三种条件下的等效电阻
    r_typ = build_r_dict(resistors_wc, "R_typ")
    r_max = build_r_dict(resistors_wc, "R_max_Tmax")
    r_min = build_r_dict(resistors_wc, "R_min_Tmax")

    Rp_typ = evaluate_topology(topo_cfg, r_typ)
    Rp_max = evaluate_topology(topo_cfg, r_max)
    Rp_min = evaluate_topology(topo_cfg, r_min)

    # 放电时间
    # 典型: 使用 C_typ, V_HVDC_typ
    t_typ = t_discharge(Rp_typ, Cap_typ, params.V_Safety, params.V_HVDC_typ)
    # 最坏情况: 使用 R_max, C_max, V_HVDC_max (所有不利因素同时发生)
    t_max = t_discharge(Rp_max, C_max, params.V_Safety, V_HVDC_max)

    # 功率 (使用 V_HVDC_max — 电压越高功率越大)
    # 主放电电阻 = 主支路第一个元件
    main_branch = _find_main_branch(params.topology)
    main_ref = main_branch.elements[0].ref
    r_wc = resistors_wc[main_ref]
    R_min_total = r_wc.R_min_Tmax * cfg.n_serial / cfg.n_parallel
    P_all = P_all_max(V_HVDC_max, R_min_total)
    P_one = P_single_max(
        V_HVDC_max, r_wc.R_min_Tmax,
        r_wc.R_max_Tmax, cfg.n_serial,
    )

    t_limit = 120.0   # 放电时间限值 (s)
    t_passed = t_max <= t_limit
    P_passed = P_one < P_derate

    return ConfigResult(
        config_name=cfg.name,
        n_serial=cfg.n_serial,
        n_parallel=cfg.n_parallel,
        R_parallel_typ=Rp_typ,
        R_parallel_max=Rp_max,
        R_parallel_min=Rp_min,
        C_max=C_max,
        V_HVDC_max=V_HVDC_max,
        t_discharge_typ=t_typ,
        t_discharge_max=t_max,
        P_all_max=P_all,
        P_single_max=P_one,
        P_derate_target=P_derate,
        t_passed=t_passed,
        P_passed=P_passed,
    )
