"""衣序 HangFlow v2（rev-C）—— 圆柱长度规划器。

结构（用户 2026-11-23 三轮澄清后锁定）
-------------------------------------
    墙/边缘 ─ 调节器0 ─ 衣物1 ─ 调节器1 ─ 衣物2 ─ … ─ 衣物K ─ 调节器K ─ 墙/边缘

* K 件衣服配 **K+1 个调节器**（两端各 1、内部 K−1）。
* 内部 K−1 段长度 L_i = **净风道**（中心距 = L_i + t_h，t_h=10 mm）。
* 端部 2 段的长度是**安装配置值**（演示 L0=LK=60 mm，可调范围 30–120 mm），
  **不负责把链填满整根杆**：总链长 = ΣL + K·t_h（演示 460 mm），
  剩下的杆段是空杆 / 端部夹头锁位区（演示 640 mm）。
* 可行性只要求 `ΣL + K·t_h ≤ 可用长度`，不要求相等。
* 每个调节器两端是**锥面收口夹头**（开槽夹头环 + 外套筒，套筒向内滑 5–8 mm
  径向压紧杆），算法状态只有 lock/free：锁一端→单向伸缩；锁两端→绝对锁长。
  端部调节器夹住杆，需要顶墙预紧时再用 fill 模式（把空杆余量补进端部段，
  但端部段仍受 30–120 mm 上限约束）。
* 没有恒力卷簧。

三种模式
--------
1) ``equal``    L_i = g_target（默认 100 mm）。
2) ``weighted`` 总风道不变，按湿度权重分配：a_i = ((q_i+q_{i+1})/2)^γ + eps，
   有上限做比例注水 + 饱和。
3) ``collect``  内部段全部缩到 40 mm；端部仍保持配置值。

端部模式
--------
* 默认 ``end_lengths=(60, 60)`` 固定；
* ``fill=True`` 才把空杆余量分给两端（受 30–120 mm 限制，填不满会告警）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

EPS = 1e-9

# ---- 锁定参数（mm）----
T_H_MM = 10.0
INNER_MIN_MM = 40.0        # 内部段最短（净风道 4 cm）
INNER_MAX_MM = 220.0       # 内部段最长（净风道 22 cm）
END_MIN_MM = 30.0          # 端部段最短
END_MAX_MM = 120.0         # 端部段最长
END_CONFIG_MM = 60.0       # 端部段安装配置值（演示）
WALL_MARGIN_MM = 50.0      # 杆端到墙/挡块
DEFAULT_ROD_MM = 1200.0
DEFAULT_GAP_MM = 100.0
PRELOAD_MM = 0.5           # fill 模式顶墙过盈
PRELOAD_FORCE_N = 10.0
MODES = ("equal", "weighted", "collect")


@dataclass
class LengthPlan:
    """一次长度规划（mm）。"""

    inner: np.ndarray            # (K-1,) 内部段 = 净风道
    ends: Tuple[float, float]    # (L0, LK) 端部段（安装配置值）
    mode: str
    garment_count: int
    rod_length: float
    available_mm: float
    inner_total_mm: float
    chain_length_mm: float
    leftover_mm: float           # 空杆 / 端部夹头锁位区
    target_gap_mm: float
    fill: bool = False
    preload_mm: float = 0.0
    feasible: bool = True
    status: str = "ok"
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

    @property
    def wall_contact(self) -> bool:
        """链条是否正好顶到两侧墙（只有 fill 模式可能为真）。"""
        return abs(self.chain_length_mm - self.available_mm) < 1e-6

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "K": self.K,
            "regulators": self.regulator_count,
            "inner_mm": [round(float(v), 3) for v in self.inner],
            "ends_mm": [round(float(v), 3) for v in self.ends],
            "all_lengths_mm": [round(float(v), 3) for v in self.all_lengths],
            "center_distances_mm": [round(float(v), 3) for v in self.center_distances],
            "rod_length_mm": round(float(self.rod_length), 3),
            "available_mm": round(float(self.available_mm), 3),
            "inner_total_mm": round(float(self.inner_total_mm), 3),
            "chain_length_mm": round(float(self.chain_length_mm), 3),
            "leftover_mm": round(float(self.leftover_mm), 3),
            "target_gap_mm": round(float(self.target_gap_mm), 3),
            "fill": bool(self.fill),
            "wall_contact": bool(self.wall_contact),
            "preload_mm": round(float(self.preload_mm), 3),
            "feasible": bool(self.feasible),
            "status": self.status,
            "warnings": list(self.warnings),
            "degradation": self.degradation,
            "drop_advice": int(self.drop_advice),
        }


# ---------------------------------------------------------------------------
def available_length(rod_length: float = DEFAULT_ROD_MM,
                     wall_margin: float = WALL_MARGIN_MM) -> float:
    """可用长度 = 杆长 − 2×端部余量（墙/法兰）。1.2 m 杆 → 1100 mm。"""
    return max(0.0, float(rod_length) - 2.0 * float(wall_margin))


def max_garments(rod_length: float, gap_mm: float = DEFAULT_GAP_MM,
                 end_mm: float = END_CONFIG_MM,
                 wall_margin: float = WALL_MARGIN_MM) -> int:
    """端部按 2×end_mm、内部按 gap，这根杆最多挂几件。"""
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


# ---------------------------------------------------------------------------
def plan_lengths(garment_count: int,
                 rod_length: float = DEFAULT_ROD_MM,
                 mode: str = "equal",
                 target_gap: float = DEFAULT_GAP_MM,
                 moisture: Optional[Sequence[float]] = None,
                 gap_weights: Optional[Sequence[float]] = None,
                 inner_max: float = INNER_MAX_MM,
                 end_lengths: Optional[Sequence[float]] = None,
                 fill: bool = False,
                 moisture_exponent: float = 2.0,
                 wall_margin: float = WALL_MARGIN_MM) -> LengthPlan:
    """规划 K−1 个内部段 + 2 个端部段的长度。

    end_lengths : 端部段配置值，默认 (60, 60)；给 None 且 fill=True 时按余量分。
    可行性只要求 ΣL + K·t_h ≤ 可用长度；端部段不负责填满杆。
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
    warnings: List[str] = []
    degradation = ""
    drop_advice = 0
    status = "ok"

    # 端部配置值
    if end_lengths is None:
        ends = (END_CONFIG_MM, END_CONFIG_MM)
    else:
        ends = tuple(float(v) for v in end_lengths)
        if len(ends) != 2:
            raise ValueError("end_lengths 必须是 (L0, LK)")
        if any(v < END_MIN_MM - 1e-9 or v > END_MAX_MM + 1e-9 for v in ends):
            raise ValueError(f"端部段必须在 [{END_MIN_MM}, {END_MAX_MM}] mm 内")

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

    # 内部段
    if mode == "collect":
        inner = np.full(n_inner, INNER_MIN_MM)
        target = INNER_MIN_MM
    else:
        g = float(np.clip(target_gap, INNER_MIN_MM, inner_max))
        if abs(g - target_gap) > 1e-9:
            status = "clipped"
            warnings.append(
                f"目标风道 {target_gap:.0f} mm 超出范围，已夹到 {g:.0f} mm"
                f"（内部段 {INNER_MIN_MM:.0f}–{inner_max:.0f} mm）")
        target = g
        if mode == "equal":
            inner = np.full(n_inner, g)
        else:
            total = n_inner * g
            extra = max(0.0, total - n_inner * INNER_MIN_MM)
            cap = np.full(n_inner, max(0.0, inner_max - INNER_MIN_MM))
            shares, leftover = _waterfill(extra, weights, cap)
            inner = INNER_MIN_MM + shares
            if leftover > 1e-6:
                warnings.append(
                    f"内部段上限 {inner_max:.0f} mm 让 {leftover:.1f} mm 分不出去，"
                    f"总风道比预算少 {leftover:.1f} mm")

    fixed = K * T_H_MM
    # 可行性：ΣL + K·t_h ≤ 可用长度（端部段固定配置值）
    inner_total = float(inner.sum())
    if inner_total + fixed + ends[0] + ends[1] > avail + 1e-9:
        allowed_inner = avail - fixed - ends[0] - ends[1]
        if allowed_inner >= n_inner * INNER_MIN_MM - 1e-9:
            if mode == "equal" or np.allclose(inner, inner[0]):
                inner = np.full(n_inner, allowed_inner / n_inner)
            else:
                scale = allowed_inner / inner_total
                inner = np.maximum(inner * scale, INNER_MIN_MM)
                if inner.sum() > allowed_inner:
                    inner = np.full(n_inner, allowed_inner / n_inner)
            inner_total = float(inner.sum())
            status = "clipped"
            warnings.append(
                f"杆放不下：{K} 件 + {K + 1} 段在 {ends[0]:.0f}/{ends[1]:.0f} mm 端部下，"
                f"内部段被压到 {inner.min():.0f}–{inner.max():.0f} mm")
            degradation = "降级方案：减少件数 / 换更长杆 / 降低目标风道"
        else:
            status = "infeasible"
            inner = np.full(n_inner, INNER_MIN_MM)
            inner_total = float(inner.sum())
            warnings.append(
                f"连最短状态都放不下：{K} 件 + {K + 1} 段最短合计 "
                f"{fixed + (n_inner + 2) * INNER_MIN_MM:.0f} mm，可用仅 {avail:.0f} mm")
            degradation = "必须减少件数或换杆"
        kmax = max_garments(rod_length, target if mode != "collect" else INNER_MIN_MM,
                            ends[0], wall_margin)
        drop_advice = max(0, K - kmax)
        if drop_advice:
            degradation += f"（本杆长建议 ≤{kmax} 件）"

    chain = inner_total + fixed + ends[0] + ends[1]
    leftover = avail - chain

    # 可选 fill 模式：把空杆余量补进端部段（受 30–120 限制）
    if fill and feasible_status(status):
        room = (END_MAX_MM - ends[0]) + (END_MAX_MM - ends[1])
        add = min(leftover, room)
        if add > 1e-9:
            ends = (ends[0] + add / 2.0, ends[1] + add / 2.0)
            chain = inner_total + fixed + ends[0] + ends[1]
            leftover = avail - chain
        if leftover > 1e-6 and status == "ok":
            status = "clipped"
            warnings.append(
                f"fill 模式也填不满：空杆还剩 {leftover:.0f} mm（端部段上限 "
                f"{END_MAX_MM:.0f} mm）→ 建议缩短杆长或加件")

    if not fill and leftover > 0 and status == "ok":
        warnings.append(
            f"链长 {chain:.0f} mm，剩余 {leftover:.0f} mm 为空心杆段 / 端部夹头锁位区"
            f"（端部段固定 {ends[0]:.0f}/{ends[1]:.0f} mm，不填满杆）")

    preload = PRELOAD_MM if (fill and abs(chain - avail) < 1e-6) else 0.0
    return LengthPlan(
        inner=inner, ends=(float(ends[0]), float(ends[1])), mode=mode,
        garment_count=K, rod_length=float(rod_length), available_mm=float(avail),
        inner_total_mm=inner_total, chain_length_mm=float(chain),
        leftover_mm=float(leftover), target_gap_mm=float(target), fill=bool(fill),
        preload_mm=float(preload), feasible=bool(status != "infeasible"),
        status=status, weights=np.asarray(weights, dtype=float),
        warnings=warnings, degradation=degradation,
        drop_advice=int(drop_advice))


