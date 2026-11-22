"""衣序 HangFlow · 中枢规划层（把 sim 里的算法接到真实坐标系）。

sim/ 里的规划器以"可用杆段左端"为原点；实际上层以"杆左端挡块"为原点，
两者相差一个端部留白 END_CLEARANCE_MM。本模块负责这层转换，并给出
四种模式的统一入口，供 web/MQTT/测试复用。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 允许从仓库根目录 `python -m software.hub.mock_demo` 运行
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.spacing_planner import (  # noqa: E402
    END_CLEARANCE_MM,
    MIN_GAP_MM,
    plan_spacing,
)

ROD_LENGTH_MM = 1200.0
END_CLEARANCE = END_CLEARANCE_MM  # 50mm


def plan_layout(
    thickness_mm,
    moisture=None,
    mode: str = "equalize",
    rod_length_mm: float = ROD_LENGTH_MM,
    target_gap_mm: float = 100.0,
):
    """返回杆坐标（0=左端挡块）下的目标中心位置与间隙。

    mode:
      - "equalize" : 所有间隙相等（取 target_gap_mm）
      - "smart"    : 按湿度加权分配
      - "gather"   : 全部靠右端，间隙 60mm（收衣）
    """
    n = len(thickness_mm)
    usable = rod_length_mm - 2 * END_CLEARANCE
    if mode == "gather":
        # 收衣：从右往左排，间隙 60mm
        gap = 60.0
        total = sum(thickness_mm) + gap * (n - 1)
        left = usable - total
        centers_rel = []
        x = left
        for t in thickness_mm:
            centers_rel.append(x + t / 2)
            x += t + gap
        target_span = total
    else:
        wet = [1.0] * n if mode == "equalize" or moisture is None else list(moisture)
        target_span = min(
            usable,
            sum(thickness_mm) + target_gap_mm * (n - 1),
        )
        plan = plan_spacing(
            thickness_mm,
            max_span=usable,
            target_span=target_span,
            moisture=wet,
        )
        centers_rel = list(map(float, plan.centers))
        target_span = float(plan.used_span)

    # 平移到杆坐标（左端挡块 = 0），并让整体在可用段内居中
    block_left = centers_rel[0] - thickness_mm[0] / 2
    offset = END_CLEARANCE + (usable - target_span) / 2 - block_left
    centers = [round(c + offset, 1) for c in centers_rel]
    gaps = [round(centers[i + 1] - centers[i] - (thickness_mm[i] + thickness_mm[i + 1]) / 2, 1)
            for i in range(n - 1)]
    return {"centers_mm": centers, "gaps_mm": gaps, "target_span_mm": round(target_span, 1)}
