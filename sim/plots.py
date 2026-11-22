"""所有结果图（300 dpi，宽 8–10 英寸，直接放进方案文档）。

每张图都对应 docs/_data/algorithm-results.md 里的一句话结论。
"""

from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib.lines import Line2D

from common import L, PALETTE, save_fig, style_axis, ZH
import spacing_planner as sp
import reorder as ro
import control_sim as cs
import vision_error as ve


def _moist_color(q: float):
    """湿度 → 颜色（干=浅黄，湿=橙红）。"""
    return plt.cm.YlOrRd(0.18 + 0.72 * float(np.clip(q, 0, 1)))


# ---------------------------------------------------------------------------
# 图 1：间距规划（加权 water-filling ＋ 等距基准对照）
# ---------------------------------------------------------------------------
def fig_spacing_plan(spacing: dict) -> str:
    plan: sp.SpacingPlan = spacing["demo"]
    base: sp.SpacingPlan = spacing["uniform"]
    labels: Sequence[str] = spacing["labels"]
    q = dict(zip(labels, plan.moisture))
    t = dict(zip(labels, plan.thickness))

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(10.0, 4.2), gridspec_kw={"width_ratios": [1.65, 1.0]})
    rod_len = sp.ROD_LENGTH_MM
    off = sp.END_CLEARANCE_MM  # 可用杆段左端 = 杆端 + 5 cm
    rows = [("加权（按湿度）", plan), ("等距基准（不看湿度）", base)]
    for row_i, (name, p) in enumerate(rows):
        y = 1.05 - row_i * 0.70
        ax1.plot([0, rod_len], [y, y], color="#9aa0a6", lw=7,
                 solid_capstyle="round", zorder=1)
        for i, lab in enumerate(labels):
            left, right = p.edges[i] + off
            w = right - left
            ax1.add_patch(Rectangle((left, y - 0.085), w, 0.17,
                                    facecolor=_moist_color(q[lab]),
                                    edgecolor="#333", lw=1.0, zorder=3))
            ax1.text((left + right) / 2, y, lab, ha="center", va="center",
                     fontsize=9, fontweight="bold", zorder=4)
            ax1.text((left + right) / 2, y - 0.16,
                     L(f"{t[lab]:.0f} mm", f"{t[lab]:.0f} mm"),
                     ha="center", va="top", fontsize=6.8, color="#444")
        for i, g in enumerate(p.gaps):
            xm = (p.edges[i, 1] + p.edges[i + 1, 0]) / 2 + off
            ax1.text(xm, y + 0.135, f"{g:.0f}", ha="center", va="bottom",
                     fontsize=7.8, color="#1f4e79" if p is plan else "#666")
        ax1.text(rod_len / 2, y + 0.30, name, ha="center", va="bottom",
                 fontsize=9.5, color="#222")
        # 端部留白
        ax1.plot([off, off], [y - 0.05, y + 0.05], color="#c0392b", lw=1.2)
        ax1.plot([rod_len - off, rod_len - off], [y - 0.05, y + 0.05],
                 color="#c0392b", lw=1.2)
    ax1.set_xlim(-20, rod_len + 20)
    ax1.set_ylim(0.02, 1.58)
    ax1.set_yticks([])
    ax1.set_xlabel(L("沿杆位置（mm，0 = 杆左端）", "Position along rod (mm)"), fontsize=9.5)
    ax1.set_title(L("① 4 件衣物在 1.2 m 杆上的目标位置（数字 = 间隙 mm）",
                    "① Target layout on 1.2 m rod (numbers = gaps in mm)"),
                  fontsize=10.5)
    ax1.text(rod_len / 2, 1.52,
             L(f"规划块居中：两端各留白 {plan.block_left:.0f} mm",
               f"block centered, {plan.block_left:.0f} mm free each side"),
             ha="center", va="top", fontsize=7.4, color="#666")
    ax1.grid(True, axis="x", ls="--", lw=0.6, alpha=0.4)
    ax1.set_axisbelow(True)
    ax1.tick_params(labelsize=8.5)

    # ---- 右：间隙分配的堆叠柱 ----
    x = np.arange(len(plan.gaps))
    base_h = np.full(len(plan.gaps), sp.MIN_GAP_MM)
    extra = plan.gaps - base_h
    wts = plan.weights / plan.weights.sum() if plan.weights.sum() > 0 else plan.weights
    ax2.bar(x, base_h, width=0.62, color="#d9d9d9",
            edgecolor="#888", lw=0.8, label=L("安全底 30 mm", "floor 30 mm"))
    ax2.bar(x, extra, bottom=base_h, width=0.62,
            color=[plt.cm.Blues(0.35 + 0.5 * w) for w in wts],
            edgecolor="#1f4e79", lw=0.8, label=L("按干燥需求加权分配", "weighted extra"))
    for i, (g, u) in enumerate(zip(plan.gaps, wts)):
        ax2.text(i, g + 3, f"{g:.0f}", ha="center", va="bottom", fontsize=8)
        ax2.text(i, sp.MIN_GAP_MM / 2, f"w={u:.2f}", ha="center", va="center",
                 fontsize=7, color="#333")
    ax2.axhline(float(np.mean(base.gaps)), color=PALETTE[4], ls="--", lw=1.2,
                label=L(f"等距基准 {np.mean(base.gaps):.0f} mm",
                        f"uniform {np.mean(base.gaps):.0f} mm"))
    ax2.set_xticks(x)
    ax2.set_xticklabels([L(f"间隙{i + 1}", f"gap {i + 1}") for i in x], fontsize=8.5)
    ax2.set_ylabel(L("间隙长度（mm）", "Gap length (mm)"), fontsize=9.5)
    ax2.set_title(L("② 30 mm 底 + 加权分配剩余空间", "② 30 mm floor + weighted water-filling"),
                  fontsize=10.5)
    ax2.legend(fontsize=7.2, loc="upper right", framealpha=0.9)
    style_axis(ax2)
    fig.tight_layout()
    return str(save_fig(fig, "alg-01-spacing-waterfill"))


