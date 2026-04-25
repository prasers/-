"""
modules/calculator.py
P1 模块：杨氏模量计算与不确定度分析核心算法
严格遵循国内普通大学物理实验规范
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
import math


# ─────────────────────────────────────────────
# 仪器参数配置（全部可由用户在界面修改）
# ─────────────────────────────────────────────
@dataclass
class InstrumentConfig:
    """仪器最大允差配置（单位统一为 SI 基本单位）"""
    # 千分尺（螺旋测微器）测量金属丝直径 d
    micrometer_delta: float = 0.004e-3    # 4 μm → 0.004 mm
    # 钢卷尺/米尺测量原长 l
    ruler_delta: float = 0.5e-3           # 0.5 mm
    # 拉力传感器测量力 F
    force_sensor_delta: float = 0.05      # 0.05 N
    # 激光波长（通常由激光器厂家给定，此处仅作参考）
    lambda_delta: float = 0.1e-9          # 0.1 nm
    # 干涉环计数误差（ΔN 的仪器误差，通常取 0.5 个环）
    delta_n_instrument: float = 0.5       # 0.5 环


@dataclass
class ExperimentParams:
    """实验固定参数"""
    lambda_m: float = 632.8e-9   # 激光波长 m（He-Ne 默认值）
    wire_length_m: float = 0.800  # 金属丝原长 m


@dataclass
class MeasurementData:
    """测量数据"""
    # 金属丝直径多次测量值（单位 m）
    diameters: List[float] = field(default_factory=list)
    # (拉力 F/N, 对应 ΔN) 数据组
    force_delta_n_pairs: List[Tuple[float, int]] = field(default_factory=list)


# ─────────────────────────────────────────────
# 贝塞尔公式 A 类不确定度
# ─────────────────────────────────────────────
def uncertainty_A(values: List[float]) -> Tuple[float, float, float]:
    """
    A 类不确定度（贝塞尔公式）
    返回 (mean, std_dev, u_A)
    u_A = std_dev / sqrt(n)
    """
    n = len(values)
    if n < 2:
        mean = values[0] if values else 0.0
        return mean, 0.0, 0.0
    arr = np.array(values, dtype=float)
    mean = float(np.mean(arr))
    # 贝塞尔公式标准偏差 s
    s = float(np.std(arr, ddof=1))
    # 平均值的 A 类不确定度
    u_A = s / math.sqrt(n)
    return mean, s, u_A


# ─────────────────────────────────────────────
# B 类不确定度（仪器允差）
# ─────────────────────────────────────────────
def uncertainty_B(instrument_delta: float, k: float = math.sqrt(3)) -> float:
    """
    B 类不确定度
    均匀分布：u_B = Δ / √3
    正态分布（k=3）：u_B = Δ / 3
    默认均匀分布
    """
    return instrument_delta / k


# ─────────────────────────────────────────────
# 合成不确定度（方和根）
# ─────────────────────────────────────────────
def combined_uncertainty(u_A: float, u_B: float) -> float:
    """合成不确定度 u_c = sqrt(u_A² + u_B²)"""
    return math.sqrt(u_A**2 + u_B**2)


# ─────────────────────────────────────────────
# 最小二乘法线性拟合
# ─────────────────────────────────────────────
def least_squares_fit(x: List[float], y: List[float]
                      ) -> Tuple[float, float, float]:
    """
    最小二乘线性拟合 y = kx + b
    返回 (k, b, R²)
    """
    x_arr = np.array(x, dtype=float)
    y_arr = np.array(y, dtype=float)
    n = len(x_arr)
    if n < 2:
        return 0.0, y_arr[0] if n else 0.0, 0.0

    x_mean, y_mean = np.mean(x_arr), np.mean(y_arr)
    Sxx = float(np.sum((x_arr - x_mean)**2))
    Sxy = float(np.sum((x_arr - x_mean) * (y_arr - y_mean)))
    Syy = float(np.sum((y_arr - y_mean)**2))

    if Sxx < 1e-30:
        return 0.0, y_mean, 0.0

    k = Sxy / Sxx
    b = y_mean - k * x_mean
    R2 = (Sxy**2) / (Sxx * Syy) if Syy > 1e-30 else 1.0
    return k, b, R2


# ─────────────────────────────────────────────
# 核心：杨氏模量计算 + 完整不确定度分析
# ─────────────────────────────────────────────
@dataclass
class CalculationResult:
    # 基本测量结果
    d_mean: float = 0.0          # 金属丝直径平均值 m
    d_uA: float = 0.0
    d_uB: float = 0.0
    d_uc: float = 0.0            # d 合成不确定度

    l_m: float = 0.0             # 金属丝原长 m（用户输入）
    l_uc: float = 0.0            # l 合成不确定度

    lambda_m: float = 0.0        # 激光波长 m
    lambda_uc: float = 0.0

    # 最小二乘拟合结果（F vs ΔN）
    fit_k: float = 0.0           # k = dF/dΔN
    fit_b: float = 0.0
    fit_R2: float = 0.0
    fit_k_uc: float = 0.0        # k 的不确定度（简化估算）

    # 杨氏模量
    E_value: float = 0.0         # Pa
    E_rel_unc: float = 0.0       # 相对不确定度
    E_abs_unc: float = 0.0       # 绝对不确定度 Pa

    # 各量相对不确定度贡献
    rel_unc_d: float = 0.0
    rel_unc_l: float = 0.0
    rel_unc_lambda: float = 0.0
    rel_unc_k: float = 0.0

    # 报告文本
    report_lines: List[str] = field(default_factory=list)
    success: bool = False
    error_msg: str = ""


def calculate_youngs_modulus(
        data: MeasurementData,
        params: ExperimentParams,
        inst: InstrumentConfig) -> CalculationResult:
    """
    完整杨氏模量计算流程
    
    核心公式（需求文档定版）：
        E = 8Fl / (π d² λ ΔN)
    
    不确定度传递（对数微分法）：
        (u_E/E)² = (2·u_d/d)² + (u_l/l)² + (u_λ/λ)² + (u_k/k)²
    
    其中 k = F/ΔN 由最小二乘拟合给出
    """
    res = CalculationResult()
    lines = []

    try:
        # ── 1. 金属丝直径 d ──────────────────────
        if len(data.diameters) < 1:
            raise ValueError("至少输入1组直径测量值")

        d_mean, d_std, d_uA = uncertainty_A(data.diameters)
        d_uB = uncertainty_B(inst.micrometer_delta)
        d_uc = combined_uncertainty(d_uA, d_uB)

        res.d_mean, res.d_uA, res.d_uB, res.d_uc = d_mean, d_uA, d_uB, d_uc

        lines.append("=" * 60)
        lines.append("【1】金属丝直径 d 测量统计")
        lines.append(f"  测量组数 n = {len(data.diameters)}")
        lines.append(f"  平均值 d̄ = {d_mean*1e3:.4f} mm")
        if len(data.diameters) >= 2:
            lines.append(f"  标准偏差 s = {d_std*1e3:.4f} mm")
            lines.append(f"  A类不确定度 u_A(d) = s/√n = {d_uA*1e3:.4f} mm")
        lines.append(f"  仪器最大允差 Δ = {inst.micrometer_delta*1e3:.4f} mm")
        lines.append(f"  B类不确定度 u_B(d) = Δ/√3 = {d_uB*1e3:.4f} mm")
        lines.append(f"  合成不确定度 u_c(d) = √(u_A²+u_B²) = {d_uc*1e3:.4f} mm")

        # ── 2. 金属丝原长 l ───────────────────────
        l_m = params.wire_length_m
        l_uB = uncertainty_B(inst.ruler_delta)
        l_uc = l_uB   # 单次测量，只有 B 类
        res.l_m, res.l_uc = l_m, l_uc

        lines.append("")
        lines.append("【2】金属丝原长 l")
        lines.append(f"  l = {l_m*1e3:.1f} mm（单次测量）")
        lines.append(f"  u_c(l) = u_B(l) = {l_uc*1e3:.3f} mm")

        # ── 3. 激光波长 λ ─────────────────────────
        lam = params.lambda_m
        lam_uB = uncertainty_B(inst.lambda_delta)
        res.lambda_m, res.lambda_uc = lam, lam_uB

        lines.append("")
        lines.append("【3】激光波长 λ")
        lines.append(f"  λ = {lam*1e9:.1f} nm")
        lines.append(f"  u_c(λ) = {lam_uB*1e9:.2f} nm")

        # ── 4. 最小二乘拟合 F vs ΔN ───────────────
        if len(data.force_delta_n_pairs) < 2:
            raise ValueError("至少输入2组 (F, ΔN) 数据点")

        F_list  = [p[0] for p in data.force_delta_n_pairs]
        dN_list = [float(p[1]) for p in data.force_delta_n_pairs]

        # 以 ΔN 为 x，F 为 y，拟合斜率 k = dF/dΔN
        k, b, R2 = least_squares_fit(dN_list, F_list)
        res.fit_k, res.fit_b, res.fit_R2 = k, b, R2

        # k 的不确定度（残差标准差传递）
        F_arr  = np.array(F_list)
        dN_arr = np.array(dN_list)
        F_pred = k * dN_arr + b
        residuals = F_arr - F_pred
        n_pts = len(F_list)
        if n_pts > 2:
            s_res = float(np.std(residuals, ddof=2))
            Sxx = float(np.sum((dN_arr - np.mean(dN_arr))**2))
            k_uc = s_res / math.sqrt(Sxx) if Sxx > 1e-30 else 0.0
        else:
            k_uc = abs(k) * 0.05   # 数据点不足时估算 5%
        res.fit_k_uc = k_uc

        lines.append("")
        lines.append("【4】F-ΔN 最小二乘线性拟合")
        lines.append(f"  拟合结果：F = {k:.4f}·ΔN + {b:.4f}  (N)")
        lines.append(f"  相关系数 R² = {R2:.6f}")
        lines.append(f"  拟合斜率 k = dF/dΔN = {k:.4f} N/环")
        lines.append(f"  k 的不确定度 u(k) = {k_uc:.4f} N/环")

        # ── 5. 杨氏模量 E ─────────────────────────
        # 公式：E = 8Fl / (π d² λ ΔN) = 8kl / (π d² λ)
        # 其中 k = F/ΔN（最小二乘斜率）
        if d_mean <= 0 or lam <= 0 or k <= 0:
            raise ValueError("参数值不合法（d/λ/k 必须为正数）")

        E = (8.0 * k * l_m) / (math.pi * d_mean**2 * lam)
        res.E_value = E

        lines.append("")
        lines.append("【5】杨氏模量 E 计算")
        lines.append("  公式：E = 8Fl / (π d² λ ΔN) = 8kl / (π d² λ)")
        lines.append(f"  E = 8 × {k:.4f} × {l_m:.4f} / (π × {d_mean*1e3:.4f}e-3² × {lam*1e9:.1f}e-9)")
        lines.append(f"  E = {E:.4e} Pa = {E/1e9:.2f} GPa")

        # ── 6. 不确定度传递 ───────────────────────
        # 相对不确定度各分量：
        #   (u_E/E)² = (2·u_d/d)² + (u_l/l)² + (u_λ/λ)² + (u_k/k)²
        rel_d   = 2 * d_uc / d_mean
        rel_l   = l_uc / l_m
        rel_lam = lam_uB / lam
        rel_k   = k_uc / k if k > 0 else 0.0

        rel_E = math.sqrt(rel_d**2 + rel_l**2 + rel_lam**2 + rel_k**2)
        abs_E = E * rel_E

        res.rel_unc_d      = rel_d
        res.rel_unc_l      = rel_l
        res.rel_unc_lambda = rel_lam
        res.rel_unc_k      = rel_k
        res.E_rel_unc      = rel_E
        res.E_abs_unc      = abs_E

        lines.append("")
        lines.append("【6】不确定度传递分析")
        lines.append("  传递公式：(u_E/E)² = (2u_d/d)² + (u_l/l)² + (u_λ/λ)² + (u_k/k)²")
        lines.append(f"  2·u_c(d)/d   = {rel_d*100:.3f}%  （最大误差来源之一）")
        lines.append(f"  u_c(l)/l     = {rel_l*100:.3f}%")
        lines.append(f"  u_c(λ)/λ     = {rel_lam*100:.4f}%")
        lines.append(f"  u_c(k)/k     = {rel_k*100:.3f}%")
        lines.append(f"  → 相对不确定度 u_E/E = {rel_E*100:.3f}%")
        lines.append(f"  → 绝对不确定度 u_E   = {abs_E:.3e} Pa")

        # ── 7. 最终结果 ───────────────────────────
        # 不确定度取1位有效数字，结果末位与不确定度对齐
        unc_order = math.floor(math.log10(abs_E)) if abs_E > 0 else 0
        round_digits = -unc_order + 1  # 保留到不确定度第1位

        lines.append("")
        lines.append("=" * 60)
        lines.append("【最终结果】")
        lines.append(f"  E = ({E/1e9:.2f} ± {abs_E/1e9:.2f}) GPa")
        lines.append(f"  相对不确定度：{rel_E*100:.2f}%")
        lines.append(f"  （置信概率约 68%，k=1）")
        lines.append("")
        lines.append("  参考值：钢 ~200 GPa，铜 ~120 GPa，铝 ~70 GPa")
        lines.append("=" * 60)

        res.report_lines = lines
        res.success = True

    except Exception as e:
        res.error_msg = str(e)
        res.success = False

    return res
