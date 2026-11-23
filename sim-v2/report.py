"""把 v2（rev-B）仿真结果写成 docs/_data-v2/results.md 与 .json。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np

from common import DATA_DIR, ROOT

FIG_REL = "docs/figures-v2"


def build_captions(results: dict) -> Dict[str, dict]:
    eq = results["plans"]["equal"]
    wt = results["plans"]["weighted"]
    co = results["plans"]["collect"]
    cmp = results["chain"]["demo"]["comparison"]
    a = cmp["锚定左墙（推荐）"]
    b = cmp["不锁端（整链推）"]
    daily = results["timing"]["rows"]
    d4 = next(r for r in daily if r["K"] == 4)
    setup = results["setup"]
    rows = results["control"]["study"]["rows"]
    lead8 = rows[0]          # T4/8 @4 mm/s 校核（DRIVES[0]）
    drv = lead8["drive"]
    bl = results["backlash"]["rows"]
    stall = results["stall"]
    budget = results["budget"]
    mc = budget["monte_carlo"]
    vis = results["vision"]
    acq = vis["acq_1p5m_30mm"]
    return {
        "v2-01-length-plan": {
            "caption": (
                f"4 件衣服 = 5 个调节器：等距时端部 L0/L4 各 {eq.ends[0]:.0f} mm（安装配置值，不填满杆）、"
                f"内部 3 段各 100 mm，链长 {eq.chain_length_mm:.0f} mm，"
                f"还剩 {eq.leftover_mm:.0f} mm 空杆（端部夹头锁位区）；"
                f"加权模式只重分内部段（{wt.inner.round(0).tolist()}），"
                f"收衣把内部缩到 40 mm、端部不动 → 链长 {co.chain_length_mm:.0f} mm。"
            ),
        },
        "v2-02-chain-order": {
            "caption": (
                f"每个调节器有 L/R 两个夹持：锁一端就能单向伸缩、只推动相邻衣架；"
                f"锚定左墙逐段调，峰值轴向力 {a['peak_force_n']:.0f} N / 电流 {a['peak_current_a']:.2f} A，"
                f"已定位段 0 滑移；不锁端整链推则 {b['peak_force_n']:.0f} N / {b['peak_current_a']:.2f} A，"
                f"且必须重新标定全部衣架位置。"
            ),
        },
        "v2-03-timing": {
            "caption": (
                f"按 4 mm/s 校核，日常工况（收衣→等距、只动内部 3 段）4 件要 "
                f"{d4[results['timing']['drives'][0]]['time_s']:.1f} s，**超 30 s**；"
                f"把轴向速度提到 7 mm/s 后 {d4[results['timing']['drives'][1]]['time_s']:.1f} s 达标——"
                f"所以驱动选型要按 ≥7 mm/s 选（T8 导程 8 mm + 50 rpm 以上）。"
                f"安装标定（端部也要伸长）一次性 {setup['time_s']:.0f} s。"
            ),
        },
        "v2-04-control": {
            "caption": (
                f"长度闭环 40→100 mm：{drv} 上升 {lead8['rise_s']:.1f} s、"
                f"稳态误差 {lead8['sse_mm']:+.2f} mm、超调 {lead8['overshoot_mm']:.2f} mm；"
                f"0.2 mm 反向间隙在负载侧只剩 "
                f"±{max(abs(r['error_mm']) for r in bl) * 1000:.0f} µm；"
                f"2 s 卡死时 {stall['detect_time_s'] * 1000:.0f} ms 判出堵转。"
            ),
        },
        "v2-05-error-budget": {
            "caption": (
                f"净风道误差 RSS {budget['rss_mm']:.2f} mm（最坏叠加 "
                f"{budget['worst_case_mm']:.2f} mm），{mc['n_runs']} 次蒙特卡洛里 "
                f"{mc['p_within_spec'] * 100:.1f}% 落在 ±2 mm 内；最大项是"
                f"衣架/端面定位公差 0.5 mm（占方差 {budget['contributions'][0]['share_pct']:.0f}%），"
                f"丝杆和编码器都不是瓶颈。"
            ),
        },
        "v2-06-vision-id": {
            "caption": (
                f"真实 ArUco 检测器在 6–8 px 才掉识别率，1.5 m、30 mm 标记有 18 px，余量 2 倍以上；"
                f"限制项是遮挡——3 帧去抖后 {vis['params']['n_units']} 个 ID 全认全 "
                f"{acq['success_rate'] * 100:.1f}%、p95 {acq['p95_s']:.2f} s，"
                f"认不出时用长度反馈 + 固定顺序降级。"
            ),
        },
    }


def _table(headers: List[str], rows: List[List[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
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
    params = results["planner_params"]
    plans = results["plans"]
    eq, wt, co = plans["equal"], plans["weighted"], plans["collect"]
    ptime = results["planner_timing"]
    cases = results["plan_cases"]
    cap = results["capacity"]
    demo = results["chain"]["demo"]
    cmp = demo["comparison"]
    a = cmp["锚定左墙（推荐）"]
    b = cmp["不锁端（整链推）"]
    c = cmp["锚定右墙"]
    setup = results["setup"]
    plan_case = results["timing"]
    rows = results["control"]["study"]["rows"]
    lead8 = rows[0]          # T4/8 @4 mm/s 校核（DRIVES[0]）
    drv = lead8["drive"]
    bl = results["backlash"]["rows"]
    stall = results["stall"]
    limits = results["limits"]
    budget = results["budget"]
    mc = budget["monte_carlo"]
    vis = results["vision"]
    acq = vis["acq_1p5m_30mm"]

    L: List[str] = []
    A = L.append

    A("# v2 算法与控制仿真结果（衣序 HangFlow · rev-C）")
    A("")
    A(f"> 本文件由 `python sim-v2/run_all.py` 自动生成（{meta['generated']}），**请勿手改**。")
    A(f"> 环境：Python {meta['python']} / numpy {meta['numpy']}；"
      f"单元测试 {meta['test_passed']}/{meta['test_total']} 通过。")
    A("> **数据口径**：全部为**仿真/估算值，不是实测**。结构口径来自 "
      "`docs/_shared-context-v2.md` 与 lead 2026-11-23 的结构澄清（K 件衣服 = K+1 个调节器）。")
    A("")

    A("## 0. 先看结论")
    A("")
    A(f"1. **结构**：K 件衣服配 **K+1 个调节器**（两端各 1、内部 K−1）。"
      f"内部段 = 净风道，端部段 = 安装配置值（演示 60 mm，范围 30–120 mm）；"
      f"端部段**不填满杆**，取消恒力卷簧。等距工况 4 件 → 5 段 "
      f"`{eq.all_lengths.round(0).astype(int).tolist()}`，"
      f"链长 {eq.chain_length_mm:.0f} mm、空杆 {eq.leftover_mm:.0f} mm。")
    A(f"2. **端部不再填杆**：可行性只看 `ΣL + K·t_h ≤ 可用长度`，"
      f"剩余 {eq.leftover_mm:.0f} mm 是空杆 / 端部夹头锁位区（不要求贴墙）。"
      f"所以 1.2 m 杆挂 4 件是「杆长富余」：同一根杆 10 cm 风道能挂 9 件（§2.3）；"
      f"产品上 4 件建议配 0.5–0.6 m 杆，现场演示保留 1.2 m 亦可。")
    A(f"3. **调节顺序**：锚定左墙、从左往右逐段「先锁靠基准侧那端 → 伸缩自由端 → "
      f"锁死另一端」。峰值力 {a['peak_force_n']:.0f} N、电流 {a['peak_current_a']:.2f} A，"
      f"已定位段 0 滑移；不锁端整链推要 {b['peak_force_n']:.0f} N、{b['peak_current_a']:.2f} A，"
      f"还要重新标定全部衣架。")
    A(f"4. **耗时**：按 **4 mm/s** 校核，日常（收衣→等距，只动内部 3 段）4 件要 "
      f"{plan_case['rows'][1][plan_case['drives'][0]]['time_s']:.1f} s，**超 30 s**；"
      f"提到 **7 mm/s** 后 {plan_case['rows'][1][plan_case['drives'][1]]['time_s']:.1f} s 达标 → "
      f"驱动按 ≥7 mm/s 选（T8 导程 8 mm，≥50 rpm）。"
      f"安装标定（端部也要伸长）一次性 {setup['time_s']:.0f} s。")
    A(f"5. **长度闭环**：{drv} 阶跃 40→100 mm 上升 {lead8['rise_s']:.1f} s、"
      f"稳态误差 {lead8['sse_mm']:+.2f} mm、超调 {lead8['overshoot_mm']:.2f} mm；"
      f"0.2 mm 反向间隙 + 单向逼近补偿后残余 "
      f"{max(abs(r['error_mm']) for r in bl) * 1000:.0f} µm；堵转 "
      f"{stall['detect_time_s'] * 1000:.0f} ms 判出。")
    A(f"6. **误差预算**：RSS **{budget['rss_mm']:.2f} mm**、最坏 {budget['worst_case_mm']:.2f} mm，"
      f"±2 mm 目标可达（蒙特卡洛 {mc['p_within_spec'] * 100:.1f}%）；"
      f"最大项是衣架/端面定位公差，视觉 2 mm 不进闭环。")
    A("")

    A("## 1. 图表索引（每张图一句「这张图说明什么」）")
    A("")
    rows_t = []
    for p in figures:
        rows_t.append([f"[{p.name}](../figures-v2/{p.name})",
                       captions.get(p.stem, {}).get("caption", "")])
    A(_table(["图（300 dpi）", "这张图说明什么"], rows_t))
    A("")
    A("> 图在 `docs/figures-v2/`，9–10 英寸宽、300 dpi。")
    A("")

    A("## 2. 长度规划（sim-v2/length_planner.py）")
    A("")
    A("### 2.1 结构与变量")
    A("")
    A(_table(["符号", "含义", "值"],
             [["K", "衣物件数", "演示 4（2–8）"],
              ["K+1", "调节器数量（两端各 1）", "演示 5"],
              ["t_h", "衣架沿杆厚度", f"{params['t_h_mm']:.0f} mm"],
              ["L_i", "内部段 = 净风道",
               f"[{params['inner_min_mm']:.0f}, {params['inner_max_mm']:.0f}] mm"],
              ["L_0/L_K", "端部段 = 安装配置值（**不填满杆**）",
               f"默认 {params['end_config_mm']:.0f} mm，范围 "
               f"[{params['end_min_mm']:.0f}, {params['end_max_mm']:.0f}] mm"],
              ["墙距", "可用长度 = 杆长 − 2×50", f"{params['available_mm']:.0f} mm"],
              ["链长", "ΣL + K·t_h（4 件等距 = 460 mm）",
               "460 mm"],
              ["空杆", "剩余杆段 = 端部夹头锁位区", "640 mm（演示）"],
              ["目标风道", "一键等距", f"{params['target_gap_mm']:.0f} mm"]]))
    A("")
    A("位置递推（x 从左侧墙算起，调节器 0 在墙边）：")
    A("")
    A("```")
    A("调节器 i 占 [x_i, x_i + L_i]；x_0 = 0")
    A("衣物 i 中心 = x_i + L_i + t_h/2          # 挂在调节器 i−1 与 i 之间")
    A("x_{i+1} = 衣物 i 中心 + t_h/2 = x_i + L_i + t_h")
    A("链长 = ΣL + K·t_h ≤ 可用长度；剩余 = 空杆 / 端部夹头锁位区（不要求贴墙）")
    A("```")
    A("")
    A("### 2.2 三模式结果（4 件 / 5 段）")
    A("")
    A(_table(["模式", "L0 / L1 / L2 / L3 / L4 (mm)", "内部总和 (mm)", "链长 (mm)",
              "空杆 (mm)"],
             [[{"equal": "等距", "weighted": "加权", "collect": "收衣"}[k],
               " / ".join(_f(v, 1) for v in plans[k].all_lengths),
               _f(plans[k].inner_total_mm, 1),
               _f(plans[k].chain_length_mm, 1),
               _f(plans[k].leftover_mm, 1)]
              for k in ("equal", "weighted", "collect")]))
    A("")
    A(f"加权模式：总风道不变（{wt.inner_total_mm:.0f} mm），只按湿度权重重分内部段；"
      "权重 `a_i = ((q_i+q_{i+1})/2)^γ`（γ=2），有上限时用比例注水 + 饱和。")
    A("")
    A("可选 `fill=True` 模式（把空杆余量补进端部段，端部仍受 30–120 mm 上限）：")
    A("")
    A(_table(["模式", "L0 / L4 (mm)", "链长 (mm)", "剩余空杆 (mm)", "状态"],
             [[{"equal": "等距", "weighted": "加权", "collect": "收衣"}[k],
               f"{_f(results['plans_fill'][k].ends[0], 0)} / "
               f"{_f(results['plans_fill'][k].ends[1], 0)}",
               _f(results['plans_fill'][k].chain_length_mm, 0),
               _f(results['plans_fill'][k].leftover_mm, 0),
               results['plans_fill'][k].status]
              for k in ("equal", "weighted", "collect")]))
    A("")
    A("> 1.2 m 杆对 4 件来说太长：fill 也只能把端部补到 120 mm 上限，仍剩 ~700 mm，"
      "程序会告警。演示默认用固定 60 mm 端部、接受空杆；产品上 4 件配 0.5–0.6 m 杆更紧凑。")
    A("")
    A("### 2.3 容量（1.2 m 杆、端部 2×60 mm）")
    A("")
    A(_table(["目标风道 (mm)", *[str(g) for g in cap["gap_mm"]]],
             [["最多件数 K", *[str(v) for v in cap["max_k"]]]]))
    A("")
    A("> 端部只占 2×60 mm 后，1.2 m 杆在 10 cm 风道下能挂 **9 件**（演示只挂 4 件，"
      "所以空杆 640 mm 是正常的，不是规划错误）。")
    A("")
    A("### 2.4 边界与不可行（不静默）")
    A("")
    A(_table(["场景", "状态", "内部段 (mm)", "端部 (mm)", "链条 (mm)", "告警 / 降级"],
             [[c_["label"],
               f"`{c_['status']}`" + ("" if c_["feasible"] else "（不可行）"),
               " / ".join(_f(v, 0) for v in c_["inner_mm"][:4]) +
               (" …" if len(c_["inner_mm"]) > 4 else ""),
               f"{_f(c_['ends_mm'][0], 0)}/{_f(c_['ends_mm'][1], 0)}",
               _f(c_["chain_mm"], 0),
               (c_["warnings"][0] if c_["warnings"] else "—") +
               (f"；{c_['degradation']}" if c_["degradation"] else "")]
              for c_ in cases]))
    A("")
    A(f"规划耗时：K=4 中位 {ptime['n4']['median_us']:.0f} µs、K=10 "
      f"{ptime['n10']['median_us']:.0f} µs，比一次伸缩动作（秒级）小 4 个数量级。")
    A("")

    A("## 3. 链几何、夹持状态与调节顺序（sim-v2/chain.py）")
    A("")
    A("### 3.1 数值例子（4 件、等距）")
    A("")
    lay = demo["layout"]
    A(_table(["项", "数值"],
             [["调节器区间 (mm)", "；".join(
                 f"[{l:.0f}, {r:.0f}]" for l, r in lay.regulator_edges)],
              ["衣物中心 (mm)", " / ".join(f"{v:.0f}" for v in lay.garment_centers)],
              ["中心距 (mm)", " / ".join(f"{v:.0f}" for v in lay.inner + 10)],
              ["链条末端", f"{lay.chain_end_mm:.0f} mm（右墙 {lay.available_mm:.0f} mm）"]]))
    A("")
    A('### 3.2 夹持状态机与「先锁哪端」')
    A("")
    A("每个调节器有两个夹持：`clamp_left`、`clamp_right`。一次调节的动作序列是：")
    A("")
    A("```")
    A("for i in 0..K:                 # 从基准端（左墙）向另一端推进")
    A("    锁靠基准侧的一端              # 反作用进杆，已定位段不动")
    A("    伸缩自由端到目标 L_i          # 只推动相邻那一件衣服")
    A("    锁另一端                      # 长度锁死 = 绝对位置，不依赖链张力")
    A("# 末段端部调节器再顶一次墙，压入 0.5 mm / 10 N 预紧")
    A("```")
    A("")
    A("一次内部段调节的步骤（以第 2 个调节器为例）：")
    A("")
    ex_steps = [s for s in a["steps"] if s["unit"] == 1]
    A(_table(["动作", "夹持前 (L/R)", "夹持后 (L/R)", "长度 (mm)", "行程 (mm)",
              "力 (N)", "电流 (A)", "耗时 (s)"],
             [[s["action"],
               f"{'锁' if s['clamp_before']['left'] else '-'}/"
               f"{'锁' if s['clamp_before']['right'] else '-'}",
               f"{'锁' if s['clamp_after']['left'] else '-'}/"
               f"{'锁' if s['clamp_after']['right'] else '-'}",
               f"{s['length_after_mm']:.1f}",
               _f(s["travel_mm"], 1), _f(s["force_n"], 1),
               _f(s["current_a"], 2), _f(s["time_s"], 1)]
              for s in ex_steps]))
    A("")
    A("### 3.3 三种下发策略对比")
    A("")
    A(_table(["策略", "总耗时 (s)", "峰值力 (N)", "峰值电流 (A)",
              "最大滑动块（衣架数）", "已定位段滑移", "需重新标定"],
             [[k, _f(v["total_time_s"], 1), _f(v["peak_force_n"], 1),
               _f(v["peak_current_a"], 2), str(v["max_block_garments"]),
               "0" if not v["requires_redatum"] else "—",
               "否" if not v["requires_redatum"] else "是"]
              for k in ("锚定左墙（推荐）", "锚定右墙", "不锁端（整链推）")
              for v in [cmp[k]]]))
    A("")
    A(f"- 锚定左墙：峰值 {a['peak_force_n']:.0f} N（2 N 副阻力 + 3×3 N 衣架），"
      f"电流 {a['peak_current_a']:.2f} A，已定位段严格 0 滑移；")
    A(f"- 不锁端：峰值 {b['peak_force_n']:.0f} N、电流 {b['peak_current_a']:.2f} A，"
      '整条链一起滑，必须重新标定全部衣架位置——这就是「必须锁一端」的量化理由。')
    A("")
    A("### 3.4 日常 vs 安装")
    A("")
    daily_rows = plan_case["rows"]
    A(_table(["K", "调节器数", "内部行程 (mm)", "收衣链条 (mm)", "等距链条 (mm)",
              *[f"{d} (s)" for d in plan_case["drives"]]],
             [[str(r["K"]), str(r["regulators"]), _f(r["travel_mm"], 0),
               _f(r["start_chain_mm"], 0), _f(r["end_chain_mm"], 0),
               *[(_f(r[d]["time_s"], 1) +
                  ("" if r[d]["within_budget"] else " ✗")) for d in plan_case["drives"]]]
              for r in daily_rows]))
    A("")
    A(f"> 安装标定（端部 30→60 mm、内部 40→100 mm）：{setup['total_travel_mm']:.0f} mm 行程、"
      f"{setup['time_s']:.0f} s、{setup['clamp_actions']} 次夹持，属于装配流程；"
      "日常只动内部段，4 件按 4 mm/s 约 "
      f"{daily_rows[1][plan_case['drives'][0]]['time_s']:.1f} s、按 7 mm/s 约 "
      f"{daily_rows[1][plan_case['drives'][1]]['time_s']:.1f} s。")
    A("")

    A("## 4. 长度闭环控制（sim-v2/length_control.py）")
    A("")
    A(_table(["参数", "值", "说明"],
             [["电机 / 丝杆", "N20 6V + T8 导程 8 mm，η=0.35",
               "静载 13.3 mm/s；校核取 **4 mm/s**，提速取 7 mm/s"],
              ["测量", "AS5600 12 bit/圈", f"分辨率 {results['control']['study']['encoder_res_mm'] * 1000:.1f} µm"],
              ["负载", "11 N（日常）/ 14 N（安装）", "副阻力 2 N + 3 N/件衣架"],
              ["反向间隙", "0.2 mm", "T8 + 塑料螺母（估算）"],
              ["控制", "PID kp=6, ki=1.0, kd=0.10", "速度指令 + 抗饱和"],
              ["限位", "40 / 220 mm（内部）", "软限位 + 硬限位"],
              ["堵转判据", f"> {stall['threshold_a']:.2f} A 且 "
                          f"{stall['window_s']:.1f} s 无位移", "回退 2 mm"]]))
    A("")
    A(_table(["驱动", "上升 10–90% (s)", "稳定 2% (s)", "超调 (mm)", "稳态误差 (mm)",
              "峰值电流 (A)"],
             [[r["drive"], _f(r["rise_s"], 2), _f(r["settle_s"], 2),
               _f(r["overshoot_mm"], 2), _f(r["sse_mm"], 3),
               _f(r["peak_current_a"], 2)] for r in rows]))
    A("")
    A(_table(["反向间隙策略", "最终长度 (mm)", "误差 (mm)", "稳定 (s)"],
             [[r["case"], _f(r["x_final_mm"], 2), f"{r['error_mm']:+.3f}",
               _f(r["settle_s"], 1)] for r in bl]))
    A("")
    A(f"> 间隙残余 ≤{max(abs(r['error_mm']) for r in bl) * 1000:.0f} µm、方向确定，"
      "标定一次即可消掉，不是 ±2 mm 预算里的主要项。")
    A("")
    A(f"堵转：2 s 时遇 60 N 阻塞，电流 {stall['peak_current_a']:.2f} A，"
      f"**{stall['detect_time_s'] * 1000:.0f} ms** 判出，随后回退 2 mm 解除。")
    A("")
    A(_table(["请求 (mm)", "钳制 (mm)", "告警", "提示"],
             [[_f(r["requested_mm"], 0), _f(r["clamped_mm"], 0),
               "是" if r["warned"] else "否", r["text"] or "—"]
              for r in limits["rows"]]))
    A("")

    A("## 5. 误差预算（±2 mm）")
    A("")
    A(_table(["误差项", "±值 (mm)", "依据"],
             [[r["name"], _f(r["tol_mm"], 3), r["basis"]] for r in budget["rows"]] +
             [["**RSS 合成**", f"**{budget['rss_mm']:.2f}**", "各项独立"],
              ["**最坏叠加**", f"**{budget['worst_case_mm']:.2f}**", "同向相加"]]))
    A("")
    A("不进闭环的项（只影响显示/校验）：")
    A("")
    A(_table(["项", "±值 (mm)", "说明"],
             [[r["name"], _f(r["tol_mm"], 1), r["basis"]] for r in budget["excluded"]]))
    A("")
    A(f"蒙特卡洛 {mc['n_runs']} 次：p95 |e| {mc['p95_abs_mm']:.2f} mm、"
      f"99.9% 分位 {mc['p999_abs_mm']:.2f} mm、落在 ±2 mm 内 "
      f"{mc['p_within_spec'] * 100:.1f}%。")
    A("")
    sc = budget["seam_scenario"]
    A(f"灵敏度：衣架/端面定位公差若从 0.5 mm 放到 2.0 mm，RSS 从 "
      f"{sc['good']['rss_mm']:.2f} mm 涨到 {sc['bad']['rss_mm']:.2f} mm"
      f"{'（超 ±2 mm）' if not sc['bad_ok'] else ''}——机械上要把调节器自由端面和"
      "衣架钩的贴合做到 0.5 mm 以内，丝杆精度不是重点。")
    A("")

    A("## 6. 视觉 ID 识别（sim-v2/vision_id.py）")
    A("")
    A(f"相机 1280×720、f={vis['params']['f_px']:.0f} px、30 mm 标记；"
      f"演示 {vis['params']['n_units']} 个调节器 = {vis['params']['n_units']} 个 ArUco 编码（01–0{vis['params']['n_units']}）。"
      "用真实 OpenCV ArUco 检测器在合成图上做实验。")
    A("")
    curve = vis["rate_curve"]
    px_list = sorted(int(k) for k in curve)
    A(_table(["标记像素 (px)", *[str(p) for p in px_list]],
             [["单帧识别率 (%)", *[f"{curve[p] * 100:.0f}" for p in px_list]]]))
    A("")
    A(f"拐点 ~{vis['px95']} px；工作点 1.5 m → 18 px、1.2 m → 22.5 px，"
      "像素不是瓶颈。识别耗时（遮挡 8%/帧、3 帧去抖、30 fps）：")
    A("")
    A(_table(["场景", "全认全概率", "p95 耗时", "均值"],
             [["1.2 m / 30 mm", f"{vis['acq_1p2m_30mm']['success_rate'] * 100:.1f}%",
               f"{vis['acq_1p2m_30mm']['p95_s']:.2f} s",
               f"{vis['acq_1p2m_30mm']['mean_s']:.2f} s"],
              ["1.5 m / 30 mm", f"{acq['success_rate'] * 100:.1f}%",
               f"{acq['p95_s']:.2f} s", f"{acq['mean_s']:.2f} s"],
              ["1.5 m / 50 mm", f"{vis['acq_1p5m_50mm']['success_rate'] * 100:.1f}%",
               f"{vis['acq_1p5m_50mm']['p95_s']:.2f} s",
               f"{vis['acq_1p5m_50mm']['mean_s']:.2f} s"]]))
    A("")
    bd = vis["binding_demo"]
    bdeg = vis["binding_degraded"]
    A(f"ID 绑定：读到 {bd['ids']} → 物理顺序 {bd['order']}，自洽={bd['ok']}；"
      f"缺读一段时 missing={bdeg['missing']}，"
      f"用「不换序先验 + 长度反馈」补位（{bdeg['notes'][0]}）。")
    A("")
    A("降级：① 缺一段 → 长度反馈 + 固定顺序补位；② 全部认不出 → 保持上次绑定，"
      "长度闭环继续工作；③ 重复 ID / 顺序倒挂 → 判误读丢弃，连续异常则报警。")
    A("")

    A("## 7. 与 v1 的关系 & 对外接口")
    A("")
    A(_table(["v1", "v2（rev-B）", "复用"],
             [["衣架挂在自走模块", "衣架挂在两调节器之间，调节器不承重", "重写"],
              ["4 模块 / 1.2 m", "K+1 调节器（4 件 → 5 个）", "重写"],
              ["间距规划 water-filling", "同一套数学，变量 g_i → 内部段 L_i，t_h=10", "**复用**"],
              ["重排 move-to-end", "不换序 + 唯一编码", "删除"],
              ["ArUco 定位", "ArUco 只做 ID 识别 + 位置校验", "复用流程，改用途"],
              ["卷簧收 slack", "双端夹持 + 端部顶墙预紧", "删除卷簧"]]))
    A("")
    A("MQTT 下发（建议格式，软件文档可直接用）：")
    A("")
    A("```json")
    A('{"cmd":"set_lengths","ts":1732345678,')
    A(' "targets":[{"id":"01","L_mm":100,"clamp":"both"},')
    A('            {"id":"02","L_mm":117.6,"clamp":"both"}],')
    A(' "preload":{"id":"05","force_n":10},')
    A(' "order":["03","02","01"],"mode":"serial"}')
    A("```")
    A("")
    A("> 顺序字段就是本文档给出的「先锁哪端、再伸缩哪端」：`clamp` 指明锁端，"
      "`order` 是串行下发顺序；单元本地执行，中枢只给目标。")
    A("")

    A("## 8. 复现与文件清单")
    A("")
    A("```powershell")
    A("cd E:\\D-robotics-ClothesRodHelper")
    A("python sim-v2/run_all.py     # 单测 → 仿真 → 出图 → 写本文件")
    A("python sim-v2/tests.py       # 只跑单元测试（14 项 assert）")
    A("```")
    A("")
    A(_table(["文件", "作用"],
             [["`sim-v2/length_planner.py`", "内部段 + 端部段规划，三模式与不可行降级"],
              ["`sim-v2/chain.py`", "链几何、夹持状态机、调节顺序与耗时"],
              ["`sim-v2/length_control.py`", "长度闭环（PID、反向间隙、堵转、限位）"],
              ["`sim-v2/vision_id.py`", "ArUco 识别实验、ID 绑定、降级"],
              ["`sim-v2/error_budget.py`", "±2 mm 误差预算与蒙特卡洛"],
              ["`sim-v2/tests.py`", "14 项单元测试"],
              ["`sim-v2/plots.py` / `report.py` / `run_all.py`", "图 / 报告 / 一键入口"],
              ["`docs/figures-v2/v2-0*.png`", "6 张结果图（300 dpi）"]]))
    A("")
    A("## 9. 假设与局限")
    A("")
    A("- 全部为仿真/估算；答辩说「仿真」。")
    A("- 衣架滑动摩擦 3 N/件、伸缩副阻力 2 N、夹持动作 0.4 s、预紧 10 N 都是设计估算。")
    A("- 端部调节器按 40–480 mm 两级伸缩建模；如果坚持 40–220 mm 单级，"
      "1.2 m 杆只能挂 4 件左右且端部悬空——这条已通过 capacity 表量化。")
    A("- 视觉实验是合成图 + 真实检测器，未建模反光/逆光；识别率按 95% 目标留余量。")
    A("")
    return "\n".join(L)


def write_all(results: dict, figures: List[Path], captions: Dict[str, dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    figures = [Path(p) for p in figures]
    md = build_md(results, figures, captions)
    md_path = DATA_DIR / "results.md"
    md_path.write_text(md, encoding="utf-8")

    payload = {
        "meta": results["meta"],
        "plans": {k: results["plans"][k].to_dict() for k in results["plans"]},
        "plans_fill": {k: results["plans_fill"][k].to_dict()
                       for k in results["plans_fill"]},
        "plan_metrics": results["plan_metrics"],
        "planner_timing": results["planner_timing"],
        "plan_cases": results["plan_cases"],
        "capacity": results["capacity"],
        "planner_params": results["planner_params"],
        "chain": {
            "layout": results["chain"]["demo"]["layout"].to_dict(),
            "layout_start": results["chain"]["demo"]["layout_start"].to_dict(),
            "comparison": results["chain"]["demo"]["comparison"],
            "daily": results["chain"]["daily"],
            "setup": results["chain"]["setup"],
            "weighted_transition": results["chain"]["weighted_transition"],
        },
        "control": {
            "study": {"rows": results["control"]["study"]["rows"],
                      "gains": results["control"]["study"]["gains"],
                      "load_extend_n": results["control"]["study"]["load_extend_n"],
                      "backlash_mm": results["control"]["study"]["backlash_mm"],
                      "encoder_res_mm": results["control"]["study"]["encoder_res_mm"]},
            "backlash": results["control"]["backlash"],
            "stall": {k: v for k, v in results["control"]["stall"].items()
                      if k != "result"},
            "limits": results["control"]["limits"],
        },
        "budget": {
            "spec_mm": results["budget"]["spec_mm"],
            "rows": results["budget"]["rows"],
            "excluded": results["budget"]["excluded"],
            "rss_mm": results["budget"]["rss_mm"],
            "worst_case_mm": results["budget"]["worst_case_mm"],
            "contributions": results["budget"]["contributions"],
            "monte_carlo": results["budget"]["monte_carlo"],
            "seam_scenario": results["budget"]["seam_scenario"],
        },
        "vision": {k: v for k, v in results["vision"].items()
                   if k != "acq_times_s"},
        "figures": [f"{FIG_REL}/{p.name}" for p in figures],
        "captions": captions,
    }
    json_path = DATA_DIR / "results.json"
    json_path.write_text(
        json.dumps(_to_jsonable(payload), ensure_ascii=False, indent=2),
        encoding="utf-8")
    return md_path, json_path


__all__ = ["build_captions", "build_md", "write_all"]


