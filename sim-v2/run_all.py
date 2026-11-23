"""衣序 HangFlow v2（rev-B）—— 算法与控制仿真一键运行。

    python sim-v2/run_all.py

流程：单元测试 → 长度规划 / 链几何与夹持顺序 / 视觉识别 / 长度闭环 /
误差预算 → 出图 → 写 docs/_data-v2/results.md 与 .json。
"""

from __future__ import annotations

import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sim-v2"))

import numpy as np  # noqa: E402

import chain as ch  # noqa: E402
import common  # noqa: E402
import error_budget as eb  # noqa: E402
import length_control as lc  # noqa: E402
import length_planner as lp  # noqa: E402
import plots  # noqa: E402
import report  # noqa: E402
import tests as v2_tests  # noqa: E402
import vision_id as vi  # noqa: E402

ROD = lp.DEFAULT_ROD_MM
K_DEMO = 4


def _timing(fn, n_repeat: int) -> dict:
    for _ in range(5):
        fn()
    ts = []
    for _ in range(n_repeat):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1e6)
    ts = np.asarray(ts)
    return {"n_repeat": int(n_repeat), "mean_us": float(ts.mean()),
            "median_us": float(np.median(ts)), "p95_us": float(np.percentile(ts, 95))}


def collect_plans() -> dict:
    q = [0.55, 0.90, 0.35, 0.75]
    plans = lp.demo_plans(K_DEMO, q)
    plans_fill = lp.demo_plans(K_DEMO, q, fill=True)
    timing = {
        "n4": _timing(lambda: lp.plan_lengths(K_DEMO, mode="weighted", moisture=q), 2000),
        "n10": _timing(lambda: lp.plan_lengths(10, mode="weighted",
                                               moisture=list(np.linspace(0, 1, 10))), 1000),
    }
    cases = []
    for label, kw in [
        ("11 件 @10 cm（杆不够，压内部段）", dict(garment_count=11, target_gap=100.0)),
        ("23 件（完全不可行）", dict(garment_count=23, target_gap=100.0)),
        ("目标 300 mm（超内部上限）", dict(garment_count=4, target_gap=300.0)),
        ("目标 20 mm（低于下限）", dict(garment_count=4, target_gap=20.0)),
        ("fill 模式（端部补到 120 上限仍不满）", dict(garment_count=4, mode="collect",
                                                    fill=True)),
        ("收衣（内部缩到 40，端部不动）", dict(garment_count=4, mode="collect")),
        ("端部配置改为 120 mm", dict(garment_count=4, end_lengths=(120.0, 120.0))),
    ]:
        p = lp.plan_lengths(**kw)
        cases.append({
            "label": label, "mode": p.mode, "status": p.status,
            "feasible": bool(p.feasible),
            "inner_mm": [round(float(v), 1) for v in p.inner],
            "ends_mm": [round(float(v), 1) for v in p.ends],
            "chain_mm": round(float(p.chain_length_mm), 1),
            "leftover_mm": round(float(p.leftover_mm), 1),
            "warnings": list(p.warnings),
            "degradation": p.degradation,
            "drop_advice": int(p.drop_advice),
        })
    return {
        "plans": plans,
        "plans_fill": plans_fill,
        "metrics": {k: lp.plan_metrics(v) for k, v in plans.items()},
        "timing": timing,
        "cases": cases,
        "capacity": {
            "gap_mm": [40, 60, 80, 100, 140, 220],
            "max_k": [lp.max_garments(ROD, g) for g in (40, 60, 80, 100, 140, 220)],
        },
        "params": {
            "rod_mm": ROD,
            "wall_margin_mm": lp.WALL_MARGIN_MM,
            "available_mm": lp.available_length(ROD),
            "t_h_mm": lp.T_H_MM,
            "inner_min_mm": lp.INNER_MIN_MM,
            "inner_max_mm": lp.INNER_MAX_MM,
            "end_min_mm": lp.END_MIN_MM,
            "end_max_mm": lp.END_MAX_MM,
            "end_config_mm": lp.END_CONFIG_MM,
            "target_gap_mm": lp.DEFAULT_GAP_MM,
            "preload_mm": lp.PRELOAD_MM,
            "preload_force_n": lp.PRELOAD_FORCE_N,
            "moisture": q,
        },
    }


def collect_chain() -> dict:
    demo = ch.demo_chain(K_DEMO)
    daily = ch.daily_cycle_study(rod_length=ROD, garment_counts=(3, 4, 5, 6, 8))
    setup = ch.setup_study(rod_length=ROD, garment_count=K_DEMO)
    # 等距 → 加权（内部段有伸有缩，仍按锚定左墙逐段处理）
    plans = lp.demo_plans(K_DEMO, [0.55, 0.90, 0.35, 0.75])
    trans = ch.simulate_sequence(plans["equal"], plans["weighted"], ch.DRIVES[0],
                                 strategy="anchor_left")
    return {
        "demo": demo,
        "daily": daily,
        "setup": setup,
        "weighted_transition": trans.to_dict(),
    }


