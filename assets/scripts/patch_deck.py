from pathlib import Path

p = Path('deck/index.html')
h = p.read_text(encoding='utf-8')

# 1) 成本页：用 HTML 条形替代图片（图在 380px 高时字太小）
old_cost = '''      <div>
        <div class="imgbox" style="height:380px"><img src="../docs/figures/cost-breakdown.png" alt="成本构成"></div>
        <div class="fig-cap">4 单元 + 相机 + 演示架，不含 RDK（RDK 由赛事发放）。</div>
      </div>'''
new_cost = '''      <div>
        <div class="card" style="padding:28px 30px">
          <div style="display:flex;justify-content:space-between;align-items:baseline">
            <span class="label">整机打样成本（不含 RDK）</span>
            <span class="num" style="font-size:42px">¥850</span>
          </div>
          <div style="margin-top:24px">
            <div class="barrow"><span>套挂单元 ×4</span><div class="track"><i style="width:71%"></i></div><b>¥600</b></div>
            <div class="barrow"><span>中枢外设（相机等）</span><div class="track"><i style="width:21%"></i></div><b>¥175</b></div>
            <div class="barrow"><span>演示架</span><div class="track"><i style="width:9%"></i></div><b>¥75</b></div>
            <div class="barrow"><span>RDK X5（现场发放）</span><div class="track"><i style="width:65%"></i></div><b>¥549</b></div>
          </div>
          <div style="font-size:12px;color:var(--txt3);margin-top:18px">量产 1 万台：单单元 ¥125，整机（4 单元 + 中枢）¥650。</div>
        </div>
        <div class="fig-cap">口径见 docs/09；RDK 由赛事发放，不计自购。</div>
      </div>'''
assert old_cost in h, 'cost block not found'
h = h.replace(old_cost, new_cost)

# 2) 结尾页：真实二维码 + 修右下角重叠
old_qr = '<div class="qr">扫码看<br>交互演示<br><span style="color:#888;font-size:10px">192.168.4.1:8000</span></div>'
new_qr = '<img class="qr-img" src="../assets/screenshots/qr-demo.png" alt="演示二维码"><div style="font-size:11px;color:var(--txt3);margin-top:8px">192.168.4.1:8000</div>'
assert old_qr in h, 'qr block not found'
h = h.replace(old_qr, new_qr)
h = h.replace('class="brandline" style="top:auto;bottom:36px;right:80px"', 'class="brandline" style="top:auto;bottom:34px;left:80px;right:auto"')

# 3) 补样式
h = h.replace('''  .hint{position:fixed;right:18px;bottom:14px;color:#3a4150;font-size:12px;font-family:var(--mono)}''',
'''  .barrow{display:grid;grid-template-columns:150px 1fr 64px;gap:14px;align-items:center;margin:14px 0;font-size:15px;color:var(--txt2)}
  .barrow b{font-family:var(--mono);color:var(--txt);font-size:15px;text-align:right}
  .track{height:10px;border-radius:999px;background:rgba(255,255,255,.06);overflow:hidden}
  .track i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--gold),var(--gold-hi))}
  .qr-img{width:168px;height:168px;border-radius:14px;background:#fff;padding:8px}
  .hint{position:fixed;right:18px;bottom:14px;color:#3a4150;font-size:12px;font-family:var(--mono)}''')

p.write_text(h, encoding='utf-8')
print('deck patched')

# 4) 架构图文字与机械/电控真相对齐
s = Path('assets/diagrams/sys-architecture.svg')
t = s.read_text(encoding='utf-8')
repl = {
    'ToF 防撞 · 电流保护': 'ToF 防撞 · 堵转判据',
    'ESP32-C3 · N20 · 编码器': 'ESP32-C3 · N20 · AS5600',
    '断电自锁': '断电即停',
    '左端归零磁铁': '左端挡块归零',
    '滑杆/档位 · 急停': '手动/档位 · 急停',
}
for a, b in repl.items():
    t = t.replace(a, b)
s.write_text(t, encoding='utf-8')
print('arch svg patched')
