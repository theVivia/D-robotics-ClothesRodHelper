"""sim-v2（rev-D）单元测试：端点锚定、端部内端吸收、K+1 调节器、双端锥面夹头。

验收用例对齐 docs/v2/10-端点锚定模型.md §5：
  1) 默认 [60,100,100,100,60]，总长 460，锚点 0/460 不动
  2) 等距 12cm → [30,120,120,120,30]，Δ=+60 由端部吸收，总长仍 460
  3) 再等距 8cm → [90,80,80,80,90]，总长 460
  4) 目标 20cm → 端部行程不够，拒绝
  5) 收衣 → 端部 120/120，链 400，空杆 60，提示未完全收拢
  6) 手动拖一段 +20 → 同侧端部优先吸收（60→40）
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

import chain as ch  # noqa: E402
import length_planner as lp  # noqa: E402

TOL = 1e-6


def test_default_install_state() -> str:
    p = lp.plan_lengths(4, mode="equal", target_gap=100.0)
    assert p.to_dict()["all_lengths_mm"] == [60.0, 100.0, 100.0, 100.0, 60.0]
    assert abs(p.anchor_span_mm - 460.0) < TOL
    assert abs(p.chain_length_mm - 460.0) < TOL
    assert abs(p.gap_mm - 0.0) < TOL
    assert abs(p.free_rod_mm - 640.0) < TOL
    assert p.status == "ok" and p.feasible and p.regulator_count == 5
    assert np.allclose(p.ends, (60.0, 60.0))
    return "默认 [60,100,100,100,60]，D=460，空杆 640"


def test_equal_12cm_ends_absorb() -> str:
    p = lp.plan_lengths(4, mode="equal", target_gap=120.0)
    assert np.allclose(p.inner, 120.0)
    assert np.allclose(p.ends, (30.0, 30.0))          # Δ=+60 → 各 −30
    assert np.allclose(p.all_lengths, [30, 120, 120, 120, 30])
    assert abs(p.chain_length_mm - 460.0) < TOL
    assert abs(p.gap_mm) < TOL
    return "等距 12 cm：端部 60→30（各吸收 −30），链长仍 460"


def test_then_collect_from_12cm() -> str:
    p12 = lp.plan_lengths(4, mode="equal", target_gap=120.0)
    p = lp.plan_lengths(4, mode="collect",
                        current_inner=p12.inner, current_ends=p12.ends)
    assert np.allclose(p.inner, 100.0)                 # 收衣 = 回动力段最短 100
    assert np.allclose(p.ends, (60.0, 60.0))           # Δ=−60 → 各 +30
    assert np.allclose(p.all_lengths, [60, 100, 100, 100, 60])
    assert abs(p.chain_length_mm - 460.0) < TOL
    return "12 cm→收衣：内部回 100、端部 30→60，链长仍 460"


def test_target_20cm_rejected() -> str:
    p = lp.plan_lengths(4, mode="equal", target_gap=200.0)
    assert p.status == "rejected" and not p.feasible
    assert any("超过锚定跨度" in w for w in p.warnings)
    return "目标 20 cm：内部 600 mm 超过 D 允许值 → 拒绝"


def test_low_gap_rejected() -> str:
    # 4–10 cm 用被动短套，不进入自动规划
    p = lp.plan_lengths(4, mode="equal", target_gap=80.0)
    assert p.status == "rejected" and not p.feasible
    assert any("被动短套" in w for w in p.warnings)
    p2 = lp.plan_lengths(4, mode="equal", target_gap=40.0)
    assert p2.status == "rejected"
    return "目标 8/4 cm：低于动力段下限 10 cm → 拒绝（被动短套）"


def test_gap_15cm_rejected() -> str:
    p = lp.plan_lengths(4, mode="equal", target_gap=150.0)
    assert p.status == "rejected" and not p.feasible
    assert any("端部" in w for w in p.warnings)
    return "目标 15 cm：端部需 60−75 < 30 下限 → 拒绝"


def test_collect_at_min_internal() -> str:
    p = lp.plan_lengths(4, mode="collect")
    assert np.allclose(p.inner, lp.INNER_MIN_MM)       # 收衣 = 回 100 mm
    assert np.allclose(p.ends, (60.0, 60.0))
    assert abs(p.chain_length_mm - 460.0) < TOL
    assert abs(p.gap_mm) < TOL
    assert p.status == "ok" and p.feasible
    return "收衣：[60,100,100,100,60]，链长 460（动力段最短 100）"


def test_small_span_rejected() -> str:
    # D 太小：内部 300 已占满，端部只剩 40 → 低于 30×2 下限 → 拒绝
    p = lp.plan_lengths(4, mode="equal", anchor_span=380.0)
    assert p.status == "rejected" and not p.feasible
    assert any("超过锚定跨度" in w for w in p.warnings)
    return "D=380：端部只剩 40 mm < 2×30 → 拒绝"


def test_one_side_limit_other_compensates() -> str:
    # 端部不对称（120/30）：Δ=+20 需要端部合计 −20 → 05 到下限后溢出回 01
    a, b, un = lp._absorb_ends(20.0, (120.0, 30.0), lp.END_MIN_MM, lp.END_MAX_MM)
    assert abs(a + b - 130.0) < TOL
    assert abs(un) < TOL
    assert abs(a - 100.0) < TOL and abs(b - 30.0) < TOL
    # 下限侧同理：05 已到下限 → 01 补
    a2, b2, un2 = lp._absorb_ends(-20.0, (30.0, 120.0), lp.END_MIN_MM, lp.END_MAX_MM)
    assert abs(a2 + b2 - 170.0) < TOL
    assert abs(a2 - 50.0) < TOL and abs(b2 - 120.0) < TOL
    return f"不对称端部：溢出被另一端吸收（{a:.0f}/{b:.0f}、{a2:.0f}/{b2:.0f}）"


def test_manual_drag_same_side() -> str:
    a, b, un = lp._absorb_ends(20.0, (60.0, 60.0), lp.END_MIN_MM, lp.END_MAX_MM,
                               prefer="left")
    assert abs(a - 40.0) < TOL and abs(b - 60.0) < TOL
    assert abs(un) < TOL
    a2, b2, _ = lp._absorb_ends(-20.0, (60.0, 60.0), lp.END_MIN_MM, lp.END_MAX_MM,
                                prefer="right")
    assert abs(a2 - 60.0) < TOL and abs(b2 - 80.0) < TOL
    return "手动拖：同侧端部优先吸收（01 60→40 / 05 60→80）"


def test_capacity() -> str:
    assert abs(lp.available_length(1200.0) - 1100.0) < TOL
    assert abs(lp.nominal_span(4) - 460.0) < TOL
    assert lp.max_garments(1200.0, 100.0) == 9        # 端部 60
    assert lp.max_garments(1200.0, 100.0, end_mm=30.0) == 10
    return "1.2 m 杆、10 cm：端部 60 → 9 件；端部 30 → 10 件"


def test_k10_span_clamped() -> str:
    # K=10 名义 D=1120 > 可用 1100 → 钳到 1100，端部 50/50
    p = lp.plan_lengths(10, mode="equal", target_gap=100.0)
    assert p.feasible and p.status in ("ok", "partial")
    assert abs(p.anchor_span_mm - 1100.0) < TOL
    assert np.allclose(p.inner, 100.0)
    assert np.allclose(p.ends, (50.0, 50.0))
    assert any("1120" in w and "1100" in w for w in p.warnings)
    return "K=10：D 1120→1100 钳制，端部 50/50（告警不报错）"


def test_validation() -> str:
    bad = [dict(garment_count=1),
           dict(garment_count=4, mode="bogus"),
           dict(garment_count=4, rod_length=0.0),
           dict(garment_count=4, moisture=[0.5, 0.5]),
           dict(garment_count=4, gap_weights=[1.0]),
           dict(garment_count=4, anchor_span=2000.0),
           dict(garment_count=4, current_ends=(20.0, 60.0))]
    for kw in bad:
        try:
            lp.plan_lengths(**kw)
        except ValueError:
            continue
        raise AssertionError(f"应报错：{kw}")
    return "7 类非法输入均被拦截"


def test_chain_layout_anchored() -> str:
    p = lp.plan_lengths(4, mode="equal", target_gap=100.0)
    lay = ch.chain_layout(p)
    assert np.allclose(lay.regulator_edges,
                       [[0, 60], [70, 170], [180, 280], [290, 390], [400, 460]])
    assert np.allclose(lay.garment_centers, [65, 175, 285, 395])
    assert abs(lay.anchor_span_mm - 460.0) < TOL
    assert abs(lay.content_end_mm - 400.0) < TOL
    assert abs(lay.gap_mm) < TOL
    # 12 cm：右端部外端仍在 D=460，内端 430
    p12 = lp.plan_lengths(4, mode="equal", target_gap=120.0)
    lay12 = ch.chain_layout(p12)
    assert abs(lay12.regulator_edges[-1, 1] - 460.0) < TOL
    assert abs(lay12.regulator_edges[-1, 0] - 430.0) < TOL
    assert abs(lay12.content_end_mm - 400.0) < TOL
    return "锚点 0/460 固定；12 cm 时右端内端 430，链末端 400"


def test_clamp_sequence_daily() -> str:
    start = lp.plan_lengths(4, mode="equal", target_gap=120.0)
    end = lp.plan_lengths(4, mode="collect")
    plan = ch.simulate_sequence(start, end, ch.DRIVES[0], strategy="anchor_left")
    # 5 段都动（端部 30→60、内部 120→100），每段 3 个动作 + 压紧
    assert len(plan.steps) == 16
    actions = [s.action for s in plan.steps]
    assert actions.count("clamp_left") == 5
    assert actions.count("move_right") == 5
    assert actions.count("clamp_right") == 5
    assert plan.peak_force_n == 14.0     # 最左端部：2 + 4×3 N
    return f"日常 5 段×3 动作 + 压紧，峰值 {plan.peak_force_n:.0f} N"


def test_anchor_vs_no_clamp() -> str:
    start = lp.plan_lengths(4, mode="equal", target_gap=120.0)
    end = lp.plan_lengths(4, mode="collect")
    d = ch.DRIVES[0]
    a = ch.simulate_sequence(start, end, d, strategy="anchor_left")
    b = ch.simulate_sequence(start, end, d, strategy="anchor_right")
    n = ch.simulate_sequence(start, end, d, strategy="no_clamp")
    assert a.peak_force_n <= n.peak_force_n + 1e-9   # 端部段一动，峰值力与整链推相当
    assert a.untouched_drift_mm == 0.0 and not a.requires_redatum
    assert n.requires_redatum and np.isnan(n.untouched_drift_mm)
    assert n.peak_current_a > a.peak_current_a * 2
    assert a.max_block_garments == 4 and b.max_block_garments == 4
    return (f"锚定峰值 {a.peak_force_n:.0f} N vs 整链推 {n.peak_force_n:.0f} N；"
            f"电流 {a.peak_current_a:.2f} vs {n.peak_current_a:.2f} A")


def test_daily_vs_setup_time() -> str:
    rows = ch.daily_cycle_study(garment_counts=(4,))["rows"]
    daily = rows[0][ch.DRIVES[0].name]["time_s"]
    fast = rows[0][ch.DRIVES[1].name]["time_s"]
    setup = ch.setup_study(garment_count=4)["time_s"]
    assert 60 < daily < 140, daily
    assert fast < daily
    assert setup > 0
    return (f"4 mm/s 校核 {daily:.1f} s；7 mm/s {fast:.1f} s；"
            f"安装标定 {setup:.1f} s")


def test_deterministic() -> str:
    q = [0.55, 0.90, 0.35, 0.75]
    a = lp.demo_plans(4, q)
    b = lp.demo_plans(4, q)
    for k in a:
        assert np.array_equal(a[k].inner, b[k].inner)
        assert a[k].ends == b[k].ends
    return "三模式方案齐备，重复调用一致"


TESTS = [
    test_default_install_state,
    test_equal_12cm_ends_absorb,
    test_then_collect_from_12cm,
    test_target_20cm_rejected,
    test_low_gap_rejected,
    test_gap_15cm_rejected,
    test_collect_at_min_internal,
    test_small_span_rejected,
    test_one_side_limit_other_compensates,
    test_manual_drag_same_side,
    test_capacity,
    test_k10_span_clamped,
    test_validation,
    test_chain_layout_anchored,
    test_clamp_sequence_daily,
    test_anchor_vs_no_clamp,
    test_daily_vs_setup_time,
    test_deterministic,
]


def run_all_tests(verbose: bool = True) -> tuple:
    passed = 0
    for fn in TESTS:
        msg = fn()
        passed += 1
        if verbose:
            print(f"  [test] {fn.__name__:<34s} OK  —  {msg}")
    if verbose:
        print(f"[test] v2 单元测试：{passed}/{len(TESTS)} 通过")
    return passed, len(TESTS)


if __name__ == "__main__":
    try:
        passed, total = run_all_tests()
    except AssertionError as exc:
        print(f"[test] FAILED: {exc}")
        raise SystemExit(1)
    print(f"\n全部通过：{passed}/{total}")
