"""衣序 HangFlow —— 算法仿真一键运行。

    python sim/run_all.py

流程：单元测试 → 间距规划 / 重排 / 控制 / 视觉误差 → 出图 → 写结果表。

产物：
    docs/figures/alg-01 … alg-07 *.png     （300 dpi，宽 8–10 英寸）
    docs/_data/algorithm-results.md        （参数、结果、结论，供主文档引用）
    docs/_data/algorithm-results.json      （同数据的机器可读版）
"""

from __future__ import annotations

import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sim"))

import numpy as np  # noqa: E402

import common  # noqa: E402
import control_sim as cs  # noqa: E402
import plots  # noqa: E402
import report  # noqa: E402
import reorder as ro  # noqa: E402
import spacing_planner as sp  # noqa: E402
import test_planner  # noqa: E402
import vision_error as ve  # noqa: E402

# 演示用衣物（A/B/C/D）：沿杆厚度投影 + 湿度
DEMO_T = {"A": 25.0, "B": 40.0, "C": 30.0, "D": 55.0}
DEMO_Q = {"A": 0.55, "B": 0.90, "C": 0.35, "D": 0.75}
DEMO_LABELS = ["A", "B", "C", "D"]
DEMO_SPAN = 480.0
MAX_SPAN = sp.usable_span(sp.ROD_LENGTH_MM)  # 1100 mm


# ---------------------------------------------------------------------------
def _timing(fn, n_repeat: int) -> dict:
    """测规划器耗时（微秒/次）。"""
    for _ in range(5):  # 预热
        fn()
    ts = []
    for _ in range(n_repeat):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1e6)
    ts = np.asarray(ts)
    return {
        "n_repeat": int(n_repeat),
        "mean_us": float(ts.mean()),
        "median_us": float(np.median(ts)),
        "p95_us": float(np.percentile(ts, 95)),
        "max_us": float(ts.max()),
    }


def collect_spacing() -> dict:
    t = [DEMO_T[k] for k in DEMO_LABELS]
    q = [DEMO_Q[k] for k in DEMO_LABELS]
    demo = sp.plan_spacing(t, max_span=MAX_SPAN, target_span=DEMO_SPAN, moisture=q)
    uniform = sp.plan_spacing(t, max_span=MAX_SPAN, target_span=DEMO_SPAN)
    demo_m = sp.plan_metrics(demo)
    uniform_m = sp.plan_metrics(uniform)

    # 规划器耗时（不同规模）
    rng = np.random.default_rng(7)
    timings = {
        "n4": _timing(lambda: sp.plan_spacing(t, max_span=MAX_SPAN,
                                              target_span=DEMO_SPAN, moisture=q), 2000),
        "n8": _timing(lambda: sp.plan_spacing(
            list(rng.uniform(25, 55, 8)), max_span=MAX_SPAN, target_span=900.0,
            moisture=list(rng.uniform(0, 1, 8))), 1000),
        "n24": _timing(lambda: sp.plan_spacing(
            list(rng.uniform(25, 55, 24)), max_span=MAX_SPAN, target_span=MAX_SPAN,
            moisture=list(rng.uniform(0, 1, 24))), 500),
    }

    # 目标跨度扫描（4 件）
    spans = np.arange(150.0, 1225.0, 25.0)
    sweep = {"span": [], "min_gap": [], "max_gap": [], "mean_gap": [],
             "used_span": [], "status": []}
    for s in spans:
        p = sp.plan_spacing(t, max_span=MAX_SPAN, target_span=float(s), moisture=q)
        m = sp.plan_metrics(p)
        sweep["span"].append(float(s))
        sweep["min_gap"].append(m["min_gap_mm"])
        sweep["max_gap"].append(m["max_gap_mm"])
        sweep["mean_gap"].append(m["mean_gap_mm"])
        sweep["used_span"].append(m["used_span_mm"])
        sweep["status"].append(p.status)

    # 容量曲线
    rods = np.arange(700.0, 2001.0, 50.0)
    nmax = {"rod_mm": [float(r) for r in rods], "curves": {}}
    for th in (25.0, 40.0, 60.0):
        nmax["curves"][float(th)] = [
            int(sp.max_garments(float(r), [th] * 40, min_gap=sp.MIN_GAP_MM,
                                end_clearance=sp.END_CLEARANCE_MM)) for r in rods]

    # 不可行/降级案例
    cases = []
    specs = [
        ("杆太短（10 件 40 mm 厚，L_max 500）", dict(
            thicknesses=[40.0] * 10, max_span=500.0)),
        ("衣物总厚超过杆（12 件 45 mm，L_max 500）", dict(
            thicknesses=[45.0] * 12, max_span=500.0)),
        ("目标跨度太紧（4 件 30 mm，目标 200）", dict(
            thicknesses=[30.0] * 4, max_span=MAX_SPAN, target_span=200.0)),
        ("间隙上限 100 mm（4 件 30 mm，目标 600）", dict(
            thicknesses=[30.0] * 4, max_span=MAX_SPAN, target_span=600.0,
            max_gap=100.0)),
        ("目标跨度超杆长（4 件 30 mm，目标 900，L_max 400）", dict(
            thicknesses=[30.0] * 4, max_span=400.0, target_span=900.0)),
    ]
    for label, kw in specs:
        p = sp.plan_spacing(**kw)
        cases.append({
            "label": label,
            "status": p.status,
            "feasible": bool(p.feasible),
            "gaps_mm": [round(float(g), 2) for g in p.gaps],
            "used_span_mm": round(float(p.used_span), 2),
            "warnings": list(p.warnings),
            "degradation": p.degradation,
            "drop_advice": int(p.drop_advice),
        })

    return {
        "labels": DEMO_LABELS,
        "demo": demo,
        "uniform": uniform,
        "demo_metrics": demo_m,
        "uniform_metrics": uniform_m,
        "timing": timings,
        "sweep": sweep,
        "nmax": nmax,
        "cases": cases,
        "params": {
            "rod_mm": sp.ROD_LENGTH_MM,
            "end_clearance_mm": sp.END_CLEARANCE_MM,
            "max_span_mm": MAX_SPAN,
            "min_gap_mm": sp.MIN_GAP_MM,
            "target_span_mm": DEMO_SPAN,
            "moisture_exponent": sp.DEFAULT_MOISTURE_EXPONENT,
            "thickness_mm": dict(DEMO_T),
            "moisture": dict(DEMO_Q),
        },
    }


