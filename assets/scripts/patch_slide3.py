from pathlib import Path

p = Path('deck/index.html')
h = p.read_text(encoding='utf-8')

old = '''    <div style="display:flex;gap:12px;margin-top:34px;flex-wrap:wrap">
      <span class="tag hi">手动</span><span class="tag hi">一键等距</span>
      <span class="tag hi">智能分配（按湿度）</span><span class="tag hi">收衣归拢</span>
      <span class="tag">断电保持</span><span class="tag">堵转即停</span><span class="tag">断网自停</span>
    </div>
    <div class="foot">不换杆 · 不布线 · 搬家能带走</div>'''
new = '''    <div style="display:flex;gap:12px;margin-top:30px;flex-wrap:wrap">
      <span class="tag hi">手动</span><span class="tag hi">一键等距</span>
      <span class="tag hi">智能分配（按湿度）</span><span class="tag hi">收衣归拢</span>
      <span class="tag">断电短时保持</span><span class="tag">堵转即停</span><span class="tag">断网自停</span>
    </div>
    <div style="display:flex;gap:72px;margin-top:56px">
      <div><div class="num">4<small> 个</small></div><div class="label">套挂单元（可扩展到 8）</div></div>
      <div><div class="num">30<small> s</small></div><div class="label">4 件衣服一键排开（典型）</div></div>
      <div><div class="num">0<small> 改造</small></div><div class="label">不动杆、不布线、搬家带走</div></div>
    </div>
    <div class="foot">不换杆 · 不布线 · 搬家能带走</div>'''
assert old in h, 'slide3 block not found'
h = h.replace(old, new)
p.write_text(h, encoding='utf-8')
print('slide3 patched')
