"""衣序 HangFlow —— 间距规划器（spacing planner）。

口径（锁定，与 docs/_shared-context.md 一致）
-------------------------------------------
* **t_i 是衣物沿杆方向的厚度投影**（cm / mm），不是衣架宽度。
  干衣 20–40 mm，湿衣 30–60 mm。
* 杆上约束：L = Σt_i + Σg_i，g_i 为相邻衣物之间的风道间隙。
* 规划坐标原点 = **可用杆段左端**（杆两端各留 5 cm 端部留白之后）。
  所以传入的 ``max_span`` = 可用杆长 = 杆长 − 2×50 mm（1.2 m 杆 → 1100 mm）。

算法
----
1) 每件衣物的干燥需求 q_i ∈ [0,1]（湿度，0=已干，1=全湿）。
   间隙 i（连接衣物 i 与 i+1）的权重
       a_i = ( (q_i + q_{i+1}) / 2 ) ** gamma + eps
   gamma 默认 2：越湿的地方风道越宽（对两侧"就高不就低"，但用指数放大差异）。
2) 基础分配：每个间隙先给 g_min（默认 30 mm = 3 cm 安全间隙）。
3) 目标总跨度 S（首件左边缘 → 末件右边缘）：S 被夹到 [S_min, max_span]，
   S_min = Σt + 2*0 + (N-1)*g_min（本坐标下无端部余量）。
   剩余空间 E = S − Σt − (N-1)*g_min 按权重 a_i 比例分配（**闭式解**）。
4) 若有上限 g_max，按"比例注水 + 饱和"迭代：先按比例分，超过 g_max 的间隙
   钉死在上限，剩余额度在未饱和间隙里重新按比例分，直到无饱和。
   每轮至少饱和一个间隙 ⇒ 至多 N-1 轮，O(N^2) 上界、实测 O(N)。
5) 规划块在可用杆段内**居中**（也可以按 target_span 更紧凑，居中只是摆放习惯）。

不可行处理（不静默：warnings + degradation + drop_advice）
--------------------------------------------------------
* **杆太短**（Σt + (N-1)g_min > max_span）：先把间隙压到可行值并告警
  （status="compressed"），若端部无法再让就直接压到 0；若连 Σt > max_span
  则 status="infeasible"，给出建议件数。
* **目标跨度太紧**（target_span < S_min）：不能为了凑跨度而牺牲 3 cm 安全间隙，
  自动放宽到 S_min 并告警。
* **目标跨度超过 max_span**：截到 max_span 并告警。
* **g_max 太小时**：多余空间转成端部留白，告警实际跨度小于目标。

典型用法
--------
>>> plan = plan_spacing([25, 40, 30, 55], max_span=1100, target_span=480,
...                     moisture=[0.9, 0.5, 0.8, 0.4])
>>> plan.gaps            # 三个间隙，mm
array([122.4, 109.7,  97.9])
>>> plan.feasible, plan.status
(True, 'ok')
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

EPS = 1e-9

# ---- 设计默认值（与 docs/_shared-context.md 第 3 节量化目标对齐，单位 mm）----
ROD_LENGTH_MM = 1200.0          # 演示杆长
END_CLEARANCE_MM = 50.0         # 杆两端各留 5 cm
MIN_GAP_MM = 30.0               # 最小安全间隙 3 cm
TARGET_GAP_RANGE_MM = (80.0, 120.0)  # 目标间隙 8–12 cm
DEFAULT_TARGET_SPAN_MM = 480.0  # 4 件衣物、目标间隙约 10 cm 时的总跨度
DEFAULT_MOISTURE_EXPONENT = 2.0  # 干燥需求权重敏感度


@dataclass
class SpacingPlan:
    """一次间距规划的输出。所有长度单位 mm，坐标原点 = 可用杆段左端。"""

    thickness: np.ndarray           # (N,) 衣物沿杆厚度投影 t_i
    moisture: np.ndarray            # (N,) 湿度 q_i ∈ [0,1]
    weights: np.ndarray             # (N-1,) 各间隙的干燥需求权重 a_i
    gaps: np.ndarray                # (N-1,) 相邻间隙 g_i
    centers: np.ndarray             # (N,) 衣物中心位置
    edges: np.ndarray               # (N,2) 左/右边缘
    max_span: float                 # 跨度上限 L_max（可用杆长）
    target_span: float              # 期望总跨度（规划前）
    used_span: float                # 实际总跨度 = Σt + Σg
    status: str = "ok"              # "ok" / "compressed" / "infeasible"
    feasible: bool = True           # 只有 ok 为 True（compressed 已违反 g_min）
    warnings: List[str] = field(default_factory=list)
    degradation: str = ""           # 人话降级方案
    drop_advice: int = 0            # 建议减少的件数

    # ---- 便捷视图 ----
    @property
    def n(self) -> int:
        return int(self.thickness.size)

    @property
    def block_left(self) -> float:
        return float(self.edges[0, 0]) if self.n else 0.0

    @property
    def block_right(self) -> float:
        return float(self.edges[-1, 1]) if self.n else 0.0

    def to_dict(self) -> dict:
        """转成 JSON 友好的字典（写入 docs/_data/algorithm-results.json）。"""
        return {
            "n": self.n,
            "thickness_mm": [round(float(v), 3) for v in self.thickness],
            "moisture": [round(float(v), 3) for v in self.moisture],
            "gaps_mm": [round(float(v), 3) for v in self.gaps],
            "centers_mm": [round(float(v), 3) for v in self.centers],
            "max_span_mm": round(float(self.max_span), 3),
            "target_span_mm": round(float(self.target_span), 3),
            "used_span_mm": round(float(self.used_span), 3),
            "status": self.status,
            "feasible": bool(self.feasible),
            "warnings": list(self.warnings),
            "degradation": self.degradation,
            "drop_advice": int(self.drop_advice),
        }


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def usable_span(rod_length: float = ROD_LENGTH_MM,
                end_clearance: float = END_CLEARANCE_MM) -> float:
    """可用杆长 = 杆长 − 2×端部留白（mm）。1.2 m 杆默认 → 1100 mm。"""
    return max(0.0, float(rod_length) - 2.0 * float(end_clearance))


def _as_positive_1d(values: Sequence[float], name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float).ravel()
    if arr.size == 0:
        raise ValueError(f"{name} 不能为空")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} 含 NaN/Inf")
    if np.any(arr <= 0):
        raise ValueError(f"{name} 必须全为正（mm）")
    return arr


def _waterfill(extra: float, weights: np.ndarray,
               cap: Optional[np.ndarray] = None
               ) -> Tuple[np.ndarray, np.ndarray, float]:
    """加权 water-filling：把 ``extra`` 按 ``weights`` 比例分给各间隙。

    参数
    ----
    extra : 待分配空间 (mm)，> 0
    weights : (M,) 各间隙权重，> 0
    cap : (M,) 或 None，每个间隙能拿到的额外空间上限 (mm)

    返回
    ----
    shares : (M,) 分到的额外空间
    saturated : (M,) 是否被上限钉住
    leftover : 因上限限制而没分出去的空间 (mm)
    """
    m = int(weights.size)
    shares = np.zeros(m)
    saturated = np.zeros(m, dtype=bool)
    if m == 0:
        return shares, saturated, float(max(0.0, extra))
    if extra <= 0:
        return shares, saturated, 0.0
    if cap is None:
        return extra * weights / weights.sum(), saturated, 0.0

    cap = np.asarray(cap, dtype=float)
    active = np.ones(m, dtype=bool)
    remaining = float(extra)
    for _ in range(m):  # 每轮至少饱和一个，最多 m 轮
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
            saturated[j] = True
            active[j] = False
    return shares, saturated, float(max(0.0, remaining))


def max_garments(rod_length: float, thicknesses: Sequence[float],
                 min_gap: float = MIN_GAP_MM,
                 end_clearance: float = END_CLEARANCE_MM) -> int:
    """这根杆最多能安全挂几件（按厚度从小到大贪心，保证最优件数）。"""
    avail = usable_span(rod_length, end_clearance)
    if avail <= 0:
        return 0
    ts = np.sort(np.asarray(thicknesses, dtype=float).ravel())
    total, k = 0.0, 0
    for t in ts:
        need = total + float(t) + (min_gap if k > 0 else 0.0)
        if need <= avail + 1e-9:
            total = need
            k += 1
        else:
            break
    return k


def _assemble(thickness: np.ndarray, gaps: np.ndarray, moisture: np.ndarray,
              weights: np.ndarray, max_span: float, target_span: float,
              status: str, feasible: bool, warnings: List[str],
              degradation: str, drop_advice: int) -> SpacingPlan:
    """由间隙数组组装完整方案（居中摆放、算位置与边缘）。"""
    n = int(thickness.size)
    total_t = float(thickness.sum())
    block_span = total_t + float(gaps.sum())
    if status == "infeasible":
        left = 0.0  # 放不下：从最左端紧密排（会超出，如实暴露问题）
    else:
        free = max_span - block_span
        left = free / 2.0 if free > 0 else 0.0

    edges = np.zeros((n, 2))
    centers = np.zeros(n)
    cursor = left
    for i in range(n):
        edges[i, 0] = cursor
        edges[i, 1] = cursor + thickness[i]
        centers[i] = cursor + thickness[i] / 2.0
        cursor += thickness[i]
        if i < gaps.size:
            cursor += gaps[i]
    return SpacingPlan(
        thickness=thickness,
        moisture=moisture,
        weights=weights,
        gaps=gaps,
        centers=centers,
        edges=edges,
        max_span=float(max_span),
        target_span=float(target_span),
        used_span=block_span,
        status=status,
        feasible=feasible,
        warnings=list(warnings),
        degradation=degradation,
        drop_advice=int(drop_advice),
    )


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------
def plan_spacing(thicknesses: Sequence[float],
                 max_span: float = 1100.0,
                 min_gap: float = MIN_GAP_MM,
                 target_span: Optional[float] = None,
                 moisture: Optional[Sequence[float]] = None,
                 gap_weights: Optional[Sequence[float]] = None,
                 max_gap: Optional[float] = None,
                 moisture_exponent: float = DEFAULT_MOISTURE_EXPONENT,
                 ) -> SpacingPlan:
    """在 ``max_span`` 内规划 N 件衣物的位置与间隙（按干燥需求加权）。

    参数
    ----
    thicknesses : 衣物沿杆厚度投影 t_i（mm），干衣 20–40、湿衣 30–60。
    max_span : 跨度上限 L_max（mm）= 可用杆长 = 杆长 − 2×50 mm。
    min_gap : 最小安全间隙 g_min（mm），默认 30（3 cm）。
    target_span : 期望总跨度 S（mm）。None → 直接用 max_span。
        演示常用 480（4 件、目标间隙约 10 cm）。
    moisture : 每件衣物湿度 q_i ∈ [0,1]；None → 全 0（等距）。
    gap_weights : 直接给 (N-1) 个间隙权重（覆盖 moisture 推导）。
    max_gap : 间隙上限（mm）；None 不限。用于"别摊太开"。
    moisture_exponent : 权重指数 gamma；1 = 线性平均，2 = 放大差异。

    返回
    ----
    SpacingPlan（见类文档）。不可行时 status/feasible/warnings/degradation 说明原因。
    """
    t = _as_positive_1d(thicknesses, "thicknesses")
    n = int(t.size)
    max_span = float(max_span)
    min_gap = float(min_gap)
    if not np.isfinite(max_span) or max_span <= 0:
        raise ValueError("max_span 必须为有限正数（mm）")
    if not np.isfinite(min_gap) or min_gap < 0:
        raise ValueError("min_gap 不能为负")
    if moisture_exponent <= 0:
        raise ValueError("moisture_exponent 必须 > 0")
    if max_gap is not None:
        max_gap = float(max_gap)
        if max_gap < min_gap:
            raise ValueError("max_gap 必须 >= min_gap")

    if moisture is None:
        q = np.zeros(n)
    else:
        q = np.asarray(moisture, dtype=float).ravel()
        if q.size != n:
            raise ValueError(f"moisture 长度 {q.size} 与衣物数 {n} 不一致")
        if not np.all(np.isfinite(q)):
            raise ValueError("moisture 含 NaN/Inf")
        q = np.clip(q, 0.0, 1.0)

    if gap_weights is not None:
        gw = np.asarray(gap_weights, dtype=float).ravel()
        if gw.size != max(n - 1, 0):
            raise ValueError(f"gap_weights 长度 {gw.size} 应为 {max(n - 1, 0)}")
        if np.any(gw < 0):
            raise ValueError("gap_weights 不能为负")
        weights = gw + EPS
    elif n >= 2:
        weights = np.power(0.5 * (q[:-1] + q[1:]), moisture_exponent) + EPS
    else:
        weights = np.zeros(0)

    warnings: List[str] = []
    degradation = ""
    drop_advice = 0
    s_req = target_span if target_span is not None else max_span
    s_req = float(s_req)
    if not np.isfinite(s_req) or s_req <= 0:
        raise ValueError("target_span 必须为有限正数（mm）")
    total_t = float(t.sum())

    # ---- 杆太短：连最小安全间隙都放不下 ----
    s_min = total_t + (n - 1) * min_gap
    if s_min > max_span + 1e-9:
        if max_span >= total_t - 1e-9:
            g = max(0.0, (max_span - total_t) / (n - 1)) if n > 1 else 0.0
            status, feasible = "compressed", False
            warnings.append(
                f"杆太短：{n} 件衣物需要 ≥{s_min:.0f} mm 跨度，可用仅 {max_span:.0f} mm；"
                f"间隙被压到 {g:.1f} mm（< 最小 {min_gap:.0f} mm），风道效果打折"
            )
            degradation = (
                "降级方案：减少件数 / 换更长杆 / 接受更小间隙"
            )
        else:
            g = 0.0
            status, feasible = "infeasible", False
            warnings.append(
                f"衣物总厚度 {total_t:.0f} mm 已超过可用杆长 {max_span:.0f} mm，物理上放不下"
            )
            degradation = "必须减少件数或换杆，本杆长下不存在可行方案"
        nmax = max_garments(max_span + 2 * END_CLEARANCE_MM, t, min_gap)
        drop_advice = max(0, n - nmax)
        if drop_advice:
            degradation += f"（建议 ≤{nmax} 件）"
        gaps = np.full(max(n - 1, 0), max(0.0, g))
        return _assemble(t, gaps, q, weights, max_span, s_req,
                         status, feasible, warnings, degradation, drop_advice)

    # ---- 正常：目标跨度夹到 [s_min, max_span] ----
    s = min(max(s_req, s_min), max_span)
    if target_span is not None and s_req > max_span + 1e-9:
        warnings.append(
            f"目标总跨度 {s_req:.0f} mm 超过可用杆长 {max_span:.0f} mm，已截到 {max_span:.0f} mm"
        )
    if target_span is not None and s_req < s_min - 1e-9:
        warnings.append(
            f"目标总跨度 {s_req:.0f} mm 太紧：留不出 {min_gap:.0f} mm 安全间隙，"
            f"已放宽到最小可行跨度 {s_min:.0f} mm"
        )

    extra = max(0.0, s - total_t - (n - 1) * min_gap)
    cap_extra = None if max_gap is None else np.full(max(n - 1, 0), max(0.0, max_gap - min_gap))
    shares, _saturated, leftover = _waterfill(extra, weights, cap_extra)
    gaps = min_gap + shares if n >= 2 else np.zeros(0)
    if n < 2:
        leftover = 0.0

    if leftover > 1e-6 and max_gap is not None:
        warnings.append(
            f"间隙上限 {max_gap:.0f} mm 让 {leftover:.1f} mm 空间分不出去，"
            f"实际跨度 {total_t + float(gaps.sum()):.0f} mm < 目标 {s:.0f} mm（多出空间留在端部）"
        )
    if n == 1:
        warnings.append("只有 1 件衣物，无间隙可分配；按 max_span 居中摆放")

    return _assemble(t, gaps, q, weights, max_span, s_req,
                     "ok", True, warnings, degradation, drop_advice)


# ---------------------------------------------------------------------------
# 评估
# ---------------------------------------------------------------------------
def plan_metrics(plan: SpacingPlan) -> dict:
    """把方案压缩成可引用的指标（供图表与结果表使用）。"""
    gaps = plan.gaps
    has = gaps.size > 0
    mean_gap = float(gaps.mean()) if has else float("nan")
    std_gap = float(gaps.std()) if has else float("nan")
    return {
        "n": plan.n,
        "status": plan.status,
        "feasible": bool(plan.feasible),
        "max_span_mm": float(plan.max_span),
        "target_span_mm": float(plan.target_span),
        "used_span_mm": float(plan.used_span),
        "block_left_mm": plan.block_left,
        "block_right_mm": plan.block_right,
        "min_gap_mm": float(gaps.min()) if has else float("nan"),
        "max_gap_mm": float(gaps.max()) if has else float("nan"),
        "mean_gap_mm": mean_gap,
        "gap_std_mm": std_gap,
        "gap_cv": float(std_gap / mean_gap) if has and mean_gap > 0 else 0.0,
        "weighted_vent_mm": float(np.dot(gaps, plan.weights)) if has else 0.0,
        "utilization": float(plan.used_span / plan.max_span) if plan.max_span else float("nan"),
        "n_warnings": len(plan.warnings),
        "drop_advice": int(plan.drop_advice),
    }


def move_distance(plan: SpacingPlan, current_centers: Sequence[float]) -> float:
    """从当前位置平移到目标位置的总行程 Σ|Δx|（mm），用于估算调整耗时。"""
    cur = np.asarray(current_centers, dtype=float).ravel()
    if cur.size != plan.n:
        raise ValueError("current_centers 长度与衣物数不一致")
    return float(np.abs(plan.centers - cur).sum())


__all__ = [
    "SpacingPlan",
    "plan_spacing",
    "plan_metrics",
    "max_garments",
    "move_distance",
    "usable_span",
    "ROD_LENGTH_MM",
    "END_CLEARANCE_MM",
    "MIN_GAP_MM",
    "TARGET_GAP_RANGE_MM",
    "DEFAULT_TARGET_SPAN_MM",
]
