"""sim-v2（rev-C）单元测试：K+1 调节器、端部固定配置、双端锥面夹头。

覆盖：长度规划（内部/端部）、端部不填满杆、leftover、三模式、fill 模式、
不可行降级、链位置递推、夹持顺序与力、锚定策略对比、安装 vs 日常耗时。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

import chain as ch  # noqa: E402
import length_planner as lp  # noqa: E402

TOL = 1e-6


def test_available_and_capacity() -> str:
    assert abs(lp.available_length(1200.0) - 1100.0) < TOL
    assert lp.max_garments(1200.0, 100.0) == 9    # 9×10+8×100+120 ≤ 1100
    assert lp.max_garments(1200.0, 40.0) == 20
    return "1.2 m 杆（端部 60×2）：10 cm 风道 → 9 件；4 cm → 20 件"


def test_equal_plan_not_filling_rod() -> str:
    p = lp.plan_lengths(4, mode="equal", target_gap=100.0)
    assert p.feasible and p.status == "ok"
    assert np.allclose(p.inner, 100.0)
    assert np.allclose(p.ends, lp.END_CONFIG_MM)          # 端部固定 60，不填杆
    assert p.regulator_count == 5
    assert abs(p.chain_length_mm - 460.0) < TOL           # 60+300+60+40
    assert abs(p.leftover_mm - 640.0) < TOL               # 空杆 / 端部锁位区
    assert not p.wall_contact
    assert p.to_dict()["all_lengths_mm"] == [60.0, 100.0, 100.0, 100.0, 60.0]
    assert any("空心杆段" in w or "锁位区" in w for w in p.warnings)
    return "等距：[60,100,100,100,60]，链 460 mm，空杆 640 mm"


def test_weighted_keeps_chain() -> str:
    q = [0.55, 0.90, 0.35, 0.75]
    base = lp.plan_lengths(4, mode="equal", target_gap=100.0)
    p = lp.plan_lengths(4, mode="weighted", target_gap=100.0, moisture=q)
    assert abs(p.inner_total_mm - base.inner_total_mm) < TOL
    assert np.allclose(p.ends, base.ends)
    assert abs(p.chain_length_mm - base.chain_length_mm) < TOL
    assert np.all(p.inner >= lp.INNER_MIN_MM - 1e-9)
    assert np.all(p.inner <= lp.INNER_MAX_MM + 1e-9)
    assert p.inner[0] > p.inner[2]
    return f"加权内部段 {p.inner.round(1).tolist()}，链长不变"


def test_collect_holds_ends() -> str:
    p = lp.plan_lengths(4, mode="collect")
    assert np.allclose(p.inner, lp.INNER_MIN_MM)
    assert np.allclose(p.ends, lp.END_CONFIG_MM)
    assert abs(p.chain_length_mm - 280.0) < TOL
    assert abs(p.leftover_mm - 820.0) < TOL
    return "收衣：内部 40×3，链 280 mm，空杆 820 mm"


def test_fill_mode_optional() -> str:
    p = lp.plan_lengths(4, mode="collect", fill=True)
    assert np.allclose(p.ends, (lp.END_MAX_MM, lp.END_MAX_MM))
    assert p.status == "clipped"
    assert any("fill" in w for w in p.warnings)
    # 1.2 m 杆太长，fill 也填不满（端部上限 120）
    assert p.leftover_mm > 0
    return "fill 模式：端部补到 120 上限，仍剩空杆 → 告警"


def test_gap_clamp() -> str:
    p = lp.plan_lengths(4, mode="equal", target_gap=300.0)
    assert p.status == "clipped"
    assert np.allclose(p.inner, lp.INNER_MAX_MM)
    assert any("夹到" in w for w in p.warnings)
    return "目标 300 mm → 夹到 INNER_MAX=220 mm"


def test_too_long_compresses() -> str:
    p = lp.plan_lengths(11, mode="equal", target_gap=100.0)
    assert p.status == "clipped" and p.feasible
    assert p.inner.mean() < 100.0
    assert p.chain_length_mm <= p.available_mm + 1e-6
    p2 = lp.plan_lengths(23, mode="equal", target_gap=100.0)
    assert p2.status == "infeasible" and not p2.feasible
    assert p2.drop_advice > 0
    return f"11 件压到 {p.inner.mean():.1f} mm；23 件判不可行"


def test_validation() -> str:
    bad = [dict(garment_count=1),
           dict(garment_count=4, mode="bogus"),
           dict(garment_count=4, rod_length=0.0),
           dict(garment_count=4, moisture=[0.5, 0.5]),
           dict(garment_count=4, gap_weights=[1.0]),
           dict(garment_count=4, end_lengths=(10.0, 60.0))]
    for kw in bad:
        try:
            lp.plan_lengths(**kw)
        except ValueError:
            continue
        raise AssertionError(f"应报错：{kw}")
    return "6 类非法输入均被拦截"


def test_chain_layout() -> str:
    p = lp.plan_lengths(4, mode="equal", target_gap=100.0)
    lay = ch.chain_layout(p)
    assert np.allclose(lay.regulator_edges,
                       [[0, 60], [70, 170], [180, 280], [290, 390], [400, 460]])
    assert np.allclose(lay.garment_centers, [65, 175, 285, 395])
    assert abs(lay.chain_end_mm - 460.0) < TOL
    assert abs(lay.right_gap_mm - 640.0) < TOL
    assert not lay.wall_contact
    return "位置：5 段端点 + 4 个衣架中心 65/175/285/395"


def test_clamp_sequence() -> str:
    start = lp.plan_lengths(4, mode="collect")
    end = lp.plan_lengths(4, mode="equal")
    plan = ch.simulate_sequence(start, end, ch.DRIVES[0], strategy="anchor_left")
    # 只动内部 3 段，每段 3 个动作
    assert len(plan.steps) == 9
    actions = [s.action for s in plan.steps]
    assert actions.count("clamp_left") == 3
    assert actions.count("move_right") == 3
    assert actions.count("clamp_right") == 3
    for s in plan.steps:
        if s.action == "move_right":
            assert s.clamp_before.left and not s.clamp_before.right
    assert plan.peak_force_n == 11.0
    assert plan.clamp_actions == 6
    return f"3 段×3 动作，峰值 {plan.peak_force_n:.0f} N，{plan.clamp_actions} 次夹持"


def test_anchor_vs_no_clamp() -> str:
    start = lp.plan_lengths(4, mode="collect")
    end = lp.plan_lengths(4, mode="equal")
    d = ch.DRIVES[0]
    a = ch.simulate_sequence(start, end, d, strategy="anchor_left")
    b = ch.simulate_sequence(start, end, d, strategy="anchor_right")
    n = ch.simulate_sequence(start, end, d, strategy="no_clamp")
    assert a.peak_force_n < n.peak_force_n
    assert a.untouched_drift_mm == 0.0 and not a.requires_redatum
    assert n.requires_redatum and np.isnan(n.untouched_drift_mm)
    assert n.peak_current_a > a.peak_current_a * 2
    assert a.max_block_garments == 3 and b.max_block_garments == 3
    return (f"锚定峰值 {a.peak_force_n:.0f} N vs 整链推 {n.peak_force_n:.0f} N；"
            f"电流 {a.peak_current_a:.2f} vs {n.peak_current_a:.2f} A")


def test_daily_vs_setup_time() -> str:
    rows = ch.daily_cycle_study(garment_counts=(4,))["rows"]
    daily = rows[0][ch.DRIVES[0].name]["time_s"]
    fast = rows[0][ch.DRIVES[1].name]["time_s"]
    setup = ch.setup_study(garment_count=4)["time_s"]
    assert 35 < daily < 80, daily
    assert fast < daily
    assert setup > daily
    return (f"4 mm/s 校核 {daily:.1f} s；提速 7 mm/s {fast:.1f} s；"
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
    test_available_and_capacity,
    test_equal_plan_not_filling_rod,
    test_weighted_keeps_chain,
    test_collect_holds_ends,
    test_fill_mode_optional,
    test_gap_clamp,
    test_too_long_compresses,
    test_validation,
    test_chain_layout,
    test_clamp_sequence,
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
            print(f"  [test] {fn.__name__:<32s} OK  —  {msg}")
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
