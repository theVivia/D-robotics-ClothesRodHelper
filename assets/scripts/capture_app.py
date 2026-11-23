"""用 CDP 真 390×844 截 app-v2 的图（Edge 最小窗口 459，必须设备模拟）。"""
import base64
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "app-v2" / ".verify"
PORT = 9230
URL = "file:///E:/D-robotics-ClothesRodHelper/app-v2/index.html"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    profile = str(Path.home() / ".dsh" / "cdp-shot")
    proc = subprocess.Popen([
        EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
        "--remote-allow-origins=*", f"--remote-debugging-port={PORT}",
        f"--user-data-dir={profile}", "--window-size=900,1000", URL,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = None
        for _ in range(60):
            try:
                data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                pages = [p for p in data if p.get("type") == "page"]
                if pages:
                    ws_url = pages[0]["webSocketDebuggerUrl"]
                    break
            except Exception:
                time.sleep(0.25)
        ws = websocket.create_connection(ws_url, timeout=20)
        mid = [0]

        def call(method, params=None):
            mid[0] += 1
            ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
            while True:
                m = json.loads(ws.recv())
                if m.get("id") == mid[0]:
                    return m

        call("Page.enable")
        call("Emulation.setDeviceMetricsOverride", {
            "width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True,
        })
        for name, query in [
            ("default", ""),
            ("equal10", "?demo=equal10"),
            ("collect", "?demo=collect"),
            ("rod2400", "?demo=rod2400"),
        ]:
            call("Page.navigate", {"url": URL + query})
            time.sleep(1.6)
            r = call("Page.captureScreenshot", {"format": "png", "fromSurface": True})
            data = r["result"]["data"]
            (OUT / f"390x844-{name}.png").write_bytes(base64.b64decode(data))
            print("saved", name)
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
