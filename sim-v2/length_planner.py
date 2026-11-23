"""衣序 HangFlow v2（rev-D）—— 圆柱长度规划器（端点锚定模型）。

结构（对齐 docs/v2/10-端点锚定模型.md）
--------------------------------------
    左锚点(0) ─[端部01：外端锁、内端自由]─ 衣物1 ─[内部02]─ … ─衣物K─[端部05]─ 右锚点(D)

* K 件衣服配 **K+1 个调节器**；内部 K−1 段长度 = 净风道（中心距 L_i + t_h，t_h=10）。
* **端部外端坐标 0 和 D 绝对固定**（安装时定的锚点间距，1.2 m 杆 4 件时 D=460 mm）。
  端部只有**内端**自由伸缩，`L0, LK ∈ [30, 120] mm`（默认 60）。
* 链总长 `ΣL + K·t_h` 由两端内端吸收变化：
    - 等距/加权：`Δ = Σ(新内部段 − 当前内部段)`，两端各吸收 `−Δ/2`，
      各自 clamp 30–120；一端到限位另一端补；两端都不够 → 拒绝；
    - 收衣：内部缩到 40，Δ<0，端部内端**伸出**吸收；到 120 停下，
      链长 = 400（40×3+40+240），剩下 60 mm 空杆，提示"未完全收拢"。
* 可行性：外端坐标不变，`ΣL + K·t_h` 必须等于 D（等距/加权），
  收衣允许小于 D（留下空杆）；大于 D 或端部超限 → 拒绝/告警。
* 每个夹持是**锥面收口夹头**：开槽夹头环 + 外套筒，向内滑 5–8 mm 径向压紧杆；
  算法状态只有 lock/free。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

EPS = 1e-9

# ---- 锁定参数（mm）----
T_H_MM = 10.0
INNER_MIN_MM = 100.0       # 内部动力段最短（净风道 10 cm；4–10cm 用被动短套）
INNER_MAX_MM = 220.0       # 内部段最长（净风道 22 cm）
END_MIN_MM = 30.0          # 端部内端最短
END_MAX_MM = 120.0         # 端部内端最长
END_BASE_MM = 60.0         # 端部安装默认长度
WALL_MARGIN_MM = 50.0      # 杆端到锚点
DEFAULT_ROD_MM = 1200.0
DEFAULT_GAP_MM = 100.0
MODES = ("equal", "weighted", "collect")


def nominal_span(garment_count: int, gap_mm: float = DEFAULT_GAP_MM,
                 end_mm: float = END_BASE_MM) -> float:
    """安装时的锚点间距 D：K·t_h + (K−1)·gap + 2·end。4 件等距 → 460 mm。"""
    return (garment_count * T_H_MM + (garment_count - 1) * gap_mm
            + 2.0 * end_mm)


@dataclass
class LengthPlan:
    """一次长度规划（mm）。"""

    inner: np.ndarray            # (K-1,) 内部段 = 净风道
    ends: Tuple[float, float]    # (L0, LK) 端部内端长度（外端锚定）
    mode: str
    garment_count: int
    rod_length: float
    available_mm: float          # 可用杆长 = 杆长 − 2×锚点余量
    anchor_span_mm: float        # D（外端锚点间距，固定）
    inner_total_mm: float
    chain_length_mm: float       # ΣL + K·t_h（实际链长）
    gap_mm: float                # D − 链长（空杆 / 未收拢，≥0）
    free_rod_mm: float           # 可用杆长 − D（锚点区之外的富余杆）
    target_gap_mm: float
    feasible: bool = True
    status: str = "ok"           # ok / partial / rejected
    required_end_sum_mm: float = 0.0
    weights: np.ndarray = field(default_factory=lambda: np.zeros(0))
    warnings: List[str] = field(default_factory=list)
    degradation: str = ""
    drop_advice: int = 0

    @property
    def K(self) -> int:
        return int(self.garment_count)

    @property
    def regulator_count(self) -> int:
        return self.K + 1

    @property
    def all_lengths(self) -> np.ndarray:
        return np.concatenate([[self.ends[0]], self.inner, [self.ends[1]]])

    @property
    def center_distances(self) -> np.ndarray:
        return self.inner + T_H_MM

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "K": self.K,
            "regulators": self.regulator_count,
            "inner_mm": [round(float(v), 3) for v in self.inner],
            "ends_mm": [round(float(v), 3) for v in self.ends],
            "all_lengths_mm": [round(float(v), 3) for v in self.all_lengths],
            "center_distances_mm": [round(float(v), 3) for v in self.center_distances],
            "anchor_span_mm": round(float(self.anchor_span_mm), 3),
            "rod_length_mm": round(float(self.rod_length), 3),
            "available_mm": round(float(self.available_mm), 3),
            "inner_total_mm": round(float(self.inner_total_mm), 3),
            "chain_length_mm": round(float(self.chain_length_mm), 3),
            "gap_mm": round(float(self.gap_mm), 3),
            "free_rod_mm": round(float(self.free_rod_mm), 3),
            "required_end_sum_mm": round(float(self.required_end_sum_mm), 3),
            "target_gap_mm": round(float(self.target_gap_mm), 3),
            "feasible": bool(self.feasible),
            "status": self.status,
            "warnings": list(self.warnings),
            "degradation": self.degradation,
            "drop_advice": int(self.drop_advice),
        }


# ---------------------------------------------------------------------------
def available_length(rod_length: float = DEFAULT_ROD_MM,
                     wall_margin: float = WALL_MARGIN_MM) -> float:
    """可用杆长（扣掉两端 50 mm）→ 1.2 m 杆 1100 mm。"""
    return max(0.0, float(rod_length) - 2.0 * float(wall_margin))


def max_garments(rod_length: float, gap_mm: float = DEFAULT_GAP_MM,
                 end_mm: float = END_BASE_MM,
                 wall_margin: float = WALL_MARGIN_MM) -> int:
    """D ≤ 可用杆长时最多几件：K·10 + (K−1)·gap + 2·end ≤ 可用长度。"""
    avail = available_length(rod_length, wall_margin)
    g = float(np.clip(gap_mm, INNER_MIN_MM, INNER_MAX_MM))
    k = int(np.floor((avail + g - 2.0 * end_mm) / (T_H_MM + g) + 1e-9))
    return max(1, k)


def _waterfill(extra: float, weights: np.ndarray,
               cap: Optional[np.ndarray]) -> Tuple[np.ndarray, float]:
    m = int(weights.size)
    shares = np.zeros(m)
    if m == 0:
        return shares, float(max(0.0, extra))
    if extra <= 0:
        return shares, 0.0
    if cap is None:
        return extra * weights / weights.sum(), 0.0
    cap = np.asarray(cap, dtype=float)
    active = np.ones(m, dtype=bool)
    remaining = float(extra)
    for _ in range(m):
        if remaining <= 1e-12:
            break
        idx = np.flatnonzero(active)
        if idx.size == 0:
            break
        w = weights[idx]
        wsum = float(w.sum())
        if wsum <= 0:
            break
        add = remaining * w / wsum
        room = cap[idx] - shares[idx]
        over = add > room + 1e-9
        if not over.any():
            shares[idx] += add
            remaining = 0.0
            break
        for j in idx[over]:
            room_j = max(0.0, float(cap[j] - shares[j]))
            remaining -= room_j
            shares[j] = max(shares[j], float(cap[j]))
            active[j] = False
    return shares, float(max(0.0, remaining))


def _absorb_ends(delta: float, cur_ends: Tuple[float, float],
                 end_min: float, end_max: float,
                 prefer: Optional[str] = None) -> Tuple[float, float, float]:
    """端部吸收 −Δ：默认两端各 −Δ/2，clamp 后溢出由另一端补。

    prefer="left"/"right"：手动拖动时优先让同侧端部吸收全部变化。
    返回 (L0, LK, 未吸收量)；未吸收量 = 需要的端部总长 − 实际能给的总长。
    """
    if prefer == "left":
        a = cur_ends[0] - delta
        b = cur_ends[1]
    elif prefer == "right":
        a = cur_ends[0]
        b = cur_ends[1] - delta
    else:
        a = cur_ends[0] - delta / 2.0
        b = cur_ends[1] - delta / 2.0
    a_c = float(np.clip(a, end_min, end_max))
    b += a - a_c                      # 一端到限位 → 另一端补
    b_c = float(np.clip(b, end_min, end_max))
    a_c += b - b_c
    a_c = float(np.clip(a_c, end_min, end_max))
    need = cur_ends[0] + cur_ends[1] - delta
    got = a_c + b_c
    return a_c, b_c, need - got


# ---------------------------------------------------------------------------
def plan_lengths(garment_count: int,
                 rod_length: float = DEFAULT_ROD_MM,
                 mode: str = "equal",
                 target_gap: float = DEFAULT_GAP_MM,
                 moisture: Optional[Sequence[float]] = None,
                 gap_weights: Optional[Sequence[float]] = None,
                 inner_max: float = INNER_MAX_MM,
                 anchor_span: Optional[float] = None,
                 current_inner: Optional[Sequence[float]] = None,
                 current_ends: Tuple[float, float] = (END_BASE_MM, END_BASE_MM),
                 moisture_exponent: float = 2.0,
                 wall_margin: float = WALL_MARGIN_MM) -> LengthPlan:
    """规划内部段 + 两个端部内端长度（外端锚点固定）。

    anchor_span : D，默认按 4 件等距的安装值算（460 mm）。
    current_inner / current_ends : 当前状态，用于算 Δ（默认内部 100、端部 60）。
    """
    K = int(garment_count)
    if K < 2:
        raise ValueError("至少 2 件衣物（K≥2）")
    if mode not in MODES:
        raise ValueError(f"mode 必须是 {MODES} 之一")
    if not np.isfinite(rod_length) or rod_length <= 0:
        raise ValueError("rod_length 必须为有限正数（mm）")
    if moisture_exponent <= 0:
        raise ValueError("moisture_exponent 必须 > 0")
    n_inner = K - 1
    avail = available_length(rod_length, wall_margin)
    inner_max = float(np.clip(inner_max, INNER_MIN_MM, INNER_MAX_MM))
    D_explicit = anchor_span is not None
    D = float(anchor_span) if D_explicit else nominal_span(K)
    if not np.isfinite(D) or D <= 0:
        raise ValueError("anchor_span 必须为有限正数（mm）")
    D_warn = ""
    if D > avail + 1e-9:
        if D_explicit:
            raise ValueError(
                f"显式 anchor_span D={D:.0f} mm 超过可用杆长 {avail:.0f} mm")
        D_warn = (f"名义锚点间距 D={D:.0f} mm 超过可用杆长 {avail:.0f} mm，"
                  f"已按 {avail:.0f} mm 布置（端部内端相应缩短）")
        D = avail
    if len(current_ends) != 2:
        raise ValueError("current_ends 必须是 (L0, LK)")
    cur_ends = (float(current_ends[0]), float(current_ends[1]))
    if any(v < END_MIN_MM - 1e-9 or v > END_MAX_MM + 1e-9 for v in cur_ends):
        raise ValueError(f"current_ends 必须在 [{END_MIN_MM}, {END_MAX_MM}] mm 内")

    warnings: List[str] = []
    degradation = ""
    drop_advice = 0
    status = "ok"

    # 当前内部段（默认等距安装值）
    if current_inner is None:
        cur_inner = np.full(n_inner, float(DEFAULT_GAP_MM))
    else:
        ci = np.asarray(current_inner, dtype=float).ravel()
        if ci.size != n_inner:
            raise ValueError(f"current_inner 长度 {ci.size} 应为 {n_inner}")
        cur_inner = ci.copy()
    cur_inner_total = float(cur_inner.sum())

    # 权重
    if moisture is None:
        q = np.zeros(K)
    else:
        q = np.asarray(moisture, dtype=float).ravel()
        if q.size != K:
            raise ValueError(f"moisture 长度 {q.size} 应等于 K={K}")
        q = np.clip(q, 0.0, 1.0)
    if gap_weights is not None:
        gw = np.asarray(gap_weights, dtype=float).ravel()
        if gw.size != n_inner or np.any(gw < 0):
            raise ValueError(f"gap_weights 应为 {n_inner} 个非负数")
        weights = gw + EPS
    elif mode == "weighted":
        weights = np.power(0.5 * (q[:-1] + q[1:]), moisture_exponent) + EPS
    else:
        weights = np.ones(n_inner)

    # 内部目标
    if mode == "collect":
        inner = np.full(n_inner, INNER_MIN_MM)
        target = INNER_MIN_MM
    else:
        if target_gap < INNER_MIN_MM - 1e-9:
            inner = np.full(n_inner, INNER_MIN_MM)
            target = INNER_MIN_MM
            warnings.append(
                f"目标风道 {target_gap:.0f} mm 低于内部动力段下限 "
                f"{INNER_MIN_MM:.0f} mm；4–10 cm 用被动短套，不参与自动规划")
            status = "rejected"
            feasible_flag_early = False
        elif target_gap > inner_max + 1e-9:
            inner = np.full(n_inner, inner_max)
            target = inner_max
            warnings.append(
                f"目标风道 {target_gap:.0f} mm 超过内部上限 {inner_max:.0f} mm，已夹到上限")
        else:
            g = float(target_gap)
            target = g
            if mode == "equal":
                inner = np.full(n_inner, g)
            else:
                inner = None
                total = n_inner * g
                extra = max(0.0, total - n_inner * INNER_MIN_MM)
                cap = np.full(n_inner, max(0.0, inner_max - INNER_MIN_MM))
                shares, leftover = _waterfill(extra, weights, cap)
                inner = INNER_MIN_MM + shares
                if leftover > 1e-6:
                    warnings.append(
                        f"内部段上限 {inner_max:.0f} mm 让 {leftover:.1f} mm 分不出去")

    inner_total = float(inner.sum())
    if status == "rejected" and any("被动短套" in w for w in warnings):
        return LengthPlan(
            inner=inner, ends=cur_ends, mode=mode, garment_count=K,
            rod_length=float(rod_length), available_mm=float(avail),
            anchor_span_mm=float(D), inner_total_mm=inner_total,
            chain_length_mm=float(inner_total + K * T_H_MM + sum(cur_ends)),
            gap_mm=0.0, free_rod_mm=float(avail - D), target_gap_mm=float(target),
            feasible=False, status="rejected", required_end_sum_mm=0.0,
            weights=np.asarray(weights, dtype=float),
            warnings=warnings, degradation="4–10 cm 用被动短套；自动模式最小 10 cm",
            drop_advice=0)
    delta = inner_total - cur_inner_total

    # 端点锚定：外端 0/D 不动，内端吸收 −Δ；再按 D 校正总量（D 被钳制时也要对上）
    e0, e1, _un = _absorb_ends(delta, cur_ends, END_MIN_MM, END_MAX_MM)
    required_end_sum = D - K * T_H_MM - inner_total
    # 拟合到所需端部总长（溢出由另一端补）
    d = required_end_sum - (e0 + e1)
    e0 = float(np.clip(e0 + d / 2.0, END_MIN_MM, END_MAX_MM))
    e1 = float(np.clip(required_end_sum - e0, END_MIN_MM, END_MAX_MM))
    e0 = float(np.clip(required_end_sum - e1, END_MIN_MM, END_MAX_MM))
    unabsorbed = required_end_sum - (e0 + e1)
    chain = inner_total + K * T_H_MM + e0 + e1
    gap = D - chain
    free_rod = avail - D

    if required_end_sum < 2 * END_MIN_MM - 1e-9:
        # 内部段总长太大：两端缩到 30 也不够（链比 D 长）
        status = "rejected"
        warnings.append(
            f"内部段总长 {inner_total:.0f} mm 超过锚定跨度允许值："
            f"端部最短 {END_MIN_MM:.0f}×2 时链长 "
            f"{inner_total + K * T_H_MM + 2 * END_MIN_MM:.0f} mm > D={D:.0f} mm；"
            f"拒绝，请减小目标风道或减少件数")
        degradation = "降低目标风道 / 减少件数 / 加大锚点间距 D"
    elif unabsorbed > 1e-6:
        if mode == "collect" or gap > 1e-6:
            status = "partial"
            warnings.append(
                f"端部到限位：内端已到 {END_MAX_MM:.0f} mm，链长 {chain:.0f} mm，"
                f"比锚点间距短 {gap:.0f} mm（未完全收拢）")
            degradation = "收衣受端部行程限制；要完全收拢需加大端部行程"
        else:
            status = "rejected"
            warnings.append(
                f"端部行程不够：需要端部合计 {required_end_sum:.0f} mm，"
                f"实际只能给 {e0 + e1:.0f} mm（{END_MIN_MM:.0f}–{END_MAX_MM:.0f}）")
            degradation = "端部行程不够，先减件或缩短目标"
    elif gap > 1e-6:
        status = "partial"
        warnings.append(
            f"端部到上限，链长 {chain:.0f} mm，比 D 短 {gap:.0f} mm（未完全收拢）")

    if D_warn:
        warnings.append(D_warn)
    feasible = status != "rejected"
    kmax = max_garments(rod_length, target if mode != "collect" else INNER_MIN_MM,
                        END_BASE_MM, wall_margin)
    drop_advice = max(0, K - kmax) if not feasible else 0

    return LengthPlan(
        inner=inner, ends=(float(e0), float(e1)), mode=mode,
        garment_count=K, rod_length=float(rod_length), available_mm=float(avail),
        anchor_span_mm=float(D), inner_total_mm=inner_total,
        chain_length_mm=float(chain), gap_mm=float(max(0.0, gap)),
        free_rod_mm=float(free_rod), target_gap_mm=float(target),
        feasible=bool(feasible), status=status,
        required_end_sum_mm=float(required_end_sum),
        weights=np.asarray(weights, dtype=float),
        warnings=warnings, degradation=degradation,
        drop_advice=int(drop_advice))


def plan_metrics(plan: LengthPlan) -> Dict[str, float]:
    lengths = plan.inner
    return {
        "K": plan.K,
        "regulators": plan.regulator_count,
        "mode": plan.mode,
        "status": plan.status,
        "feasible": bool(plan.feasible),
        "inner_total_mm": float(plan.inner_total_mm),
        "min_gap_mm": float(lengths.min()),
        "max_gap_mm": float(lengths.max()),
        "mean_gap_mm": float(lengths.mean()),
        "gap_std_mm": float(lengths.std()),
        "ends_mm": [float(v) for v in plan.ends],
        "anchor_span_mm": float(plan.anchor_span_mm),
        "chain_length_mm": float(plan.chain_length_mm),
        "gap_mm": float(plan.gap_mm),
        "free_rod_mm": float(plan.free_rod_mm),
        "n_warnings": len(plan.warnings),
        "drop_advice": int(plan.drop_advice),
    }


def demo_plans(garment_count: int = 4,
               moisture: Optional[Sequence[float]] = None,
               target_gap: float = DEFAULT_GAP_MM,
               ) -> Dict[str, LengthPlan]:
    """演示：等距 / 加权 / 收衣（从等距安装态 60/100 出发）。"""
    q = [0.55, 0.90, 0.35, 0.75][:garment_count] if moisture is None else moisture
    equal = plan_lengths(garment_count, mode="equal", target_gap=target_gap)
    cur_inner = equal.inner
    cur_ends = equal.ends
    return {
        "equal": equal,
        "weighted": plan_lengths(garment_count, mode="weighted",
                                 target_gap=max(target_gap, 120.0), moisture=q,
                                 current_inner=cur_inner, current_ends=cur_ends),
        "collect": plan_lengths(garment_count, mode="collect",
                                current_inner=cur_inner, current_ends=cur_ends),
    }


__all__ = [
    "LengthPlan", "plan_lengths", "plan_metrics", "demo_plans",
    "max_garments", "available_length", "nominal_span",
    "T_H_MM", "INNER_MIN_MM", "INNER_MAX_MM", "END_MIN_MM", "END_MAX_MM",
    "END_BASE_MM", "WALL_MARGIN_MM", "DEFAULT_ROD_MM", "DEFAULT_GAP_MM",
    "MODES",
]