# ---------------------------------------------------------------------------
# 图 2：可行域与降级（跨度上限、杆太短）
# ---------------------------------------------------------------------------
def fig_spacing_feasibility(spacing: dict) -> str:
    sweep = spacing["sweep"]
    nmax = spacing["nmax"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.0, 3.9))

    s = np.asarray(sweep["span"])
    ax1.plot(s, sweep["mean_gap"], color=PALETTE[0], lw=1.8,
             label=L("平均间隙", "mean gap"))
    ax1.fill_between(s, sweep["min_gap"], sweep["max_gap"], color=PALETTE[0],
                     alpha=0.15, label=L("间隙区间", "gap range"))
    ax1.axhline(sp.MIN_GAP_MM, color=PALETTE[4], ls="--", lw=1.2,
                label=L("最小安全间隙 30 mm", "min gap 30 mm"))
    ax1.axvline(sp.MIN_GAP_MM * 3 + sum(spacing["demo"].thickness),
                color=PALETTE[5], ls=":", lw=1.2)
    ax1.axvline(1100.0, color=PALETTE[5], ls=":", lw=1.2)
    ax1.axvline(sp.DEFAULT_TARGET_SPAN_MM, color=PALETTE[1], ls="-.", lw=1.2)
    ax1.text(sp.DEFAULT_TARGET_SPAN_MM + 12, 392,
             L(f"演示\n{sp.DEFAULT_TARGET_SPAN_MM:.0f} mm",
               f"demo\n{sp.DEFAULT_TARGET_SPAN_MM:.0f} mm"),
             fontsize=7.2, color=PALETTE[1], va="top", ha="left")
    ax1.annotate(L("目标跨度 < 最小可行跨度\n→ 自动放宽并告警",
                   "target too tight\n→ relaxed + warning"),
                 xy=(220, 105), fontsize=7.2, color="#555")
    ax1.annotate(L("S > L_max → 截到 1100 mm",
                   "S > L_max -> clipped"),
                 xy=(830, 105), fontsize=7.2, color="#555")
    ax1.set_xlabel(L("目标总跨度 S（mm）", "target span S (mm)"), fontsize=9.5)
    ax1.set_ylabel(L("规划出的间隙（mm）", "planned gap (mm)"), fontsize=9.5)
    ax1.set_title(L("① 4 件衣物：间隙随目标跨度变化", "① 4 garments: gap vs target span"),
                  fontsize=10.5)
    ax1.legend(fontsize=7.4, loc="upper left")
    style_axis(ax1)

    rods = np.asarray(nmax["rod_mm"])
    for i, (th, vals) in enumerate(nmax["curves"].items()):
        ax2.plot(rods, vals, color=PALETTE[i], lw=1.6,
                 label=L(f"厚度 {th:.0f} mm", f"t = {th:.0f} mm"))
    ax2.axvline(1200.0, color="#444", ls=":", lw=1.0)
    ymax = max(max(v) for v in nmax["curves"].values())
    ax2.text(1215, ymax * 0.93, L("演示杆 1.2 m", "demo rod 1.2 m"),
             fontsize=7.6, color="#444")
    ax2.set_xlabel(L("杆长（mm）", "rod length (mm)"), fontsize=9.5)
    ax2.set_ylabel(L("最多可挂件数（件）", "max garments"), fontsize=9.5)
    ax2.set_title(L("② 安全挂载上限（间隙 ≥ 30 mm）", "② safe capacity (gap ≥ 30 mm)"),
                  fontsize=10.5)
    ax2.legend(fontsize=7.4)
    style_axis(ax2)
    fig.tight_layout()
    return str(save_fig(fig, "alg-02-spacing-feasibility"))


