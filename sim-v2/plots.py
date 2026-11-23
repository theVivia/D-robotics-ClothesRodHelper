"""衣序 HangFlow v2（rev-B）结果图（300 dpi，宽 9–10 英寸）。"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch, Rectangle

from common import L, PALETTE, save_fig, style_axis
import length_planner as lp
import chain as ch
import error_budget as eb
import vision_id as vi


def _draw_chain(ax, plan: lp.LengthPlan, y: float = 0.58,
                show_len: bool = True, color: str = "#2f6fb3",
                annotate_clamps: bool = False, label_units: bool = True) -> None:
    """画墙 + K+1 个调节器 + K 件衣物。"""
    lay = ch.chain_layout(plan)
    avail = plan.available_mm
    box_h = 0.12
    ax.plot([0, avail], [y, y], color="#c9ced6", lw=5,
            solid_capstyle="round", zorder=1)
    for x in (0.0, avail):
        ax.plot([x, x], [y - 0.22, y + 0.22], color="#5b6779", lw=4, zorder=4)
    for i, (l, r) in enumerate(lay.regulator_edges):
        role = "end" if (i == 0 or i == plan.K) else "inner"
        c = color if role == "inner" else "#8a6d3b"
        ax.add_patch(FancyBboxPatch(
            (l, y - box_h / 2), r - l, box_h,
            boxstyle="round,pad=0,rounding_size=8",
            facecolor=c, edgecolor="#1f3a5f", lw=0.9, alpha=0.88, zorder=3))
        if show_len and (r - l) > 45:
            ax.text((l + r) / 2, y, f"{r - l:.0f}", ha="center", va="center",
                    fontsize=7.4, color="white", zorder=4)
        if annotate_clamps:
            ax.text(l + 1.5, y + 0.075, "L", fontsize=6.0, color="#4a4a4a",
                    va="bottom")
            ax.text(r - 5.0, y + 0.075, "R", fontsize=6.0, color="#4a4a4a",
                    va="bottom")
        if label_units and (r - l) > 60:
            ax.text((l + r) / 2, y - 0.30, f"调{i}", ha="center", va="top",
                    fontsize=6.2, color="#666")
    for j, cx in enumerate(lay.garment_centers):
        ax.add_patch(Rectangle((cx - 2.2, y - 0.17), 4.4, 0.34,
                               facecolor="#f2d18b", edgecolor="#8a6d3b",
                               lw=0.9, zorder=5))
        ax.text(cx, y - 0.50, f"衣{j + 1}", ha="center", va="top", fontsize=6.2,
                color="#8a6d3b")
    ax.set_xlim(-25, avail + 25)
    ax.set_ylim(0.05, 1.02)
    ax.set_yticks([])
    ax.grid(True, axis="x", ls="--", lw=0.5, alpha=0.4)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=7.5)


# ---------------------------------------------------------------------------
def fig_length_plan(plans: Dict[str, lp.LengthPlan]) -> str:
    fig = plt.figure(figsize=(10.0, 4.9))
    gs = GridSpec(3, 2, figure=fig, width_ratios=[1.8, 1.0],
                  wspace=0.24, hspace=0.62)
    axes = [fig.add_subplot(gs[i, 0]) for i in range(3)]
    axb = fig.add_subplot(gs[:, 1])
    modes = [("equal", L("① 一键等距：内部 100 mm，链长 460 mm（空杆 640 mm）",
                         "① equal: inner 100 mm, chain 460 mm"), PALETTE[0]),
             ("weighted", L("② 按湿度加权：只重分内部段，链长不变",
                            "② weighted: same chain length"), PALETTE[1]),
             ("collect", L("③ 收衣：内部全 40 mm，端部不动 → 链长 280 mm",
                           "③ collect: inner 40 mm, chain 280 mm"), PALETTE[4])]
    for i, (key, title, color) in enumerate(modes):
        plan = plans[key]
        lay = ch.chain_layout(plan)
        ax = axes[i]
        # 空杆 / 端部夹头锁位区
        if plan.leftover_mm > 5:
            ax.axvspan(lay.chain_end_mm, plan.available_mm, color="#eceff3", zorder=0)
            ax.text((lay.chain_end_mm + plan.available_mm) / 2, 0.86,
                    L(f"空杆 {plan.leftover_mm:.0f} mm（夹头锁位区）",
                      f"free rod {plan.leftover_mm:.0f} mm"),
                    ha="center", va="top", fontsize=6.8, color="#7a7f87")
        _draw_chain(ax, plan, y=0.62, color=color)
        ax.set_title(title, fontsize=8.4, loc="left", pad=2)
        if i == 2:
            ax.set_xlabel(L("沿杆位置（mm，0 = 左墙）",
                                 "position (mm, 0 = left wall)"), fontsize=9)
    fig.suptitle(L("4 件衣物 = 5 个调节器（两端各 1、内部 3）",
                   "4 garments = 5 regulators (2 end + 3 inner)"),
                 fontsize=10.5, y=0.99)

    x = np.arange(len(plans["equal"].all_lengths))
    w = 0.26
    for k, (key, _, color) in enumerate(modes):
        axb.bar(x + (k - 1) * w, plans[key].all_lengths, width=w, color=color,
                edgecolor="white", lw=0.7,
                label={"equal": L("等距", "equal"),
                       "weighted": L("加权", "weighted"),
                       "collect": L("收衣", "collect")}[key])
    axb.set_xticks(x)
    axb.set_xticklabels(["L0", "L1", "L2", "L3", "L4"], fontsize=8.5)
    axb.set_ylabel(L("长度（mm）", "length (mm)"), fontsize=9.5)
    axb.set_title(L("各段：L0/L4 端部，L1–L3 净风道", "segment lengths"),
                  fontsize=9.5)
    axb.legend(fontsize=7.2, ncol=3, loc="upper right")
    axb.set_ylim(0, 230)
    style_axis(axb)
    return str(save_fig(fig, "v2-01-length-plan"))


# ---------------------------------------------------------------------------
def fig_chain_order(demo: dict) -> str:
    plan: lp.LengthPlan = demo["end_plan"]
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(10.0, 4.3), gridspec_kw={"width_ratios": [1.55, 1.0]})

    _draw_chain(ax1, plan, y=0.62, color=PALETTE[0], annotate_clamps=True)
    lay = ch.chain_layout(plan)
    ax1.axvspan(lay.chain_end_mm, plan.available_mm, color="#eceff3", zorder=0)
    ax1.text((lay.chain_end_mm + plan.available_mm) / 2, 0.86,
             L(f"空杆 {plan.leftover_mm:.0f} mm（端部夹头锁位区）",
               f"free rod {plan.leftover_mm:.0f} mm"),
             ha="center", va="top", fontsize=7.0, color="#7a7f87")
    for i, (l, r) in enumerate(lay.regulator_edges):
        if 0 < i < plan.K:
            ax1.annotate("", xy=(l, 0.34), xytext=(r, 0.34),
                         arrowprops=dict(arrowstyle="<->", color=PALETTE[1],
                                         lw=1.0))
            ax1.text((l + r) / 2, 0.26, f"L{i}", ha="center", va="top",
                     fontsize=7.0, color=PALETTE[1])
    ax1.text(-22, 0.99, L("每个调节器两端都有夹持（L/R）：锁一端→单向伸缩；锁两端→绝对锁长",
                          "double-end clamps"), ha="left", va="top", fontsize=7.2,
             color="#333")
    ax1.set_ylim(-0.08, 1.02)
    ax1.set_xlabel(L("沿杆位置（mm）", "position (mm)"), fontsize=9.5)
    centers = " / ".join(f"{v:.0f}" for v in lay.garment_centers)
    ax1.set_title(L(f"等距工况：衣架中心 {centers} mm",
                    "equal layout: garment centers"), fontsize=10)

    cmp = demo["comparison"]
    ax2.set_title(L("每次伸缩动作的轴向力", "axial force per move"), fontsize=10)
    for key, color, marker, label in (
            ("锚定左墙（推荐）", PALETTE[0], "o", L("锚定左墙（推荐）", "anchor")),
            ("不锁端（整链推）", PALETTE[4], "s", L("不锁端（反例）", "no clamp"))):
        moves = [s for s in cmp[key]["steps"]
                 if s["action"] in ("move_right", "move_left", "preload",
                                    "push_block")]
        xs = np.arange(1, len(moves) + 1)
        ax2.plot(xs, [s["force_n"] for s in moves], marker + "-", color=color,
                 lw=1.7, ms=5, label=label)
    ax2.axhline(ch.F_UNIT_N, color="#888", ls=":", lw=1.0)
    ax2.text(2.45, 3.0, L("伸缩副自身 2 N", "unit drag 2 N"), fontsize=7)
    ax2.set_xlabel(L("第几次伸缩动作", "move index"), fontsize=9.5)
    ax2.set_ylabel(L("轴向力（N）", "axial force (N)"), fontsize=9.5)
    ax2.set_xticks([1, 2, 3])
    ax2.legend(fontsize=7.4, loc="upper right")
    a = cmp["锚定左墙（推荐）"]
    b = cmp["不锁端（整链推）"]
    txt = (L(f"锚定：峰值 {a['peak_force_n']:.0f} N / {a['peak_current_a']:.2f} A\n"
             f"       {a['total_time_s']:.1f} s，已定位段 0 滑移\n"
             f"整链推：{b['peak_force_n']:.0f} N / {b['peak_current_a']:.2f} A，"
             f"{b['total_time_s']:.1f} s，需重标定",
             f"anchor {a['peak_force_n']:.0f} N, {a['total_time_s']:.1f} s\n"
             f"no-clamp {b['peak_force_n']:.0f} N"))
    ax2.text(0.02, 0.05, txt, transform=ax2.transAxes, ha="left", va="bottom",
             fontsize=6.8, color="#444",
             bbox=dict(boxstyle="round,pad=0.3", fc="#f7f7f7", ec="#ccc"))
    ax2.set_ylim(0, 17)
    style_axis(ax2)
    fig.tight_layout()
    return str(save_fig(fig, "v2-02-chain-order"))


# ---------------------------------------------------------------------------
def fig_timing(timing: dict, setup: dict) -> str:
    rows = timing["rows"]
    K = [r["K"] for r in rows]
    fig, ax = plt.subplots(figsize=(9.5, 3.9))
    colors = [PALETTE[0], PALETTE[2], PALETTE[4]]
    markers = ["o", "^", "s"]
    for i, name in enumerate(timing["drives"]):
        t = [r[name]["time_s"] for r in rows]
        ax.plot(K, t, marker=markers[i], color=colors[i], lw=1.8, ms=5,
                label=name)
    ax.axhline(timing["budget_s"], color="#333", ls="--", lw=1.2)
    ax.text(K[0], timing["budget_s"] + 1.0,
            L("需求：单次调整 ≤30 s", "budget 30 s"), fontsize=7.6)
    ax.scatter([setup["K"]], [setup["time_s"]], marker="*", s=150,
               color=PALETTE[3], zorder=5,
               label=L(f"安装标定（一次性）{setup['time_s']:.0f} s",
                       f"setup {setup['time_s']:.0f} s"))
    ax.annotate(L("日常工况：收衣→等距，只动内部段",
                  "daily: inner segments only"),
                xy=(4, rows[1][timing["drives"][0]]["time_s"]),
                xytext=(4.9, 9.0), fontsize=7.2, color=PALETTE[0],
                arrowprops=dict(arrowstyle="->", lw=0.8, color=PALETTE[0]))
    ax.set_xlabel(L("衣物件数 K（件）", "garments K"), fontsize=9.5)
    ax.set_ylabel(L("耗时（s）", "time (s)"), fontsize=9.5)
    ax.set_title(L("日常调节耗时 vs K（串行、锚定左墙、每段夹持 2 次）",
                   "daily cycle time vs K"), fontsize=10.5)
    ax.legend(fontsize=7.6, loc="upper left")
    ax.set_xticks(K)
    ax.set_ylim(0, max(max(r[d]["time_s"] for d in timing["drives"]) for r in rows) * 1.12)
    style_axis(ax)
    fig.tight_layout()
    return str(save_fig(fig, "v2-03-timing"))


# ---------------------------------------------------------------------------
def fig_control(study: dict, backlash: dict, stall: dict) -> str:
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(10.0, 3.6),
                                        gridspec_kw={"width_ratios": [1.2, 1.0, 1.05]})
    colors = [PALETTE[0], PALETTE[2], PALETTE[4]]
    for i, drive in enumerate(ch.DRIVES):
        res = study["traces"][drive.name]
        ax1.plot(res.t, res.x_load, color=colors[i], lw=1.6, label=drive.name)
    ax1.axhline(100.0, color="#333", ls=":", lw=1.0)
    ax1.text(0.6, 102.0, L("目标 100 mm", "target 100 mm"), fontsize=7.4)
    ax1.set_xlim(0, 16)
    ax1.set_ylim(35, 112)
    ax1.set_xlabel(L("时间（s）", "time (s)"), fontsize=9)
    ax1.set_ylabel(L("圆柱长度（mm）", "length (mm)"), fontsize=9)
    ax1.set_title(L("① 40→100 mm 阶跃（11 N 负载）", "① step 40→100 (11 N)"),
                  fontsize=9.6)
    ax1.legend(fontsize=6.8, loc="lower right")

    rows = backlash["rows"]
    errs = [r["error_mm"] for r in rows]
    short = [L("缩短", "shorten"), L("伸长", "extend"),
             L("单向逼近", "uni-dir"), L("单向+补偿", "uni+comp")]
    bars = ax2.bar(range(len(errs)), errs, width=0.6,
                   color=[PALETTE[1], PALETTE[0], PALETTE[2], PALETTE[3]],
                   edgecolor="white", lw=0.7)
    ax2.axhline(0, color="#333", lw=0.8)
    ax2.axhspan(-eb.SPEC_MM, eb.SPEC_MM, color="#3c9a5f", alpha=0.08)
    for b, e in zip(bars, errs):
        ax2.text(b.get_x() + b.get_width() / 2,
                 e + (0.008 if e >= 0 else -0.008), f"{e * 1000:+.0f} µm",
                 ha="center", va="bottom" if e >= 0 else "top", fontsize=6.8)
    ax2.set_xticks(range(len(errs)))
    ax2.set_xticklabels(short, fontsize=7.4)
    ax2.set_ylim(-0.11, 0.11)
    ax2.set_ylabel(L("负载侧长度误差（mm）", "load-side error (mm)"), fontsize=9)
    ax2.set_title(L(f"② 反向间隙 {backlash['backlash_mm']:.1f} mm",
                    "② backlash"), fontsize=9.6)

    res = stall["result"]
    ax3.plot(res.t, res.current, color=PALETTE[4], lw=1.4)
    ax3.axhline(stall["threshold_a"], color="#333", ls="--", lw=1.0)
    ax3.text(0.3, stall["threshold_a"] + 0.06,
             L(f"阈值 {stall['threshold_a']:.2f} A", "threshold"), fontsize=7.0)
    ax3.axvline(stall["stall_at_s"], color="#888", ls=":", lw=1.0)
    if stall["detect_abs_s"] is not None:
        ax3.axvline(stall["detect_abs_s"], color=PALETTE[3], ls="-.", lw=1.1)
        ax3.annotate(L(f"判出 {stall['detect_time_s'] * 1000:.0f} ms",
                       f"{stall['detect_time_s'] * 1000:.0f} ms"),
                     xy=(stall["detect_abs_s"], stall["peak_current_a"] * 0.92),
                     xytext=(6.0, stall["peak_current_a"] * 0.45),
                     fontsize=7.2, color=PALETTE[3],
                     arrowprops=dict(arrowstyle="->", lw=0.8, color=PALETTE[3]))
    ax3.set_xlim(0, 12)
    ax3.set_xlabel(L("时间（s）", "time (s)"), fontsize=9)
    ax3.set_ylabel(L("电机电流（A）", "current (A)"), fontsize=9)
    ax3.set_title(L("③ 2 s 卡住 → 堵转判据", "③ jam → stall detect"),
                  fontsize=9.6)
    for ax in (ax1, ax2, ax3):
        style_axis(ax)
    fig.tight_layout()
    return str(save_fig(fig, "v2-04-control"))


# ---------------------------------------------------------------------------
def fig_budget(budget: dict) -> str:
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(10.0, 3.9), gridspec_kw={"width_ratios": [1.15, 1.0]})
    contrib = budget["contributions"]
    names = [c["name"] for c in contrib][::-1]
    shares = [c["share_pct"] for c in contrib][::-1]
    tols = [c["tol_mm"] for c in contrib][::-1]
    y = np.arange(len(names))
    ax1.barh(y, shares, color=[PALETTE[i % len(PALETTE)] for i in range(len(names))],
             edgecolor="white", lw=0.6)
    for i, (s_, t) in enumerate(zip(shares, tols)):
        ax1.text(s_ + 1.0, i, f"{s_:.0f}%（±{t:.2f} mm）", va="center", fontsize=6.9)
    ax1.set_yticks(y)
    ax1.set_yticklabels(names, fontsize=7.6)
    ax1.set_xlim(0, max(shares) * 1.42)
    ax1.set_xlabel(L("对合成误差方差的贡献（%）", "share of variance (%)"), fontsize=9)
    ax1.set_title(L(f"① 误差来源（RSS = {budget['rss_mm']:.2f} mm）",
                    f"① sources (RSS {budget['rss_mm']:.2f} mm)"), fontsize=10)
    style_axis(ax1)

    mc = budget["monte_carlo"]
    samples = np.asarray(budget["samples_mm"])
    ax2.hist(samples, bins=60, color=PALETTE[0], alpha=0.75, edgecolor="white",
             lw=0.3, density=True)
    spec = budget["spec_mm"]
    ax2.axvspan(-spec, spec, color="#3c9a5f", alpha=0.10)
    for v in (-spec, spec):
        ax2.axvline(v, color="#2e7d4f", ls="--", lw=1.0)
    ax2.axvline(0, color="#333", lw=0.8)
    ax2.text(-spec + 0.05, ax2.get_ylim()[1] * 0.92,
             L("±2 mm 目标", "±2 mm spec"), fontsize=7.4, color="#2e7d4f")
    ax2.text(0.97, 0.60,
             L(f"p95 |e| = {mc['p95_abs_mm']:.2f} mm\n"
               f"99.9% = {mc['p999_abs_mm']:.2f} mm\n"
               f"±2 mm 内：{mc['p_within_spec'] * 100:.1f}%",
               f"p95 {mc['p95_abs_mm']:.2f} mm\n"
               f"p99.9 {mc['p999_abs_mm']:.2f} mm\n"
               f"within: {mc['p_within_spec'] * 100:.1f}%"),
             transform=ax2.transAxes, ha="right", va="top", fontsize=7.4,
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#ccc", alpha=0.9))
    ax2.set_xlim(-2.2, 2.2)
    ax2.set_xlabel(L("净风道误差（mm）", "gap error (mm)"), fontsize=9)
    ax2.set_ylabel(L("概率密度", "density"), fontsize=9)
    ax2.set_title(L(f"② 蒙特卡洛 {mc['n_runs']} 次", f"② MC {mc['n_runs']}"),
                  fontsize=10)
    style_axis(ax2)
    fig.tight_layout()
    return str(save_fig(fig, "v2-05-error-budget"))


# ---------------------------------------------------------------------------
def fig_vision(vision: dict) -> str:
    curve = vision["rate_curve"]
    px = np.array(sorted(int(k) for k in curve))
    rate = np.array([curve[int(k)] for k in px])
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.0, 3.7))

    ax1.plot(px, rate * 100, "o-", color=PALETTE[0], lw=1.8, ms=4)
    for z, name, color in ((1200.0, "1.2 m", PALETTE[2]),
                           (1500.0, "1.5 m", PALETTE[1]),
                           (2000.0, "2.0 m", PALETTE[4])):
        p = vi.marker_pixels(z)
        ax1.axvline(p, color=color, ls="--", lw=1.1)
        ax1.text(p + 0.3, 12, name, rotation=90, fontsize=7.2, color=color)
    ax1.axhline(95, color="#666", ls=":", lw=1.0)
    ax1.text(px.max() * 0.68, 96.5, L("95% 目标", "95% target"), fontsize=7.2)
    ax1.set_xlabel(L("标记像素边长（px）", "marker size (px)"), fontsize=9)
    ax1.set_ylabel(L("单帧识别率（%）", "per-frame recognition (%)"), fontsize=9)
    ax1.set_title(L("① 真实 ArUco 检测器：6–10 px 是拐点",
                    "① real ArUco: knee at 6–10 px"), fontsize=10)
    ax1.set_ylim(0, 105)
    ax1.set_xlim(2, px.max() + 1)
    style_axis(ax1)

    acq = vision["acq_1p5m_30mm"]
    times = np.asarray(vision.get("acq_times_s", []), dtype=float)
    finite = times[np.isfinite(times)]
    ax2.hist(finite, bins=24, color=PALETTE[2], alpha=0.78,
             edgecolor="white", lw=0.4)
    ax2.axvline(acq["p95_s"], color="#333", ls="--", lw=1.1)
    ax2.text(acq["p95_s"], ax2.get_ylim()[1] * 0.9,
             L(f" p95 {acq['p95_s']:.2f} s", f" p95 {acq['p95_s']:.2f} s"),
             fontsize=7.4)
    ax2.text(0.97, 0.55,
             L(f"{vision['params']['n_units']} 个 ID 全认全："
               f"{acq['success_rate'] * 100:.1f}%\n均值 {acq['mean_s']:.2f} s",
               f"all IDs: {acq['success_rate'] * 100:.1f}%\nmean {acq['mean_s']:.2f} s"),
             transform=ax2.transAxes, ha="right", va="top", fontsize=7.4,
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#ccc"))
    ax2.set_xlabel(L("识别耗时（s，含 3 帧去抖）", "acquisition time (s)"), fontsize=9)
    ax2.set_ylabel(L("次数", "count"), fontsize=9)
    ax2.set_title(L("② 1.5 m、30 mm：全部 ID 识别耗时",
                    "② acquisition at 1.5 m"), fontsize=10)
    style_axis(ax2)
    fig.tight_layout()
    return str(save_fig(fig, "v2-06-vision-id"))


# ---------------------------------------------------------------------------
def make_all(results: dict) -> List[str]:
    paths = []
    paths.append(fig_length_plan(results["plans"]))
    paths.append(fig_chain_order(results["chain"]["demo"]))
    paths.append(fig_timing(results["timing"], results["setup"]))
    paths.append(fig_control(results["control"]["study"],
                             results["control"]["backlash"],
                             results["control"]["stall"]))
    paths.append(fig_budget(results["budget"]))
    paths.append(fig_vision(results["vision"]))
    return paths


__all__ = ["make_all"]
