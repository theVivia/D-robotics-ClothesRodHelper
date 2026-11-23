import json
import subprocess
import time
import urllib.request
from pathlib import Path

import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
URL = "file:///E:/D-robotics-ClothesRodHelper/app-v2/index.html"
PORT = 9223
PROFILE = str(Path.home() / ".dsh" / "cdp-edge-profile")

proc = subprocess.Popen([
    EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--remote-allow-origins=*",
    f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
    "--window-size=390,844", URL,
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

try:
    ws_url = None
    for _ in range(40):
        try:
            data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
            pages = [p for p in data if p.get("type") == "page"]
            if pages:
                ws_url = pages[0]["webSocketDebuggerUrl"]
                break
        except Exception:
            time.sleep(0.25)
    if not ws_url:
        raise SystemExit("no page")
    ws = websocket.create_connection(ws_url, timeout=10)
    msg_id = [0]
    def call(method, params=None):
        msg_id[0] += 1
        ws.send(json.dumps({"id": msg_id[0], "method": method, "params": params or {}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == msg_id[0]:
                return m

    def evaluate(expr):
        r = call("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        return r["result"]["result"].get("value")

    call("Runtime.enable")
    time.sleep(1.5)
    before = evaluate("""(() => {
      const el = document.querySelector('.cyl[data-index="1"] .handle-right');
      const r = el.getBoundingClientRect();
      return {x:r.x+r.width/2, y:r.y+r.height/2, w:r.width, h:r.height,
              labels:[...document.querySelectorAll('.cyl-len')].map(e=>e.textContent),
              total:document.getElementById('statChain').textContent};
    })()""")
    print("before", before)
    x, y = before["x"], before["y"]
    call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    for dx in (5, 10, 20, 30):
        call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x + dx, "y": y, "button": "left", "buttons": 1})
        time.sleep(0.05)
    call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x + 30, "y": y, "button": "left", "clickCount": 1})
    time.sleep(0.5)
    after = evaluate("""(() => ({
      labels:[...document.querySelectorAll('.cyl-len')].map(e=>e.textContent),
      total:document.getElementById('statChain').textContent,
      toast:(document.querySelector('.toast')||{}).textContent||''
    }))()""")
    print("after", after)
finally:
    proc.terminate()