# ---------------------------------------------------------------------------
# 图 3：一次完整重排的步骤图
# ---------------------------------------------------------------------------
def fig_reorder_steps(reorder_demo: dict) -> str:
    rp: ro.ReorderPlan = reorder_demo["reorder"]
    labels = reorder_demo["labels"]
    q = reorder_demo["moisture"]
    th = reorder_demo["thickness"]
    rank_to_label = {i + 1: reorder_demo["desired_order"][i] for i in range(rp.n)}
    slots = [p + sp.END_CLEARANCE_MM for p in rp.slot_positions]
    n_states = len(rp.states)
    fig, axes = plt.subplots(n_states, 1, figsize=(9.5, 1.45 * n_states + 0.9),
                             sharex=True)
    axes = np.atleast_1d(axes)
    rod_len = sp.ROD_LENGTH_MM
    for si, state in enumerate(rp.states):
        ax = axes[si]
        ax.plot([0, rod_len], [0.5, 0.5], color="#9aa0a6", lw=7,
                solid_capstyle="round", zorder=1)
        order = [rank_to_label[r] for r in state]
        for slot_i, lab in enumerate(order):
            cx = slots[slot_i]
            w = th[lab]
            ax.add_patch(Rectangle((cx - w / 2, 0.5 - 0.19), w, 0.38,
                                   facecolor=_moist_color(q[lab]),
                                   edgecolor="#333", lw=1.0, zorder=3))
            ax.text(cx, 0.5, lab, ha="center", va="center", fontsize=10,
                    fontweight="bold", zorder=4)
            ax.text(cx, 0.24, f"{q[lab] * 100:.0f}%", ha="center", va="top",
                    fontsize=6.8, color="#444")
        # 转移段示意
        ax.axvspan(slots[-1] + 40, min(slots[-1] + 160, rod_len),
                   color="#e8eef7", zorder=0)
        if si == 0:
            ax.text(slots[-1] + 100, 0.78, L("转移段\n（抬升越障）", "transfer bay\n(lift-over)"),
                    ha="center", va="bottom", fontsize=7.2, color="#5b6b82")
        if si > 0:
            op = rp.ops[si - 1]
            # 被移动单元：从上一状态位置 → 远端
            prev_state = rp.states[si - 1]
            prev_order = [rank_to_label[r] for r in prev_state]
            x_from = slots[prev_order.index(op.label)]
            x_to = slots[-1]
            arrow = FancyArrowPatch((x_from, 0.5), (x_to, 0.5),
                                    arrowstyle="-|>", mutation_scale=13,
                                    color=PALETTE[4], lw=1.4, ls="--",
                                    shrinkA=8, shrinkB=8, zorder=2.5)
            ax.add_patch(arrow)
            ax.text((x_from + x_to) / 2, 0.86,
                    L(f"第 {op.step} 步：{op.label} → 最远端（本步 {op.total_s:.1f} s）",
                      f"step {op.step}: {op.label} -> far end ({op.total_s:.1f} s)"),
                    ha="center", va="bottom", fontsize=7.6, color=PALETTE[4])
        ax.set_ylim(0.05, 1.12)
        ax.set_yticks([])
        ax.set_xlim(-20, rod_len + 20)
        ax.tick_params(labelsize=8)
        ax.grid(True, axis="x", ls="--", lw=0.55, alpha=0.4)
        ax.set_axisbelow(True)
        if si == 0:
            title = L("状态 0：初始（左→右 A B C D）", "state 0: initial")
        else:
            op = rp.ops[si - 1]
            title = L(f"状态 {si}：{op.label} 已移到最远端（本步 {op.total_s:.1f} s）",
                      f"state {si}: {op.label} moved to far end")
        ax.set_title(title, fontsize=9, loc="left", pad=2)
    axes[-1].set_xlabel(L("沿杆位置（mm）", "position along rod (mm)"), fontsize=9)
    fig.suptitle(
        L(f"一次完整重排：上界 N-1 = {rp.upper_bound} 次，本例只走 {rp.moves} 次"
          f"（{rp.reorder_time_s:.1f} s @ {rp.speed_mm_s:.0f} mm/s）",
          f"full reorder: upper bound {rp.upper_bound}, this case {rp.moves} moves"),
        fontsize=10.5, y=1.0)
    fig.tight_layout()
    return str(save_fig(fig, "alg-03-reorder-steps"))