def collect_control() -> dict:
    return {
        "study": lc.control_study(),
        "backlash": lc.backlash_study(),
        "stall": lc.stall_study(),
        "limits": lc.limit_study(),
    }


def collect_budget() -> dict:
    return eb.budget_study()


def collect_vision() -> dict:
    return vi.vision_study()


def main() -> None:
    t_start = time.perf_counter()
    print("=" * 72)
    print("衣序 HangFlow v2 · 算法与控制仿真 run_all（K+1 调节器 + 双端夹持）")
    print("=" * 72)
    common.setup_fonts()

    print("\n[1/5] v2 单元测试")
    passed, total = v2_tests.run_all_tests()

    print("\n[2/5] 计算")
    t0 = time.perf_counter()
    plan = collect_plans()
    print(f"  长度规划 … {time.perf_counter() - t0:.2f} s")
    t0 = time.perf_counter()
    chain = collect_chain()
    print(f"  链与夹持顺序 … {time.perf_counter() - t0:.2f} s")
    t0 = time.perf_counter()
    control = collect_control()
    print(f"  长度闭环 … {time.perf_counter() - t0:.2f} s")
    t0 = time.perf_counter()
    budget = collect_budget()
    print(f"  误差预算 … {time.perf_counter() - t0:.2f} s")
    t0 = time.perf_counter()
    vision = collect_vision()
    print(f"  视觉识别 … {time.perf_counter() - t0:.2f} s")

    results = {
        "meta": {
            "project": "衣序 HangFlow v2 (rev-B)",
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "test_passed": int(passed),
            "test_total": int(total),
            "zh_labels": bool(common.ZH),
            "note": "全部为仿真/估算值，不是实测数据",
        },
        "plans": plan["plans"],
        "plans_fill": plan["plans_fill"],
        "plan_metrics": plan["metrics"],
        "planner_timing": plan["timing"],
        "plan_cases": plan["cases"],
        "capacity": plan["capacity"],
        "planner_params": plan["params"],
        "chain": chain,
        "timing": chain["daily"],
        "setup": chain["setup"],
        "control": control,
        "backlash": control["backlash"],
        "stall": control["stall"],
        "limits": control["limits"],
        "budget": budget,
        "vision": vision,
    }

    print("\n[3/5] 生成图（300 dpi）")
    t0 = time.perf_counter()
    figures = plots.make_all(results)
    print(f"  共 {len(figures)} 张，用时 {time.perf_counter() - t0:.2f} s")

    print("\n[4/5] 写 docs/_data-v2/results.md / .json")
    captions = report.build_captions(results)
    md_path, json_path = report.write_all(results, figures, captions)
    print(f"  {md_path.relative_to(ROOT)}")
    print(f"  {json_path.relative_to(ROOT)}")

    print("\n[5/5] 关键数字")
    eq = results["plans"]["equal"]
    wt = results["plans"]["weighted"]
    co = results["plans"]["collect"]
    print(f"  规划：等距 [{eq.all_lengths.round(0).tolist()}]，"
          f"加权内部 {wt.inner.round(1).tolist()}，收衣链条 {co.chain_length_mm:.0f} mm")
    print(f"  规划耗时：K=4 中位 {results['planner_timing']['n4']['median_us']:.0f} µs")
    print(f"  日常调节（4 件）：{chain['daily']['rows'][1][ch.DRIVES[0].name]['time_s']:.1f} s；"
          f"安装标定 {chain['setup']['time_s']:.1f} s")
    cmp = chain["demo"]["comparison"]
    a = cmp["锚定左墙（推荐）"]
    b = cmp["不锁端（整链推）"]
    print(f"  夹持顺序：峰值 {a['peak_force_n']:.0f} N / {a['peak_current_a']:.2f} A；"
          f"不锁端 {b['peak_force_n']:.0f} N / {b['peak_current_a']:.2f} A")
    ctrl = control["study"]["rows"]
    print("  闭环阶跃：" + "；".join(
        f"{r['drive']} rise {r['rise_s']:.2f}s / sse {r['sse_mm']:+.3f}mm" for r in ctrl))
    print(f"  堵转：{control['stall']['detect_time_s'] * 1000:.0f} ms 判出")
    mc = budget["monte_carlo"]
    print(f"  误差预算：RSS {budget['rss_mm']:.2f} mm，p95 {mc['p95_abs_mm']:.2f} mm，"
          f"±2 mm 内 {mc['p_within_spec'] * 100:.1f}%")
    acq = vision["acq_1p5m_30mm"]
    print(f"  视觉：{vision['params']['n_units']} 个 ID 全认全 "
          f"{acq['success_rate'] * 100:.1f}%，p95 {acq['p95_s']:.2f} s")
    print(f"\n全部完成，用时 {time.perf_counter() - t_start:.1f} s；"
          f"单元测试 {passed}/{total}")


if __name__ == "__main__":
    main()
