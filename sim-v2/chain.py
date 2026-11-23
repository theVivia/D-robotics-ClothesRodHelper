"""衣序 HangFlow v2（rev-B）—— 链几何、双端夹持状态与调节顺序。

结构
----
    墙 ─ 调节器0 ─ 衣物1 ─ 调节器1 ─ 衣物2 ─ … ─ 衣物K ─ 调节器K ─ 墙

* K+1 个调节器、K 件衣物；内部 K−1 段 = 净风道，端部 2 段 = 端部余量。
* 每端是**锥面收口夹头**：开槽夹头环 + 外套筒，套筒向内滑 5–8 mm 径向压紧杆
  （不是爪子/凸轮）。算法里状态只有 lock / free：
    - 锁一端：另一端自由伸缩，只推动/拉动相邻的那一件衣服，**反作用进杆**；
    - 锁两端：长度锁死 = 绝对位置，不依赖链条张力。
* 端部两个调节器顶墙/挡块预紧 → 不需要恒力卷簧。

调节顺序（这就是"先锁哪端、再伸缩哪端"的答案）
--------------------------------------------
日常模式（只动内部段）按"锚定端 → 自由端"推进：
    1) 以已贴墙的那一端为基准（默认左墙，端部调节器顶紧左墙）；
    2) 从基准端向另一端逐段处理：**先锁靠基准侧的那一端**，再伸缩自由端；
    3) 伸缩完成后把另一端也锁上（锁两端 = 绝对长度，之后不受链条张力影响）；
    4) 最后一段（另一端端部调节器）伸出顶住对面墙，恢复预紧。

这样每一步的反作用都通过已锁的夹持进杆，**已定位的左段不会动、预紧不会被推散**；
代价是右侧未定位的衣架会作为一个块一起滑动（不可避免：间距变化必须移动一侧）。

对比"不锁端、整条链一起推"：力更小、已定位段 0 滑移、不需要重新标定；
代价是每段多两次夹持动作（约 0.4 s/次）。

参数（设计估算）
----------------
f_hanger = 3 N/件（衣架在杆上滑动），f_unit = 2 N（伸缩副自身阻力），
夹持动作 0.4 s，段间稳定 0.3 s，预紧力 10 N。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

from length_planner import (DEFAULT_ROD_MM, WALL_MARGIN_MM, T_H_MM,
                            LengthPlan, plan_lengths)

F_HANGER_N = 3.0
F_UNIT_N = 2.0
CLAMP_TIME_S = 0.4
SETTLE_TIME_S = 0.3
PRELOAD_FORCE_N = 10.0
PRELOAD_MM_EXTRA = 0.5      # 顶墙过盈量（mm）
OVERHEAD_S = 0.2


@dataclass
class Drive:
    """丝杆 + 电机驱动参数。

    导程按 **T8 / 8 mm**；实际轴向速度用 v_cap 校核（设计值 4 mm/s，
    力矩与电流仍按负载线性下降估算）。
    """

    name: str
    lead_mm: float = 8.0
    rpm: float = 100.0
    efficiency: float = 0.35
    stall_torque: float = 0.15
    kt: float = 0.125
    no_load_current: float = 0.08
    v_cap_mm_s: Optional[float] = None   # 轴向速度校核上限（None = 不限）

    @property
    def v_free_mm_s(self) -> float:
        return self.lead_mm * self.rpm / 60.0

    @property
    def f_stall_n(self) -> float:
        return 2.0 * np.pi * self.stall_torque * self.efficiency / (self.lead_mm / 1000.0)

    def speed_mm_s(self, force_n: float) -> float:
        if force_n >= self.f_stall_n:
            return 0.0
        v = self.v_free_mm_s * (1.0 - force_n / self.f_stall_n)
        if self.v_cap_mm_s is not None:
            v = min(v, self.v_cap_mm_s)
        return v

    def current_a(self, force_n: float) -> float:
        torque = force_n * (self.lead_mm / 1000.0) / (2.0 * np.pi * self.efficiency)
        return self.no_load_current + torque / self.kt


DRIVES = [
    Drive("T8/8 @4 mm/s（校核）", lead_mm=8.0, rpm=100.0, v_cap_mm_s=4.0),
    Drive("T8/8 @7 mm/s（提速）", lead_mm=8.0, rpm=100.0, v_cap_mm_s=7.0),
    Drive("T8/8 不限速（理论上限）", lead_mm=8.0, rpm=100.0, v_cap_mm_s=None),
]


# ---------------------------------------------------------------------------
@dataclass
class ClampState:
    left: bool = False
    right: bool = False

    def to_dict(self) -> dict:
        return {"left": bool(self.left), "right": bool(self.right)}

    def __str__(self) -> str:
        return ("L" if self.left else "-") + ("R" if self.right else "-")


@dataclass
class ChainLayout:
    """一条链的几何（mm，x 从墙/杆左端算起）。"""

    inner: np.ndarray
    ends: tuple
    regulator_edges: np.ndarray     # (K+1, 2)
    garment_centers: np.ndarray     # (K,)
    chain_end_mm: float
    right_gap_mm: float             # 链末端到右墙的距离
    wall_contact: bool
    available_mm: float
    t_h: float = T_H_MM

    @property
    def regulator_count(self) -> int:
        return int(self.regulator_edges.shape[0])

    def to_dict(self) -> dict:
        return {
            "inner_mm": [round(float(v), 2) for v in self.inner],
            "ends_mm": [round(float(v), 2) for v in self.ends],
            "regulator_edges_mm": [[round(float(a), 2), round(float(b), 2)]
                                   for a, b in self.regulator_edges],
            "garment_centers_mm": [round(float(v), 2) for v in self.garment_centers],
            "chain_end_mm": round(float(self.chain_end_mm), 2),
            "right_gap_mm": round(float(self.right_gap_mm), 2),
            "wall_contact": bool(self.wall_contact),
        }


def chain_layout(plan: LengthPlan) -> ChainLayout:
    """由规划结果算每个调节器与每件衣物的位置。"""
    ends = (float(plan.ends[0]), float(plan.ends[1]))
    inner = np.asarray(plan.inner, dtype=float)
    K = plan.K
    lengths = np.concatenate([[ends[0]], inner, [ends[1]]])
    edges = np.zeros((K + 1, 2))
    centers = np.zeros(K)
    cursor = 0.0
    for i, L in enumerate(lengths):
        edges[i] = (cursor, cursor + L)
        cursor += L
        if i < K:
            centers[i] = cursor + T_H_MM / 2.0
            cursor += T_H_MM
    chain_end = float(cursor)
    return ChainLayout(
        inner=inner, ends=ends, regulator_edges=edges, garment_centers=centers,
        chain_end_mm=chain_end,
        right_gap_mm=float(plan.available_mm - chain_end),
        wall_contact=bool(abs(chain_end - plan.available_mm) < 1e-6),
        available_mm=float(plan.available_mm), t_h=T_H_MM)


# ---------------------------------------------------------------------------
@dataclass
class AdjustStep:
    unit: int                   # 第几个调节器（0 = 最左端）
    role: str                   # end_left / inner / end_right
    action: str                 # clamp_left / move_right / clamp_right / preload
    clamp_before: ClampState
    clamp_after: ClampState
    length_before: float
    length_after: float
    travel_mm: float
    force_n: float
    current_a: float
    speed_mm_s: float
    time_s: float
    garment_moved: Optional[int] = None   # 被推/拉的衣架（1 基），None = 顶墙
    block_garments: int = 0               # 一起滑动的衣架数

    def to_dict(self) -> dict:
        return {
            "unit": int(self.unit), "role": self.role, "action": self.action,
            "clamp_before": self.clamp_before.to_dict(),
            "clamp_after": self.clamp_after.to_dict(),
            "length_before_mm": round(float(self.length_before), 2),
            "length_after_mm": round(float(self.length_after), 2),
            "travel_mm": round(float(self.travel_mm), 2),
            "force_n": round(float(self.force_n), 2),
            "current_a": round(float(self.current_a), 3),
            "speed_mm_s": round(float(self.speed_mm_s), 2),
            "time_s": round(float(self.time_s), 2),
            "garment_moved": self.garment_moved,
            "block_garments": int(self.block_garments),
        }


@dataclass
class AdjustPlan:
    steps: List[AdjustStep]
    strategy: str
    drive_name: str
    total_time_s: float
    peak_force_n: float
    peak_current_a: float
    max_block_garments: int
    requires_redatum: bool
    untouched_drift_mm: float
    final_lengths: np.ndarray
    clamp_actions: int

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy, "drive": self.drive_name,
            "steps": [s.to_dict() for s in self.steps],
            "total_time_s": round(float(self.total_time_s), 2),
            "peak_force_n": round(float(self.peak_force_n), 2),
            "peak_current_a": round(float(self.peak_current_a), 3),
            "max_block_garments": int(self.max_block_garments),
            "requires_redatum": bool(self.requires_redatum),
            "untouched_drift_mm": round(float(self.untouched_drift_mm), 2),
            "clamp_actions": int(self.clamp_actions),
        }


# ---------------------------------------------------------------------------
def _roles(K: int) -> List[str]:
    return ["end_left"] + ["inner"] * (K - 1) + ["end_right"]


def _unit_move_force(unit: int, K: int, pulling: bool,
                     f_hanger: float = F_HANGER_N,
                     f_unit: float = F_UNIT_N) -> float:
    """移动第 unit 个调节器的自由端需要克服的力（N）。

    自由端在右侧 → 一起滑动的衣架数 = K − unit（右侧块）；
    自由端在左侧（右锚定）→ 一起滑动的衣架数 = unit（左侧块）。
    """
    block = (K - unit) if not pulling else unit
    return f_unit + f_hanger * max(0, block)


def simulate_sequence(start: LengthPlan, end: LengthPlan, drive: Drive,
                      strategy: str = "anchor_left",
                      f_hanger: float = F_HANGER_N,
                      f_unit: float = F_UNIT_N,
                      clamp_time: float = CLAMP_TIME_S,
                      settle_time: float = SETTLE_TIME_S,
                      overhead: float = OVERHEAD_S,
                      skip_unchanged: bool = True) -> AdjustPlan:
    """按"锚定端 → 自由端"逐段生成并计时一次完整的长度调节。

    strategy:
      "anchor_left"  —— 以左墙为基准，从左往右，锁左端、动右端（推荐）
      "anchor_right" —— 以右墙为基准，从右往左，锁右端、动左端
      "no_clamp"     —— 反例：不锁端，整条链一起推（对照）
    """
    a = np.concatenate([[start.ends[0]], start.inner, [start.ends[1]]])
    b = np.concatenate([[end.ends[0]], end.inner, [end.ends[1]]])
    if a.size != b.size:
        raise ValueError("起止长度数量不一致")
    K = a.size - 1
    roles = _roles(K)
    a0 = a.copy()   # 原始长度（用于判断端部是否动作）
    steps: List[AdjustStep] = []
    clamp_actions = 0
    clock = 0.0

    if strategy == "no_clamp":
        # 反例：所有段同时动，整链被推，已定位段会滑移
        for i in range(a.size):
            delta = float(b[i] - a[i])
            if abs(delta) < 1e-9:
                continue
            force = f_unit + f_hanger * K
            speed = drive.speed_mm_s(force)
            t = overhead + (abs(delta) / speed if speed > 0 else float("inf"))
            steps.append(AdjustStep(
                unit=i, role=roles[i], action="push_block",
                clamp_before=ClampState(False, False),
                clamp_after=ClampState(False, False),
                length_before=float(a[i]), length_after=float(b[i]),
                travel_mm=abs(delta), force_n=float(force),
                current_a=float(drive.current_a(force)),
                speed_mm_s=float(speed), time_s=float(t),
                garment_moved=(i + 1 if i < K else None),
                block_garments=K))
        # 整链同时动作，时间取最长一段
        total_time = max([s.time_s for s in steps], default=0.0)
        return AdjustPlan(
            steps=steps, strategy=strategy, drive_name=drive.name,
            total_time_s=float(total_time),
            peak_force_n=max([s.force_n for s in steps], default=0.0),
            peak_current_a=sum(s.current_a for s in steps),
            max_block_garments=K, requires_redatum=True,
            untouched_drift_mm=float("nan"),
            final_lengths=b.copy(), clamp_actions=0)

    order = (list(range(a.size)) if strategy == "anchor_left"
             else list(range(a.size - 1, -1, -1)))
    if strategy not in ("anchor_left", "anchor_right"):
        raise ValueError("strategy 必须是 anchor_left / anchor_right / no_clamp")

    for i in order:
        delta = float(b[i] - a[i])
        role = roles[i]
        moved = (i + 1) if (strategy == "anchor_left" and i < K) else (
            i if strategy == "anchor_right" else None)
        if skip_unchanged and abs(delta) < 1e-9:
            continue

        clamp_side_left = (strategy == "anchor_left")
        cb = ClampState(clamp_side_left, not clamp_side_left)
        clock += overhead

        # 1) 锁靠基准侧的一端
        steps.append(AdjustStep(
            unit=i, role=role, action="clamp_left" if clamp_side_left else "clamp_right",
            clamp_before=ClampState(), clamp_after=cb,
            length_before=float(a[i]), length_after=float(a[i]),
            travel_mm=0.0, force_n=0.0, current_a=float(drive.current_a(0.0)),
            speed_mm_s=0.0, time_s=clamp_time))
        clock += clamp_time
        clamp_actions += 1

        # 2) 伸缩自由端
        is_last_wall = (role == "end_right" and strategy == "anchor_left")
        preload = is_last_wall and abs(delta) < 1e-9
        if preload:
            force = PRELOAD_FORCE_N
            travel = 0.0
            garment = None
            block = 0
            action = "preload"
        elif abs(delta) >= 1e-9:
            force = _unit_move_force(i, K, pulling=(strategy == "anchor_right"),
                                     f_hanger=f_hanger, f_unit=f_unit)
            travel = abs(delta)
            garment = moved
            block = (K - i) if strategy == "anchor_left" else i
            action = "move_right" if strategy == "anchor_left" else "move_left"
        else:
            force = 0.0
            travel = 0.0
            garment = None
            block = 0
            action = "hold"
        speed = drive.speed_mm_s(force) if force > 0 else 0.0
        t_move = (travel / speed if speed > 0 else 0.0) + (
            SETTLE_TIME_S if travel > 0 or preload else 0.0)
        clock += t_move
        steps.append(AdjustStep(
            unit=i, role=role, action=action,
            clamp_before=cb, clamp_after=ClampState(True, True),
            length_before=float(a[i]), length_after=float(b[i]),
            travel_mm=float(travel), force_n=float(force),
            current_a=float(drive.current_a(force)),
            speed_mm_s=float(speed), time_s=float(t_move),
            garment_moved=garment, block_garments=int(block)))

        # 3) 锁另一端（绝对位置锁死）
        steps.append(AdjustStep(
            unit=i, role=role, action="clamp_right" if clamp_side_left else "clamp_left",
            clamp_before=cb, clamp_after=ClampState(True, True),
            length_before=float(b[i]), length_after=float(b[i]),
            travel_mm=0.0, force_n=float(force), current_a=float(drive.current_a(force)),
            speed_mm_s=0.0, time_s=clamp_time))
        clock += clamp_time
        clamp_actions += 1
        a[i] = b[i]

    # 端部有动作、且目标贴墙 → 补一个"顶墙预紧"动作（最后 0.5 mm 压紧）
    ends_changed = any(abs(b[j] - a0[j]) > 1e-9 for j in (0, a.size - 1))
    if ends_changed and end.wall_contact:
        steps.append(AdjustStep(
            unit=int(a.size - 1), role=roles[-1], action="preload",
            clamp_before=ClampState(True, True), clamp_after=ClampState(True, True),
            length_before=float(b[-1]), length_after=float(b[-1] + PRELOAD_MM_EXTRA),
            travel_mm=float(PRELOAD_MM_EXTRA), force_n=float(PRELOAD_FORCE_N),
            current_a=float(drive.current_a(PRELOAD_FORCE_N)),
            speed_mm_s=float(drive.speed_mm_s(PRELOAD_FORCE_N)),
            time_s=0.5, garment_moved=None, block_garments=0))
        clock += 0.5

    forces = [s.force_n for s in steps]
    currents = [s.current_a for s in steps]
    return AdjustPlan(
        steps=steps, strategy=strategy, drive_name=drive.name,
        total_time_s=float(clock), peak_force_n=float(max(forces, default=0.0)),
        peak_current_a=float(max(currents, default=0.0)),
        max_block_garments=int(max([s.block_garments for s in steps], default=0)),
        requires_redatum=False, untouched_drift_mm=0.0,
        final_lengths=b.copy(), clamp_actions=int(clamp_actions))


def compare_strategies(start: LengthPlan, end: LengthPlan,
                       drive: Optional[Drive] = None) -> Dict[str, dict]:
    """对比锚定左墙 / 锚定右墙 / 不锁端（反例）。"""
    d = drive or DRIVES[0]
    out = {}
    for name, label in (("anchor_left", "锚定左墙（推荐）"),
                        ("anchor_right", "锚定右墙"),
                        ("no_clamp", "不锁端（整链推）")):
        p = simulate_sequence(start, end, d, strategy=name)
        out[label] = p.to_dict()
    return out


def daily_cycle_study(rod_length: float = DEFAULT_ROD_MM,
                      garment_counts: Sequence[int] = (3, 4, 5, 6, 8),
                      drives: Optional[Sequence[Drive]] = None,
                      budget_s: float = 30.0) -> dict:
    """日常工况：收衣 → 一键等距（只动内部段，端部保持安装值）。"""
    drives = list(drives or DRIVES)
    rows = []
    for K in garment_counts:
        start = plan_lengths(K, rod_length=rod_length, mode="collect")
        end = plan_lengths(K, rod_length=rod_length, mode="equal")
        row = {"K": int(K), "regulators": int(K + 1),
               "travel_mm": float(np.abs(end.inner - start.inner).sum()),
               "start_chain_mm": float(start.chain_length_mm),
               "end_chain_mm": float(end.chain_length_mm)}
        for d in drives:
            p = simulate_sequence(start, end, d, strategy="anchor_left")
            row[d.name] = {
                "time_s": float(p.total_time_s),
                "peak_force_n": float(p.peak_force_n),
                "peak_current_a": float(p.peak_current_a),
                "within_budget": bool(p.total_time_s <= budget_s),
            }
        rows.append(row)
    return {"rows": rows, "drives": [d.name for d in drives],
            "budget_s": float(budget_s)}


def setup_study(rod_length: float = DEFAULT_ROD_MM,
                garment_count: int = 4,
                drive: Optional[Drive] = None) -> dict:
    """安装/首次标定：端部与内部都从最短伸到工作值（一次性）。"""
    d = drive or DRIVES[0]
    K = garment_count
    start = plan_lengths(K, rod_length=rod_length, mode="collect")
    # 从"全部最短"起步：内部 40、端部 30
    from copy import copy
    start_all_min = copy(start)
    start_all_min.ends = (30.0, 30.0)
    start_all_min.inner = np.full(K - 1, 40.0)
    start_all_min.chain_length_mm = 30.0 * 2 + 40.0 * (K - 1) + K * T_H_MM
    end = plan_lengths(K, rod_length=rod_length, mode="equal")
    p = simulate_sequence(start_all_min, end, d, strategy="anchor_left",
                          skip_unchanged=False)
    return {
        "K": K,
        "start_lengths_mm": [round(float(v), 1) for v in
                             np.concatenate([[30.0], np.full(K - 1, 40.0), [30.0]])],
        "end_lengths_mm": [round(float(v), 1) for v in end.all_lengths],
        "total_travel_mm": float(np.abs(end.all_lengths - np.concatenate(
            [[30.0], np.full(K - 1, 40.0), [30.0]])).sum()),
        "time_s": float(p.total_time_s),
        "peak_force_n": float(p.peak_force_n),
        "peak_current_a": float(p.peak_current_a),
        "clamp_actions": int(p.clamp_actions),
    }


def demo_chain(garment_count: int = 4) -> dict:
    """演示：4 件衣物、5 个调节器；收衣（400 mm 内）→ 等距（1100 mm）。"""
    K = garment_count
    start = plan_lengths(K, mode="collect")
    end = plan_lengths(K, mode="equal")
    drive = DRIVES[0]
    return {
        "K": K,
        "start_plan": start,
        "end_plan": end,
        "layout": chain_layout(end),
        "layout_start": chain_layout(start),
        "comparison": compare_strategies(start, end, drive),
        "drive": drive,
    }


__all__ = [
    "Drive", "DRIVES", "ClampState", "ChainLayout", "chain_layout",
    "AdjustStep", "AdjustPlan", "simulate_sequence", "compare_strategies",
    "daily_cycle_study", "setup_study", "demo_chain",
    "F_HANGER_N", "F_UNIT_N", "CLAMP_TIME_S", "SETTLE_TIME_S",
    "PRELOAD_FORCE_N", "OVERHEAD_S",
]
