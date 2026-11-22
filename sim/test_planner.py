"""间距规划器单元测试（纯 assert，不依赖 pytest）。

运行：
    python sim/test_planner.py      # 单独跑
    python sim/run_all.py           # run_all 里也会跑（验收要求）

覆盖：闭式加权分配、跨度守恒、上限饱和、杆太短/太挤降级、居中、确定性、
随机属性测试（300 组随机构型，检查不重叠/不出界/间隙下界）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from spacing_planner import (
    END_CLEARANCE_MM,
    MIN_GAP_MM,
    _waterfill,
    max_garments,
    move_distance,
    plan_metrics,
    plan_spacing,
    usable_span,
)

TOL = 1e-6


# ---------------------------------------------------------------------------
def test_usable_span() -> str:
    """1.2 m 杆、两端各留 5 cm → 可用跨度 1100 mm。"""
    assert abs(usable_span(1200.0) - 1100.0) < TOL
    assert abs(usable_span(1200.0, 50.0) - 1100.0) < TOL
    assert abs(usable_span(800.0, 60.0) - 680.0) < TOL
    return "可用杆长 L_max = 杆长 − 2×50mm"


def test_equal_weights_equal_gaps() -> str:
    """无湿度信息 → 间隙严格等距，且总跨度守恒。"""
    t = [25.0, 40.0, 30.0, 45.0]
    p = plan_spacing(t, max_span=1100.0, target_span=480.0)
    assert p.feasible and p.status == "ok"
    assert p.gaps.size == 3
    expect = (480.0 - sum(t)) / 3.0
    assert np.allclose(p.gaps, expect, atol=1e-6), (p.gaps, expect)
    assert abs(p.used_span - 480.0) < TOL
    return f"等湿度 → 间隙全部 {expect:.2f} mm"


def test_span_conserved() -> str:
    """有湿度权重时，Σt + Σg == 目标总跨度。"""
    t = [25.0, 40.0, 30.0, 55.0]
    p = plan_spacing(t, max_span=1100.0, target_span=480.0,
                     moisture=[0.95, 0.4, 0.8, 0.2])
    assert abs(p.used_span - 480.0) < TOL
    assert abs(p.used_span - (p.thickness.sum() + p.gaps.sum())) < TOL
    return "Σ厚度 + Σ间隙 = 480.0 mm"


def test_wetter_gap_wider() -> str:
    """湿衣服两侧的间隙更宽（指数权重 gamma=2 时比例 = 权重比）。"""
    t = [30.0, 30.0, 30.0]
    p = plan_spacing(t, max_span=1100.0, target_span=480.0,
                     moisture=[1.0, 0.2, 0.6], moisture_exponent=2.0)
    w0 = ((1.0 + 0.2) / 2) ** 2
    w1 = ((0.2 + 0.6) / 2) ** 2
    expect_ratio = w0 / w1
    got_ratio = (p.gaps[0] - MIN_GAP_MM) / (p.gaps[1] - MIN_GAP_MM)
    assert abs(got_ratio - expect_ratio) < 1e-6, (got_ratio, expect_ratio)
    assert p.gaps[0] > p.gaps[1]
    return f"湿侧间隙 {p.gaps[0]:.1f} mm > 干侧 {p.gaps[1]:.1f} mm"


def test_gap_cap_saturated() -> str:
    """g_max 生效：所有间隙钉在上限，多出的空间转端部留白并告警。"""
    t = [30.0] * 4
    p = plan_spacing(t, max_span=1100.0, target_span=600.0, max_gap=100.0)
    assert p.feasible
    assert np.allclose(p.gaps, 100.0, atol=1e-6)
    assert abs(p.used_span - (120.0 + 300.0)) < TOL
    assert len(p.warnings) == 1 and "上限" in p.warnings[0]
    return "间隙上限 100 mm 生效，实际跨度 420 mm"


def test_rod_too_short_compressed() -> str:
    """杆太短：间隙压到 g_min 以下 → feasible=False、有告警与降级建议。"""
    t = [40.0] * 10
    p = plan_spacing(t, max_span=500.0, target_span=500.0)
    assert p.status == "compressed" and not p.feasible
    assert p.drop_advice > 0
    g = (500.0 - 400.0) / 9.0
    assert np.allclose(p.gaps, g, atol=1e-6)
    assert g < MIN_GAP_MM
    assert any("间隙被压到" in w for w in p.warnings)
    assert p.degradation.startswith("降级方案")
    return f"10 件压到 {g:.1f} mm（<30 mm），建议 ≤{10 - p.drop_advice} 件"


def test_infeasible_too_wide() -> str:
    """衣物总厚度超过杆长 → infeasible，不允许假装可行。"""
    t = [45.0] * 12
    p = plan_spacing(t, max_span=500.0)
    assert p.status == "infeasible" and not p.feasible
    assert p.drop_advice > 0
    assert any("物理上放不下" in w for w in p.warnings)
    return "540 mm 衣物塞 500 mm 杆 → 判为 infeasible"


def test_target_too_tight_relaxed() -> str:
    """目标跨度小于最小可行跨度 → 不牺牲 3 cm 安全间隙，放宽并告警。"""
    t = [30.0] * 4
    p = plan_spacing(t, max_span=1100.0, target_span=200.0)
    s_min = 120.0 + 3 * MIN_GAP_MM
    assert p.feasible
    assert abs(p.used_span - s_min) < TOL
    assert any("太紧" in w for w in p.warnings)
    return f"目标 200 mm → 放宽到 {s_min:.0f} mm（保 30 mm 间隙）"


def test_target_exceeds_span_clipped() -> str:
    """目标跨度超过 L_max → 截断并告警。"""
    t = [30.0] * 4
    p = plan_spacing(t, max_span=400.0, target_span=900.0)
    assert abs(p.used_span - 400.0) < TOL
    assert any("超过可用杆长" in w for w in p.warnings)
    return "目标 900 mm → 截到 L_max=400 mm"


def test_single_garment() -> str:
    """单件：无间隙，居中。"""
    p = plan_spacing([30.0], max_span=1100.0)
    assert p.gaps.size == 0
    assert abs(p.centers[0] - 550.0) < TOL
    assert p.feasible and any("1 件" in w for w in p.warnings)
    return "单件居中于 550 mm"


def test_centered_layout() -> str:
    """规划块在可用杆段内居中，且位置不越界。"""
    t = [25.0, 40.0, 30.0, 45.0]
    p = plan_spacing(t, max_span=1100.0, target_span=480.0)
    assert p.block_left > 0 and p.block_right < 1100.0
    left_space = p.block_left
    right_space = 1100.0 - p.block_right
    assert abs(left_space - right_space) < TOL
    return f"左侧留白 {left_space:.1f} mm = 右侧"


def test_move_distance() -> str:
    """调整行程 = 各件 |Δx| 之和。"""
    t = [30.0] * 4
    p = plan_spacing(t, max_span=1100.0, target_span=480.0)
    cur = p.centers + 10.0
    assert abs(move_distance(p, cur) - 40.0) < TOL
    return "4 件各偏 10 mm → 总行程 40 mm"


def test_deterministic() -> str:
    """同一输入两次调用结果一致（便于复现报告里的数字）。"""
    kw = dict(max_span=1100.0, target_span=480.0,
              moisture=[0.95, 0.4, 0.8, 0.2])
    a = plan_spacing([25.0, 40.0, 30.0, 55.0], **kw)
    b = plan_spacing([25.0, 40.0, 30.0, 55.0], **kw)
    assert np.array_equal(a.gaps, b.gaps)
    assert np.array_equal(a.centers, b.centers)
    return "两次调用完全一致"


def test_max_garments() -> str:
    """件数上界：35 mm 厚 + 30 mm 间隙，1.2 m 杆 → 17 件。"""
    n = max_garments(1200.0, [35.0] * 30, min_gap=30.0,
                     end_clearance=END_CLEARANCE_MM)
    # 35k + 30(k-1) <= 1100 → k <= 17.38
    assert n == 17, n
    assert max_garments(1200.0, [60.0] * 30) == 12  # 60k+30(k-1)<=1100 → k<=12.5
    return "35 mm 厚 → 17 件；60 mm 厚 → 12 件"


def test_waterfill_mass_and_cap() -> str:
    """water-filling 守恒：分配量 + 剩余 = 总量；饱和槽正好等于上限。"""
    w = np.array([1.0, 2.0, 3.0])
    shares, sat, left = _waterfill(60.0, w)
    assert abs(shares.sum() + left - 60.0) < TOL
    assert np.allclose(shares, 60.0 * w / w.sum())
    cap = np.array([5.0, 20.0, 100.0])
    shares2, sat2, left2 = _waterfill(200.0, w, cap)
    assert abs(shares2.sum() + left2 - 200.0) < TOL
    assert shares2[0] <= cap[0] + TOL and shares2[1] <= cap[1] + TOL
    assert np.allclose(shares2, cap) and sat2.all()
    assert abs(left2 - 75.0) < TOL  # 200 − (5+20+100)
    return "分配守恒，饱和槽钉在上限，余量 75 mm"


def test_validation_errors() -> str:
    """非法输入必须报错（不静默返回垃圾）。"""
    bad = [
        (dict(thicknesses=[], max_span=1100.0), "空输入"),
        (dict(thicknesses=[30.0, -5.0], max_span=1100.0), "负厚度"),
        (dict(thicknesses=[30.0], max_span=0.0), "杆长为 0"),
        (dict(thicknesses=[30.0, 30.0], max_span=1100.0, moisture=[0.5]), "湿度长度不符"),
        (dict(thicknesses=[30.0, 30.0], max_span=1100.0, min_gap=50.0, max_gap=40.0), "g_max<g_min"),
    ]
    for kwargs, why in bad:
        try:
            plan_spacing(**kwargs)
        except ValueError:
            continue
        raise AssertionError(f"应报错但没有：{why}")
    return "5 类非法输入均被拦截"


def test_random_property() -> str:
    """随机属性测试：300 组随机构型，检查不重叠 / 不出界 / 间隙下界。"""
    rng = np.random.default_rng(20261123)
    checked = 0
    for _ in range(300):
        n = int(rng.integers(1, 10))
        t = rng.uniform(20.0, 60.0, n)
        max_span = float(rng.uniform(300.0, 1100.0))
        target = float(rng.choice([max_span, rng.uniform(200.0, 1100.0)]))
        q = rng.uniform(0.0, 1.0, n)
        p = plan_spacing(t, max_span=max_span, target_span=target, moisture=q)
        assert p.gaps.size == max(n - 1, 0)
        # 不重叠：下一个左边缘 - 上一个右边缘 == 间隙
        if n >= 2:
            sep = p.edges[1:, 0] - p.edges[:-1, 1]
            assert np.allclose(sep, p.gaps, atol=1e-6)
            assert np.all(p.gaps >= -1e-9)
        # 居中/不越界（仅可行时）
        if p.feasible:
            assert np.all(p.gaps >= MIN_GAP_MM - 1e-6)
            assert p.used_span <= max_span + 1e-6
            assert p.edges[0, 0] >= -1e-6
            assert p.edges[-1, 1] <= max_span + 1e-6
        # 指标可用
        m = plan_metrics(p)
        assert m["n"] == n and np.isfinite(m["used_span_mm"])
        checked += 1
    return f"{checked} 组随机构型全部通过"


TESTS = [
    test_usable_span,
    test_equal_weights_equal_gaps,
    test_span_conserved,
    test_wetter_gap_wider,
    test_gap_cap_saturated,
    test_rod_too_short_compressed,
    test_infeasible_too_wide,
    test_target_too_tight_relaxed,
    test_target_exceeds_span_clipped,
    test_single_garment,
    test_centered_layout,
    test_move_distance,
    test_deterministic,
    test_max_garments,
    test_waterfill_mass_and_cap,
    test_validation_errors,
    test_random_property,
]


def run_all_tests(verbose: bool = True) -> tuple:
    """跑全部测试，返回 (passed, total)。失败直接抛 AssertionError。"""
    passed = 0
    for fn in TESTS:
        msg = fn()
        passed += 1
        if verbose:
            print(f"  [test] {fn.__name__:<32s} OK  —  {msg}")
    if verbose:
        print(f"[test] 间距规划器单元测试：{passed}/{len(TESTS)} 通过")
    return passed, len(TESTS)


if __name__ == "__main__":
    try:
        passed, total = run_all_tests()
    except AssertionError as exc:
        print(f"[test] FAILED: {exc}")
        raise SystemExit(1)
    print(f"\n全部通过：{passed}/{total}")