# ---------------------------------------------------------------------------
# 图 4：重排代价随件数增长
# ---------------------------------------------------------------------------
def fig_reorder_cost(cost: dict, spacing_time_s: float) -> str:
    rows = cost["rows"]
    n = [r["n"] for r in rows]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.0, 3.9))

    ax1.bar(n, [r["moves_worst"] for r in rows], width=0.55,
            color="#c9d6e8", edgecolor=PALETTE[0], lw=0.9,
            label=L("最坏（完全逆序）= N-1", "worst (reversed) = N-1"))
    ax1.plot(n, [r["moves_mean"] for r in rows], "o-", color=PALETTE[4], lw=1.6,
             ms=4, label=L("随机排列平均", "random average"))
    ax1.axvline(4, color="#555", ls=":", lw=1.0,
                label=L("演示 4 件", "demo N=4"))
    ax1.set_ylim(-0.2, 7.8)
    ax1.set_xlabel(L("衣物件数 N（件）", "number of garments N"), fontsize=9.5)
    ax1.set_ylabel(L("move-to-end 次数（次）", "move-to-end count"), fontsize=9.5)
    ax1.set_title(L("① 重排需要的移动次数", "① moves needed for reorder"), fontsize=10.5)
    ax1.legend(fontsize=7.4)
    style_axis(ax1)

    ax2.plot(n, [r["time_worst_s"] for r in rows], "s-", color=PALETTE[0], lw=1.6,
             ms=4, label=L(f"换序：{cost['speed_mm_s']:.0f} mm/s 电机",
                           f"reorder @ {cost['speed_mm_s']:.0f} mm/s"))
    ax2.plot(n, [r["time_worst_fast_s"] for r in rows], "^--", color=PALETTE[2],
             lw=1.4, ms=4, label=L(f"换序：{cost['fast_speed_mm_s']:.0f} mm/s 电机",
                                   f"reorder @ {cost['fast_speed_mm_s']:.0f} mm/s"))
    ax2.plot(n, [r["spacing_only_time_s"] for r in rows], "o:", color=PALETTE[3],
             lw=1.4, ms=4, label=L("只调间距（不换序）", "spacing only"))
    ax2.axhline(cost["budget_s"], color=PALETTE[4], ls="--", lw=1.2,
                label=L("需求上限 30 s", "budget 30 s"))
    ax2.axvline(4, color="#555", ls=":", lw=1.0)
    ax2.set_xlabel(L("衣物件数 N（件）", "number of garments N"), fontsize=9.5)
    ax2.set_ylabel(L("预计耗时（s）", "estimated time (s)"), fontsize=9.5)
    ax2.set_title(L("② 换序 vs 只调间距的耗时", "② reorder vs spacing-only time"),
                  fontsize=10.5)
    ax2.legend(fontsize=7.0, loc="upper left")
    ax2.set_ylim(0, max(max(r["time_worst_s"] for r in rows), cost["budget_s"]) * 1.18)
    style_axis(ax2)
    fig.tight_layout()
    return str(save_fig(fig, "alg-04-reorder-cost"))


