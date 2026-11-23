# 中枢（RDK X5）v2 接线与网络配置

> 中枢只做"看得见的事"：相机、ArUco 识别、规划、网页、MQTT broker。**不接任何电机、不跨杆拉线。**
>
> 板卡：RDK X5 4GB（现场发放）· 系统：Ubuntu 22.04 · 依据：`docs/05-硬件与电控设计.md` §2、`docs/17-RDK平台与开发环境.md`
>
> 版本 v2.0 · 2026-11-23

---

## 1. 接线总表

| # | 起点 | 终点 | 线材 | 备注 |
|---|---|---|---|---|
| H1 | 220V 排插（带开关） | 5V/5A 适配器 | 国标电源线 | 适配器 25W，USB-C 口 |
| H2 | 5V/5A 适配器 USB-C | RDK X5 **USB-C 供电口** | **支持 5A 的 Type-C 线**（1m） | 3A 线满载压降 0.3—0.5V → 板子随机重启 |
| H3 | RDK X5 **USB3.0 Type-A**（离网口最远的那个） | USB UVC 相机 | 相机自带线（≥1m） | 1080p30，广角 100—120° |
| H4 | RDK X5 microSD 槽 | 32GB A1 工作卡 | — | 备份卡另带一张（已烧同镜像） |
| H5 | RDK X5 40PIN | **不接** | — | P0 不从 40PIN 取电/接外设 |
| H6 | RDK X5 HDMI（调试可选） | 现场显示器 | HDMI 线 | 演示时可不接，SSH/网页即可 |
| H7 | RDK X5 网口（可选） | 现场网线 | 千兆网线 | 2.4G 太脏时的 Plan B（有线 + 随身 2.4G AP） |

**电源硬规则**

1. **只用官方 5V/5A 适配器**（或明确支持 5V/5A 固定 PDO / PPS 3.3—11V/5A 的 PD 电源）。
2. **不要**用笔记本 USB 口给 X5 供电——启动电流不够会反复重启。
3. 适配器与板之间可串一个 **USB-C 功率计**，现场读数：静置 6—8W / 推理+推流 10—14W（估算），满载 5V 轨 **≥4.75V**。
4. 演示时 X5 **竖放 + 底部垫高 10mm**，不要平放在桌布/纸上；有散热片就装。

---

## 2. 相机布置

| 项 | 值 |
|---|---|
| 距离 | 杆正前方 **1.2—1.5m** |
| 高度 | 与杆同高，或略高 5—10cm |
| 俯角 | ≤15°（俯角太大 ArUco 角点变形） |
| 视场 | 100—120° 广角，需完整覆盖 1.2m 杆 + 两端挡块 |
| 光照 | 避免窗口/射灯直射镜头；ArUco 用**哑光**打印（亮面反光丢角点） |
| 对焦 | 手动/固定焦距，锁定后不再动 |

相机只插一个口（单目即可）；不要插 USB Hub，避免供电/枚举问题。

---

## 3. 网络：2.4GHz 热点 + MQTT

```
手机 ─┐
      ├─ Wi-Fi 2.4GHz（SSID: HangFlow，无密码或 hangflow2026）
单元 ─┤        RDK X5：10.42.0.1
      │          ├ mosquitto :1883
      └─ 单元 01—07：10.42.0.11—10.42.0.17（静态 IP，按 ID）
                 └ FastAPI :8000（手机网页）
```

**为什么必须 2.4G**：ESP32-C3 只支持 2.4GHz；X5 支持 5G，但单元用不了。

### 3.1 现场三组命令

```bash
# 0) 先扫信道占用（1/6/11 三选一，别用 3、8）
sudo iw dev wlan0 scan | grep -E "freq|SSID|signal" | head -60
#    freq:2412=ch1  2437=ch6  2462=ch11

# 1) 开 2.4G 热点（强制 20MHz）
sudo nmcli device wifi hotspot ifname wlan0 ssid HangFlow band bg channel 6 password hangflow2026
sudo iw dev wlan0 set power_save off

# 2) MQTT broker
sudo apt install -y mosquitto mosquitto-clients
echo -e "listener 1883 0.0.0.0\nallow_anonymous true" | sudo tee /etc/mosquitto/conf.d/local.conf
sudo systemctl restart mosquitto

# 3) 自测
mosquitto_sub -h 10.42.0.1 -t 'hangflow/#' -v
```

### 3.2 单元静态 IP 约定

| 单元 ID | 静态 IP | MQTT client id |
|---|---|---|
| 01 | 10.42.0.11 | `hangflow-unit-01` |
| 02 | 10.42.0.12 | `hangflow-unit-02` |
| 03 | 10.42.0.13 | `hangflow-unit-03` |
| 04 | 10.42.0.14 | `hangflow-unit-04` |
| 05 | 10.42.0.15 | `hangflow-unit-05` |
| 06 | 10.42.0.16 | `hangflow-unit-06` |
| 07 | 10.42.0.17 | `hangflow-unit-07` |

### 3.3 MQTT 参数

| 参数 | 值 |
|---|---|
| 协议 | MQTT 3.1.1，明文 1883（P0 局域网，不启 TLS） |
| keepalive | 15s |
| clean_session | true |
| QoS | cmd/evt/cfg 用 1；state 用 0 |
| LWT | `hangflow/unit/{id}/state` → `{"v":1,"id":"xx","state":"offline"}`（retain） |
| retain | 单元最后一个 state 保留；cmd 不 retain |
| 中枢心跳 | `hangflow/hub/status` 1Hz |

主题与 JSON 完整定义见 `docs/v2/02-电控与BOM.md` §7（ID 01—07）。

---

## 4. 手机网页

- 手机连 `HangFlow` 热点 → 浏览器打开 `http://10.42.0.1:8000`；
- 无需安装 App；断网不影响单元就地保持；
- 急停按钮在网页第一屏，红色，不需要二次确认（安全优先）。

---

## 5. 与单元的关系（为什么这么接线）

- 中枢与单元之间**没有任何信号线**，全靠 2.4G + MQTT；单元各自带电池，互不供电。
- 好处：一根杆上不用布线、不用滑环；单元坏一个不影响整条链（其余单元保持位置）。
- 代价：Wi-Fi 抖动会带来 100—500ms 延迟，所以单元本地闭环、断网保持是硬要求。

---

## 6. 现场清单（上台前 5 分钟）

- [ ] 适配器灯亮；USB-C 功率计电压 ≥5V
- [ ] `nmcli device status` 里 wlan0 是 AP 模式
- [ ] `mosquitto_sub -h 10.42.0.1 -t 'hangflow/#' -v` 能看到 5 个单元（01—05，K=4 → K+1）的 state
- [ ] 手机能打开网页
- [ ] 相机预览正常、ArUco 三个 ID 都能读出
- [ ] 网页急停按一次：5 个单元 `<500ms` 停 + 红灯
- [ ] 散热片装好、X5 竖放

