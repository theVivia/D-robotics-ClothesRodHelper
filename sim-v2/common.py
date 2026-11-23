"""衣序 HangFlow v2 仿真公共工具：中文字体、输出目录、300 dpi 出图。

v2 与 v1 的公共部分（字体回退、图幅规范）直接复用，但输出目录是
docs/figures-v2/ 与 docs/_data-v2/，不碰 v1 的产物。
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "docs" / "figures-v2"
DATA_DIR = ROOT / "docs" / "_data-v2"

DPI = 300
ZH = False

PALETTE = [
    "#2f6fb3",
    "#d9822b",
    "#3c9a5f",
    "#a05195",
    "#c0392b",
    "#7f8c8d",
]

_FONT_CANDIDATES = [
    r"C:/Windows/Fonts/msyh.ttc",
    r"C:/Windows/Fonts/msyhbd.ttc",
    r"C:/Windows/Fonts/simhei.ttf",
    r"C:/Windows/Fonts/simsun.ttc",
    r"/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    r"/System/Library/Fonts/PingFang.ttc",
]
_PROBE_CHARS = "圆柱长度接缝衣架湿度误差风道"


def setup_fonts(verbose: bool = True) -> bool:
    """安装可用中文字体；找不到就退回英文标签，避免方块。"""
    global ZH
    for path in _FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            font_manager.fontManager.addfont(path)
            name = font_manager.FontProperties(fname=path).get_name()
            from matplotlib.ft2font import FT2Font

            face = FT2Font(path)
            if any(face.get_char_index(ord(ch)) == 0 for ch in _PROBE_CHARS):
                continue
            plt.rcParams["font.family"] = [name, "DejaVu Sans"]
            plt.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            ZH = True
            if verbose:
                print(f"[fonts] 中文标签已启用：{name}  ({path})")
            return True
        except Exception as exc:
            if verbose:
                print(f"[fonts] 跳过 {path}: {exc}")
    plt.rcParams["font.family"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    ZH = False
    if verbose:
        print("[fonts] 未找到可用中文字体，图内标签改用英文")
    return False


def L(zh: str, en: str) -> str:
    return zh if ZH else en


def new_fig(width: float = 9.8, height: float = 4.0, **kwargs):
    return plt.subplots(figsize=(width, height), **kwargs)


def save_fig(fig, name: str) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / (name if name.endswith(".png") else f"{name}.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[fig]  {path.relative_to(ROOT)}  ({path.stat().st_size / 1024:.0f} KB)")
    return path


def style_axis(ax, title: str = "", xlabel: str = "", ylabel: str = "") -> None:
    if title:
        ax.set_title(title, fontsize=11, pad=7)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9.5)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9.5)
    ax.tick_params(labelsize=8.5)
    ax.grid(True, ls="--", lw=0.6, alpha=0.45)
    ax.set_axisbelow(True)
