"""把 docs/v2/12-完整方案书.md 转成 HTML，供 Edge 打印 PDF。"""
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
src = ROOT / "docs" / "v2" / "12-完整方案书.md"
out = ROOT / "docs" / "v2" / "衣序-v2-完整方案书.html"

body = markdown.markdown(
    src.read_text(encoding="utf-8"),
    extensions=["tables", "fenced_code", "toc", "sane_lists"],
)

html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>衣序 HangFlow · v2 完整方案书</title>
<style>
  @page {{ size: A4; margin: 18mm 16mm; }}
  body {{ font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
         color:#1F2937; font-size:10.6pt; line-height:1.7; }}
  h1 {{ font-size:24pt; line-height:1.2; margin:0 0 8mm; }}
  h2 {{ font-size:15pt; margin:9mm 0 3mm; border-bottom:1px solid #E2E6EB; padding-bottom:2mm; }}
  h3 {{ font-size:12pt; margin:6mm 0 2mm; }}
  p {{ margin:2.2mm 0; }}
  blockquote {{ margin:4mm 0; padding:3mm 5mm; background:#F4F6F8; border-left:3px solid #2F6FED;
                color:#4B5563; font-size:9.6pt; }}
  table {{ width:100%; border-collapse:collapse; margin:3mm 0; font-size:9.2pt; }}
  th,td {{ border:1px solid #E2E6EB; padding:1.8mm 2.2mm; text-align:left; vertical-align:top; }}
  th {{ background:#F4F6F8; }}
  img {{ max-width:100%; display:block; margin:4mm auto; border:1px solid #E2E6EB; border-radius:2mm; }}
  code {{ background:#F4F6F8; padding:0.4mm 1mm; border-radius:1mm; font-size:9pt; }}
  pre {{ background:#F4F6F8; padding:3mm; border-radius:2mm; overflow:hidden; font-size:8.6pt; }}
  hr {{ border:0; border-top:1px solid #E2E6EB; margin:6mm 0; }}
  h2, h3 {{ page-break-after:avoid; }}
  table, img, pre {{ page-break-inside:avoid; }}
</style></head><body>
{body}
</body></html>"""

out.write_text(html, encoding="utf-8")
print(out)
