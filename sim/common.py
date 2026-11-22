"""衣序 HangFlow 仿真公共工具：中文字体、输出目录、图幅与保存。

- 自动挑选系统可用中文字体（msyh/simhei/simsun 等）；找不到就退回英文标签（ZH=False），
  绝不让图里出现方块字。
- 统一 300 dpi，图宽 8–10 英寸，直接放进方案文档。
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无 GUI 环境（RDK / 服务器）也能出图
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "docs" / "figures"
DATA_DIR = ROOT / "docs" / "_data"

DPI = 300
ZH = False  # 是否启用中文标签（setup_fonts() 里决定）

# 亮色系、色盲友好（tab10 风格微调）
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
# 用这些字判断字体是否真含汉字（缺字会画成方块）
_PROBE_CHARS = "间隙速度误差杆长衣物湿度重排"


def setup_fonts(verbose: bool = True) -> bool:
    """安装可用中文字体并设置 rcParams，返回是否启用中文。"""
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
        except Exception as exc:  # 字体文件损坏/权限问题都不该中断仿真
            if verbose:
                print(f"[fonts] 跳过 {path}: {exc}")
    plt.rcParams["font.family"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    ZH = False
    if verbose:
        print("[fonts] 未找到可用中文字体，图内标签改用英文")
    return False


def L(zh: str, en: str) -> str:
    """按字体可用性返回中文或英文标签。"""
    return zh if ZH else en


def new_fig(width: float = 9.5, height: float = 4.2, **kwargs):
    """建图：默认 9.5 英寸宽，300dpi 下约 2850px，够文档与答辩屏。"""
    fig, axes = plt.subplots(figsize=(width, height), **kwargs)
    return fig, axes


def save_fig(fig, name: str) -> Path:
    """保存到 docs/figures/，返回路径。"""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / (name if name.endswith(".png") else f"{name}.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[fig]  {path.relative_to(ROOT)}  ({path.stat().st_size / 1024:.0f} KB)")
    return path


def style_axis(ax, title: str = "", xlabel: str = "", ylabel: str = "") -> None:
    """统一坐标轴风格：网格、字号、单位提示。"""
    if title:
        ax.set_title(title, fontsize=11.5, pad=8)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9.5)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9.5)
    ax.tick_params(labelsize=8.5)
    ax.grid(True, ls="--", lw=0.6, alpha=0.45)
    ax.set_axisbelow(True)
