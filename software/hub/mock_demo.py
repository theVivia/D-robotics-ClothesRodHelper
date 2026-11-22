"""衣序 HangFlow · 无硬件演示（mock）。

跑法（仓库根目录）：
    python -m software.hub.mock_demo
    python -m software.hub.mock_demo --mode smart

它会：
  1) 起 4 个"虚拟单元"（一阶速度响应 + 编码器噪声 + 2% 打滑）；
  2) 用 planner 算目标位置；
  3) 串行下发目标（与真实控制器同策略）；
  4) 打印时间线、每个单元到位误差、总耗时，并把日志写到 logs/mock-run-*.jsonl。

用途：赛前调 UI/规划/异常流程；现场演示的"软备份"。
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from software.hub.planner import plan_layout

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "logs"


@dataclass
class FakeUnit:
    uid: str
    x_mm: float
    speed_mm_s: float = 45.0
    batt_mv: int = 3950
    x_enc: float = 0.0
    log: list = field(default_factory=list)

    def __post_init__(self):
        self.x_enc = self.x_mm

    def move_to(self, target_mm: float, slip: float = 0.02, noise: float = 0.5,
                dt: float = 0.02) -> float:
        """一阶速度逼近 + 编码器噪声；返回耗时（秒）。"""
        t = 0.0
        v = 0.0
        while abs(target_mm - self.x_enc) > 2.0 and t < 12.0:
            err = target_mm - self.x_enc
            v = min(self.speed_mm_s, max(-self.speed_mm_s, err * 3.0))
            step = v * dt
            self.x_mm += step * (1.0 + random.gauss(0, slip))
            self.x_enc += step + random.gauss(0, noise) * 0.02
            t += dt
        # 单向逼近：最终把编码器位置拉到目标（真实系统靠视觉校正）
        self.x_enc += (target_mm - self.x_enc) * 0.9
        # 视觉校正后残余误差：±2mm 量级
        self.x_mm = self.x_enc + random.gauss(0, 1.2)
        return round(t, 2)

    @property
    def error_mm(self) -> float:
        return round(self.x_mm - self.x_enc, 2)


def run(mode: str = "equalize", n: int = 4, gap_mm: float = 100.0, seed: int = 7):
    random.seed(seed)
    thickness = [30.0, 45.0, 30.0, 50.0][:n]
    moisture = [0.78, 0.84, 0.22, 0.46][:n]
    # 初始：挤在左侧 0.35m 内
    start = [120 + i * 55.0 for i in range(n)]
    units = [FakeUnit(f"0{i+1}", start[i]) for i in range(n)]

    plan = plan_layout(thickness, moisture, mode=mode, target_gap_mm=gap_mm)
    print(f"模式: {mode} | 初始位置: {[round(u.x_mm) for u in units]}")
    print(f"目标位置: {plan['centers_mm']} | 目标间隙: {plan['gaps_mm']} mm")
    print("-" * 68)

    t0 = time.perf_counter()
    sim_total = 0.0
    records = []
    for u, target in zip(units, plan["centers_mm"]):
        # 串行：与真实控制器一致（避免互相干扰）
        print(f"  {u.uid}  {u.x_mm:6.1f} → {target:6.1f} mm ...", end="", flush=True)
        dt = u.move_to(target)
        sim_total += dt
        print(f" 完成 {dt:4.1f}s  误差 {u.error_mm:+.1f}mm")
        records.append({"t": round(time.perf_counter() - t0, 3), "uid": u.uid,
                        "x_mm": round(u.x_mm, 1), "target_mm": target, "seconds": dt})
    total = sim_total

    # 校验
    gaps = [round(units[i + 1].x_mm - units[i].x_mm
                  - (thickness[i] + thickness[i + 1]) / 2, 1) for i in range(n - 1)]
    print("-" * 68)
    print(f"最终位置: {[round(u.x_mm, 1) for u in units]}")
    print(f"最终间隙(净空): {gaps} mm | 最小 {min(gaps)} mm（要求 ≥ 30）")
    print(f"总耗时: {total:.2f}s（要求 ≤ 45s，典型 ≤35s）")

    LOG_DIR.mkdir(exist_ok=True)
    logfile = LOG_DIR / f"mock-run-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    with logfile.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "plan", "mode": mode, "plan": plan},
                           ensure_ascii=False) + "\n")
        for r in records:
            f.write(json.dumps({"type": "move", **r}, ensure_ascii=False) + "\n")
    print(f"日志: {logfile.relative_to(ROOT)}")

    ok = (min(gaps) >= 30) and (total <= 45)
    print("结果:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="equalize", choices=["equalize", "smart", "gather"])
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--gap", type=float, default=100.0)
    a = ap.parse_args()
    raise SystemExit(run(a.mode, a.n, a.gap))

