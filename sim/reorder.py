"""顺序问题：单杆上的重排代价与 move-to-end 避让策略。

物理事实（序不变性）
-------------------
所有单元只能沿同一根杆平移、彼此不得重叠（1 维有序系统），
连续运动**不可能**改变相对次序——要换序就必须有一瞬间互相穿过。
所以"把最湿的衣服挪到进风口侧"不能靠沿杆慢慢挪实现，这是仿真里要写清的前提。

本项目的口径（与 docs/_shared-context.md 第 6 节不冲突，属 P1）
-----------------------------------------------------------
套挂单元是 C 形夹爪，可被抬离杆面。杆最远端留一个 **transfer bay（转移段）**：
单元抬起 → 纵移到最远端 → 落下，记为 **1 次 move-to-end 操作**。
P0 不换序，只调间距（间距规划器已经能按湿度分配风道）；
换序作为 P1，机械上必须支持"抬升越障"，否则无解。

最小移动次数（闭式）
-------------------
令 ``ranks[slot]`` = 该槽位单元的目标序号（1..N）。
没被移动的单元必须停留在前缀、且已按 1..k 递增排列
⇒ k = 满足 pos(1) < pos(2) < … < pos(k) 的最大值。
最少 move-to-end 次数 = N − k；上界 = N − 1（k 最小为 1）。
贪心序列：把 k+1, k+2, …, N 依次移到最远端（每个只动一次）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

from spacing_planner import plan_spacing

# 设计值：N20 40 rpm + 20 mm 摩擦轮 → 轮面线速度
WHEEL_CIRC_MM = np.pi * 20.0
DESIGN_SPEED_MM_S = WHEEL_CIRC_MM * 40.0 / 60.0     # ≈ 41.9 mm/s
FAST_SPEED_MM_S = WHEEL_CIRC_MM * 100.0 / 60.0      # ≈ 104.7 mm/s（换 100rpm 电机）
LIFT_OVERHEAD_S = 2.5                               # 抬升 + 落下 + 对位（估算）
SECURITY_BUDGET_S = 30.0                            # 需求：4 件单次调整 ≤ 30 s


@dataclass
class MoveOp:
    """一次 move-to-end 操作（抬升越障 → 放最远端）。"""

    step: int
    rank: int                     # 该单元的目标序号
    label: str                    # 显示用编号（如 "A"）
    from_slot: int
    to_slot: int
    distance_mm: float
    travel_s: float               # 主动行程耗时
    total_s: float                # 含抬升开销
    order_after: List[int] = field(default_factory=list)  # 每槽位的目标序号


@dataclass
class ReorderPlan:
    """一次完整重排方案。"""

    ranks: List[int]             # 初始：每槽位单元的目标序号
    n: int
    kept: int                    # 无需移动的件数 k
    moves: int                   # 实际移动次数 = n - k
    upper_bound: int             # 上界 n - 1
    ops: List[MoveOp]
    states: List[List[int]]      # 每步之后的槽位排名序列（含初始态）
    labels: List[str]            # 槽位初始摆放的单元编号
    slot_positions: List[float]  # 目标槽位中心位置（mm）
    active_travel_mm: float      # 主动行程合计
    letway_mm: float             # 已放好的单元向内让位行程
    reorder_time_s: float
    speed_mm_s: float = DESIGN_SPEED_MM_S

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "kept": self.kept,
            "moves": self.moves,
            "upper_bound": self.upper_bound,
            "labels": list(self.labels),
            "ranks": list(self.ranks),
            "states": [list(s) for s in self.states],
            "ops": [
                {
                    "step": op.step,
                    "rank": op.rank,
                    "label": op.label,
                    "from_slot": op.from_slot,
                    "to_slot": op.to_slot,
                    "distance_mm": round(op.distance_mm, 2),
                    "total_s": round(op.total_s, 2),
                }
                for op in self.ops
            ],
            "active_travel_mm": round(self.active_travel_mm, 2),
            "letway_mm": round(self.letway_mm, 2),
            "reorder_time_s": round(self.reorder_time_s, 2),
            "speed_mm_s": round(self.speed_mm_s, 2),
        }


# ---------------------------------------------------------------------------
def ranks_from_orders(current_order: Sequence, desired_order: Sequence) -> List[int]:
    """把"当前物理顺序 + 期望顺序"转成每槽位的目标序号（1..N）。"""
    cur = list(current_order)
    des = list(desired_order)
    if sorted(map(str, cur)) != sorted(map(str, des)):
        raise ValueError("current_order 与 desired_order 必须是同一组单元的不同排列")
    if len(set(map(str, cur))) != len(cur):
        raise ValueError("单元编号重复")
    rank = {str(item): i + 1 for i, item in enumerate(des)}
    return [rank[str(item)] for item in cur]


def longest_inorder_prefix(ranks: Sequence[int]) -> int:
    """k = 满足 pos(1)<pos(2)<…<pos(k) 的最大 k（这些单元可原地不动）。"""
    r = np.asarray(ranks, dtype=int).ravel()
    n = int(r.size)
    if n == 0:
        return 0
    pos = np.empty(n + 1, dtype=int)
    for slot, value in enumerate(r):
        pos[value] = slot
    k = 1
    while k < n and pos[k] < pos[k + 1]:
        k += 1
    return k


def move_upper_bound(n: int) -> int:
    """最坏情况（完全逆序）移动次数上界 = N-1。"""
    return max(0, int(n) - 1)


def reachable_permutations_without_passing(n: int) -> int:
    """不抬升、只沿杆平移时可到达的排列数 = 1（次序不变）。"""
    return 1


def greedy_move_to_end(ranks: Sequence[int],
                       labels: Optional[Sequence[str]] = None,
                       slot_positions: Optional[Sequence[float]] = None,
                       speed_mm_s: float = DESIGN_SPEED_MM_S,
                       lift_overhead_s: float = LIFT_OVERHEAD_S) -> ReorderPlan:
    """贪心 move-to-end：把 k+1..N 依次移到最远端，给出每一步状态与耗时。"""
    cur = [int(v) for v in ranks]
    n = len(cur)
    if n == 0:
        raise ValueError("ranks 不能为空")
    if sorted(cur) != list(range(1, n + 1)):
        raise ValueError("ranks 必须是 1..N 的排列")

    k = longest_inorder_prefix(cur)
    lab = list(labels) if labels is not None else [chr(ord("A") + i) for i in range(n)]
    if len(lab) != n:
        raise ValueError("labels 长度与单元数不一致")
    # 初始槽位 i 上是 lab[i]，其目标序号是 ranks[i] → 反查序号对应的单元名
    rank2label = {int(ranks[i]): lab[i] for i in range(n)}
    # 槽位位置：默认按"4 件、目标间隙 10 cm"的规划结果，其它 N 按均匀间隙近似
    if slot_positions is None:
        t = [35.0] * n
        target = 35.0 * n + 100.0 * (n - 1)
        plan = plan_spacing(t, max_span=1100.0, target_span=min(target, 1100.0))
        pos = list(plan.centers)
    else:
        pos = [float(v) for v in slot_positions]
        if len(pos) != n:
            raise ValueError("slot_positions 长度与单元数不一致")

    x_end = pos[-1]
    states: List[List[int]] = [cur.copy()]
    ops: List[MoveOp] = []
    active_travel = 0.0
    letway = 0.0
    clock = 0.0
    for step, rank in enumerate(range(k + 1, n + 1), start=1):
        from_slot = cur.index(rank)
        label = rank2label[int(rank)]
        dist = abs(x_end - pos[from_slot])
        travel = dist / speed_mm_s
        clock += lift_overhead_s + travel
        active_travel += dist
        # 之前已放到最远端的单元被向内挤一个槽位
        if step > 1:
            letway += abs(pos[-1] - pos[max(0, n - step)])
        cur.pop(from_slot)
        cur.append(rank)
        states.append(cur.copy())
        ops.append(MoveOp(
            step=step, rank=rank, label=label,
            from_slot=from_slot, to_slot=n - 1,
            distance_mm=dist, travel_s=travel,
            total_s=lift_overhead_s + travel,
            order_after=cur.copy(),
        ))
    # 让位行程换算成时间（低速同步平移）
    clock += letway / speed_mm_s
    return ReorderPlan(
        ranks=[int(v) for v in ranks], n=n, kept=k, moves=n - k,
        upper_bound=move_upper_bound(n), ops=ops, states=states, labels=lab,
        slot_positions=pos, active_travel_mm=active_travel, letway_mm=letway,
        reorder_time_s=clock, speed_mm_s=speed_mm_s,
    )


# ---------------------------------------------------------------------------
# 代价研究（给图用）
# ---------------------------------------------------------------------------
def _plan_slots(n: int, thickness_mm: float = 35.0, target_gap_mm: float = 100.0):
    target = thickness_mm * n + target_gap_mm * (n - 1)
    plan = plan_spacing([thickness_mm] * n, max_span=1100.0,
                        target_span=min(target, 1100.0))
    return plan


def _reorder_time_for(ranks: Sequence[int], pos: Sequence[float],
                      speed: float) -> float:
    """给定排列与槽位位置，算 move-to-end 重排总耗时（含抬升开销）。"""
    r = [int(v) for v in ranks]
    n = len(r)
    k = longest_inorder_prefix(r)
    x_end = float(pos[-1])
    t = 0.0
    for step, rank in enumerate(range(k + 1, n + 1), start=1):
        from_slot = r.index(rank)
        t += LIFT_OVERHEAD_S + abs(x_end - pos[from_slot]) / speed
        if step > 1:
            t += abs(x_end - pos[max(0, n - step)]) / speed
        r.pop(from_slot)
        r.append(rank)
    return t


def cost_study(n_values: Sequence[int] = range(3, 9),
               n_random: int = 3000,
               seed: int = 20261123) -> dict:
    """统计不同件数下的移动次数与重排耗时（最坏 / 随机平均）。"""
    rng = np.random.default_rng(seed)
    rows = []
    for n in n_values:
        plan = _plan_slots(n)
        pos = list(plan.centers)
        worst = list(range(n, 0, -1))           # 完全逆序 → k=1 → N-1 次
        t_worst = _reorder_time_for(worst, pos, DESIGN_SPEED_MM_S)
        t_worst_fast = _reorder_time_for(worst, pos, FAST_SPEED_MM_S)
        moves_rand = []
        for _ in range(n_random):
            perm = list(rng.permutation(n) + 1)
            moves_rand.append(n - longest_inorder_prefix(perm))
        moves_rand = np.asarray(moves_rand, dtype=float)
        # 随机排列的平均耗时：按平均移动次数与平均单次行程估算
        t_mean = t_worst * (moves_rand.mean() / (n - 1)) if n > 1 else 0.0
        # 只调间距（不换序）的耗时：假设平均每件移动 200 mm
        spacing_time = n * 200.0 / DESIGN_SPEED_MM_S
        rows.append({
            "n": int(n),
            "span_mm": float(plan.used_span),
            "moves_worst": int(move_upper_bound(n)),
            "moves_mean": float(moves_rand.mean()),
            "moves_min": int(moves_rand.min()),
            "time_worst_s": float(t_worst),
            "time_worst_fast_s": float(t_worst_fast),
            "time_mean_s": float(t_mean),
            "spacing_only_time_s": float(spacing_time),
        })
    return {
        "n_values": [int(n) for n in n_values],
        "rows": rows,
        "speed_mm_s": float(DESIGN_SPEED_MM_S),
        "fast_speed_mm_s": float(FAST_SPEED_MM_S),
        "lift_overhead_s": float(LIFT_OVERHEAD_S),
        "budget_s": float(SECURITY_BUDGET_S),
        "n_random": int(n_random),
    }


# ---------------------------------------------------------------------------
# 演示：4 件衣物，按湿度重排
# ---------------------------------------------------------------------------
def demo_reorder() -> dict:
    """演示用例：4 件衣物、干湿不均，需要 2 次 move-to-end。

    单元（左→右）：A B C D
    湿度：          A 0.55  B 0.90  C 0.35  D 0.75
    进风口在左端 ⇒ 期望顺序按湿度降序：B D A C
    """
    current = ["A", "B", "C", "D"]
    moisture = {"A": 0.55, "B": 0.90, "C": 0.35, "D": 0.75}
    thickness = {"A": 25.0, "B": 40.0, "C": 30.0, "D": 55.0}
    desired = sorted(current, key=lambda k: -moisture[k])
    ranks = ranks_from_orders(current, desired)

    # 目标槽位：按厚度/湿度规划出的位置（居中于 1100 mm 可用杆段）
    plan = plan_spacing([thickness[k] for k in current], max_span=1100.0,
                        target_span=480.0, moisture=[moisture[k] for k in current])
    rp = greedy_move_to_end(ranks, labels=current,
                            slot_positions=list(plan.centers))

    # 仅调间距（不换序）的耗时：从"挤在一起"的初始位置移到目标位置
    squeezed = np.array([300.0, 380.0, 460.0, 550.0])  # 演示：初始挤在 25 cm 内
    spacing_move_mm = float(np.abs(np.asarray(plan.centers) - squeezed).sum())
    spacing_time = spacing_move_mm / DESIGN_SPEED_MM_S

    return {
        "current_order": current,
        "desired_order": desired,
        "moisture": moisture,
        "thickness": thickness,
        "ranks": ranks,
        "plan": plan,
        "reorder": rp,
        "spacing_move_mm": spacing_move_mm,
        "spacing_time_s": float(spacing_time),
        "labels": current,
    }


__all__ = [
    "MoveOp",
    "ReorderPlan",
    "ranks_from_orders",
    "longest_inorder_prefix",
    "move_upper_bound",
    "reachable_permutations_without_passing",
    "greedy_move_to_end",
    "cost_study",
    "demo_reorder",
    "DESIGN_SPEED_MM_S",
    "FAST_SPEED_MM_S",
    "LIFT_OVERHEAD_S",
    "SECURITY_BUDGET_S",
]
