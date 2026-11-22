"""把 README + docs/00—17 合并成一本可打印的《衣序 HangFlow 方案书》。

用法：
    python assets/scripts/build_book.py
产物：
    deck/book.html
    deck/衣序-完整方案书.pdf  （用 Edge / Chrome 打印，命令见 deck/README.md）

说明：
- 图片路径转成绝对 file:// URI，保证打印时能加载；
- 站内 .md 链接转成书内锚点，外链保留；
- 浅色"纸张"排版（深色只用于封面），A4，章节分页。
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "deck"
OUT_HTML = DECK / "book.html"

CHAPTERS = [
    ("README.md", "总览"),
    ("docs/00-执行摘要.md", "执行摘要"),
    ("docs/01-赛题解读与参赛策略.md", "赛题解读与参赛策略"),
    ("docs/02-产品定义与用户研究.md", "产品定义与用户研究"),
    ("docs/03-系统总体方案.md", "系统总体方案"),
    ("docs/04-机械结构设计.md", "机械结构设计"),
    ("docs/05-硬件与电控设计.md", "硬件与电控设计"),
    ("docs/06-视觉与算法.md", "视觉与算法"),
    ("docs/07-软件架构与通信协议.md", "软件架构与通信协议"),
    ("docs/08-交互与App设计.md", "交互与 App 设计"),
    ("docs/09-BOM与成本.md", "BOM 与成本"),
    ("docs/10-赛前12天准备计划.md", "赛前 12 天准备计划"),
    ("docs/11-现场48小时执行计划.md", "现场 48 小时执行计划"),
    ("docs/12-演示脚本与答辩.md", "演示脚本与答辩"),
    ("docs/13-风险与PlanB.md", "风险与 Plan B"),
    ("docs/14-测试与验收.md", "测试与验收"),
    ("docs/15-产品化与商业化.md", "产品化与商业化"),
    ("docs/16-AI辅助开发与过程证据.md", "AI 辅助开发与过程证据"),
    ("docs/17-RDK平台与开发环境.md", "RDK 平台与开发环境"),
    ("docs/_data/algorithm-results.md", "附录 A · 算法仿真结果"),
]

ANCHOR = {src: f"ch-{i}" for i, (src, _) in enumerate(CHAPTERS)}


def resolve_links(text: str, src: Path) -> str:
    """把图片/链接的相对路径改成可打印/可跳转的形式。"""

    def img(m: re.Match) -> str:
        path = m.group(1).strip()
        if path.startswith(("http://", "https://", "data:")):
            return m.group(0)
        p = (src.parent / path).resolve()
        return f"![{m.group(2)}]({p.as_uri()})" if p.exists() else m.group(0)

    def link(m: re.Match) -> str:
        label, path = m.group(1), m.group(2).strip()
        if path.startswith(("http://", "https://", "mailto:", "#")):
            return m.group(0)
        clean = path.split("#")[0]
        p = (src.parent / clean).resolve()
        try:
            rel = p.relative_to(ROOT).as_posix()
        except ValueError:
            return label
        if rel in ANCHOR:
            return f"[{label}](#{ANCHOR[rel]})"
        if p.exists() and p.suffix.lower() in {".md", ".pdf", ".html"}:
            return f"[{label}]({p.as_uri()})"
        return label

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", img, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    return text


def build() -> None:
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "toc"],
                           extension_configs={"toc": {"permalink": False}})
    parts: list[str] = []
    toc: list[str] = []

    for i, (src, title) in enumerate(CHAPTERS):
        p = ROOT / src
        if not p.exists():
            continue
        raw = p.read_text(encoding="utf-8", errors="ignore")
        raw = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.S)  # 去 YAML
        raw = resolve_links(raw, p)
        md.reset()
        body = md.convert(raw)
        ch = ANCHOR[src]
        toc.append(f'<li><a href="#{ch}">{html.escape(title)}</a></li>')
        parts.append(f'<section class="chapter" id="{ch}"><div class="ch-label">{i:02d}</div>{body}</section>')

    cover = f"""
    <section class="cover">
      <div class="cover-tag">DDC2026 · 地瓜机器人黑客松 · 方案书 v1.0</div>
      <h1>衣序 <span>HangFlow</span></h1>
      <p class="sub">不换晾衣杆，让衣服自己让出风道。</p>
      <img src="{(ROOT / 'assets/diagrams/product-hero.svg').as_uri()}" alt="产品概念">
      <div class="cover-meta">
        <div>套挂式衣物间距调节器 · RDK X5 视觉中枢 · 4 单元协同</div>
        <div>2026-11-23 · theVivia/D-robotics-ClothesRodHelper</div>
      </div>
    </section>
    """

    css = """
    @page { size: A4; margin: 17mm 16mm 16mm; }
    * { box-sizing: border-box; }
    body {
      margin: 0; color: #1b1f26; background: #fff;
      font-family: -apple-system, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
      font-size: 10.3pt; line-height: 1.72;
    }
    .cover {
      height: 260mm; display: flex; flex-direction: column; justify-content: center;
      padding: 0 4mm; page-break-after: always;
      background: #06080b; color: #eef2f8; margin: -17mm -16mm 0; padding: 30mm 22mm;
    }
    .cover-tag { color: #d6b173; letter-spacing: .22em; font-size: 9pt; margin-bottom: 8mm; }
    .cover h1 { font-size: 46pt; margin: 0 0 4mm; letter-spacing: -.02em; color: #eef2f8; }
    .cover h1 span { font-weight: 300; color: #98a4b5; }
    .cover .sub { font-size: 16pt; color: #eef2f8; margin: 0 0 12mm; }
    .cover img { width: 100%; border-radius: 4mm; border: 1px solid rgba(255,255,255,.12); }
    .cover-meta { margin-top: 10mm; color: #98a4b5; font-size: 9pt; line-height: 1.9; letter-spacing: .04em; }
    .toc { page-break-after: always; }
    .toc h2 { font-size: 22pt; margin: 0 0 8mm; color: #0b0d10; }
    .toc ol { columns: 2; column-gap: 14mm; padding-left: 6mm; }
    .toc li { margin: 0 0 3.2mm; font-size: 11pt; }
    .toc a { color: #1b1f26; text-decoration: none; }
    .chapter { page-break-before: always; }
    .ch-label { font-family: Consolas, monospace; color: #b08a45; font-size: 9pt; letter-spacing: .2em; margin-bottom: 2mm; }
    h1 { font-size: 22pt; line-height: 1.25; margin: 0 0 5mm; color: #0b0d10; }
    h2 { font-size: 15.5pt; margin: 9mm 0 3mm; padding-bottom: 1.6mm; border-bottom: 1px solid #e6dcc8; color: #14181f; }
    h3 { font-size: 12.3pt; margin: 6mm 0 2mm; color: #232936; }
    h4 { font-size: 11pt; margin: 4mm 0 1.5mm; }
    p { margin: 0 0 2.6mm; }
    a { color: #8a641f; text-decoration: none; }
    blockquote { margin: 3mm 0; padding: 2.5mm 4mm; border-left: 2.2pt solid #d6b173; background: #faf7f1; color: #3a4150; }
    code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 9pt; background: #f3f1ec; padding: .3mm 1mm; border-radius: 1mm; }
    pre { background: #0e1218; color: #d8e0ea; padding: 3.5mm 4mm; border-radius: 2mm; overflow: hidden; font-size: 8.2pt; line-height: 1.5; page-break-inside: avoid; }
    pre code { background: none; color: inherit; padding: 0; font-size: 8.2pt; }
    table { width: 100%; border-collapse: collapse; margin: 2.5mm 0 4mm; font-size: 9pt; page-break-inside: auto; }
    th { background: #f4efe4; text-align: left; font-weight: 650; }
    th, td { border: 1px solid #ddd4c3; padding: 1.4mm 2mm; vertical-align: top; }
    tr { page-break-inside: avoid; }
    img { max-width: 100%; height: auto; display: block; margin: 3mm auto; page-break-inside: avoid; }
    ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
    li { margin: 0 0 1.2mm; }
    hr { border: none; border-top: 1px solid #e6dcc8; margin: 6mm 0; }
    """

    doc = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
    <title>衣序 HangFlow · 方案书 v1.0</title><style>{css}</style></head><body>
    {cover}
    <section class="toc"><h2>目录</h2><ol>{''.join(toc)}</ol></section>
    {''.join(parts)}
    </body></html>"""

    OUT_HTML.write_text(doc, encoding="utf-8")
    print("written", OUT_HTML.relative_to(ROOT), f"({len(doc)/1024:.0f} KB, {len(CHAPTERS)} chapters)")


if __name__ == "__main__":
    build()