# ---------------------------------------------------------------------------
# 图 5：阶跃响应 / 误差 / 坡度敏感性
# ---------------------------------------------------------------------------
def fig_control_step(study: dict, tilt: dict) -> str:
    traces = study["traces"]
    fig, axes = plt.subplots(2, 2, figsize=(10.0, 6.2))
    ax1, ax2, ax3, ax4 = axes.ravel()
    styles = {
        "P": (PALETTE[0], "-"),
        "PI": (PALETTE[2], "-"),
        "PID": (PALETTE[3], "-"),
        "PI 无抗饱和": (PALETTE[4], "--"),
    }
    target = study["target_mm"]

    # ---- (a) 阶跃响应：P / PI / PID ----
    for name in ("P", "PI", "PID"):
        tr = traces[name]
        color, ls = styles[name]
        ax1.plot(tr.t, tr.x, ls, color=color, lw=2.1 if name == "PID" else 1.3,
                 label=name)
    ax1.axhline(target, color="#333", ls=":", lw=1.0)
    ax1.text(0.25, target + 9, L("目标 300 mm", "target 300 mm"), fontsize=7.6)
    ax1.annotate(L("60 mm/s 限速 ⇒ 走完 300 mm 约 5 s", "60 mm/s limit → ~5 s per 300 mm"),
                 xy=(2.0, 150), fontsize=7.4, color="#555")
    ax1.set_xlim(0, study["t_end_s"])
    ax1.set_ylim(-15, 335)
    ax1.set_xlabel(L("时间（s）", "time (s)"), fontsize=9)
    ax1.set_ylabel(L("位置（mm）", "position (mm)"), fontsize=9)
    ax1.set_title(L("① 阶跃响应（初始差 −5 mm，三条曲线几乎重合）",
                    "① step response (init −5 mm)"), fontsize=9.8)
    ax1.legend(fontsize=7.2, loc="lower right")

    # ---- (b) 稳态误差放大 ----
    for name in ("P", "PI", "PID"):
        tr = traces[name]
        color, ls = styles[name]
        ax2.plot(tr.t, tr.x - target, ls, color=color, lw=1.5, label=name)
    ax2.axhline(0, color="#333", lw=0.8)
    sse_p = next(r for r in study["rows"] if r["name"] == "P")["sse_mm"]
    ax2.annotate(L(f"P 差 {sse_p:+.2f} mm", f"P: {sse_p:+.2f} mm"),
                 xy=(8.2, sse_p), xytext=(9.4, sse_p - 0.55), fontsize=7.4,
                 color=PALETTE[0],
                 arrowprops=dict(arrowstyle="->", lw=0.8, color=PALETTE[0]))
    ax2.set_xlim(7.0, study["t_end_s"])
    ax2.set_ylim(-2.0, 1.1)
    ax2.set_xlabel(L("时间（s）", "time (s)"), fontsize=9)
    ax2.set_ylabel(L("位置误差（mm）", "position error (mm)"), fontsize=9)
    ax2.set_title(L("② 稳态误差：P 有偏，PI/PID 归零", "② steady-state error"),
                  fontsize=9.8)
    ax2.legend(fontsize=7.2, loc="upper right")

    # ---- (c) 坡度敏感性 ----
    tilts = tilt["tilts_deg"]
    names = tilt["config_names"]
    for i, nm in enumerate(names):
        vals = [row[nm]["sse_mm"] for row in tilt["rows"]]
        ax3.plot(tilts, vals, "o-", color=PALETTE[i], lw=1.5, ms=4, label=nm)
    ax3.axhspan(-tilt["spec_mm"], tilt["spec_mm"], color="#3c9a5f", alpha=0.10)
    ax3.axhline(0, color="#333", lw=0.7)
    ax3.text(0.05, tilt["spec_mm"] - 0.55, L("±5 mm 定位预算", "±5 mm budget"),
             fontsize=7.2, color="#2e7d4f")
    ax3.set_xlabel(L("晾衣杆倾斜角（°）", "rod tilt (deg)"), fontsize=9)
    ax3.set_ylabel(L("稳态误差（mm）", "steady-state error (mm)"), fontsize=9)
    ax3.set_title(L("③ 坡度越大，P 的偏差越大", "③ error vs rod tilt"), fontsize=9.8)
    ax3.legend(fontsize=7.4)

    # ---- (d) 反面教材：无抗饱和 ----
    ng = traces.get("PI 无抗饱和")
    if ng is not None:
        ax4.plot(ng.t, ng.x, "--", color=PALETTE[4], lw=1.8,
                 label=L("PI 无抗饱和", "PI w/o anti-windup"))
    ax4.plot(traces["PID"].t, traces["PID"].x, "-", color=PALETTE[3], lw=1.8,
             label="PID")
    ax4.axhline(target, color="#333", ls=":", lw=1.0)
    peak = ng.metrics["peak_mm"] if ng is not None else target
    ov = ng.metrics["overshoot_pct"] if ng is not None else 0.0
    ax4.set_ylim(0, peak * 1.18 if peak > 0 else 350)
    ax4.set_xlim(0, study["t_end_s"])
    ax4.annotate(
        L(f"峰值 {peak:.0f} mm（超调 {ov:.0f}%），12 s 内没回来",
          f"peak {peak:.0f} mm ({ov:.0f}%), not settled in 12 s"),
        xy=(2.4, peak * 0.88), fontsize=7.4, color=PALETTE[4])
    ax4.set_xlabel(L("时间（s）", "time (s)"), fontsize=9)
    ax4.set_ylabel(L("位置（mm）", "position (mm)"), fontsize=9)
    ax4.set_title(L("④ 反例：饱和期不夹积分 → 过冲失控", "④ counter-example: no anti-windup"),
                  fontsize=9.8)
    ax4.legend(fontsize=7.2, loc="lower right")

    for ax in (ax1, ax2, ax3, ax4):
        style_axis(ax)
    fig.tight_layout()
    return str(save_fig(fig, "alg-05-control-step"))


