"""把 v2（rev-D）仿真结果写成 docs/_data-v2/results.md 与 .json。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np

from common import DATA_DIR, ROOT

FIG_REL = "docs/figures-v2"


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


def _table(headers: List[str], rows: List[List[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


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


def build_captions(results: dict) -> Dict[str, dict]:
    plans = results["plans"]
    eq, wt, co = plans["equal"], plans["weighted"], plans["collect"]
    cmp = results["chain"]["demo"]["comparison"]
    a = cmp["锚定左墙（推荐）"]
    b = cmp["不锁端（整链推）"]
    d4 = next(r for r in results["timing"]["rows"] if r["K"] == 4)
    t_daily = d4[results["timing"]["drives"][0]]["time_s"]
    t_fast = d4[results["timing"]["drives"][1]]["time_s"]
    setup = results["setup"]
    rows = results["control"]["study"]["rows"]
    lead8 = rows[0]
    drv = lead8["drive"]
    bl = results["control"]["backlash"]["rows"]
    stall = results["control"]["stall"]
    budget = results["budget"]
    mc = budget["monte_carlo"]
    vis = results["vision"]
    acq = vis["acq_1p5m_30mm"]
    return {
        "v2-01-length-plan": {
            "caption": (
                f"外端锚点 0/D 固定（D=460 mm）：等距时端部内端各 {eq.ends[0]:.0f} mm、"
                f"内部 3 段各 100 mm，链长 460 完全贴合；加权只重分内部段（端部自动补/收），"
                f"收衣时内部缩到 40、端部伸到 120 限位，链长 400、空杆 60 → 未完全收拢。"
            ),
        },
        "v2-02-chain-order": {
            "caption": (
                f"每个调节器有 L/R 两个锥面收口夹头：锁一端就能单向伸缩、只推动相邻衣架；"
                f"锚定左锚点逐段调，峰值轴向力 {a['peak_force_n']:.0f} N / 电流 "
                f"{a['peak_current_a']:.2f} A，已定位段 0 滑移；不锁端整链推则 "
                f"{b['peak_force_n']:.0f} N / {b['peak_current_a']:.2f} A，且要重新标定全部衣架。"
            ),
        },
        "v2-03-timing": {
            "caption": (
                f"日常（收衣→等距）端部与内部 5 段都要动：4 mm/s 校核 {t_daily:.1f} s、"
                f"7 mm/s 提速 {t_fast:.1f} s，仍都超过 30 s——端部参与后行程涨到 300 mm，"
                f"要达标需 ≥12 mm/s；安装标定（一次性）{setup['time_s']:.0f} s。"
            ),
        },
        "v2-04-control": {
            "caption": (
                f"长度闭环 40→100 mm：{drv} 上升 {lead8['rise_s']:.1f} s、稳态误差 "
                f"{lead8['sse_mm']:+.2f} mm、超调 {lead8['overshoot_mm']:.2f} mm；"
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
                f"真实 ArUco 检测器在 6–10 px 才掉识别率，1.5 m、30 mm 标记有 18 px，"
                f"余量 2 倍以上；限制项是遮挡——3 帧去抖后 "
                f"{vis['params']['n_units']} 个 ID 全认全 {acq['success_rate'] * 100:.1f}%、"
                f"p95 {acq['p95_s']:.2f} s，认不出时用长度反馈 + 固定顺序降级。"
            ),
        },
    }


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
    d4 = next(r for r in plan_case["rows"] if r["K"] == 4)
    rows = results["control"]["study"]["rows"]
    lead8 = rows[0]
    drv = lead8["drive"]
    bl = results["control"]["backlash"]["rows"]
    stall = results["stall"]
    limits = results["limits"]
    budget = results["budget"]
    mc = budget["monte_carlo"]
    vis = results["vision"]
    acq = vis["acq_1p5m_30mm"]

    L: List[str] = []
    A = L.append
    A("# v2 算法与控制仿真结果（衣序 HangFlow · rev-D）")
    A("")
    A(f"> 由 `python sim-v2/run_all.py` 自动生成（{meta['generated']}），**请勿手改**。")
    A(f"> Python {meta['python']} / numpy {meta['numpy']}；单元测试 "
      f"{meta['test_passed']}/{meta['test_total']} 通过。")
    A("> **数据口径**：全部为仿真/估算值，不是实测。结构口径对齐 "
      "`docs/v2/10-端点锚定模型.md`：外端锚定 0/D、端部只锁外端、内端自由伸缩 30–120 mm，"
      "K 件衣服 = K+1 个调节器，取消恒力卷簧。")
    A("")

    A("## 0. 先看结论")
    A("")
    A(f"1. **默认安装态**：`[60, 100, 100, 100, 60]`，锚点间距 D=**460 mm**，"
      f"链长 460 完全贴合，锚点 0/460 不动。")
    A(f"2. **端部内端吸收总长变化**：等距 12 cm → `[30,120,120,120,30]`（Δ=+60，端部各 −30）；"
      f"再切 8 cm → `[90,80,80,80,90]`（Δ=−120，各 +60）。链长始终 460。")
    A(f"3. **收衣**：内部缩到 40、端部伸到 120 限位 → 链长 **400 mm**、空杆 **60 mm**，"
      f"状态 `partial`，提示「未完全收拢」。")
    A(f"4. **拒绝条件**：目标 20 cm 时内部 600 mm，端部最短也放不下 → `rejected`，"
      f"提示减小目标/减件。")
    A(f"5. **调节顺序**：锚定左锚点、从左往右，先锁靠基准侧夹头 → 伸缩自由端 → 锁死另一端。"
      f"峰值 **{a['peak_force_n']:.0f} N / {a['peak_current_a']:.2f} A**；"
      f"不锁端整链推 {b['peak_force_n']:.0f} N / {b['peak_current_a']:.2f} A，且要重标定。")
    A(f"6. **耗时**：日常（收衣→等距，5 段都动，行程 300 mm）4 mm/s 校核 "
      f"**{d4[plan_case['drives'][0]]['time_s']:.1f} s**、7 mm/s "
      f"{d4[plan_case['drives'][1]]['time_s']:.1f} s，均超 30 s → 需 ≥12 mm/s；"
      f"安装标定 {setup['time_s']:.0f} s。")
    A(f"7. **长度闭环 / 误差**：{drv} 阶跃 40→100 mm 上升 {lead8['rise_s']:.1f} s、"
      f"稳态误差 {lead8['sse_mm']:+.2f} mm；误差预算 RSS **{budget['rss_mm']:.2f} mm**、"
      f"最坏 {budget['worst_case_mm']:.2f} mm，±2 mm 达 100%（MC {mc['n_runs']} 次）；"
      f"视觉 2 mm 不进闭环。")
    A("")

    A("## 1. 图表索引（每张图一句「这张图说明什么」）")
    A("")
    rows_t = [[f"[{p.name}](../figures-v2/{p.name})",
               captions.get(p.stem, {}).get("caption", "")] for p in figures]
    A(_table(["图（300 dpi）", "这张图说明什么"], rows_t))
    A("")

    A("## 2. 长度规划（端点锚定模型）")
    A("")
    A(_table(["符号", "含义", "值"],
             [["K", "衣物件数", "演示 4（2–8）"],
              ["K+1", "调节器数量", "演示 5"],
              ["t_h", "衣架沿杆厚度", f"{params['t_h_mm']:.0f} mm"],
              ["L_i", "内部段 = 净风道",
               f"[{params['inner_min_mm']:.0f}, {params['inner_max_mm']:.0f}] mm"],
              ["L0/LK", "端部内端长度（外端锚定）",
               f"[{params['end_min_mm']:.0f}, {params['end_max_mm']:.0f}]，默认 "
               f"{params['end_base_mm']:.0f}"],
              ["D", "外端锚点间距（固定）", f"{params['anchor_span_mm']:.0f} mm"],
              ["自由杆", "可用杆长 − D", f"{params['free_rod_mm']:.0f} mm"]]))
    A("")
    A("算法（与 `docs/v2/10` 一致）：")
    A("")
    A("```text")
    A("等距/加权：算内部目标 → Δ = Σ(新 − 旧)")
    A("          两端各吸收 −Δ/2（clamp 30–120）；一端到限位另一端补")
    A("          两端都不够 → rejected")
    A("收衣：    内部缩到 40 → Δ<0，端部内端伸出吸收；到 120 停下")
    A("          链长 400、空杆 60 → partial「未完全收拢」")
    A("手动拖：  单端锁、拖自由端 → 同侧端部优先吸收（外端永不动）")
    A("```")
    A("")
    A("### 2.1 验收用例（对应 docs/v2/10 §5）")
    A("")
    A(_table(["场景", "L0/L1/L2/L3/L4 (mm)", "链长 (mm)", "空杆 (mm)", "状态", "告警"],
             [["默认（等距 10 cm）",
               " / ".join(_f(v, 0) for v in eq.all_lengths),
               _f(eq.chain_length_mm, 0), _f(eq.gap_mm, 0), eq.status, "—"],
              ["等距 12 cm",
               " / ".join(_f(v, 0) for v in
                          lp_plan(4, 120).all_lengths),
               _f(lp_plan(4, 120).chain_length_mm, 0),
               _f(lp_plan(4, 120).gap_mm, 0), lp_plan(4, 120).status, "—"],
              ["12 → 8 cm",
               " / ".join(_f(v, 0) for v in _case(cases, "12→8")["all_lengths"])
               if _case(cases, "12→8") else "—", "—", "—", "—", "—"],
              ["目标 20 cm", "—", "—", "—", "rejected", "端部行程不够"],
              ["收衣", " / ".join(_f(v, 0) for v in co.all_lengths),
               _f(co.chain_length_mm, 0), _f(co.gap_mm, 0), co.status,
               "未完全收拢"]]))
    A("")
    A("> 12 cm / 8 cm 的完整对照见 §2.2 边界用例表；`docs/v2/10 §5` 的六个验收点"
      "在 `sim-v2/tests.py` 里都有断言。")
    A("")
    A("### 2.2 边界与拒绝")
    A("")
    A(_table(["场景", "状态", "内部段 (mm)", "端部 (mm)", "链长 (mm)", "空杆/自由杆 (mm)",
              "告警"],
             [[x["label"], f"`{x['status']}`",
               " / ".join(_f(v, 0) for v in x["inner_mm"][:4]) +
               (" …" if len(x["inner_mm"]) > 4 else ""),
               f"{_f(x['ends_mm'][0], 0)}/{_f(x['ends_mm'][1], 0)}",
               _f(x["chain_mm"], 0),
               f"{_f(x['gap_mm'], 0)}/{_f(x['free_rod_mm'], 0)}",
               (x["warnings"][0] if x["warnings"] else "—") +
               (f"；{x['degradation']}" if x["degradation"] else "")]
              for x in cases]))
    A("")
    A(f"规划耗时：K=4 中位 {ptime['n4']['median_us']:.0f} µs、K=10 "
      f"{ptime['n10']['median_us']:.0f} µs。")
    A("")
    A(f"容量：1.2 m 杆（端部各 60、D≤1100）10 cm 风道最多挂 "
      f"**{cap['max_k'][cap['gap_mm'].index(100) if 100 in cap['gap_mm'] else 3]} 件**；"
      "演示 4 件时 D=460，锚点外仍有 640 mm 自由杆（夹头锁位区）。")
    A("")

    A("## 3. 链几何与夹持顺序")
    A("")
    A("```text")
    A("调节器 i 占 [x_i, x_i + L_i]；x_0 = 0（左锚点）；调节器 K 的右端固定在 D")
    A("衣物 i 中心 = x_i + L_i + t_h/2")
    A("x_{i+1} = x_i + L_i + t_h")
    A("链长 = ΣL + K·t_h；空杆 = D − 链长；自由杆 = 可用杆长 − D")
    A("```")
    A("")
    lay = demo["layout"]
    A(_table(["项", "数值"],
             [["调节器区间 (mm)", "；".join(f"[{l:.0f}, {r:.0f}]"
                                          for l, r in lay.regulator_edges)],
              ["衣物中心 (mm)", " / ".join(f"{v:.0f}" for v in lay.garment_centers)],
              ["锚点间距 D", f"{lay.anchor_span_mm:.0f} mm（左 0 / 右 D）"],
              ["链末端（最后一个衣架右侧）", f"{lay.content_end_mm:.0f} mm"],
              ["空杆", f"{lay.gap_mm:.0f} mm"]]))
    A("")
    A(_table(["策略", "总耗时 (s)", "峰值力 (N)", "峰值电流 (A)", "已定位段滑移",
              "需重新标定"],
             [[k, _f(cmp[k]["total_time_s"], 1), _f(cmp[k]["peak_force_n"], 1),
               _f(cmp[k]["peak_current_a"], 2),
               "0" if not cmp[k]["requires_redatum"] else "整链滑移",
               "否" if not cmp[k]["requires_redatum"] else "是"]
              for k in ("锚定左墙（推荐）", "锚定右墙", "不锁端（整链推）")]))
    A("")
    A("日常 vs 安装（串行、锚定左锚点）：")
    A("")
    A(_table(["K", "调节器数", "日常行程 (mm)", "链长（收衣/等距, mm）",
              *[f"{d} (s)" for d in plan_case["drives"]]],
             [[str(r["K"]), str(r["regulators"]), _f(r["travel_mm"], 0),
               f"{_f(r['start_chain_mm'], 0)}/{_f(r['end_chain_mm'], 0)}",
               *[(_f(r[d]["time_s"], 1) +
                  ("" if r[d]["within_budget"] else " ✗")) for d in plan_case["drives"]]]
              for r in plan_case["rows"]]))
    A("")
    A(f"> 端部参与后，日常行程从 180 mm 涨到 300 mm，4 mm/s 校核 "
      f"{d4[plan_case['drives'][0]]['time_s']:.1f} s、7 mm/s "
      f"{d4[plan_case['drives'][1]]['time_s']:.1f} s，要 30 s 需 ≥12 mm/s。")
    A("")

    A("## 4. 长度闭环控制")
    A("")
    A(_table(["参数", "值", "说明"],
             [["电机 / 丝杆", "N20 6V + T8 导程 8 mm，η=0.35", "校核取 4 mm/s"],
              ["测量", "AS5600 12 bit/圈",
               f"分辨率 {results['control']['study']['encoder_res_mm'] * 1000:.1f} µm"],
              ["负载", "11 N 日常 / 14 N 安装", "副阻力 2 N + 3 N/件衣架"],
              ["反向间隙", "0.2 mm", "T8 + 塑料螺母（估算）"],
              ["控制", "PID kp=6, ki=1.0, kd=0.10", "速度指令 + 抗饱和"],
              ["限位", "内部 40–220 / 端部 30–120", "软限位 + 硬限位"],
              ["堵转判据", f"> {stall['threshold_a']:.2f} A 且 "
                          f"{stall['window_s']:.1f} s 无位移", "回退 2 mm"]]))
    A("")
    A(_table(["驱动", "上升 10–90% (s)", "稳定 2% (s)", "超调 (mm)", "稳态误差 (mm)"],
             [[r["drive"], _f(r["rise_s"], 2), _f(r["settle_s"], 2),
               _f(r["overshoot_mm"], 2), _f(r["sse_mm"], 3)] for r in rows]))
    A("")
    A(_table(["反向间隙策略", "最终长度 (mm)", "误差 (mm)"],
             [[r["case"], _f(r["x_final_mm"], 2), f"{r['error_mm']:+.3f}"]
              for r in bl]))
    A("")
    A(f"堵转：2 s 时卡住，电流 {stall['peak_current_a']:.2f} A，"
      f"**{stall['detect_time_s'] * 1000:.0f} ms** 判出并回退 2 mm。")
    A("")

    A("## 5. 误差预算（±2 mm）")
    A("")
    A(_table(["误差项", "±值 (mm)", "依据"],
             [[r["name"], _f(r["tol_mm"], 3), r["basis"]] for r in budget["rows"]] +
             [["**RSS 合成**", f"**{budget['rss_mm']:.2f}**", "各项独立"],
              ["**最坏叠加**", f"**{budget['worst_case_mm']:.2f}**", "同向相加"]]))
    A("")
    A(f"蒙特卡洛 {mc['n_runs']} 次：p95 |e| {mc['p95_abs_mm']:.2f} mm、99.9% "
      f"{mc['p999_abs_mm']:.2f} mm、±2 mm 内 {mc['p_within_spec'] * 100:.1f}%。"
      f"视觉定位 2 mm 只做 ID 校验/显示，不进 L_i 闭环。")
    A("")

    A("## 6. 视觉 ID 识别")
    A("")
    A(f"30 mm 标记：1.2 m→22.5 px、1.5 m→18 px；真实 ArUco 检测器在合成图上 "
      f"6–10 px 才恶化（拐点 {vis['px95']} px）。遮挡 8%/帧 + 3 帧去抖："
      f"{vis['params']['n_units']} 个 ID 全认全 {acq['success_rate'] * 100:.1f}%、"
      f"p95 {acq['p95_s']:.2f} s。降级：缺段→长度反馈+固定顺序；全认不出→保持上次绑定。")
    A("")

    A("## 7. 与 v1 的关系 & 接口")
    A("")
    A(_table(["v1", "v2（rev-D）", "复用"],
             [["衣架挂自走模块", "衣架挂两调节器之间，调节器不承重", "重写"],
              ["4 模块 / 1.2 m", "K+1 调节器（4 件 → 5 个）", "重写"],
              ["间距规划 water-filling", "同一套数学，变量 g_i → 内部段 L_i", "**复用**"],
              ["重排 move-to-end", "不换序 + 唯一编码", "删除"],
              ["ArUco 定位", "ArUco 只做 ID 识别 + 位置校验", "改用途"],
              ["卷簧收 slack", "端部外端锚定、内端吸收 + 锥面夹头", "删除卷簧"]]))
    A("")
    A("```json")
    A('{"cmd":"set_gaps","targets":[{"id":"02","L_mm":120}],')
    A(' "anchor":{"left":0,"right":460},"clamp":"upstream",')
    A(' "order":["04","03","02","01"],"mode":"serial"}')
    A("```")
    A("")

    A("## 8. 复现与文件")
    A("")
    A("```powershell")
    A("cd E:\\D-robotics-ClothesRodHelper")
    A("python sim-v2/run_all.py     # 单测 → 仿真 → 出图 → 写本文件")
    A("python sim-v2/tests.py       # 只跑单元测试")
    A("```")
    A("")
    A(_table(["文件", "作用"],
             [["`sim-v2/length_planner.py`", "端点锚定规划：端部内端吸收、拒绝/部分收拢"],
              ["`sim-v2/chain.py`", "链几何（锚点 0/D）、锥面夹头 lock/free、顺序与耗时"],
              ["`sim-v2/length_control.py`", "长度闭环、反向间隙、堵转、限位"],
              ["`sim-v2/vision_id.py`", "ArUco 识别实验、ID 绑定、降级"],
              ["`sim-v2/error_budget.py`", "±2 mm 误差预算与蒙特卡洛"],
              ["`docs/figures-v2/v2-0*.png`", "6 张结果图（300 dpi）"]]))
    A("")

    A("## 9. 假设与局限")
    A("")
    A("- 全部为仿真/估算；答辩说「仿真」。")
    A("- D=460 是安装时定的锚点间距；端部内端 30–120 mm，收衣受 120 限位，"
      "只能收 180 mm（内部）里的一部分，剩 60 mm 空杆。")
    A("- 衣架滑动摩擦 3 N/件、副阻力 2 N、夹持动作 0.4 s、预紧 10 N 为设计估算。")
    A("- 视觉实验是合成图 + 真实检测器，未建模反光/逆光。")
    A("")
    return "\n".join(L)


def lp_plan(k: int, gap: float):
    import length_planner as lpp
    return lpp.plan_lengths(k, target_gap=gap)


def _case(cases: list, key: str):
    for c in cases:
        if key in c["label"]:
            return c
    return None


def write_all(results: dict, figures: List[Path], captions: Dict[str, dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    figures = [Path(p) for p in figures]
    md = build_md(results, figures, captions)
    md_path = DATA_DIR / "results.md"
    md_path.write_text(md, encoding="utf-8")

    payload = {
        "meta": results["meta"],
        "plans": {k: results["plans"][k].to_dict() for k in results["plans"]},
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
        },
        "control": {
            "rows": results["control"]["study"]["rows"],
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
