"""最坏情况电阻计算。

公式: R = R_typ x (1 + TOL) x (1 + TCR x (T - 25degC)) x (1 + EOL)
"""

from .models import ResistorDef, ResistorWCResult


def R_MAX_MIN(R_typ: float, TOL: float, TCR_ppm: float,
              T: float, EOL: float) -> float:
    """计算单个温度/公差/EOL 条件下的电阻值。

    Args:
        R_typ: 标称阻值 (Ohm)
        TOL: 公差 (带符号，如 +0.01 表示 +1%)
        TCR_ppm: 温度系数 (ppm/degC，带符号)
        T: 工作温度 (degC)
        EOL: 寿命漂移 (带符号)

    Returns:
        最坏情况电阻值 (Ohm)
    """
    TCR = TCR_ppm * 1e-6
    return R_typ * (1.0 + TOL) * (1.0 + TCR * (T - 25.0)) * (1.0 + EOL)


def calculate_resistor_wc(r: ResistorDef, T_max: float,
                          T_min: float) -> ResistorWCResult:
    """计算一个电阻的全部 4 个最坏情况角落值。

    策略:
      - 最大值: TOL_max + EOL_max
        * T_max 时: 取 +TCR (温度升高→阻值增大)
        * T_min 时: 取 -TCR (温度降低→阻值减小? 对正TCR来说阻值减小;
          但对于 MAX 目标，T_min下我们希望阻值最大，
          若 TCR>0，T_min时阻值更小 → 应取 -TCR 来增大阻值?

          实际物理: R(T) = R25 x (1 + TCR x (T-25))
          - T=105, TCR=+100ppm: (105-25)=80, 1+100e-6*80 = 1.008 → 增大
          - T=-40, TCR=-100ppm: (-40-25)=-65, 1+(-100e-6)*(-65)=1.0065 → 增大

          所以:
          - Rmax @ Tmax: +TCR (正TCR使高温阻值更大)
          - Rmax @ Tmin: -TCR (负TCR使低温阻值更大)
          - Rmin @ Tmax: -TCR (负TCR使高温阻值更小)
          - Rmin @ Tmin: +TCR (正TCR使低温阻值更小)
    """
    abs_tcr = abs(r.TCR)

    R_max_Tmax = R_MAX_MIN(r.R_typ, r.TOL_max, +abs_tcr, T_max, r.EOL_max)
    R_max_Tmin = R_MAX_MIN(r.R_typ, r.TOL_max, -abs_tcr, T_min, r.EOL_max)
    R_min_Tmax = R_MAX_MIN(r.R_typ, r.TOL_max, -abs_tcr, T_max, r.EOL_min)
    R_min_Tmin = R_MAX_MIN(r.R_typ, r.TOL_max, +abs_tcr, T_min, r.EOL_min)

    return ResistorWCResult(
        ref=r.ref,
        R_typ=r.R_typ,
        R_max_Tmax=R_max_Tmax,
        R_max_Tmin=R_max_Tmin,
        R_min_Tmax=R_min_Tmax,
        R_min_Tmin=R_min_Tmin,
    )
