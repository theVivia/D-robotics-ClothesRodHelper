# software_v2 · 链模型 / 规划 / 协议 / mock 中枢

无硬件可跑的部分。重心是**端点锚定模型**（外端固定、内端自由伸缩 30—220mm），它和 app-v2 的拖动规则、`docs/v2/10-端点锚定模型.md` 一致。

## 跑

```bash
python -m software_v2.mock_hub --demo
python -m software_v2.mock_hub --equalize 12
python -m pytest software_v2 -q
```

`--demo` 输出：

```
初始: [60, 100, 100, 100, 60] total=460 外端: (0.0, 460.0)
等距 12cm: [30, 120, 120, 120, 30] total=460
收衣（回 10cm）: [60, 100, 100, 100, 60] total=460
等距 8cm 拒绝: outside powered range [100,220]
```

## 结构

| 文件 | 内容 |
|---|---|
| `model.py` | Chain/Unit；外端锚定；`equalize/weighted/collect`；行程不足抛 `ChainError` |
| `protocol.py` | MQTT v2 `set_length/clamp/state/evt` 校验与编解码（不依赖 paho） |
| `mock_hub.py` | CLI：打印规划结果与 5 条 MQTT 命令 |
| `tests/` | 11 个单测：总长、锚点、等距/收衣、超限拒绝、双端 free 拒绝 |

## 还没写

- FastAPI/WebSocket 中枢、真实 paho MQTT、ArUco 视觉接入；
- ESP32 固件（在 `firmware-v2/`，由电控写）；
- 与 app-v2 的实时联调（当前 app 是本地模拟）。

## 一个关键口径

内部动力段 100—220mm；40—100mm 用被动短套。端部 30—120mm（外端锚定）。4—10cm 风道不在自动模式里。见 `docs/v2/01`、`10`。

