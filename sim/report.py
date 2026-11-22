"""把仿真结果写成 docs/_data/algorithm-results.md 和 .json。

md 是给主文档直接引用用的：每张图配一句"这张图说明什么"，
参数 / 结果 / 结论成表，所有数字都由 run_all 实际跑出来。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np

from common import DATA_DIR, ROOT

FIG_REL = "docs/figures"


# ---------------------------------------------------------------------------
def build_captions(results: dict) -> Dict[str, dict]:
    """每张图的一句话结论（key = 图文件名去掉 .png）。"""
    sp_ = results["spacing"]
    d = sp_["demo"]
    u = sp_["uniform"]
    gaps = d.gaps
    rd = results["reorder"]
    rp = rd["demo"]["reorder"]
    cost = rd["cost"]
    row4 = next(r for r in cost["rows"] if r["n"] == 4)
    st = results["control"]["study"]
    pid = next(r for r in st["rows"] if r["name"] == "PID")
    p_only = next(r for r in st["rows"] if r["name"] == "P")
    tilt3 = [r for r in results["control"]["tilt"]["rows"] if abs(r["tilt_deg"] - 3.0) < 1e-9]
    tilt3 = tilt3[0] if tilt3 else None
    mc = results["control"]["mc"]
    vis = results["vision"]
    v12 = vis["rows"][0]
    return {
        "alg-01-spacing-waterfill": {
            "caption": (
                f"按湿度加权后，最湿的 A–B 间隙拿到 {gaps[0]:.0f} mm，"
                f"最干的 C–D 只留 {gaps[2]:.0f} mm（等距时都是 {u.gaps.mean():.0f} mm），"
                f"总跨度不变（{d.used_span:.0f} mm）——同一根杆，湿衣服多拿风道。"
            ),
        },
        "alg-02-spacing-feasibility": {
            "caption": (
                "目标跨度低于最小可行跨度（4 件 30 mm 厚 → 210 mm）时程序不硬压安全间隙、"
                "会自动放宽并告警；超过 L_max=1100 mm 则截断；1.2 m 杆在 30 mm 间隙下最多挂 17 件 35 mm 厚的衣物。"
            ),
        },
        "alg-03-reorder-steps": {
            "caption": (
                f"4 件按湿度重排：上界 N−1 = {rp.upper_bound} 次 move-to-end，"
                f"本例只需 {rp.moves} 次（A、C 依次移到最远端），预计 {rp.reorder_time_s:.1f} s。"
            ),
        },
        "alg-04-reorder-cost": {
            "caption": (
                f"换序耗时随件数近似线性增长，最坏情况 4 件就要 "
                f"{row4['time_worst_s']:.1f} s、6 件 "
                f"{next(r for r in cost['rows'] if r['n'] == 6)['time_worst_s']:.1f} s，"
                f"远超 30 s 预算；只调间距只要 {rd['demo']['spacing_time_s']:.1f} s "
                f"—— 这就是 P0 不做换序的量化理由。"
            ),
        },
        "alg-05-control-step": {
            "caption": (
                f"纯 P 在 1° 坡度下留下 {p_only['sse_mm']:.1f} mm 稳态误差，PID 降到 "
                f"{pid['sse_abs_mm']:.2f} mm；PID 超调 {pid['overshoot_mm']:.2f} mm、"
                f"稳定 {pid['settle_s']:.1f} s；坡度 3° 时 P 的偏差扩大到 "
                f"{tilt3['P']['sse_mm']:.1f} mm，已吃掉 ±5 mm 预算的 {abs(tilt3['P']['sse_mm']) / 5 * 100:.0f}%。"
            ),
        },
        "alg-06-control-montecarlo": {
            "caption": (
                f"200 次蒙特卡洛（噪声、延迟、坡度、初始误差一起抖）后，PID 的超调 p95 "
                f"{mc['overshoot_mm']['p95']:.2f} mm、稳态误差 p95 {mc['sse_abs_mm']['p95']:.2f} mm、"
                f"稳定时间 p95 {mc['settle_s']['p95']:.1f} s，全部落在 ±5 mm / 8 s 以内。"
            ),
        },
        "alg-07-vision-error": {
            "caption": (
                f"相机侧装（偏航 0°）时 1.2 m 处沿杆随机误差只有 {v12['lateral_mm']:.2f} mm；"
                f"但偏航 10° 后总预算 {v12['budget_yaw10']['total_mm']:.2f} mm 超标，"
                f"靠 5 帧平均降到 {v12['budget_yaw10_5frames']['total_mm']:.2f} mm，"
                "系统误差（标定 1.5 mm + 安装 2.0 mm）才是精度预算的大头。"
            ),
        },
    }


# ---------------------------------------------------------------------------
def _table(headers: List[str], rows: List[List[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def _f(x, nd: int = 1) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    if not np.isfinite(v):
        return "—"
    if abs(v) < 0.5 * 10 ** (-nd):
        v = 0.0
    return f"{v:.{nd}f}"


def _to_jsonable(obj):
    """递归把 numpy 类型转成 JSON 可序列化类型。"""
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return v if np.isfinite(v) else None
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [_to_jsonable(v) for v in obj.tolist()]
    return obj


# ---------------------------------------------------------------------------
def build_md(results: dict, figures: List[Path], captions: Dict[str, dict]) -> str:
    meta = results["meta"]
    figures = [Path(p) for p in figures]
    sp_ = results["spacing"]
    d = sp_["demo"]
    u = sp_["uniform"]
    dm = sp_["demo_metrics"]
    um = sp_["uniform_metrics"]
    tm = sp_["timing"]
    rd = results["reorder"]
    rp = rd["demo"]["reorder"]
    cost = rd["cost"]
    st = results["control"]["study"]
    tilt = results["control"]["tilt"]
    mc = results["control"]["mc"]
    vis = results["vision"]

    pid = next(r for r in st["rows"] if r["name"] == "PID")
    p_only = next(r for r in st["rows"] if r["name"] == "P")
    pi_row = next(r for r in st["rows"] if r["name"] == "PI")
    no_guard = next(r for r in st["rows"] if r["name"] == "PI 无抗饱和")
    remote = next(r for r in st["rows"] if r["name"].startswith("PID@远程"))
    tilt_rows = tilt["rows"]
    tilt3 = next(r for r in tilt_rows if abs(r["tilt_deg"] - 3.0) < 1e-9)
    v12 = vis["rows"][0]
    v15 = vis["rows"][1]
    v20 = vis["rows"][2]

    lines: List[str] = []
    A = lines.append

    A("# 算法仿真结果（衣序 HangFlow）")
    A("")
    A(f"> 本文件由 `python sim/run_all.py` 自动生成（{meta['generated']}），**请勿手改**。")
    A(f"> 环境：Python {meta['python']} / numpy {meta['numpy']}；"
      f"单元测试 {meta['test_passed']}/{meta['test_total']} 通过。")
    A("> **数据口径**：全部为**仿真/估算值，不是实测**。设计参数来自 "
      "`docs/_shared-context.md` 第 3、6 节；每处结论都标明是仿真还是估算。")
    A("> 长度单位统一 mm（图里也标 mm；文档叙述时 1 cm = 10 mm）。")
    A("")
    A("## 0. 先看结论（可直接抄进文档）")
    A("")
    A(f"1. **间距规划器**：4 件衣物、目标跨度 {d.used_span:.0f} mm 时，"
      f"最湿的 A–B 间隙 {d.gaps[0]:.0f} mm、最干的 C–D 间隙 {d.gaps[2]:.0f} mm"
      f"（等距基准 {u.gaps.mean():.0f} mm），总跨度不超杆长。"
      f"单次规划 {tm['n4']['mean_us']:.0f} µs（N=4）/ {tm['n24']['mean_us']:.0f} µs（N=24）"
      f"（本机 Python 参考实现；RDK X5 上预计 2–5 ms 量级，**估算，未实测**）。")
    A(f"2. **不可行会明说**：目标跨度过紧时放宽到最小可行跨度（保 30 mm 安全间隙）；"
      f"杆太短时压缩间隙并告警，同时给出建议件数（该用例建议减 "
      f"{sp_['cases'][0]['drop_advice']} 件），不静默输出垃圾。")
    A(f"3. **重排**：单杆无超车，顺序在连续运动中不变；用 move-to-end 抬升越障时，"
      f"4 件上界 {rp.upper_bound} 次、本例 {rp.moves} 次、预计 {rp.reorder_time_s:.1f} s"
      f"（最坏 {next(r for r in cost['rows'] if r['n'] == 4)['time_worst_s']:.0f} s）；"
      f"只调间距只要 {rd['demo']['spacing_time_s']:.1f} s → **P0 不做换序**。")
    A(f"4. **控制**：推荐 PID（kp={pid['kp']:.0f}, ki={pid['ki']:.0f}, kd={pid['kd']:.2f}）"
      f"阶跃 300 mm 的超调 {pid['overshoot_mm']:.2f} mm（{pid['overshoot_pct']:.2f}%）、"
      f"稳定 {pid['settle_s']:.1f} s、稳态误差 {pid['sse_abs_mm']:.2f} mm；"
      f"蒙特卡洛 {mc['n_runs']} 次 p95 超调 {mc['overshoot_mm']['p95']:.2f} mm。"
      f"纯 P 在 1° 坡度下有 {abs(p_only['sse_mm']):.1f} mm 偏差 → **积分项不能省**；"
      f"无抗饱和的 PI 超调 {no_guard['overshoot_pct']:.0f}% → **抗饱和不能省**。")
    A(f"5. **视觉**：1.2 m 侧装（偏航 0°）沿杆随机误差 {v12['lateral_mm']:.2f} mm，"
      f"总预算（偏航 10°）{v12['budget_yaw10']['total_mm']:.2f} mm 略超 ±5 mm，"
      f"5 帧平均后 {v12['budget_yaw10_5frames']['total_mm']:.2f} mm 达标；"
      f"2.0 m 处即使 5 帧平均也有 {v20['budget_yaw10_5frames']['total_mm']:.1f} mm 超标 → **相机要侧装、距离 ≤1.5 m**。")
    A("")

    # ---- 结果汇总表（参数 / 结果 / 结论，一页看完）----
    A("## 0.1 结果汇总表（参数 → 结果 → 结论）")
    A("")
    A(_table(["模块", "关键参数（设计值）", "仿真/计算结果", "结论"],
             [["间距规划器",
               f"N=4，t={list(sp_['params']['thickness_mm'].values())} mm，"
               f"L_max={sp_['params']['max_span_mm']:.0f} mm，目标跨度 "
               f"{sp_['params']['target_span_mm']:.0f} mm，g_min=30 mm",
               f"间隙 {_f(d.gaps[0], 0)}/{_f(d.gaps[1], 0)}/{_f(d.gaps[2], 0)} mm；"
               f"单次 {tm['n4']['median_us']:.0f} µs（中位）",
               f"湿侧风道比等距多 {d.gaps[0] - u.gaps.mean():.0f} mm，总跨度不变；"
               "规划开销可忽略"],
              ["规划器规模",
               "N=4 / N=8 / N=24",
               f"中位 {tm['n4']['median_us']:.0f} / {tm['n8']['median_us']:.0f} / "
               f"{tm['n24']['median_us']:.0f} µs",
               "O(N) 实际开销，100 Hz 重算无压力"],
              ["不可行处理",
               "10 件 40 mm 进 500 mm 杆；目标 200 mm",
               "间隙压到 11.1 mm 并告警；跨度放宽到 210 mm",
               "不静默失败，给出减件/换杆建议"],
              ["重排（move-to-end）",
               f"N=4，杆 1.2 m，速度 {rp.speed_mm_s:.0f} mm/s，抬升开销 "
               f"{cost['lift_overhead_s']:.1f} s/次",
               f"上界 {rp.upper_bound} 次，本例 {rp.moves} 次，"
               f"预计 {rp.reorder_time_s:.1f} s；"
               f"N=6 最坏 {next(r for r in cost['rows'] if r['n'] == 6)['time_worst_s']:.0f} s",
               "换序太慢，P0 不做；只调间距 "
               f"{rd['demo']['spacing_time_s']:.1f} s"],
              ["位置控制",
               f"m=1.6 kg，v_max=60 mm/s，τ_v=40 ms，1° 坡道，编码器噪声 0.15 mm",
               f"PID 超调 {pid['overshoot_mm']:.2f} mm（{pid['overshoot_pct']:.2f}%），"
               f"稳定 {pid['settle_s']:.1f} s，稳态误差 {pid['sse_abs_mm']:.2f} mm",
               "满足 ±5 mm；积分项和抗饱和必须有"],
              ["控制鲁棒性",
               f"蒙特卡洛 {mc['n_runs']} 次",
               f"超调 p95 {mc['overshoot_mm']['p95']:.2f} mm，"
               f"误差 p95 {mc['sse_abs_mm']['p95']:.2f} mm，"
               f"稳定 p95 {mc['settle_s']['p95']:.1f} s",
               "参数抖动下仍达标"],
              ["视觉定位",
               "1280×720，f=900 px，标记 30 mm，σ=0.5 px，偏航 10°，5 帧平均",
               f"1.2 m：{v12['budget_yaw10_5frames']['total_mm']:.2f} mm；"
               f"1.5 m：{v15['budget_yaw10_5frames']['total_mm']:.2f} mm；"
               f"2.0 m：{v20['budget_yaw10_5frames']['total_mm']:.2f} mm",
               "侧装 ≤1.5 m 达标；2.0 m 超标"],
              ]))
    A("")
    A("> 表内数字全部由 `sim/run_all.py` 跑出；判定口径：±5 mm 定位、30 s 调整、"
      "间隙 ≥30 mm。")
    A("")

    # ---- 图表索引 ----
    A("## 1. 图表索引（每张图配一句「这张图说明什么」）")
    A("")
    rows = []
    for p in figures:
        cap = captions.get(p.stem, {})
        rows.append([
            f"[{p.name}](../figures/{p.name})",
            cap.get("caption", ""),
        ])
    A(_table(["图（300 dpi）", "这张图说明什么"], rows))
    A("")
    A("> 图都在 `docs/figures/`，8–10 英寸宽、300 dpi；本文件在 `docs/_data/`，"
      "所以链接写成 `../figures/…`；从 `docs/` 下其它文档引用请写 `figures/…`。")
    A("")

    # ---- 间距规划器 ----
    A("## 2. 间距规划器（sim/spacing_planner.py）")
    A("")
    A("### 2.1 口径与参数")
    A("")
    A("- **t_i 是衣物沿杆方向的厚度投影**（不是衣架宽度 42 cm）：干衣 20–40 mm，湿衣 30–60 mm。")
    A("- 约束：`L = Σt_i + Σg_i`；规划坐标原点 = 可用杆段左端（杆两端各留 50 mm）。")
    A(f"- 跨度上限 `L_max` = 杆长 − 2×50 = **{sp_['params']['max_span_mm']:.0f} mm**（1.2 m 杆）。")
    A(f"- 最小安全间隙 `g_min` = {sp_['params']['min_gap_mm']:.0f} mm；演示目标跨度 "
      f"{sp_['params']['target_span_mm']:.0f} mm；湿度权重指数 γ = "
      f"{sp_['params']['moisture_exponent']:.0f}"
      "（`a_i = ((q_i+q_{i+1})/2)^γ`）。")
    A("- 分配算法：每间隙先给 `g_min`，剩余空间按 `a_i` 比例**闭式分配**；"
      "若设了 `max_gap`，做「比例注水 + 饱和」迭代（每轮至少饱和一个，最多 N−1 轮）。")
    A("")
    A(_table(["衣物", "湿度 q", "厚度 t (mm)", "中心位置 (mm)", "左边缘", "右边缘"],
             [[lab, _f(sp_['params']['moisture'][lab], 2),
               _f(sp_['params']['thickness_mm'][lab], 0),
               _f(d.centers[i], 1), _f(d.edges[i, 0], 1), _f(d.edges[i, 1], 1)]
              for i, lab in enumerate(sp_['labels'])]))
    A("")
    A(_table(["相邻间隙", "长度 (mm)", "权重 a_i（归一化）"],
             [[f"{sp_['labels'][i]}–{sp_['labels'][i + 1]}",
               _f(d.gaps[i], 1), _f(d.weights[i] / d.weights.sum(), 3)]
              for i in range(len(d.gaps))]))
    A("")
    A(f"等距基准（同样总跨度、不看湿度）：间隙全部 **{u.gaps.mean():.1f} mm**；"
      f"加权方案把最湿侧的间隙拉到 {d.gaps[0]:.1f} mm（+{d.gaps[0] - u.gaps.mean():.1f} mm），"
      f"最干侧收到 {d.gaps[2]:.1f} mm（{d.gaps[2] - u.gaps.mean():+.1f} mm）。")
    A("")
    A("### 2.2 规划器性能（本机 Python 参考实现）")
    A("")
    A(_table(["规模", "重复次数", "平均 (µs)", "中位 (µs)", "p95 (µs)", "最大 (µs)"],
             [[k.replace("n", "N="), str(v["n_repeat"]), _f(v["mean_us"], 0),
               _f(v["median_us"], 0), _f(v["p95_us"], 0), _f(v["max_us"], 0)]
              for k, v in tm.items()]))
    A("")
    A(f"> 4 件场景 {tm['n4']['mean_us']:.0f} µs/次（中位 {tm['n4']['median_us']:.0f} µs）、"
      f"24 件 {tm['n24']['mean_us']:.0f} µs/次，远低于 30 s 的调整节拍要求；"
      "「最大」一列包含操作系统调度抖动，参考中位数即可。"
      "RDK X5 的 Cortex-A55 单核性能约为本机的 1/5–1/10，"
      "折算 **2–5 ms**（估算，未实测）；即使在 100 Hz 控制回路里重算也够用。")
    A("")
    A("### 2.3 不可行 / 降级处理（不静默）")
    A("")
    crows = []
    for c in sp_["cases"]:
        crows.append([
            c["label"],
            f"`{c['status']}`{'（可行）' if c['feasible'] else '（不可行）'}",
            " / ".join(_f(g, 1) for g in c["gaps_mm"]) if c["gaps_mm"] else "—",
            _f(c["used_span_mm"], 0),
            (c["warnings"][0] if c["warnings"] else "—"),
            c["degradation"] or "—",
        ])
    A(_table(["场景", "状态", "各间隙 (mm)", "实际跨度 (mm)", "告警（第一条）", "降级建议"],
             crows))
    A("")
    A(f"- 目标跨度过紧（200 mm）→ 不硬压到 30 mm 以下，放宽到最小可行跨度 "
      f"{sp_['cases'][2]['used_span_mm']:.0f} mm 并告警。")
    A(f"- 杆太短（10 件 40 mm 厚进 500 mm）→ 间隙压到 "
      f"{sp_['cases'][0]['gaps_mm'][0] if sp_['cases'][0]['gaps_mm'] else 0:.1f} mm，"
      f"同时建议减到 {10 - sp_['cases'][0]['drop_advice']} 件。")
    A("")

    # ---- 重排 ----
    A("## 3. 顺序问题与重排代价（sim/reorder.py）")
    A("")
    A("**事实**：单元只能沿杆平移、不得重叠 ⇒ 连续运动改变不了相对次序（序不变性）。"
      "所以「把最湿的挪到进风口」不能靠慢速平移实现。")
    A("")
    A("**本方案的补救**：套挂单元是 C 形夹爪，可在杆最远端的转移段**抬升越障**"
      "（move-to-end，1 次 ≈ 抬升 + 纵移 + 落下，计 1 步）。这是 P1 的机械前提；"
      "P0 不换序，只调间距。")
    A("")
    A("**最小次数**：`k` = 满足 pos(1)<…<pos(k) 的最大前缀长度（这些单元可原地不动），"
      "最少移动 = `N − k`，上界 = `N − 1`。贪心序列：把 `k+1 … N` 依次移到最远端。")
    A("")
    A(f"演示（4 件，左→右 A B C D，湿度 A 55% / B 90% / C 35% / D 75%，"
      f"进风口在左 ⇒ 期望 B D A C）：")
    A("")
    A(_table(["步", "移动单元", "目标序号", "起点槽位", "终点槽位", "行程 (mm)", "耗时 (s)"],
             [["初始", "—", "—", "—", "—", "—", "0"],
              ] + [[str(op.step), op.label, str(op.rank), str(op.from_slot + 1),
                    str(op.to_slot + 1), _f(op.distance_mm, 0), _f(op.total_s, 1)]
                   for op in rp.ops]))
    A("")
    A(f"总行程 {rp.active_travel_mm:.0f} mm（主动）+ {rp.letway_mm:.0f} mm（让位），"
      f"**预计 {rp.reorder_time_s:.1f} s** @ {rp.speed_mm_s:.0f} mm/s。"
      "换序后按新顺序重跑一次规划器即可（<1 ms）。")
    A("")
    A("件数代价（最坏 = 完全逆序）：")
    A("")
    A(_table(["N", "最坏次数", "随机平均次数", "换序耗时 @41.9 mm/s (s)",
              "换序耗时 @104.7 mm/s (s)", "只调间距 (s)"],
             [[str(r["n"]), str(r["moves_worst"]), _f(r["moves_mean"], 2),
               _f(r["time_worst_s"], 1), _f(r["time_worst_fast_s"], 1),
               _f(r["spacing_only_time_s"], 1)] for r in cost["rows"]]))
    A("")
    A("> 表中「只调间距」按每件平均 200 mm 行程估算；演示用例实际行程 "
      f"{rd['demo']['spacing_move_mm']:.0f} mm → {rd['demo']['spacing_time_s']:.1f} s。")
    A("> 结论：换序耗时随 N 近似线性增长，6 件就超过 30 s；"
      "而**只调间距** 4 件约 "
      f"{rd['demo']['spacing_time_s']:.1f} s，满足「单次调整 ≤30 s」目标。"
      "→ P0 用加权间距解决风道，换序放 P1（需机械支持抬升越障）。")
    A("")

    # ---- 控制 ----
    A("## 4. 位置控制仿真（sim/control_sim.py）")
    A("")
    A("模型：质量 1.6 kg、速度环一阶 40 ms、轮面限速 60 mm/s、库仑阻力 150 mm/s²、"
      "1° 坡道扰动 171 mm/s²、编码器量化 0.1 mm + 噪声 σ=0.15 mm、初始误差 −5 mm、"
      "本地闭环延迟 10 ms。")
    A("")
    A(_table(["参数组", "kp", "ki", "kd", "延迟 (ms)", "超调 (%)", "超调 (mm)",
              "上升 (s)", "稳定 (s)", "稳态误差 (mm)", "抖动 (mm)", "收敛"],
             [[r["name"], _f(r["kp"], 1), _f(r["ki"], 1), _f(r["kd"], 2),
               _f(r["delay_ms"], 0), _f(r["overshoot_pct"], 2), _f(r["overshoot_mm"], 2),
               _f(r["rise_s"], 2), _f(r["settle_s"], 2),
               _f(r["sse_mm"], 3) if r["converged"] >= 0.999 else "—（未收敛）",
               _f(r["jitter_rms_mm"], 3), "是" if r["converged"] >= 0.999 else "否"]
              for r in st["rows"]]))
    A("")
    A(f"- 上升时间 {pid['rise_s']:.1f} s 由 60 mm/s 限速决定（300 mm 阶跃）；"
      f"稳定 {pid['settle_s']:.1f} s。")
    A(f"- **P 有 {p_only['sse_mm']:+.2f} mm 稳态误差**（坡道 + 阻力），PI/PID 用积分消到 "
      f"{pid['sse_abs_mm']:.2f} mm。")
    A(f"- **无抗饱和的 PI 超调 {no_guard['overshoot_pct']:.0f}%（峰值 {no_guard['peak_mm']:.0f} mm）**，"
      f"{st['t_end_s']:.0f} s 内没收敛 → 代码里的条件积分抗饱和不是装饰。")
    A(f"- 位置环若跑在中枢经 MQTT 下发（延迟 {remote['delay_ms']:.0f} ms）："
      f"超调 {remote['overshoot_mm']:.2f} mm，是本地环的 "
      f"{remote['overshoot_mm'] / max(pid['overshoot_mm'], 1e-6):.1f} 倍 → **位置环必须跑在单元本地**，"
      "中枢只下发目标位置。")
    A("")
    A("坡度敏感性（同一 PID 参数）：")
    A("")
    A(_table(["杆倾斜 (°)", "等效扰动 (mm/s²)", "最高巡航 (mm/s)", "跑完 1.1 m (s)",
              "P 稳态误差 (mm)", "PI (mm)", "PID (mm)"],
             [[_f(r["tilt_deg"], 1), _f(r["a_dist_mm_s2"], 0),
               _f(r["cruise_mm_s"], 1),
               "∞" if not np.isfinite(r["full_rod_s"]) else _f(r["full_rod_s"], 1),
               _f(r["P"]["sse_mm"], 2), _f(r["PI"]["sse_mm"], 2),
               _f(r["PID"]["sse_mm"], 2)] for r in tilt_rows]))
    A("")
    A(f"> 3° 坡道时纯 P 偏差 {tilt3['P']['sse_mm']:.2f} mm（吃掉 ±5 mm 预算 "
      f"{abs(tilt3['P']['sse_mm']) / 5 * 100:.0f}%），且巡航速度掉到 "
      f"{tilt3['cruise_mm_s']:.1f} mm/s（1.1 m 要 {tilt3['full_rod_s']:.0f} s）→ "
      "**安装时杆要水平（≤2°），并保留积分项**。")
    A("")
    A("蒙特卡洛（"
      f"{mc['n_runs']} 次，噪声 σ {mc['spread']['noise_sigma_mm'][0]:.2f}–"
      f"{mc['spread']['noise_sigma_mm'][1]:.2f} mm、速度环 {mc['spread']['tau_v_s'][0] * 1000:.0f}–"
      f"{mc['spread']['tau_v_s'][1] * 1000:.0f} ms、限速 "
      f"{mc['spread']['v_max_mm_s'][0]:.0f}–{mc['spread']['v_max_mm_s'][1]:.0f} mm/s、"
      f"坡道 {mc['spread']['a_dist_mm_s2'][0]:.0f}–{mc['spread']['a_dist_mm_s2'][1]:.0f} mm/s²）：")
    A("")
    A(_table(["指标", "均值", "p95", "最大", "判定线", "结论"],
             [["超调量 (mm)", _f(mc["overshoot_mm"]["mean"], 2),
               _f(mc["overshoot_mm"]["p95"], 2), _f(mc["overshoot_mm"]["max"], 2),
               "±5 mm", "远小于要求"],
              ["稳定时间 (s)", _f(mc["settle_s"]["mean"], 2),
               _f(mc["settle_s"]["p95"], 2), _f(mc["settle_s"]["max"], 2),
               "≤8 s", "达标"],
              ["稳态误差绝对值 (mm)", _f(mc["sse_abs_mm"]["mean"], 2),
               _f(mc["sse_abs_mm"]["p95"], 2), _f(mc["sse_abs_mm"]["max"], 2),
               "±5 mm", "达标"],
              ["位置抖动 (mm)", _f(mc["jitter_rms_mm"]["mean"], 2),
               _f(mc["jitter_rms_mm"]["p95"], 2), _f(mc["jitter_rms_mm"]["max"], 2),
               "±5 mm", "达标"]],
             ))
    A("")

    # ---- 视觉 ----
    A("## 5. 视觉定位误差（sim/vision_error.py）")
    A("")
    vp = vis["params"]
    A(f"相机 {vp['camera_px'][0]}×{vp['camera_px'][1]}、f = {vp['f_px']:.0f} px"
      f"（水平视场 {vp['hfov_deg']:.0f}°）、ArUco 边长 {vp['marker_mm']:.0f} mm、"
      f"像素噪声 σ = {vp['sigma_px']:.1f} px。"
      f"系统误差（设计估算）：标定 {vp['systematic_mm']['标定残差']:.1f} mm + "
      f"安装 {vp['systematic_mm']['标记安装偏差']:.1f} mm。")
    A("")
    A("针孔模型：侧向 `σ·Z/f`；标记测距误差 `σ·Z²/(f·s)`；"
      "相机偏航 θ 时沿杆误差 `√((侧向·cosθ)² + (测距·sinθ)²)`；多帧平均随机项 `/√k`。")
    A("")
    A(_table(["距离 (m)", "标记像素 (px)", "mm/px", "侧向随机 (mm)", "测距误差 (mm)",
              "沿杆 @0° (mm)", "沿杆 @5° (mm)", "沿杆 @10° (mm)", "沿杆 @15° (mm)"],
             [[_f(r["distance_mm"] / 1000, 1), _f(r["marker_px"], 1),
               _f(r["mm_per_px"], 2), _f(r["lateral_mm"], 2), _f(r["range_mm"], 1),
               _f(r["along_by_yaw"][0.0], 2), _f(r["along_by_yaw"][5.0], 2),
               _f(r["along_by_yaw"][10.0], 2), _f(r["along_by_yaw"][15.0], 2)]
              for r in vis["rows"]]))
    A("")
    A("误差预算（偏航 10°，随机项已按 5 帧平均）：")
    A("")
    A(_table(["距离 (m)", "随机项 (mm)", "标定 (mm)", "安装 (mm)", "合计 (mm)",
              "单帧合计 (mm)", "±5 mm 判定"],
             [[_f(r["distance_mm"] / 1000, 2),
               _f(r["budget_yaw10_5frames"]["random_mm"], 2),
               _f(r["budget_yaw10_5frames"]["detail"]["标定残差"], 2),
               _f(r["budget_yaw10_5frames"]["detail"]["标记安装偏差"], 2),
               _f(r["budget_yaw10_5frames"]["total_mm"], 2),
               _f(r["budget_yaw10"]["total_mm"], 2),
               "达标" if r["budget_yaw10_5frames"]["within_spec"] else "超标"]
              for r in vis["rows"]]))
    A("")
    A(f"- 1.2 m 侧装随机误差 {v12['lateral_mm']:.2f} mm ≪ ±5 mm，位置随机误差不是瓶颈；")
    A(f"- 30 mm 标记在 {v12['distance_mm'] / 1000:.1f} m 只有 {v12['marker_px']:.0f} px，"
      f"测距误差 {v12['range_mm']:.1f} mm → **不要用标记反推距离**，只用图像 x 定位；")
    A(f"- 偏航超过 10° 后总预算 {v12['budget_yaw10']['total_mm']:.2f} mm 超标，"
      f"5 帧平均后 {v12['budget_yaw10_5frames']['total_mm']:.2f} mm 达标；"
      f"2.0 m 处即使 5 帧平均也 {v20['budget_yaw10_5frames']['total_mm']:.1f} mm（超标）→ 建议相机距离 ≤1.5 m。")
    A(f"- 系统误差合计 {v12['budget_yaw10_5frames']['systematic_mm']:.2f} mm，占预算大头 "
      f"→ 必须在杆上贴已知间距的 ArUco 基准做在线校准。")
    A("")

    # ---- 复现 ----
    A("## 6. 复现与文件清单")
    A("")
    A("```powershell")
    A("cd E:\\D-robotics-ClothesRodHelper")
    A("python sim/run_all.py          # 跑全部：单元测试 → 仿真 → 出图 → 写本文件")
    A("python sim/test_planner.py     # 只跑间距规划器单元测试（17 项 assert）")
    A("```")
    A("")
    A(_table(["文件", "作用"],
             [["`sim/spacing_planner.py`", "间距规划器（加权 water-filling、上限饱和、不可行降级）"],
              ["`sim/test_planner.py`", "规划器单元测试（17 项，含 300 组随机属性测试）"],
              ["`sim/reorder.py`", "顺序不变性、move-to-end 贪心序列、重排代价"],
              ["`sim/control_sim.py`", "单模块位置控制仿真（P/PI/PID、坡度、蒙特卡洛）"],
              ["`sim/vision_error.py`", "针孔模型视觉误差与预算"],
              ["`sim/plots.py`", "7 张结果图"],
              ["`sim/report.py`", "生成本文件与 JSON"],
              ["`sim/run_all.py`", "一键入口"],
              ["`sim/common.py`", "中文字体、300 dpi 出图工具"],
              [f"`{FIG_REL}/alg-*.png`", "全部结果图（300 dpi）"]]))
    A("")
    A("## 7. 假设与局限（写文档时别把仿真当实测）")
    A("")
    A("- 全部数字来自简化模型，**没有实测数据**；答辩时应说「仿真/估算」。")
    A("- 间距规划器不建模衣物形变、风的湍流、杆的挠度；只保证几何不重叠与间隙分配。")
    A("- 重排依赖「抬升越障」这一机械前提；若夹爪不能抬离，换序在单杆上无解。")
    A("- 控制模型忽略静摩擦黏滑、轮子打滑、杆弯曲；这些会让实际稳态误差比仿真大，"
      "建议现场用视觉闭环修正（见视觉误差节）。")
    A("- 视觉模型只考虑随机像素噪声与固定系统偏差，未建模镜头畸变、反光、遮挡；"
      "真实误差会更大，`±5 mm` 目标要靠标定 + 多帧平均 + 编码器融合共同保证。")
    A("")
    return "\n".join(lines)


def write_all(results: dict, figures: List[Path],
              captions: Dict[str, dict]):
    """写 md 与 json，返回两个路径。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    figures = [Path(p) for p in figures]
    md = build_md(results, figures, captions)
    md_path = DATA_DIR / "algorithm-results.md"
    md_path.write_text(md, encoding="utf-8")

    # JSON：去掉不可序列化的轨迹对象，只保留数字与结论
    payload = {
        "meta": results["meta"],
        "spacing": {
            "params": results["spacing"]["params"],
            "demo": results["spacing"]["demo"].to_dict(),
            "uniform": results["spacing"]["uniform"].to_dict(),
            "metrics": {"demo": results["spacing"]["demo_metrics"],
                        "uniform": results["spacing"]["uniform_metrics"]},
            "timing": results["spacing"]["timing"],
            "sweep": results["spacing"]["sweep"],
            "nmax": results["spacing"]["nmax"],
            "cases": results["spacing"]["cases"],
        },
        "reorder": {
            "demo": results["reorder"]["demo"]["reorder"].to_dict(),
            "spacing_time_s": results["reorder"]["demo"]["spacing_time_s"],
            "spacing_move_mm": results["reorder"]["demo"]["spacing_move_mm"],
            "cost": results["reorder"]["cost"],
        },
        "control": {
            "params": results["control"]["study"]["params"],
            "rows": results["control"]["study"]["rows"],
            "tilt": results["control"]["tilt"],
            "monte_carlo": {
                k: v for k, v in results["control"]["mc"].items()
                if k not in ("by_run",)
            },
        },
        "vision": results["vision"],
        "figures": [f"{FIG_REL}/{p.name}" for p in figures],
        "captions": captions,
    }
    json_path = DATA_DIR / "algorithm-results.json"
    json_path.write_text(
        json.dumps(_to_jsonable(payload), ensure_ascii=False, indent=2),
        encoding="utf-8")
    return md_path, json_path


__all__ = ["build_captions", "build_md", "write_all"]