def feasible_status(status: str) -> bool:
    return status != "infeasible"


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
        "chain_length_mm": float(plan.chain_length_mm),
        "leftover_mm": float(plan.leftover_mm),
        "wall_contact": bool(plan.wall_contact),
        "n_warnings": len(plan.warnings),
        "drop_advice": int(plan.drop_advice),
    }


def demo_plans(garment_count: int = 4,
               moisture: Optional[Sequence[float]] = None,
               target_gap: float = DEFAULT_GAP_MM,
               fill: bool = False) -> Dict[str, LengthPlan]:
    """演示：等距 / 加权 / 收衣（端部固定 60 mm）。"""
    q = [0.55, 0.90, 0.35, 0.75][:garment_count] if moisture is None else moisture
    return {
        "equal": plan_lengths(garment_count, mode="equal", target_gap=target_gap,
                              fill=fill),
        "weighted": plan_lengths(garment_count, mode="weighted",
                                 target_gap=target_gap, moisture=q, fill=fill),
        "collect": plan_lengths(garment_count, mode="collect", fill=fill),
    }


__all__ = [
    "LengthPlan", "plan_lengths", "plan_metrics", "demo_plans",
    "max_garments", "available_length",
    "T_H_MM", "INNER_MIN_MM", "INNER_MAX_MM", "END_MIN_MM", "END_MAX_MM",
    "END_CONFIG_MM", "WALL_MARGIN_MM", "DEFAULT_ROD_MM", "DEFAULT_GAP_MM",
    "PRELOAD_MM", "PRELOAD_FORCE_N", "MODES",
]