def collect_reorder() -> dict:
    demo = ro.demo_reorder()
    cost = ro.cost_study()
    return {"demo": demo, "cost": cost}


def collect_control() -> dict:
    st = cs.study()
    tilt = cs.tilt_study()
    mc = cs.monte_carlo()
    return {"study": st, "tilt": tilt, "mc": mc}


def collect_vision() -> dict:
    return ve.vision_study()


# ---------------------------------------------------------------------------
def main() -> None:
    t_start = time.perf_counter()
    print("=" * 72)
    print("衣序 HangFlow · 算法仿真 run_all")
    print("=" * 72)
    common.setup_fonts()

    # ---- 1) 单元测试 ----
    print("\n[1/5] 间距规划器单元测试")
    passed, total = test_planner.run_all_tests()

    # ---- 2) 计算 ----
    print("\n[2/5] 计算：间距规划 / 重排 / 控制 / 视觉误差")
    t0 = time.perf_counter()
    spacing = collect_spacing()
    print(f"  间距规划 … {time.perf_counter() - t0:.2f} s")
    t0 = time.perf_counter()
    reorder = collect_reorder()
    print(f"  重排代价 … {time.perf_counter() - t0:.2f} s")
    t0 = time.perf_counter()
    control = collect_control()
    print(f"  控制仿真 … {time.perf_counter() - t0:.2f} s")
    t0 = time.perf_counter()
    vision = collect_vision()
    print(f"  视觉误差 … {time.perf_counter() - t0:.2f} s")

    results = {
        "meta": {
            "project": "衣序 HangFlow",
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "test_passed": int(passed),
            "test_total": int(total),
            "zh_labels": bool(common.ZH),
            "note": "全部为仿真/估算值，不是实测数据",
        },
        "spacing": spacing,
        "reorder": reorder,
        "control": control,
        "vision": vision,
    }

    # ---- 3) 出图 ----
    print("\n[3/5] 生成图（300 dpi）")
    t0 = time.perf_counter()
    figures = plots.make_all(results, {})
    print(f"  共 {len(figures)} 张，用时 {time.perf_counter() - t0:.2f} s")

    # ---- 4) 写结果表 ----
    print("\n[4/5] 写 docs/_data/algorithm-results.md / .json")
    captions = report.build_captions(results)
    md_path, json_path = report.write_all(results, figures, captions)
    print(f"  {md_path.relative_to(ROOT)}")
    print(f"  {json_path.relative_to(ROOT)}")

    # ---- 5) 摘要 ----
    print("\n[5/5] 关键数字")
    d = spacing["demo"]
    print(f"  规划器（4 件）：间隙 {', '.join(f'{g:.1f}' for g in d.gaps)} mm "
          f"（总跨度 {d.used_span:.0f} mm）")
    print(f"  规划耗时：N=4 {spacing['timing']['n4']['mean_us']:.0f} µs，"
          f"N=24 {spacing['timing']['n24']['mean_us']:.0f} µs")
    rp = reorder["demo"]["reorder"]
    print(f"  重排：上界 {rp.upper_bound} 次，本次 {rp.moves} 次，"
          f"预计 {rp.reorder_time_s:.1f} s")
    print(f"  只调间距：{reorder['demo']['spacing_time_s']:.1f} s")
    pid = next(r for r in control["study"]["rows"] if r["name"] == "PID")
    print(f"  控制（PID）：超调 {pid['overshoot_pct']:.2f}%（{pid['overshoot_mm']:.2f} mm），"
          f"稳定 {pid['settle_s']:.2f} s，稳态误差 {pid['sse_abs_mm']:.3f} mm")
    mc = control["mc"]
    print(f"  蒙特卡洛 {mc['n_runs']} 次：超调 p95 {mc['overshoot_mm']['p95']:.2f} mm，"
          f"误差 p95 {mc['sse_abs_mm']['p95']:.2f} mm")
    r0 = vision["rows"][0]
    print(f"  视觉 1.2 m 侧装随机误差 {r0['lateral_mm']:.2f} mm；"
          f"偏航 10° 总预算 {r0['budget_yaw10']['total_mm']:.2f} mm "
          f"→ 5 帧平均 {r0['budget_yaw10_5frames']['total_mm']:.2f} mm")
    print(f"\n全部完成，用时 {time.perf_counter() - t_start:.1f} s；"
          f"单元测试 {passed}/{total}")


if __name__ == "__main__":
    main()
