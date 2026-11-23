"""衣序 HangFlow v2 —— ArUco 编码识别与位置反算。

v2 里视觉只做两件事：
1) **识别 ID**：每个伸缩圆柱贴唯一 ArUco（01…K−1），装上去什么顺序就什么顺序，
   中枢读码把「物理第几段」和「编码」绑定起来；
2) **核位置**：给出每个圆柱中心的像素/物理位置，用于校验链条没卡住、没脱钩。

注意：**净风道不靠视觉闭环**。L_i 由丝杆 + AS5600 直接测，视觉误差 1–3 mm
只影响"显示/校验"，不影响 L_i 的控制精度。这一点是误差预算的关键。

识别模型
--------
* 用真实的 OpenCV ArUco 检测器在合成图像上做实验（含旋转、透视、运动模糊、
  低对比、JPEG 压缩），得到「标记像素数 → 单帧识别率」的拐点；
* 把拐点换算成工作距离：`标记像素 = f·s / Z`（f=900 px，s=30 mm）；
* 实际限制不是像素，而是**遮挡**（衣服/衣架挡住标记）。遮挡用每帧 8% 的
  伯努利模型，配合「连续 3 帧一致才确认」的抗抖动逻辑，算识别所需时间。

降级策略
--------
* 认不出某一段 → 用「长度反馈 + 固定顺序」推断它是哪一段（不换序 ⇒ 顺序已知）；
* 全部认不出 → 保持上次绑定，只靠长度闭环继续工作（调节本身不需要视觉）；
* 读到重复 ID / 顺序倒挂 → 判为误读，丢弃该帧并重试。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

F_PX = 900.0             # 等效焦距（1280×720，≈71° 水平视场）
CAM_W, CAM_H = 1280, 720
MARKER_MM = 30.0         # 贴在圆柱顶部的 ArUco 边长
MARKER_IDS = list(range(1, 8))   # 编码 01–07
P_OCCLUSION = 0.08       # 单标记单帧被遮挡概率（估算）
DEBOUNCE_FRAMES = 3      # 连续 3 帧一致才确认
FPS = 30.0
CONFUSION_RATE = 1e-3    # 误读成别的 ID 的概率（估算）


# ---------------------------------------------------------------------------
# 1) 真实检测器实验
# ---------------------------------------------------------------------------
def _marker_frame(marker_px: int, seed: int,
                  blur: float = 1.0, rot_deg: float = 25.0,
                  contrast: float = 0.55, noise: float = 12.0,
                  motion: int = 3, jpeg: int = 50):
    """合成一帧「远处小标记」图像：固定 1 px 传感器模糊 + 旋转 + 运动模糊 + 低对比 + JPEG。"""
    import cv2

    rng = np.random.default_rng(seed)
    dic = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dic, 3, 160)
    img = cv2.copyMakeBorder(marker, 80, 80, 80, 80,
                             cv2.BORDER_CONSTANT, value=255)
    h, w = img.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2),
                                rng.uniform(-rot_deg, rot_deg),
                                rng.uniform(0.9, 1.1))
    img = cv2.warpAffine(img, M, (w, h), borderValue=255)
    side = int(max(4, marker_px) * 6)
    img = cv2.resize(img, (side, side), interpolation=cv2.INTER_AREA)
    k = max(1, motion)
    ker = np.zeros((k, k), np.float32)
    ker[k // 2, :] = 1.0 / k
    img = cv2.filter2D(img, -1, ker)
    img = cv2.GaussianBlur(img, (0, 0), blur)   # 固定传感器 PSF（不随尺寸缩放）
    img = img.astype(np.float32) * contrast + 60.0
    img = np.clip(img + rng.normal(0.0, noise, img.shape), 0, 255)
    ok, buf = cv2.imencode(".jpg", img,
                           [int(cv2.IMWRITE_JPEG_QUALITY), jpeg])
    return cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)


def detection_rate_vs_pixels(pixel_sizes: Sequence[int] = (3, 4, 5, 6, 7, 8, 10,
                                                          12, 14, 16, 18, 20, 24),
                             frames_per_size: int = 20,
                             target_id: int = 3) -> Dict[int, float]:
    """单帧识别率 vs 标记像素数（真实 cv2.aruco 检测器）。"""
    import cv2

    dic = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detector = cv2.aruco.ArucoDetector(dic, cv2.aruco.DetectorParameters())
    out: Dict[int, float] = {}
    for px in pixel_sizes:
        ok = 0
        for seed in range(frames_per_size):
            img = _marker_frame(int(px), seed)
            _corners, ids, _rej = detector.detectMarkers(img)
            if ids is not None and target_id in ids.ravel():
                ok += 1
        out[int(px)] = ok / frames_per_size
    return out


def marker_pixels(distance_mm: float, f_px: float = F_PX,
                  size_mm: float = MARKER_MM) -> float:
    """该距离下标记的像素边长。"""
    return f_px * size_mm / float(distance_mm)


def decode_probability(distance_mm: float, rate_curve: Dict[int, float],
                       f_px: float = F_PX,
                       size_mm: float = MARKER_MM) -> float:
    """查表插值：给定距离的标记像素 → 单帧识别率（含遮挡前的纯解码概率）。"""
    px = marker_pixels(distance_mm, f_px, size_mm)
    xs = np.array(sorted(rate_curve))
    ys = np.array([rate_curve[int(x)] for x in xs])
    return float(np.clip(np.interp(px, xs, ys), 0.0, 1.0))


# ---------------------------------------------------------------------------
# 2) 识别耗时（遮挡 + 3 帧去抖）
# ---------------------------------------------------------------------------
@dataclass
class AcquisitionResult:
    times_s: np.ndarray          # 每轮仿真「全部 ID 认全」的耗时（未认全为 inf）
    success_rate: float
    p95_s: float
    per_marker_rate: float       # 单帧单标记被有效读到的概率

    def to_dict(self) -> dict:
        finite = self.times_s[np.isfinite(self.times_s)]
        return {
            "success_rate": round(float(self.success_rate), 4),
            "p95_s": round(float(self.p95_s), 3),
            "mean_s": round(float(finite.mean()) if finite.size else float("nan"), 3),
            "per_marker_rate": round(float(self.per_marker_rate), 4),
        }


def acquisition_mc(n_markers: int = 3, n_runs: int = 300,
                   max_frames: int = 120, seed: int = 20261123,
                   p_occlusion: float = P_OCCLUSION,
                   p_decode: float = 1.0,
                   debounce: int = DEBOUNCE_FRAMES,
                   fps: float = FPS) -> AcquisitionResult:
    """蒙特卡洛：每帧每标记「未被遮挡且解码成功」才计一次读数，连续 debounce 帧一致才确认。"""
    rng = np.random.default_rng(seed)
    times = np.full(n_runs, np.inf)
    for r in range(n_runs):
        streak = np.zeros(n_markers, dtype=int)
        confirmed = np.zeros(n_markers, dtype=bool)
        for f in range(1, max_frames + 1):
            for m in range(n_markers):
                if confirmed[m]:
                    continue
                hit = (rng.random() > p_occlusion) and (rng.random() < p_decode)
                streak[m] = streak[m] + 1 if hit else 0
                if streak[m] >= debounce:
                    confirmed[m] = True
            if confirmed.all():
                times[r] = f / fps
                break
    success = float(np.mean(np.isfinite(times)))
    finite = times[np.isfinite(times)]
    p95 = float(np.percentile(finite, 95)) if finite.size else float("inf")
    return AcquisitionResult(times_s=times, success_rate=success, p95_s=p95,
                             per_marker_rate=float((1 - p_occlusion) * p_decode))


# ---------------------------------------------------------------------------
# 3) ID 绑定、位置反算、降级
# ---------------------------------------------------------------------------
@dataclass
class IdBinding:
    """视觉读码结果 → 物理段号绑定。"""

    order: List[int]                 # 从左到右的物理段号（0 基）
    ids: List[int]                   # 对应读到的 ArUco 编码
    cylinders_mm: List[float]        # 对应圆柱中心 x（mm）
    ok: bool                         # 是否全部识别且顺序自洽
    missing: List[int] = field(default_factory=list)    # 缺读的物理段号
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"order": self.order, "ids": self.ids,
                "cylinders_mm": [round(float(v), 1) for v in self.cylinders_mm],
                "ok": bool(self.ok), "missing": self.missing,
                "notes": self.notes}


def bind_ids(detections: Sequence[tuple], expected_count: int) -> IdBinding:
    """把 [(id, x_mm), …] 变成物理段号绑定。

    规则：按 x 从左到右排序；若读到的 id 正好是 1..n 且顺序递增 → 全部可信；
    缺读 → 用「不换序」的先验补位（位置相邻的已知段之间）；
    重复 id / 顺序倒挂 → 判误读，标 note。
    """
    det = [(int(i), float(x)) for i, x in detections]
    det.sort(key=lambda t: t[1])
    ids = [i for i, _ in det]
    xs = [x for _, x in det]
    order = [i - 1 for i in ids]
    notes: List[str] = []
    ok = True
    missing: List[int] = []
    seen = set()
    for i in ids:
        if i in seen:
            notes.append(f"重复编码 {i:02d} → 判误读，丢弃该帧")
            ok = False
        seen.add(i)
    if any(ids[k] >= ids[k + 1] for k in range(len(ids) - 1)):
        notes.append("编码顺序倒挂（物理上不可能）→ 判误读")
        ok = False
    if len(ids) < expected_count:
        ok = False
        known = set(order)
        missing = [s for s in range(expected_count) if s not in known]
        notes.append(f"缺读 {len(missing)} 段：用长度反馈 + 固定顺序补位")
    # 若是完美递增的 1..n，直接用位置索引
    if ok and ids == list(range(1, expected_count + 1)):
        order = list(range(expected_count))
    return IdBinding(order=order, ids=ids, cylinders_mm=xs, ok=ok,
                     missing=missing, notes=notes)


def seam_positions_from_vision(binding: IdBinding,
                               lengths: Sequence[float],
                               t_h: float = 10.0) -> np.ndarray:
    """由圆柱中心 + 长度反馈反算接缝（衣架）位置（mm）。"""
    L = np.asarray(lengths, dtype=float).ravel()
    c = np.asarray(binding.cylinders_mm, dtype=float).ravel()
    if c.size != L.size:
        raise ValueError("圆柱中心与长度数量不一致")
    s = np.zeros(L.size + 1)
    s[:-1] = c - L / 2.0 - t_h / 2.0
    s[-1] = c[-1] + L[-1] / 2.0 + t_h / 2.0
    return s


def vision_study() -> dict:
    """汇总视觉识别研究（图与表用）。演示：4 件衣物 = 5 个调节器。"""
    import length_planner as lp
    import chain as ch

    curve = detection_rate_vs_pixels()
    px95 = next((px for px in sorted(curve) if curve[px] >= 0.95), max(curve))
    distances = [1000.0, 1200.0, 1500.0, 2000.0]
    rows = []
    for z in distances:
        for size in (30.0, 40.0, 50.0):
            rows.append({
                "distance_mm": z,
                "marker_mm": size,
                "marker_px": float(marker_pixels(z, size_mm=size)),
                "p_decode": float(decode_probability(z, curve, size_mm=size)),
            })
    plan = lp.plan_lengths(4, mode="equal", target_gap=100.0)
    lay = ch.chain_layout(plan)
    cyl_centers = lay.regulator_edges.mean(axis=1)
    n_units = int(lay.regulator_count)
    p15 = decode_probability(1500.0, curve)
    p12 = decode_probability(1200.0, curve)
    p15_50 = decode_probability(1500.0, curve, size_mm=50.0)
    acq15 = acquisition_mc(n_markers=n_units, p_decode=p15)
    acq12 = acquisition_mc(n_markers=n_units, p_decode=p12)
    acq50 = acquisition_mc(n_markers=n_units, p_decode=p15_50)
    detections = [(i + 1, float(cyl_centers[i])) for i in range(n_units)]
    demo_binding = bind_ids(detections, n_units)
    degraded = bind_ids([d for k, d in enumerate(detections) if k != 2], n_units)
    return {
        "params": {
            "f_px": F_PX,
            "camera_px": [CAM_W, CAM_H],
            "marker_mm": MARKER_MM,
            "p_occlusion": P_OCCLUSION,
            "debounce": DEBOUNCE_FRAMES,
            "fps": FPS,
            "confusion_rate": CONFUSION_RATE,
            "n_units": n_units,
        },
        "rate_curve": {int(k): float(v) for k, v in curve.items()},
        "px95": int(px95),
        "rows_by_distance": rows,
        "acq_1p5m_30mm": acq15.to_dict(),
        "acq_1p2m_30mm": acq12.to_dict(),
        "acq_1p5m_50mm": acq50.to_dict(),
        "acq_times_s": [float(t) for t in acq15.times_s],
        "binding_demo": demo_binding.to_dict(),
        "binding_degraded": degraded.to_dict(),
        "seam_check_mm": [round(float(v), 1) for v in
                          seam_positions_from_vision(demo_binding, plan.all_lengths)],
    }


__all__ = [
    "detection_rate_vs_pixels",
    "marker_pixels",
    "decode_probability",
    "acquisition_mc",
    "bind_ids",
    "IdBinding",
    "seam_positions_from_vision",
    "vision_study",
    "F_PX",
    "MARKER_MM",
    "P_OCCLUSION",
    "DEBOUNCE_FRAMES",
    "FPS",
]
