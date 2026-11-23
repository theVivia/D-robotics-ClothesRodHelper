# 伸缩圆柱固件骨架（ESP32-C3 · v2.3）

> **状态：骨架已用 PlatformIO 6.2.0 / espressif32 6.13.0 编译通过（2026-11-23），未上真机验证。** 构建结果：RAM 12.1%（39,724 B / 320 KB）、Flash 60.5%（793,618 B / 1.25 MB）。 按 `docs/v2/02-电控与BOM.md` 的引脚/协议实现；烧录前先核对丝印。
> 角色：`01/05` 端部（外端锚定 + 内端自由 30—120mm）；内部段 `40—220mm`。同一套硬件，固件参数区分。

---

## 1. 目录

```
firmware-v2/esp32/
├── platformio.ini
├── README.md
└── src/
    ├── config.h      // 引脚、角色、限位、阈值、Wi-Fi/MQTT（现场只改这里）
    ├── main.cpp      // setup/loop、状态机、控制、LED
    ├── as5600.*      // AS5600 I2C 0x36 + 多圈累计
    ├── store.*       // NVS 存多圈计数（magic + CRC16）
    ├── motor.*       // DRV8833 PWM / 刹车 / nSLEEP
    ├── safety.*      // 夹持/限位/按键/电池/堵转
    └── net.*         // MQTT cmd/state/evt
```

## 2. 编译与烧录

```bash
cd firmware-v2/esp32
pio run                 # 编译
pio run -t upload       # USB-C 烧录（烧录时把电源开关关掉）
pio device monitor      # 串口日志（可选；GPIO21 与 LOCK_B 复用，接串口时注意）
```

依赖：`espressif32@^6.7.0`（Arduino core 2.x）、PubSubClient 2.8、ArduinoJson 7、Adafruit NeoPixel 1.12。

## 3. 每台要改的配置（`src/config.h`）

| 宏 | 说明 |
|---|---|
| `UNIT_ID` | `"01"`—`"07"`，与顶部 ArUco 标签/静态 IP 一致 |
| `UNIT_ROLE_END` | `1` = 端部 01/05（30—120mm，外端常锁）；`0` = 内部段 02—04（40—220mm） |
| `ENCODER_INVERT` | 长度方向反了就改 1 |
| `MOTOR_INVERT` | 伸出/收缩反了就改 1 |
| `WIFI_SSID/PASS` / `MQTT_HOST` | 默认 `HangFlow` / `10.42.0.1` |
| `LENGTH_MIN_MM/MAX_MM` | 由角色自动给：端部 30/120，内部 40/220 |

## 4. 引脚表（同 `docs/v2/02` §3）

| GPIO | 网络 | 方向 | 说明 |
|---|---|---|---|
| 0 | `BAT_SENSE` | ADC | 100k/100k 分压，4.2V→2.1V |
| 1 | `LOCK_A` | 入 | 外端/数字端夹头微动；锁=低；断线=高=未锁 |
| 2 | `LED_DIN` | 出 | WS2812，串 330Ω；外部 10k 上拉（strapping） |
| 3 | `LIM_MIN` | 入 | 下限位（端部 30 / 内部 40mm），触发=低 |
| 4 | `MOTOR_AIN1` | 出 | DRV8833 AIN1，LEDC ch0 20kHz |
| 5 | `MOTOR_AIN2` | 出 | DRV8833 AIN2，LEDC ch1 20kHz |
| 6 | `I2C_SDA` | 双向 | AS5600 SDA，4.7k 上拉 |
| 7 | `I2C_SCL` | 出 | AS5600 SCL，4.7k 上拉 |
| 9 | `KEY_IN` | 入 | 按键（并板载 BOOT）；**开机勿按住**（会进下载模式） |
| 10 | `MOTOR_NSLEEP` | 出 | 10k 下拉；低=高阻 |
| 20 | `LIM_MAX` | 入 | 上限位（端部 120 / 内部 220mm），触发=低 |
| 21 | `LOCK_B` | 入 | 内端/另一端夹头微动；**串 1kΩ**；与 UART0 TX 复用 |

禁止：GPIO8 悬空；GPIO11—17 Flash；GPIO18/19 USB。

## 5. MQTT（ID 01—07）

| 主题 | 方向 | 说明 |
|---|---|---|
| `hangflow/unit/{id}/cmd` | 中枢→单元 | 命令（见下） |
| `hangflow/unit/{id}/state` | 单元→中枢 | 10Hz 运动 / 1Hz 空闲，retain |
| `hangflow/unit/{id}/evt` | 单元→中枢 | 事件（E03/E04/E05/E13/E14/E15…） |
| `hangflow/sys/estop` | 中枢→全部 | 广播急停（锁存） |
| `hangflow/sys/resume` | 中枢→全部 | 解除急停 |
| `hangflow/hub/status` | 中枢→全部 | 1Hz 心跳；单元 500ms 收不到 → 运动中停 |

