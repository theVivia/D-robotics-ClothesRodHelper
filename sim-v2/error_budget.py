"""衣序 HangFlow v2 —— 净风道误差预算（目标 ±2 mm）。

口径
----
* 「净风道」= 圆柱长度 L_i，由丝杆 + AS5600 闭环直接决定；
* 视觉只做 ID 识别与位置校验，**不进长度闭环**，所以视觉 1–3 mm 不计入；
* 机械链路各项按「±值」给出（设计/估算），统计上按 σ = ±值/2 的高斯处理，
  再用蒙特卡洛给出合成分布与 P(|误差| ≤ 2 mm)。

各项来源
--------
| 项 | ±值 (mm) | 依据 |
|---|---|---|
| 丝杆导程误差 | 0.037 | T8 轧制丝杆 ±0.05 mm / 300 mm，行程 ≤220 mm 折算 |
| AS5600 分辨率 | 0.002 | 12 bit/圈，导程 8 mm → 8/4096 |
| 反向间隙（补偿后） | 0.04 | 仿真：单向逼近 + b/2 补偿后的残余 |
| 控制稳态误差 | 0.03 | 仿真：T8/8 @4 mm/s 阶跃 |
| 接缝/衣架定位公差 | 0.50 | 10 mm 接缝内加定位筋（设计值，**最大项**） |
| 温度漂移 | 0.10 | −5–45 °C，铝件 + 塑料件 |
| 链弹性变形 | 0.10 | 17 N 张力下丝杆/壳体压缩（估算） |
| 编码器噪声 | 0.01 | AS5600 量化 + 抖动 |
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

SPEC_MM = 2.0

# (名称, ±值 mm, 依据)
TERMS: List[Tuple[str, float, str]] = [
    ("丝杆导程误差", 0.037, "T8 轧制 ±0.05/300 mm，行程 ≤480 mm"),
    ("AS5600 分辨率", 0.002, "12 bit/圈 ÷ 导程 8 mm"),
    ("反向间隙（补偿后）", 0.04, "仿真：单向逼近 + b/2 补偿残余"),
    ("控制稳态误差", 0.03, "仿真：T8/8 @4 mm/s 阶跃"),
    ("衣架/端面定位公差", 0.50, "调节器自由端面与衣架钩的贴合公差（设计值，最大项）"),
    ("夹持重复定位", 0.10, "双端夹持每次重夹的杆上位置重复性（设计值）"),
    ("端部预紧变形", 0.05, "10 N 顶墙力下壳体/杆的弹性压缩（估算）"),
    ("温度漂移", 0.10, "−5–45 °C"),
    ("编码器噪声", 0.01, "AS5600 抖动"),
]

# 不计入闭环、只影响「显示」的项
EXCLUDED: List[Tuple[str, float, str]] = [
    ("视觉中心定位", 2.0, "只用于 ID 校验与显示，不进 L_i 闭环"),
    ("衣架钩在杆上偏摆", 0.5, "衣架自由转动，不传递轴向力"),
]


def rss(terms: List[Tuple[str, float, str]] = TERMS) -> float:
    """均方根合成（各项视为独立）。"""
    return float(np.sqrt(sum(v * v for _, v, _ in terms)))


def worst_case(terms: List[Tuple[str, float, str]] = TERMS) -> float:
    """最坏线性叠加（同一方向）。"""
    return float(sum(v for _, v, _ in terms))


def contributions(terms: List[Tuple[str, float, str]] = TERMS) -> List[dict]:
    total2 = sum(v * v for _, v, _ in terms)
    out = []
    for name, v, why in terms:
        out.append({"name": name, "tol_mm": float(v),
                    "share_pct": float(100.0 * v * v / total2),
                    "basis": why})
    out.sort(key=lambda d: -d["share_pct"])
    return out


def monte_carlo(n_runs: int = 20000, seed: int = 20261123,
                terms: List[Tuple[str, float, str]] = TERMS) -> dict:
    """按 σ = ±值/2 高斯抽样，给合成误差分布。"""
    rng = np.random.default_rng(seed)
    err = np.zeros(n_runs)
    for _, v, _ in terms:
        err += rng.normal(0.0, v / 2.0, n_runs)
    abs_err = np.abs(err)
    return {
        "n_runs": int(n_runs),
        "mean_mm": float(err.mean()),
        "std_mm": float(err.std()),
        "p95_abs_mm": float(np.percentile(abs_err, 95)),
        "p999_abs_mm": float(np.percentile(abs_err, 99.9)),
        "max_abs_mm": float(abs_err.max()),
        "p_within_spec": float(np.mean(abs_err <= SPEC_MM)),
        "samples_mm": err,
    }


def seam_tolerance_scenario() -> dict:
    """灵敏度：接缝定位公差从 0.5 放到 2.0 mm 会怎样（说明为什么必须有定位筋）。"""
    good = list(TERMS)
    bad = [(n, v, why) for n, v, why in TERMS]
    bad = [(n, (2.0 if n == "接缝/衣架定位公差" else v), why)
           for n, v, why in bad]
    return {
        "good": {"rss_mm": rss(good), "worst_mm": worst_case(good)},
        "bad": {"rss_mm": rss(bad), "worst_mm": worst_case(bad)},
        "spec_mm": SPEC_MM,
        "good_ok": bool(rss(good) <= SPEC_MM),
        "bad_ok": bool(rss(bad) <= SPEC_MM),
    }


def budget_study() -> dict:
    rows = [{"name": n, "tol_mm": float(v), "basis": why}
            for n, v, why in TERMS]
    mc = monte_carlo()
    return {
        "spec_mm": SPEC_MM,
        "rows": rows,
        "excluded": [{"name": n, "tol_mm": float(v), "basis": why}
                     for n, v, why in EXCLUDED],
        "rss_mm": rss(),
        "worst_case_mm": worst_case(),
        "contributions": contributions(),
        "monte_carlo": {k: v for k, v in mc.items() if k != "samples_mm"},
        "samples_mm": mc["samples_mm"],
        "seam_scenario": seam_tolerance_scenario(),
    }


__all__ = ["SPEC_MM", "TERMS", "EXCLUDED", "rss", "worst_case",
           "contributions", "monte_carlo", "seam_tolerance_scenario",
           "budget_study"]

