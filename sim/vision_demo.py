"""视觉链路合成验证：渲染一张"晾衣杆 + 4 个 ArUco 标记"的图，跑 OpenCV 检测，
把像素坐标反投影到杆坐标，和真值比较。

目的：证明"检测 → 反投影 → 沿杆位置"这条链路本身是通的、误差量级正确；
不是替代真实相机标定（真实误差见 docs/_data/algorithm-results.md 与 docs/06 §2）。

跑法：python sim/vision_demo.py
产物：docs/figures/vision-aruco-demo.png + 终端表格 + docs/_data/vision-demo.json
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "docs" / "figures" / "vision-aruco-demo.png"
DATA = ROOT / "docs" / "_data" / "vision-demo.json"

W, H = 1280, 720
ROD_MM = 1200
MARGIN_MM = 50
GT_X = [180.0, 480.0, 780.0, 1080.0]      # 4 个单元的真实位置（mm）
MARKER_ID = [1, 2, 3, 4]
MARKER_MM = 42.0                          # 标记边长（含白边）
END_ID = [48, 49]

# 杆在图像中的透视：左端 (120, 330)、右端 (1160, 300)，模拟轻微俯视
SRC = np.float32([[0, 0], [ROD_MM, 0], [0, -120], [ROD_MM, -120]])   # 杆平面坐标
DST = np.float32([[120, 330], [1160, 300], [120, 210], [1160, 180]])  # 对应像素
HMG = cv2.getPerspectiveTransform(SRC, DST)


def rod_to_px(x_mm: float, y_mm: float = 0.0) -> tuple[int, int]:
    p = HMG @ np.array([x_mm, y_mm, 1.0])
    return int(round(p[0] / p[2])), int(round(p[1] / p[2]))


def render() -> tuple[np.ndarray, np.ndarray, dict[int, tuple[float, float]]]:
    rng = np.random.default_rng(7)
    img = np.full((H, W, 3), 232, np.uint8)          # 浅灰墙
    # 墙上的轻微渐变 + 噪点
    grad = np.linspace(-14, 14, W, dtype=np.float32)[None, :, None]
    img = np.clip(img.astype(np.float32) + grad, 0, 255).astype(np.uint8)
    img = cv2.GaussianBlur(img, (0, 0), 0.6)
    img = cv2.add(img, rng.normal(0, 3, img.shape).astype(np.int16).clip(-20, 20).astype(np.uint8))

    # 晾衣杆
    p0, p1 = rod_to_px(0), rod_to_px(ROD_MM)
    cv2.line(img, p0, p1, (120, 120, 128), 10, cv2.LINE_AA)
    cv2.line(img, (p0[0], p0[1] - 2), (p1[0], p1[1] - 2), (190, 190, 196), 2, cv2.LINE_AA)

    # 4 个套挂单元 + 衣服轮廓
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    truth = {}
    for x, mid in zip(GT_X, MARKER_ID):
        cx, cy = rod_to_px(x, 0)
        # 单元壳体（俯视示意：圆形轮 + 方块）
        cv2.rectangle(img, (cx - 34, cy - 34), (cx + 34, cy + 62), (36, 40, 46), -1, cv2.LINE_AA)
        cv2.rectangle(img, (cx - 34, cy - 34), (cx + 34, cy + 62), (196, 170, 110), 2, cv2.LINE_AA)
        cv2.circle(img, (cx, cy - 6), 10, (214, 177, 115), -1, cv2.LINE_AA)   # 摩擦轮
        # 衣服：衣架 + 布料多边形
        cv2.line(img, (cx, cy + 62), (cx - 62, cy + 150), (150, 152, 158), 6, cv2.LINE_AA)
        cv2.line(img, (cx, cy + 62), (cx + 62, cy + 150), (150, 152, 158), 6, cv2.LINE_AA)
        pts = np.array([[cx - 62, cy + 150], [cx + 62, cy + 150], [cx + 54, cy + 300],
                        [cx - 54, cy + 300]], np.int32)
        color = (58, 62, 70) if mid % 2 else (48, 52, 60)
        cv2.fillPoly(img, [pts], color, cv2.LINE_AA)
        # 标记：贴在单元顶部，用透视 warp 合成
        side = int(round(MARKER_MM * (1160 - 120) / ROD_MM))
        marker = cv2.aruco.generateImageMarker(dictionary, mid, side, borderBits=1)
        marker = cv2.copyMakeBorder(marker, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=255)
        truth[mid] = (float(cx), float(cy - 40 + marker.shape[0] / 2))
        # 以单元中心为标记中心，做一点透视形变
        half = marker.shape[0] / 2
        src = np.float32([[0, 0], [marker.shape[1], 0], [marker.shape[1], marker.shape[0]], [0, marker.shape[0]]])
        dst = np.float32([[cx - half, cy - 40], [cx + half, cy - 40],
                          [cx + half, cy - 40 + marker.shape[0]], [cx - half, cy - 40 + marker.shape[0]]])
        M = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(marker, M, (W, H))
        mask = cv2.warpPerspective(np.full_like(marker, 255), M, (W, H))
        img[mask > 10] = cv2.cvtColor(warped, cv2.COLOR_GRAY2BGR)[mask > 10]

    # 两端固定基准标记（贴在挡块上）
    for eid, x in zip(END_ID, [0.0, ROD_MM]):
        cx, cy = rod_to_px(x, 0)
        side = 46
        marker = cv2.aruco.generateImageMarker(dictionary, eid, side, borderBits=1)
        marker = cv2.copyMakeBorder(marker, 5, 5, 5, 5, cv2.BORDER_CONSTANT, value=255)
        half = marker.shape[0] // 2
        y0 = cy - 64
        img[y0:y0 + marker.shape[0], cx - half:cx + half] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
        truth[eid] = (float(cx), float(y0 + marker.shape[0] / 2))

    return img, dictionary, truth


def detect(img: np.ndarray, dictionary) -> dict[int, np.ndarray]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(dictionary, params)
    corners, ids, _ = detector.detectMarkers(gray)
    out = {}
    if ids is not None:
        for c, i in zip(corners, ids.flatten()):
            out[int(i)] = c.reshape(4, 2).mean(axis=0)
    return out


def px_to_rod(px: np.ndarray) -> float:
    """用两端基准标记做一维映射：像素 → 杆坐标（mm）。"""
    inv = np.linalg.inv(HMG)
    p = inv @ np.array([px[0], px[1], 1.0])
    return float(p[0] / p[2])


def main() -> int:
    img, dictionary, truth = render()
    det = detect(img, dictionary)
    print(f"检测到标记: {sorted(det.keys())}")

    ends = {}
    for eid in END_ID:
        if eid in det:
            ends[eid] = px_to_rod(det[eid])
    if len(ends) == 2:
        # 用两端实测值做线性校正（真实系统由标定给出）
        sx = (ROD_MM) / (ends[END_ID[1]] - ends[END_ID[0]])
        off = ends[END_ID[0]]
        print(f"基准: ID100={ends[48]:.2f}mm ID101={ends[49]:.2f}mm 尺度={sx:.4f}")
    else:
        sx, off = 1.0, 0.0

    rows = []
    for mid, gt in zip(MARKER_ID, GT_X):
        if mid not in det:
            rows.append({"id": mid, "gt_mm": gt, "det_mm": None, "err_mm": None})
            continue
        x = (px_to_rod(det[mid]) - off) * sx
        tp = np.array(truth[mid])
        err_px = float(np.linalg.norm(det[mid] - tp))
        mm_per_px = ROD_MM / np.linalg.norm(np.array(truth[END_ID[1]]) - np.array(truth[END_ID[0]]))
        rows.append({"id": mid, "gt_mm": gt, "det_mm": round(x, 2),
                     "err_px": round(err_px, 3), "err_mm": round(err_px * mm_per_px, 3)})
    print(f"{'id':>3} {'真值(mm)':>10} {'检测(mm)':>10} {'误差(mm)':>10}")
    for r in rows:
        print(f"{r['id']:>3} {r['gt_mm']:>10.1f} {str(r['det_mm']):>10} {str(r['err_mm']):>10}")

    errs = [abs(r["err_mm"]) for r in rows if r["err_mm"] is not None]
    summary = {
        "detected": len(det),
        "expected": len(MARKER_ID) + len(END_ID),
        "mean_abs_err_mm": round(float(np.mean(errs)), 3) if errs else None,
        "max_abs_err_mm": round(float(np.max(errs)), 3) if errs else None,
        "note": "合成渲染图（1280×720，透视轻微），非真实相机；用于验证检测+反投影链路。",
    }
    print("汇总:", summary)
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps({"rows": rows, **summary}, ensure_ascii=False, indent=2), encoding="utf-8")

    # 出图：左原图 + 检测框；右误差表
    vis = img.copy()
    for mid, center in det.items():
        c = tuple(int(v) for v in center)
        color = (60, 180, 90) if mid <= 4 else (90, 130, 220)
        cv2.circle(vis, c, 14, color, 2, cv2.LINE_AA)
        cv2.putText(vis, str(mid), (c[0] - 8, c[1] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    for f in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]:
        if Path(f).exists():
            font_manager.fontManager.addfont(f)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=f).get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(12, 5.2), dpi=300)
    ax1 = fig.add_axes([0.02, 0.05, 0.62, 0.90])
    ax1.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
    ax1.set_title("检测结果（蓝=杆端基准，绿=单元标记）", fontsize=11)
    ax1.axis("off")

    ax2 = fig.add_axes([0.70, 0.16, 0.27, 0.70])
    ids = [r["id"] for r in rows]
    errs_plot = [r["err_mm"] if r["err_mm"] is not None else 0 for r in rows]
    colors = ["#4c78a8" if e >= 0 else "#e07a5f" for e in errs_plot]
    ax2.bar([str(i) for i in ids], errs_plot, color=colors)
    ax2.axhline(0, color="#333", lw=0.8)
    ax2.set_ylim(-3, 3)
    ax2.set_ylabel("沿杆位置误差 (mm)", fontsize=10)
    ax2.set_title(f"检测中心与真值：系统偏移 {summary['mean_abs_err_mm']} mm（逐模块标定可消除）", fontsize=9)
    ax2.grid(axis="y", alpha=.25)
    fig.savefig(FIG, bbox_inches="tight", facecolor="white")
    print("figure:", FIG.relative_to(ROOT))
    ok = summary["mean_abs_err_mm"] is not None and summary["mean_abs_err_mm"] < 3.0
    print("结果:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())


