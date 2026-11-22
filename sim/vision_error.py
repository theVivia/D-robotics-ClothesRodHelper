"""视觉定位误差估算（针孔模型）。

设定（与 docs/_shared-context.md 第 6 节一致）
-------------------------------------------
* 相机 1280×720 USB 单目，等效焦距 f = 900 px ≈ 71° 水平视场。
* 每个套挂单元顶部贴 30 mm ArUco 标记，用于视觉校核沿杆位置。
* 像素坐标噪声 σ_px = 0.5 px（角点检测，亚像素级，设计假设）。
* 相机装在杆侧方、光轴大致垂直于杆（"侧装"）：
  杆的走向主要落在图像 x 方向，沿杆误差 ≈ σ_px·Z/f。
  若相机绕竖直轴偏航 θ 看杆（部分沿杆看），沿杆方向带出深度分量：
       ε_along(θ) = sqrt( (ε_lat·cosθ)² + (ε_range·sinθ)² )
  其中 ε_range = σ_px·Z²/(f·s) 是标记距离误差——**30 mm 标记在 1.5 m 处只有 18 px，
  距离几乎测不准**（这正是"不能靠标记测距、要靠图像 x 定位"的原因）。
* 系统误差（设计估算，非实测）：标定残差 1.5 mm、标记安装偏差 2.0 mm。
  这两项不随距离变化，也不随帧平均下降 ⇒ 精度预算的主要项。
* 多帧平均：随机项按 1/√k 下降（k=5 帧 @30fps → 167 ms 延迟）。

结论口径
--------
随机项在 1.2 m 处只有 0.67 mm，远小于 ±5 mm 目标；
真正吃掉预算的是"偏航 × 距离误差"和系统误差 ⇒
相机要侧装（|θ| ≤ 5–10°）、杆上要有已知间距的 ArUco 基准做在线校准。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

CAM_W, CAM_H = 1280, 720
F_PX = 900.0
HFOV_DEG = float(2.0 * np.degrees(np.arctan((CAM_W / 2.0) / F_PX)))
MARKER_MM = 30.0
SIGMA_PX = 0.5
SYSTEMATIC_MM = {"标定残差": 1.5, "标记安装偏差": 2.0}
FRAME_AVG = 5
SPEC_MM = 5.0
ROD_LENGTH_MM = 1200.0
END_CLEARANCE_MM = 50.0


def marker_pixels(distance_mm: float, f_px: float = F_PX,
                  size_mm: float = MARKER_MM) -> float:
    """标记在图像上的边长（px）。"""
    return f_px * size_mm / float(distance_mm)


def mm_per_px(distance_mm: float, f_px: float = F_PX) -> float:
    """该距离下 1 px 对应的物理长度（mm/px）。"""
    return float(distance_mm) / f_px


def lateral_error_mm(distance_mm: float, sigma_px: float = SIGMA_PX,
                     f_px: float = F_PX) -> float:
    """侧向（≈ 沿杆方向）随机误差：σ_px · Z / f。"""
    return sigma_px * float(distance_mm) / f_px


def range_error_mm(distance_mm: float, sigma_px: float = SIGMA_PX,
                   f_px: float = F_PX, size_mm: float = MARKER_MM) -> float:
    """由标记像素尺寸推距离的误差：σ_px · Z² / (f · s)。"""
    z = float(distance_mm)
    return sigma_px * z * z / (f_px * size_mm)


def along_rod_error_mm(distance_mm: float, yaw_deg: float = 0.0,
                       sigma_px: float = SIGMA_PX, f_px: float = F_PX,
                       size_mm: float = MARKER_MM,
                       frames: int = 1) -> float:
    """沿杆方向定位随机误差（mm），已考虑相机偏航与多帧平均。"""
    lat = lateral_error_mm(distance_mm, sigma_px, f_px)
    rng = range_error_mm(distance_mm, sigma_px, f_px, size_mm)
    th = np.radians(float(yaw_deg))
    e = float(np.hypot(lat * np.cos(th), rng * np.sin(th)))
    return e / np.sqrt(max(1, int(frames)))


def total_budget_mm(distance_mm: float, yaw_deg: float = 0.0,
                    sigma_px: float = SIGMA_PX, f_px: float = F_PX,
                    frames: int = 1,
                    systematic: Optional[Dict[str, float]] = None) -> dict:
    """误差预算：随机项（RSS）+ 各项系统误差。"""
    sys_map = dict(SYSTEMATIC_MM if systematic is None else systematic)
    rand = along_rod_error_mm(distance_mm, yaw_deg, sigma_px, f_px,
                              frames=frames)
    sys_vals = list(sys_map.values())
    total = float(np.sqrt(rand * rand + sum(v * v for v in sys_vals)))
    return {
        "distance_mm": float(distance_mm),
        "yaw_deg": float(yaw_deg),
        "frames": int(frames),
        "random_mm": float(rand),
        "systematic_mm": float(np.sqrt(sum(v * v for v in sys_vals))),
        "total_mm": total,
        "within_spec": bool(total <= SPEC_MM),
        "detail": {k: float(v) for k, v in sys_map.items()},
    }


def error_table(distances: Sequence[float] = (1200.0, 1500.0, 2000.0),
                yaws: Sequence[float] = (0.0, 5.0, 10.0, 15.0),
                sigma_px: float = SIGMA_PX, f_px: float = F_PX,
                frames: int = 1) -> List[dict]:
    """主表：每个距离一行，列出各偏航角下的沿杆误差与总预算。"""
    rows = []
    for z in distances:
        row = {
            "distance_mm": float(z),
            "marker_px": float(marker_pixels(z, f_px)),
            "mm_per_px": float(mm_per_px(z, f_px)),
            "lateral_mm": float(lateral_error_mm(z, sigma_px, f_px)),
            "range_mm": float(range_error_mm(z, sigma_px, f_px)),
            "along_by_yaw": {float(y): float(along_rod_error_mm(z, y, sigma_px, f_px, frames=frames))
                             for y in yaws},
        }
        b10 = total_budget_mm(z, 10.0, sigma_px, f_px, frames=frames)
        b10_5f = total_budget_mm(z, 10.0, sigma_px, f_px, frames=FRAME_AVG)
        row["budget_yaw10"] = b10
        row["budget_yaw10_5frames"] = b10_5f
        rows.append(row)
    return rows


def yaw_sweep(distances: Sequence[float] = (1200.0, 1500.0, 2000.0),
              yaws: Sequence[float] = tuple(np.linspace(0, 20, 21)),
              sigma_px: float = SIGMA_PX, f_px: float = F_PX) -> dict:
    """沿杆随机误差 vs 相机偏航角。"""
    return {
        "yaw_deg": [float(y) for y in yaws],
        "curves": {float(z): [float(along_rod_error_mm(z, y, sigma_px, f_px))
                              for y in yaws] for z in distances},
        "spec_mm": SPEC_MM,
    }


def distance_sweep(focals: Sequence[float] = (700.0, 900.0, 1200.0),
                   distances: Sequence[float] = tuple(np.linspace(1000, 2500, 31)),
                   sigma_px: float = SIGMA_PX,
                   yaw_deg: float = 0.0) -> dict:
    """侧向随机误差 vs 距离，不同焦距。"""
    return {
        "distance_mm": [float(z) for z in distances],
        "curves": {float(f): [float(along_rod_error_mm(z, yaw_deg, sigma_px, f))
                              for z in distances] for f in focals},
        "spec_mm": SPEC_MM,
    }


def vision_study() -> dict:
    """汇总视觉误差研究（图 + 表用）。"""
    rows = error_table()
    # 5 帧平均后的收益（1.2 m、10°）
    b5 = total_budget_mm(1200.0, 10.0, frames=FRAME_AVG)
    b1 = total_budget_mm(1200.0, 10.0, frames=1)
    return {
        "params": {
            "camera_px": [CAM_W, CAM_H],
            "f_px": F_PX,
            "hfov_deg": HFOV_DEG,
            "marker_mm": MARKER_MM,
            "sigma_px": SIGMA_PX,
            "systematic_mm": dict(SYSTEMATIC_MM),
            "frame_avg": FRAME_AVG,
            "spec_mm": SPEC_MM,
            "rod_mm": ROD_LENGTH_MM,
            "end_clearance_mm": END_CLEARANCE_MM,
        },
        "rows": rows,
        "yaw_sweep": yaw_sweep(),
        "distance_sweep": distance_sweep(),
        "frame_avg_gain": {"single": b1, "five": b5},
        "verdict": {
            "side_mount_ok": bool(total_budget_mm(1200.0, 5.0)["within_spec"]),
            "yaw10_fail": bool(not total_budget_mm(1200.0, 10.0)["within_spec"]),
            "yaw10_five_frames_ok": bool(b5["within_spec"]),
            "at_2000mm_yaw5_ok": bool(total_budget_mm(2000.0, 5.0)["within_spec"]),
        },
    }


__all__ = [
    "marker_pixels",
    "mm_per_px",
    "lateral_error_mm",
    "range_error_mm",
    "along_rod_error_mm",
    "total_budget_mm",
    "error_table",
    "yaw_sweep",
    "distance_sweep",
    "vision_study",
    "F_PX",
    "MARKER_MM",
    "SIGMA_PX",
    "SPEC_MM",
    "FRAME_AVG",
    "SYSTEMATIC_MM",
]
