from pathlib import Path

src = Path('assets/diagrams/product-concept.svg').read_text(encoding='utf-8')
drop = [
    '<text class="t" x="98" y="92" font-size="38" font-weight="bold">衣序</text>',
    '<text class="m" x="200" y="92" font-size="23" letter-spacing="1">HangFlow</text>',
    '<text class="t" x="98" y="136" font-size="19">不换晾衣杆，让衣服自己让出风道。</text>',
    '<text class="m" x="98" y="164" font-size="12">套挂式衣物间距调节器 ｜ DDC2026 地瓜机器人黑客松 ｜ 1.2 m 演示杆 · 4 个套挂单元</text>',
    '<text class="m" x="1520" y="86" font-size="11.5" text-anchor="end">平均衣物间隙（设计目标）</text>',
    '<text class="g" x="1520" y="124" font-size="25" font-weight="bold" text-anchor="end">3–5 cm  →  10–15 cm</text>',
    '<text class="m" x="1520" y="148" font-size="11.5" text-anchor="end">风道打开，内层才干得透</text>',
]
out = src
for d in drop:
    if d not in out:
        print('MISS:', d[:40])
    out = out.replace(d, '')
Path('assets/diagrams/product-hero.svg').write_text(out, encoding='utf-8')
print('written', len(out))