**命令（JSON）**

```json
{"v":1,"seq":42,"op":"set_length","set_length_mm":100.0,"speed_mm_s":4.0}
{"v":1,"seq":43,"op":"clamp","clamp":"a","action":"status"}
{"v":1,"seq":44,"op":"stop"}
{"v":1,"seq":45,"op":"resume"}
{"v":1,"seq":46,"op":"home"}
```

- P0 手动夹头：`clamp` 只支持 `action:"status"`；`lock/release` 回 evt `E15`（P1 电动推套筒才实现）。
- `stop` = 立即停（可再动）；`resume` = 解除急停/堵转锁存；`home` = 慢速收到下限位并把计数清零。
- `seq` 单调递增，旧命令丢弃。

**state（示例）**

```json
{"v":1,"id":"01","role":"END","length_mm":59.6,"length_min_mm":30,"length_max_mm":120,
 "state":"moving","clamp_a":true,"clamp_b":false,"clamp_state":"referenced_a",
 "batt_mv":3820,"current_ma":null,"limit_min":false,"limit_max":false,
 "estop":false,"fault":0,"uptime_s":813,"ts":1730000000123}
```

## 6. 控制与安全（已实现）

| 机制 | 行为 |
|---|---|
| 长度闭环 | AS5600 200Hz 多圈计数 → `L = L_MIN + counts/512`；P 控制 + 1mm 死区；到位 evt `OK` |
| 夹持联锁 | MIDDLE：`free`/`fixed` 禁动，只允许 `referenced_a/b`；END：只允许"外端锁 + 内端松"；运动中断开 → ≤50ms 停 + `E14` |
| 卡死 | PWM≥35% 且 300ms 内 AS5600 变化 <3 counts，连续 2 窗口 → 停 + 刹车 + `E03` |
| 限位 | 硬限位微动；到端停 + `E04`；下限触发把计数清零（标定基准） |
| 低压 | <3.4V 禁动 + `E05`；3.5V 告警灯 |
| 急停 | 按键长按 3s 锁存 / MQTT 广播 / 物理断电；`resume` 或再长按解除 |
| 断网 | MQTT 断开 → 单元本地保持；运动中 500ms 无 `hub/status` → 停 + holding |
| 堵转/掉电 | NVS 存计圈（magic+CRC16）；上电校验范围，不合法则自动归零；静止 5s 节流写 NVS |
| 看门狗 | 未启用（骨架）；建议后续加 `esp_task_wdt` |

## 7. 已知限制（骨架阶段）

1. **未真机验证**：已在本机用 `pio run` 编译通过（PlatformIO 6.2.0 + espressif32 6.13.0），但没有接电机/AS5600/夹头做联调。
2. **PubSubClient 只支持 QoS0**：`evt` 的 QoS1 需要换 `AsyncMqttClient` 或 hub 侧重发（协议文档标 QoS1）。
3. **P0 手动夹头没有执行器**：`clamp lock/release` 回 `E15`，state 只反映微动实际状态。
4. **无电流采样**：卡死判据只有"PWM 在给但 AS5600 不转"；P1 加 INA219 后可加电流双判据。
5. **端部/内部是同一套硬件**：限位凸台位置与固件 `UNIT_ROLE_END` 必须一致；装错会出现 30—120 与 40—220 的软限位错配。
6. **GPIO21 / GPIO9 复用**：GPIO21 接 LOCK_B 时不能同时用串口日志；GPIO9 按住开机会进下载模式。

## 8. 上电自检（真机时按顺序）

1. 不接电池量电池座不短路；上电后 6V 轨 5.9—6.1V、3V3 3.25—3.40V。
2. 扫 I2C 有 0x36；手动转丝杆，`length_mm` 单调变化。
3. 两端夹头扳动，state 里 `clamp_a/b` 翻转；`free/fixed` 下发 `set_length` 应回 `E13`。
4. 外端松开（端部）→ 下发运动应回 `E13`。
5. 手顶内管 → ≤0.8s 停并回 `E03`。
6. 触发上下限位 → 停并回 `E04`。
7. 拔热点 → 5s 内停住；重新连上后需重新下发命令（不自动续跑）。
8. 断电 10s 再上电 → `length_mm` 误差 ≤1mm（NVS 有效时）。

