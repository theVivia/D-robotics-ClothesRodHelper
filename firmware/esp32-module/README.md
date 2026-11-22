# 套挂单元固件（ESP32-C3）

> 状态：**v0.2 骨架**，引脚与 `docs/05 §5.1` 一致；标 `TODO(verify)` 的需真机标定。
> 设计依据：[docs/05-硬件与电控设计](../../docs/05-硬件与电控设计.md)、[docs/07-通信协议](../../docs/07-软件架构与通信协议.md)、[docs/04-机械](../../docs/04-机械结构设计.md)。

## 1. 编译与烧录

```bash
pio pkg install
pio run                 # 编译
pio run -t upload       # 烧录（USB-C 接 C3 的 USB 口）
pio device monitor -b 115200
```

> C3 SuperMini 进下载模式：按住 BOOT → 插 USB → 松开。烧录失败先换数据线（很多线只能充电）。

## 2. 每台设备的改动点

只改 `src/config.h` 顶部：

```c
#define UNIT_ID "01"     // 01 / 02 / 03 / 04
#define WIFI_SSID "HangFlow-01"
#define WIFI_PASS "hangflow2026"
#define MQTT_HOST "192.168.4.1"
```

身份只靠 `UNIT_ID`，其余代码完全一样。

## 3. 上电行为

1. LED 白 → 连 Wi-Fi（约 3s）→ 连 MQTT；
2. 自动归零（LED 青）：低速向左，**堵转判据触发**即认为撞到左端挡块，位置置 0；
3. 归零完成 → 白灯待机；
4. 收到 `move` → 绿灯 → 到位发 `DONE`。

## 4. 指令（MQTT）

| 主题 | 示例 |
|---|---|
| `hangflow/unit/01/cmd` | `{"v":1,"seq":12,"op":"move","target_mm":420,"speed_mm_s":45}` |
| `hangflow/unit/01/cmd` | `{"v":1,"seq":13,"op":"stop"}` |
| `hangflow/unit/01/cmd` | `{"v":1,"seq":14,"op":"home"}` |
| `hangflow/sys/estop` | `{"v":1,"seq":99,"op":"stop"}` |

调试：

```bash
mosquitto_sub -h 192.168.4.1 -t 'hangflow/#' -v
mosquitto_pub -h 192.168.4.1 -t 'hangflow/unit/01/cmd' \
  -m '{"v":1,"seq":1,"op":"move","target_mm":200}'
```

## 5. 安全逻辑（固件层）

| 条件 | 动作 | 事件码 |
|---|---|---|
| PWM 在给但 300ms 内 AS5600 角度几乎不变（连续 2 次） | 停 + 故障 | E03 |
| 前方 ToF <60mm 且前进 | 停 + 故障 | E04 |
| 电池 <3.3V | 停 + 故障 | E05 |
| 运动中 500ms 没收到指令 | 停 + 故障 | E02 |
| 按键长按 3s | 急停 | ESTOP |
| 坏 JSON / 旧 seq | 忽略 | E07 |

> **为什么不用电流判堵转**：市售 DRV8833 模块 AISEN/BISEN 接地、没有采样电阻，硬件上测不到电流；AS5600 的"角度不变"更本质，且对打滑/卡死一视同仁（见 docs/05 §11）。

## 6. 标定与 TODO(verify)

- [ ] `MM_PER_COUNT`：轮径 Ø28、AS5600 4096 CPR，理论 0.0215mm/LSB；装好后走 200mm，用卷尺核对，误差 >3% 检查轮径/磁铁气隙
- [ ] 速度环参数：当前 `duty = vErr * 0.02` 是占位，需实测整定
- [ ] 堵转阈值：`STALL_ANGLE_MIN`/`STALL_CONFIRM` 按实际轮速调整（打滑不能误判）
- [ ] 归零：确认左端挡块位置与磁铁/结构不干涉
- [ ] 电池分压比：100k/100k → 代码 ×2，实测对照万用表
- [ ] 长按/短按按键手感
- [ ] OTA（ArduinoOTA）——现场不必须

