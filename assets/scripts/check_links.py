"""检查仓库内 Markdown 的相对链接是否都存在（忽略外链/anchor）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
bad = []
total = 0

for md in ROOT.rglob('*.md'):
    if any(part in {'.git', 'node_modules', '__pycache__'} for part in md.parts):
        continue
    text = md.read_text(encoding='utf-8', errors='ignore')
    for m in LINK.finditer(text):
        target = m.group(1).strip()
        if target.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        target = target.split('#')[0].split('?')[0]
        if not target:
            continue
        total += 1
        # 相对 md 所在目录解析
        p = (md.parent / target).resolve()
        if not p.exists():
            bad.append((md.relative_to(ROOT), target))

print(f'checked {total} relative links')
if bad:
    print(f'BROKEN {len(bad)}:')
    for md, target in bad:
        print(f'  {md} -> {target}')
    sys.exit(1)
print('all relative links OK')

