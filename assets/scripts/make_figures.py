# -*- coding: utf-8 -*-
"""衣序 HangFlow · 文档配图生成脚本（可重复运行）

生成：
  docs/figures/gantt.png           赛前 12 天 + 现场 48 小时甘特图
  docs/figures/cost-breakdown.png  整机成本构成（估算）
  docs/figures/demo-flow.png       现场演示 6 步流程

用法：
  python assets/scripts/make_figures.py
依赖：Python 3.11 + matplotlib，中文字体优先 Microsoft YaHei / SimHei
颜色：背景 #0B0D10 / 卡片 #12161C / 金色 #D4A24C / 文字 #E8EAED
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, Circle, Rectangle, Polygon
from matplotlib.lines import Line2D

# ---------------------------------------------------------------- 主题与字体
BG = "#0B0D10"
CARD = "#12161C"
GOLD = "#D4A24C"
TEXT = "#E8EAED"
MUTED = "#9AA3AF"
DIM = "#6B7480"
GRID = "#232A33"
LINE = "#2F3742"

# 辅助色：低饱和，只做区分，不抢金色
STEEL = "#5F7E8C"
SAGE = "#6E8B74"
PLUM = "#9A7E9E"
TAN = "#8C7A5A"

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "figures"

FONT_CANDIDATES = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei"]


def setup_font() -> str:
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((n for n in FONT_CANDIDATES if n in available), None)
    if chosen is None:
        for p in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
            if os.path.exists(p):
                try:
                    font_manager.fontManager.addfont(p)
                    chosen = font_manager.FontProperties(fname=p).get_name()
                    break
                except Exception:
                    continue
    if chosen is None:
        chosen = "DejaVu Sans"
        print("[warn] 未找到中文字体，中文可能显示为方块")
    plt.rcParams["font.sans-serif"] = [chosen, "DejaVu Sans"]
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False
    return chosen


def style_axes(ax, title: str = ""):
    ax.set_facecolor(CARD)
    for s in ax.spines.values():
        s.set_color(LINE)
    ax.tick_params(colors=MUTED, labelsize=9)
    if title:
        ax.set_title(title, color=TEXT, fontsize=12.5, loc="left", pad=12, fontweight="bold")
    ax.grid(True, axis="x", color=GRID, linewidth=0.8, alpha=0.75)
    ax.set_axisbelow(True)


def save(fig, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    fig.savefig(path, dpi=300, facecolor=BG, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"[ok] {path.relative_to(ROOT)}  ({path.stat().st_size // 1024} KB)")


# ---------------------------------------------------------------- 1. 甘特图
CAT_COLORS = {
    "采购/供应链": TAN,
    "机械": STEEL,
    "电控": SAGE,
    "软件/视觉": GOLD,
    "产品/演示": PLUM,
}

PREP_TASKS = [
    # (lane, 起始日, 结束日, 标签, 类别)
    ("方案定稿 / 文档", 0, 1, "文档 + CAD + BOM", "产品/演示"),
    ("采购下单 → 到货", 1, 4, "长周期件 11.24 下单", "采购/供应链"),
    ("机械 CAD → 打样", 0, 3, "SCAD → 打印 → 装 1 套", "机械"),
    ("电控 → 固件闭环", 3, 7, "面包板 → 位置环 → 急停", "电控"),
    ("软件 / 视觉联调", 0, 9, "mock → 视觉 → 真机", "软件/视觉"),
    ("产品 / 演示 / 答辩", 1, 11, "访谈 → 脚本 → 彩排", "产品/演示"),
]

PREP_MILESTONES = [
    (1.5, 1, "M1 下单死线", -0.95),
    (7.5, 0.55, "M2 确认截止", -0.95),
    (10.5, 0.55, "M3 全流程彩排", -0.95),
    (11.5, 0.55, "M4 Go/No-Go", -1.40),
]

ONSITE_TASKS = [
    ("布场 + 机械装配", 0, 6, "机械"),
    ("电控 + 固件", 3, 9, "电控"),
    ("视觉标定 + 联调", 19, 27, "软件/视觉"),
    ("智能功能 + 串演", 23, 30, "软件/视觉"),
    ("冻结 / 录像 / 提交", 30, 47, "产品/演示"),
    ("评审 + 决赛路演", 49, 53.5, "产品/演示"),
]

ONSITE_GATES = [(11, "G1"), (23, "G2"), (30, "G3")]


def make_gantt(font: str):
    fig = plt.figure(figsize=(10.6, 6.9), facecolor=BG)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.55, 1.0], wspace=0.18,
                          left=0.058, right=0.985, top=0.80, bottom=0.215)

    fig.suptitle("从今天到路演：15 天节奏", x=0.058, y=0.972, ha="left",
                 color=TEXT, fontsize=17, fontweight="bold")
    fig.text(0.058, 0.915, "赛前 12 天把确定性做满，现场 48 小时只做集成、调试、展示",
             color=MUTED, fontsize=9.5, ha="left")

    # ---------------- 左：赛前 12 天
    ax = fig.add_subplot(gs[0, 0])
    style_axes(ax, "赛前 12 天（11.23 – 12.04）")
    for i, (lane, s, e, label, cat) in enumerate(PREP_TASKS):
        ax.barh(i, e - s, left=s, height=0.52, color=CAT_COLORS[cat], alpha=0.92,
                edgecolor=BG, linewidth=1.2, zorder=3)
        ax.text(e + 0.14, i, label, va="center", ha="left", color=MUTED,
                fontsize=8.0, zorder=4, clip_on=True)
    ax.set_yticks(range(len(PREP_TASKS)))
    ax.set_yticklabels([t[0] for t in PREP_TASKS], color=TEXT, fontsize=9.5)
    ax.invert_yaxis()
    ax.set_xlim(-0.3, 15.6)
    ax.set_ylim(len(PREP_TASKS) - 0.35, -1.72)
    ax.set_xticks(range(12))
    ax.set_xticklabels(["11.23", "11.24", "11.25", "11.26", "11.27", "11.28",
                        "11.29", "11.30", "12.01", "12.02", "12.03", "12.04"],
                       rotation=45, ha="right", fontsize=8, color=MUTED)

    for x, alpha, name, ylabel in PREP_MILESTONES:
        ax.axvline(x, color=GOLD, linewidth=0.9, linestyle=(0, (4, 3)), alpha=alpha, zorder=2)
        ax.plot(x, -0.55, marker="D", markersize=5.5, color=GOLD, zorder=5)
        ax.text(x, ylabel, name, ha="center", va="center", color=GOLD,
                fontsize=7.4, zorder=6)

    # ---------------- 右：现场 48 小时
    ax2 = fig.add_subplot(gs[0, 1])
    style_axes(ax2, "现场 48 小时（12.05 13:00 – 12.07 18:30）")
    for i, (lane, s, e, cat) in enumerate(ONSITE_TASKS):
        ax2.barh(i, e - s, left=s, height=0.52, color=CAT_COLORS[cat], alpha=0.92,
                 edgecolor=BG, linewidth=1.2, zorder=3)
    ax2.set_yticks(range(len(ONSITE_TASKS)))
    ax2.set_yticklabels([t[0] for t in ONSITE_TASKS], color=TEXT, fontsize=9.5)
    ax2.invert_yaxis()
    ax2.set_xlim(-0.8, 54)
    ax2.set_ylim(len(ONSITE_TASKS) - 0.35, -1.72)
    ax2.set_xticks([0, 6, 12, 18, 24, 30, 36, 42, 48, 54])
    ax2.set_xticklabels(["13:00", "19:00", "01:00", "07:00", "13:00",
                         "19:00", "01:00", "07:00", "13:00", "19:00"],
                        rotation=45, ha="right", fontsize=7.6, color=MUTED)
    for boundary in (11, 35):
        ax2.axvline(boundary, color=LINE, linewidth=1.2, zorder=1)
    for x, name in ONSITE_GATES:
        ax2.plot(x, -0.55, marker="D", markersize=5.5, color=GOLD, zorder=5)
        ax2.text(x + 0.9, -0.55, name, ha="left", va="center", color=GOLD,
                 fontsize=7.4, fontweight="bold", zorder=6)
    for x in (47, 49):
        ax2.axvline(x, color=GOLD, linewidth=0.9, linestyle=(0, (4, 3)), alpha=0.45, zorder=2)
    for lo, hi, label in [(0, 11, "Day 1 · 12.05"), (11, 35, "Day 2 · 12.06"), (35, 53.5, "Day 3 · 12.07")]:
        ax2.text((lo + hi) / 2, -1.22, label, ha="center", va="center",
                 color=MUTED, fontsize=8.2)

    # ---------------- 图例与脚注
    handles = [Rectangle((0, 0), 1, 1, color=c, label=k) for k, c in CAT_COLORS.items()]
    handles.append(Line2D([0], [0], marker="D", color="none", markerfacecolor=GOLD,
                          markeredgecolor=GOLD, markersize=7, label="门禁 / 里程碑"))
    leg = fig.legend(handles=handles, loc="lower center", ncol=6, frameon=False,
                     bbox_to_anchor=(0.52, 0.025), fontsize=8.6)
    for t in leg.get_texts():
        t.set_color(MUTED)

    fig.text(0.058, 0.145,
             "M1 11.24 下单死线  ·  M2 11.30 参赛确认截止  ·  M3 12.03 全流程彩排  ·  M4 12.04 Go/No-Go",
             color=MUTED, fontsize=7.8, ha="left")
    fig.text(0.058, 0.108,
             "G1 12.05 24:00 ≥3 单元可控  ·  G2 12.06 12:00 一键等距  ·  G3 12.06 19:00 全流程 5 次  ｜  "
             "12.07 12:00 提交 · 14:00 评审 · 18:30 路演",
             color=MUTED, fontsize=7.8, ha="left")
    fig.text(0.985, 0.108, "数据来源：docs/10 · docs/11", color=DIM, fontsize=7.2,
             ha="right", va="center")
    save(fig, "gantt.png")


# ---------------------------------------------------------------- 2. 成本构成
# 口径：docs/09-BOM与成本.md（2026-11-23 Lead 锁定值）
COST_MAIN = [
    ("套挂单元 ×4（打样）", 600, 0.95, "单单元 ¥150：电控电池 ¥86.5 + 机械 ¥65"),
    ("中枢外设", 175, 0.75, "相机 79 · 电源 45 · 5A 线 18 · SD 卡 25 · 散热 8"),
    ("演示架", 75, 0.55, "铝管 20 · 立杆 45 · ArUco 10"),
]
COST_RDK = ("RDK X5（现场发放）", 549)


def make_cost(font: str):
    fig = plt.figure(figsize=(10.0, 5.5), facecolor=BG)
    ax = fig.add_axes([0.30, 0.19, 0.655, 0.585])
    style_axes(ax)

    total = sum(c[1] for c in COST_MAIN)
    y_main = [3, 2, 1]
    bars = ax.barh(y_main, [c[1] for c in COST_MAIN], height=0.56, color=GOLD,
                   edgecolor=BG, linewidth=1.2, zorder=3)
    for b, c in zip(bars, COST_MAIN):
        b.set_alpha(c[2])
    for y, c in zip(y_main, COST_MAIN):
        ax.text(c[1] + 12, y, f"¥{c[1]}", va="center", ha="left", color=TEXT,
                fontsize=10, fontweight="bold")
        ax.text(c[1] + 72, y, f"{c[1] / total * 100:.0f}%", va="center", ha="left",
                color=MUTED, fontsize=8.5)
        ax.text(6, y - 0.42, c[3], va="center", ha="left", color=MUTED, fontsize=8.2)

    # RDK：账面参考，不计自购
    ax.axhline(0.46, color=LINE, linewidth=1, linestyle=(0, (4, 4)))
    rdk_bar = ax.barh([0], [COST_RDK[1]], height=0.42, color=GOLD, alpha=0.20,
                      edgecolor=GOLD, linewidth=1.1, zorder=3)
    ax.text(COST_RDK[1] + 12, 0, f"¥{COST_RDK[1]}", va="center", ha="left",
            color=MUTED, fontsize=9.5)
    ax.text(6, -0.36, "主办方现场发放，不计入自购金额", va="center", ha="left",
            color=DIM, fontsize=8.2)

    ax.set_yticks(y_main + [0])
    ax.set_yticklabels([c[0] for c in COST_MAIN] + [COST_RDK[0]], color=TEXT, fontsize=10)
    ax.set_ylim(-0.75, 3.45)
    ax.set_xlim(0, 720)
    ax.set_xlabel("金额（元，参考价）", color=MUTED, fontsize=9)
    ax.grid(True, axis="x", color=GRID, linewidth=0.8)
    ax.grid(False, axis="y")

    fig.text(0.035, 0.945, "整机打样成本构成（不含 RDK）", color=TEXT,
             fontsize=16, fontweight="bold", ha="left")
    fig.text(0.035, 0.898, "docs/09 锁定口径 · 参考价（2026-11 电商估价）· 非询价单", color=MUTED,
             fontsize=9.5, ha="left")
    fig.text(0.972, 0.940, f"自购打样  ¥{total}", color=GOLD,
             fontsize=21, fontweight="bold", ha="right")
    fig.text(0.972, 0.890, "含 RDK 账面 ¥1,400 ｜ 量产 1 万台 ¥650（不含 RDK）", color=MUTED,
             fontsize=9, ha="right")

    fig.text(0.035, 0.098, "自购实际 = 打样 ¥850 + 建议另购保险 ¥449（充电宝 / 排插 / 备件 / 工具 / 备份卡）= ¥1,299。",
             color=MUTED, fontsize=8.4, ha="left")
    fig.text(0.035, 0.058, "细化 BOM 与量产估算见 docs/09-BOM与成本.md §1–§5；单单元成本里机械占 43%，降本先降打印工时。",
             color=DIM, fontsize=8.0, ha="left")
    save(fig, "cost-breakdown.png")


# ---------------------------------------------------------------- 3. 演示流程
# 画布按英寸排布（1 单位 = 1 inch），保证图标不被拉伸
DEMO_STEPS = [
    ("01", "扫码连接", "评委手机\n扫展台二维码", "≈30 s", "qr"),
    ("02", "一键等距", "4 件衣服\n从挤到排开", "≈25 s", "equalize"),
    ("03", "智能分配", "按湿度加权\n湿的间隙更大", "≈20 s", "weight"),
    ("04", "收衣归拢", "一键收拢\n到一端", "≈15 s", "fold"),
    ("05", "急停验证", "红色急停\n全部立即停止", "≈5 s", "stop"),
    ("06", "复位归零", "10 秒复位\n准备下一轮", "≈10 s", "reset"),
]


def _icon(ax, kind: str, cx: float, cy: float):
    """图标几何单位为英寸；金色描边 + 浅色主体。"""
    lw = 1.7
    if kind == "qr":
        ax.add_patch(FancyBboxPatch((cx - 0.19, cy - 0.27), 0.38, 0.54,
                                    boxstyle="round,pad=0.012,rounding_size=0.06",
                                    linewidth=lw, edgecolor=TEXT, facecolor="none"))
        for dx, dy in [(-0.13, 0.10), (0.0, 0.10), (-0.13, -0.03), (0.04, -0.10)]:
            ax.add_patch(Rectangle((cx + dx, cy + dy), 0.075, 0.075, linewidth=1.1,
                                   edgecolor=GOLD, facecolor="none"))
        ax.plot([cx - 0.14, cx + 0.14], [cy + 0.16, cy + 0.16], color=GOLD, lw=1.8)
    elif kind == "equalize":
        for side in (-1, 1):
            ax.add_patch(FancyBboxPatch((cx + side * 0.30 - 0.035, cy - 0.22), 0.07, 0.44,
                                        boxstyle="round,pad=0.008,rounding_size=0.025",
                                        linewidth=1.3, edgecolor=TEXT, facecolor="none"))
            ax.annotate("", xy=(cx + side * 0.22, cy), xytext=(cx + side * 0.06, cy),
                        arrowprops=dict(arrowstyle="-|>", color=GOLD, lw=1.8,
                                        shrinkA=0, shrinkB=0))
    elif kind == "weight":
        ax.add_patch(Polygon([[cx, cy + 0.24], [cx - 0.13, cy + 0.03], [cx, cy - 0.12],
                              [cx + 0.13, cy + 0.03]], closed=True, linewidth=1.6,
                             edgecolor=GOLD, facecolor="none"))
        for i, h in enumerate((0.18, 0.30, 0.24, 0.40)):
            x = cx - 0.26 + i * 0.17
            ax.plot([x, x], [cy - 0.30, cy - 0.30 + h], color=TEXT, lw=2.0,
                    solid_capstyle="round")
    elif kind == "fold":
        for i, x in enumerate((-0.22, -0.07, 0.08)):
            ax.add_patch(Rectangle((cx + x, cy - 0.18), 0.075, 0.36, linewidth=1.3,
                                   edgecolor=TEXT, facecolor="none"))
        ax.annotate("", xy=(cx - 0.30, cy + 0.26), xytext=(cx + 0.22, cy + 0.26),
                    arrowprops=dict(arrowstyle="-|>", color=GOLD, lw=1.8,
                                    shrinkA=0, shrinkB=0))
        ax.plot([cx - 0.30, cx - 0.30], [cy + 0.26, cy + 0.16], color=GOLD, lw=1.8)
    elif kind == "stop":
        pts = [(cx + 0.24 * math.cos(math.pi / 8 + k * math.pi / 4),
                cy + 0.24 * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
        ax.add_patch(Polygon(pts, closed=True, linewidth=1.8, edgecolor=GOLD, facecolor="none"))
        ax.plot([cx - 0.08, cx + 0.08], [cy - 0.08, cy + 0.08], color=GOLD, lw=2.0)
        ax.plot([cx - 0.08, cx + 0.08], [cy + 0.08, cy - 0.08], color=GOLD, lw=2.0)
    elif kind == "reset":
        theta = np.linspace(0.30 * np.pi, 1.80 * np.pi, 60)
        ax.plot(cx + 0.22 * np.cos(theta), cy + 0.22 * np.sin(theta), color=GOLD, lw=2.0)
        ax.add_patch(Circle((cx, cy), 0.045, color=TEXT, zorder=4))
        ax.annotate("", xy=(cx + 0.05, cy + 0.30), xytext=(cx - 0.07, cy + 0.20),
                    arrowprops=dict(arrowstyle="-|>", color=GOLD, lw=1.8,
                                    shrinkA=0, shrinkB=0))


def make_demo_flow(font: str):
    W, H = 10.4, 3.6
    fig = plt.figure(figsize=(W, H), facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")

    n = len(DEMO_STEPS)
    margin, gap = 0.30, 0.22
    card_w = (W - 2 * margin - gap * (n - 1)) / n
    card_y, card_h = 0.34, 2.22

    for i, (num, title, detail, t, icon) in enumerate(DEMO_STEPS):
        x = margin + i * (card_w + gap)
        ax.add_patch(FancyBboxPatch((x, card_y), card_w, card_h,
                                    boxstyle="round,pad=0.01,rounding_size=0.10",
                                    facecolor=CARD, edgecolor=LINE, linewidth=1.1))
        ax.add_patch(Circle((x + 0.19, card_y + card_h - 0.20), 0.125,
                            facecolor=GOLD, edgecolor="none", zorder=4))
        ax.text(x + 0.19, card_y + card_h - 0.20, num, ha="center", va="center",
                color=BG, fontsize=7.2, fontweight="bold", zorder=5)
        ax.text(x + card_w - 0.14, card_y + card_h - 0.20, t, ha="right", va="center",
                color=GOLD, fontsize=7.0)

        _icon(ax, icon, x + card_w / 2, card_y + card_h - 0.78)

        ax.text(x + card_w / 2, card_y + 0.66, title, ha="center", va="center",
                color=TEXT, fontsize=10.5, fontweight="bold")
        ax.text(x + card_w / 2, card_y + 0.32, detail, ha="center", va="center",
                color=MUTED, fontsize=7.0, linespacing=1.55)

        if i < n - 1:
            ax.annotate("", xy=(x + card_w + gap - 0.02, card_y + card_h / 2),
                        xytext=(x + card_w + 0.02, card_y + card_h / 2),
                        arrowprops=dict(arrowstyle="-|>", color=GOLD, lw=2.0,
                                        shrinkA=0, shrinkB=0, mutation_scale=12))

    ax.text(margin, H - 0.42, "现场演示 6 步 · 全程 ≤90 秒", color=TEXT,
            fontsize=15, fontweight="bold", va="center")
    ax.text(margin, H - 0.72,
            "从「4 件挤在一起」到「排开 + 收衣 + 急停复位」；评委可自己上手操作",
            color=MUTED, fontsize=8.2, va="center")
    ax.text(margin, 0.16, "对应文档：docs/12 演示脚本与答辩 · docs/11 现场 48 小时执行计划 §4",
            color=DIM, fontsize=7.0, va="center")
    save(fig, "demo-flow.png")


def main():
    font = setup_font()
    print(f"[font] {font}")
    make_gantt(font)
    make_cost(font)
    make_demo_flow(font)


if __name__ == "__main__":
    main()
