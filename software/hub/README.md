# 中枢软件（RDK X5）

> 状态：**v0.1 骨架 + 可运行 mock**。没有硬件也能跑通"规划 → 串行下发 → 到位校验"。
> 真实实现待赛前 11.27—11.30 补齐（见 [docs/10](../../docs/10-赛前12天准备计划.md)）。

## 1. 现在能跑什么

```bash
# 仓库根目录
python -m software.hub.mock_demo                # 一键等距
python -m software.hub.mock_demo --mode smart   # 按湿度加权
python -m software.hub.mock_demo --mode gather  # 收衣
```

输出示例：

```
模式: equalize | 初始位置: [120, 175, 230, 285]
目标位置: [387.5, 525.0, 662.5, 802.5] | 目标间隙: [100.0, 100.0, 100.0] mm
  01   120.0 →  387.5 mm ... 完成  6.3s  误差 -1.7mm
  ...
最终间隙(净空): [103.0, 98.9, 102.0] mm | 最小 98.9 mm（要求 ≥ 30）
总耗时: 36.16s（要求 ≤ 45s，典型 ≤35s）
日志: logs/mock-run-20261123-013015.jsonl
结果: PASS
```

- 虚拟单元：一阶速度响应 + 2% 打滑 + 编码器噪声 + 视觉残余误差（±1.2mm）。
- 串行下发策略与真实控制器一致（一次只推进一个，避免 ToF 互相干扰）。

## 2. 文件

| 文件 | 作用 |
|---|---|
| `planner.py` | 把 `sim/spacing_planner.py` 的算法接到"杆坐标"（左端挡块=0），提供 equalize/smart/gather |
| `mock_demo.py` | 4 个虚拟单元的端到端演示，产出 JSONL 日志 |
| `../README.md` | 整体方案导航 |

## 3. 与真实系统的对应

| mock 里 | 真机里 |
|---|---|
| `FakeUnit.move_to()` | MQTT `move` 指令 + ESP32 闭环 |
| 串行 for 循环 | `Controller.run_plan()` 每次只推一个 |
| `random.gauss` 误差 | 视觉外环校正（docs/06 §4） |
| `planner.plan_layout()` | 同一个函数，接真实 t_i/q_i |
| JSONL 日志 | 中枢日志（docs/07 §7） |

## 4. 赛前待补（未实现）

- `camera.py` / `vision/aruco_locator.py`（OpenCV ArUco + PnP）
- `net/mqtt_bridge.py`（paho-mqtt）
- `web/server.py`（FastAPI + WebSocket，静态页用 `app/index.html`）
- `mock/fake_units.py`（把本文件的 FakeUnit 抽成可配置的模拟器）
- `tests/`（pytest：规划、重排、协议、超时）

## 5. 依赖

- Python 3.10+；`numpy`（sim 的规划器依赖）
- 真机额外：`paho-mqtt`、`fastapi`、`uvicorn`、`opencv-python`
- RDK 上：`sudo apt install mosquitto mosquitto-clients`