# ---------------------------------------------------------------------------
# 图 6：蒙特卡洛（200 次）
# ---------------------------------------------------------------------------
def fig_control_montecarlo(mc: dict) -> str:
    br = mc["by_run"]
    fig, axes = plt.subplots(1, 3, figsize=(9.5, 3.2))
    specs = [
        ("overshoot_pct", L("超调量（%）", "overshoot (%)"), PALETTE[0], None,
         L("① 超调量分布", "① overshoot")),
        ("settle_s", L("稳定时间（s）", "settling time (s)"), PALETTE[2], None,
         L("② 稳定时间分布", "② settling time")),
        ("sse_abs_mm", L("稳态误差 |e|（mm）", "|steady error| (mm)"), PALETTE[4], 5.0,
         L("③ 稳态误差分布（远小于 ±5 mm）", "③ steady error")),
    ]
    for ax, (key, xlabel, color, spec, title) in zip(axes, specs):
        data = np.asarray(br[key], dtype=float)
        data = data[np.isfinite(data)]
        ax.hist(data, bins=22, color=color, alpha=0.75, edgecolor="white", lw=0.6)
        mean = float(np.mean(data))
        p95 = float(np.percentile(data, 95))
        ax.axvline(mean, color="#222", lw=1.3)
        ax.axvline(p95, color="#222", lw=1.0, ls="--")
        ymax = ax.get_ylim()[1]
        ax.text(mean, ymax * 0.92, f" {L('均值', 'mean')} {mean:.2f}",
                fontsize=7.4, ha="left")
        ax.text(p95, ymax * 0.78, f" p95 {p95:.2f}", fontsize=7.4, ha="left")
        if spec is not None:
            ax.set_xlim(0, max(float(data.max()) * 1.3, 0.5))
            ax.text(0.33, ymax * 0.72, L("±5 mm 在右侧图外 ▸", "±5 mm spec off-chart ▸"),
                    fontsize=7.2, color=PALETTE[4], ha="left", va="center")
        ax.set_xlabel(xlabel, fontsize=9)
        ax.set_ylabel(L("次数（次）", "count"), fontsize=9)
        ax.set_title(title, fontsize=9.6)
        style_axis(ax)
    fig.suptitle(
        L(f"PID 蒙特卡洛 {mc['n_runs']} 次（噪声/延迟/坡度/初始误差一起抖）",
          f"PID Monte Carlo, {mc['n_runs']} runs"),
        fontsize=10.5, y=1.02)
    fig.tight_layout()
    return str(save_fig(fig, "alg-06-control-montecarlo"))


