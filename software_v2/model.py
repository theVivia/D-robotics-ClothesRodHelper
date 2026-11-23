"""衣序 v2 链模型（与 app-v2 的端点锚定模型一致）。

约定：
- K 件衣服 → K+1 个调节器，K 个 10mm 接缝。
- 端部 0 / K：外端锚定（坐标 0 / D 固定），内端自由伸缩（30—220mm）。
- 内部段：两端夹头可锁/松；两端都锁 = 长度固定。
- 链总长 D = ΣL + K*10，外端锚点不动；自动模式通过端部内端吸收总长变化。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

T_H = 10.0          # 衣架/接缝沿杆厚度 mm
L_INT_MIN = 100.0   # P0 动力段下限；4—10cm 用被动短套
L_INT_MAX = 220.0
L_END_MIN = 30.0
L_END_MAX = 120.0   # 端部锚定挂包 POD 120，行程 90
K_MIN, K_MAX = 2, 8


class ChainError(ValueError):
    pass


@dataclass
class Unit:
    uid: str
    length: float
    clamp_l: bool = False
    clamp_r: bool = False
    end: bool = False

    def __post_init__(self) -> None:
        lo = L_END_MIN if self.end else L_INT_MIN
        hi = L_END_MAX if self.end else L_INT_MAX
        if not (lo - 1e-9 <= self.length <= hi + 1e-9):
            raise ChainError(f"{self.uid}: length {self.length} out of [{lo},{hi}]")


@dataclass
class Chain:
    units: List[Unit]
    d_mm: Optional[float] = None
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.units) < 3:
            raise ChainError("at least one internal unit required")
        self.k = len(self.units) - 1
        if not self.units[0].end or not self.units[-1].end:
            raise ChainError("first/last unit must be end units")
        # 端部只锁外端
        self.units[0].clamp_l = True
        self.units[-1].clamp_r = True
        if self.d_mm is None:
            self.d_mm = self.total

    @property
    def total(self) -> float:
        return sum(u.length for u in self.units) + self.k * T_H

    def outer_positions(self) -> tuple[float, float]:
        return 0.0, float(self.d_mm)

    def check(self) -> None:
        if abs(self.total - self.d_mm) > 0.01:
            raise ChainError(
                f"chain total {self.total:.2f} != fixed span {self.d_mm:.2f}"
            )

    def clone(self) -> "Chain":
        return Chain([Unit(u.uid, u.length, u.clamp_l, u.clamp_r, u.end) for u in self.units], self.d_mm)

    def __str__(self) -> str:
        return "[" + ", ".join(f"{u.length:g}" for u in self.units) + f"] total={self.total:g}"

    # ---------- 自动模式 ----------
    def set_lengths(self, new_lengths: List[float]) -> None:
        if len(new_lengths) != len(self.units):
            raise ChainError("bad length count")
        old_total = self.total
        old_ends = self.units[0].length + self.units[-1].length
        for u, L in zip(self.units, new_lengths):
            lo = L_END_MIN if u.end else L_INT_MIN
            hi = L_END_MAX if u.end else L_INT_MAX
            if not (lo - 1e-9 <= L <= hi + 1e-9):
                raise ChainError(f"{u.uid}: {L} out of range")
            u.length = float(L)
        # 只允许总长不变（外端锚定）
        if abs(self.total - old_total) > 0.01:
            raise ChainError(
                f"outer anchors fixed: total must stay {old_total:.1f}, got {self.total:.1f}"
            )
        _ = old_ends

    def adjust_ends_to_total(self, target_total: Optional[float] = None) -> None:
        """把端部内端调到让总长等于 target_total（默认 D）。"""
        target = self.d_mm if target_total is None else target_total
        diff = target - self.total
        ends = [self.units[0], self.units[-1]]
        # 先均分，再按剩余补齐
        for _ in range(4):
            if abs(diff) < 0.01:
                break
            share = diff / 2.0
            moved = 0.0
            for u in ends:
                before = u.length
                u.length = min(L_END_MAX, max(L_END_MIN, u.length + share))
                moved += u.length - before
            diff -= moved
        if abs(self.total - target) > 0.01:
            raise ChainError(
                f"end stroke insufficient: need total {target:.1f}, can reach {self.total:.1f}"
            )

    def equalize(self, target_mm: float) -> "Chain":
        """内部段全部设目标；端部吸收总长变化，保持外端锚定。"""
        target = float(target_mm)
        if not (L_INT_MIN - 1e-9 <= target <= L_INT_MAX + 1e-9):
            raise ChainError(
                f"equalize target {target} outside powered range "
                f"[{L_INT_MIN},{L_INT_MAX}]"
            )
        c = self.clone()
        for u in c.units[1:-1]:
            u.length = target
        c.adjust_ends_to_total()
        return c

    def weighted(self, targets: List[float]) -> "Chain":
        c = self.clone()
        if len(targets) != c.k - 1:
            raise ChainError("need K-1 internal targets")
        for u, L in zip(c.units[1:-1], targets):
            u.length = min(L_INT_MAX, max(L_INT_MIN, L))
        c.adjust_ends_to_total()
        return c

    def collect(self, target_mm: float = 100.0) -> "Chain":
        c = self.clone()
        for u in c.units[1:-1]:
            u.length = max(L_INT_MIN, min(L_INT_MAX, target_mm))
        c.adjust_ends_to_total()
        return c


def demo_chain() -> Chain:
    """4 件衣服：端部 60 + 内部 100×3 + 端部 60，总长 460。"""
    units = [
        Unit("01", 60, clamp_l=True, clamp_r=False, end=True),
        Unit("02", 100, clamp_l=True, clamp_r=False),
        Unit("03", 100, clamp_l=False, clamp_r=True),
        Unit("04", 100, clamp_l=True, clamp_r=False),
        Unit("05", 60, clamp_l=False, clamp_r=True, end=True),
    ]
    return Chain(units)