# ---------------------------------------------------------------------------
# 图 7：视觉误差
# ---------------------------------------------------------------------------
def fig_vision(vision: dict) -> str:
    ds = vision["distance_sweep"]
    ys = vision["yaw_sweep"]
    rows = vision["rows"]
    fig, (ax1, ax2, ax3) = plt.subplots(
        1, 3, figsize=(10.0, 3.4), gridspec_kw={"width_ratios": [1.0, 1.0, 1.05]})

    z = np.asarray(ds["distance_mm"]) / 1000.0
    for i, (f, curve) in enumerate(ds["curves"].items()):
        ax1.plot(z, curve, color=PALETTE[i], lw=1.6,
                 label=L(f"f = {f:.0f} px", f"f = {f:.0f} px"))
    ax1.axvspan(1.2, 1.5, color="#3c9a5f", alpha=0.08)
    ax1.set_xlabel(L("相机到杆的距离（m）", "camera distance (m)"), fontsize=9)
    ax1.set_ylabel(L("沿杆随机误差（mm）", "along-rod random error (mm)"), fontsize=9)
    ax1.set_title(L("① 侧装（偏航 0°）：1.2 m 处 ≤0.7 mm",
                    "① side mount (0 deg): <=0.7 mm at 1.2 m"),
                  fontsize=10)
    ax1.legend(fontsize=7.2)
    style_axis(ax1)

    for i, (dist, curve) in enumerate(ys["curves"].items()):
        ax2.plot(ys["yaw_deg"], curve, color=PALETTE[i], lw=1.6,
                 label=L(f"{dist / 1000:.1f} m", f"{dist / 1000:.1f} m"))
    ax2.axvline(10, color=PALETTE[4], ls="--", lw=1.1)
    ax2.text(10.4, 1, L("偏航 10°", "yaw 10 deg"), fontsize=7.2, color=PALETTE[4])
    ax2.set_xlabel(L("相机偏航角（°）", "camera yaw (deg)"), fontsize=9)
    ax2.set_ylabel(L("沿杆随机误差（mm）", "along-rod random error (mm)"), fontsize=9)
    ax2.set_title(L("② 偏航一超 10°，误差按距离放大", "② yaw > 10 deg amplifies error"),
                  fontsize=10)
    ax2.legend(fontsize=7.2)
    style_axis(ax2)

    # 误差预算堆叠：随机（5 帧平均）+ 标定 + 安装
    labels = [L("随机项（5 帧平均）", "random (5-frame)"),
              L("标定残差", "calibration"),
              L("标记安装偏差", "marker mounting")]
    keys = ["random", "标定残差", "标记安装偏差"]
    xs = np.arange(len(rows))
    bottoms = np.zeros(len(rows))
    colors = [PALETTE[0], PALETTE[1], PALETTE[3]]
    for key, lab, col in zip(keys, labels, colors):
        vals = np.array([
            (r["budget_yaw10_5frames"]["detail"][key]
             if key in r["budget_yaw10_5frames"]["detail"]
             else r["budget_yaw10_5frames"]["random_mm"]) for r in rows])
        ax3.bar(xs, vals, bottom=bottoms, width=0.55, color=col,
                edgecolor="white", lw=0.6, label=lab)
        bottoms += vals
    totals = np.array([r["budget_yaw10_5frames"]["total_mm"] for r in rows])
    for i, tot in enumerate(totals):
        ax3.text(i, tot + 0.12, L(f"{tot:.1f} mm", f"{tot:.1f} mm"),
                 ha="center", va="bottom", fontsize=7.6)
    ax3.axhline(ve.SPEC_MM, color=PALETTE[4], ls="--", lw=1.2)
    ax3.text(0.02, 0.93, L("虚线 = ±5 mm 目标", "dashed = ±5 mm spec"),
             transform=ax3.transAxes, fontsize=7.2, color=PALETTE[4],
             ha="left", va="top")
    ax3.set_xticks(xs)
    ax3.set_xticklabels([L(f"{r['distance_mm'] / 1000:.1f} m", f"{r['distance_mm'] / 1000:.1f} m")
                         for r in rows], fontsize=8.5)
    ax3.set_xlim(-0.55, 2.55)
    ax3.set_ylim(0, ve.SPEC_MM * 1.42)
    ax3.set_xlabel(L("相机距离", "camera distance"), fontsize=9)
    ax3.set_ylabel(L("误差预算（mm）", "error budget (mm)"), fontsize=9)
    ax3.set_title(L("③ 偏航 10° + 5 帧平均：系统误差占大头", "③ budget at yaw 10 deg"),
                  fontsize=10)
    ax3.legend(fontsize=6.8, loc="upper center", bbox_to_anchor=(0.5, -0.16),
               ncol=3, frameon=False, handlelength=1.4, columnspacing=1.0)
    style_axis(ax3)
    fig.tight_layout()
    return str(save_fig(fig, "alg-07-vision-error"))


# ---------------------------------------------------------------------------
def make_all(results: dict, fig_titles: dict) -> List[str]:
    """生成全部图，返回路径列表。"""
    paths = []
    paths.append(fig_spacing_plan(results["spacing"]))
    paths.append(fig_spacing_feasibility(results["spacing"]))
    paths.append(fig_reorder_steps(results["reorder"]["demo"]))
    paths.append(fig_reorder_cost(results["reorder"]["cost"],
                                  results["reorder"]["demo"]["spacing_time_s"]))
    paths.append(fig_control_step(results["control"]["study"], results["control"]["tilt"]))
    paths.append(fig_control_montecarlo(results["control"]["mc"]))
    paths.append(fig_vision(results["vision"]))
    return paths


__all__ = ["make_all"]
