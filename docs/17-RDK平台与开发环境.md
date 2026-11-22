# RDK 平台与开发环境（学习笔记）

> **这份文档回答：地瓜机器人 RDK 是什么、我们为什么选 X5、现场怎么用它。**
> 所有规格都标了来源；抓取时间 2026-11-23。官方文档会随版本更新，**现场以板子上实际系统为准**。
> 主要来源：RDK X3/X5 用户手册 <https://developer.d-robotics.cc/rdk_x_doc/>、RDK S100/S600 用户手册 <https://developer.d-robotics.cc/rdk_s_doc/>、RDK Model Zoo <https://github.com/D-Robotics/rdk_model_zoo>。

---

## 1. RDK 是什么

地瓜机器人（D-Robotics，地平线机器人旗下）的 **RDK** 是面向机器人/端侧 AI 的开发套件：一块板子集成 CPU + BPU（神经网络加速）+ GPU + 丰富接口，预装 Ubuntu 系统与机器人软件栈，配套 Model Zoo、TROS（ROS2 发行版）、RDK Studio（烧录/管理工具）、NodeHub（应用中心）。

一句话：**它不是"带 GPIO 的树莓派"，而是"能跑 BPU 推理、能接多路相机和电机、预装机器人中间件"的开发板。**

---

## 2. 四块板子怎么选（已核实规格）

| 项 | RDK X3 | **RDK X5（我们选它）** | RDK S100 | RDK S600 |
|---|---|---|---|---|
| 定位 | 入门 | 主力性价比 | 异构：感知 + 实时控制 | 旗舰 |
| CPU | 4×A53 | **8×Cortex-A55 @1.5GHz** | 6×A78AE + 4×R52+ MCU | 18×A78AE |
| BPU | 5 TOPS | **10 TOPS** | 80 / 128 TOPS | 560 TOPS |
| 内存 | 2/4GB | **4/8GB LPDDR4** | 12/24GB LPDDR5 | 32/64GB |
| 供电 | 5V/3A | **5V/5A Type-C（25W）** | 12—20V DC（70—150W） | 12—28V |
| 相机 | 1×MIPI CSI | **2×4-lane MIPI CSI + 4×USB3** | 3×4-lane MIPI CSI | 多路 |
| 网络 | Wi-Fi/BT | **Wi-Fi6 + BT5.4 + 千兆网** | 双千兆 + M.2 Wi-Fi | 多千兆 |
| 现场发放 | 可能有 | **有** | 有 | 有 |
| 48h 风险 | 性能够用但生态老 | **低（资料最多、社区最大）** | 中（供电/散热复杂） | 高（大材小用） |

**结论**：48 小时比赛选 **X5 4GB**。理由：资料最全、供电最简单（一个 25W PD 适配器）、USB 相机即插即用、10 TOPS 足够跑 YOLO 级别的模型；S100/S600 的算力我们用不上，但它们的供电/散热/系统复杂度会直接吃掉半天。

来源：[X5 硬件简介](https://d-robotics.github.io/rdk_x_doc/Quick_start/hardware_introduction/rdk_x5/?v=3.5.0)、[S100 套件页](https://d-robotics.github.io/rdk_s_doc/01_Quick_start/01_hardware_introduction/01_rdk_s100/01_rdk_s100_kit/?v=4.0.5)、[S600 套件页](https://d-robotics.github.io/rdk_s_doc/01_Quick_start/01_hardware_introduction/02_rdk_s600/01_rdk_s600_kit/?v=5.1.0)。

---

## 3. 系统与开发工具链

| 项 | 事实 | 对我们的意义 |
|---|---|---|
| 系统 | 版本 **≥3.0.0 基于 Ubuntu 22.04**；<3.0.0 是 Ubuntu 20.04 | Python 3.10、OpenCV、ROS2 Humble 都能直接装；赛前确认镜像版本 |
| 桌面 | Ubuntu 桌面版，可接 HDMI | 现场调试可以接屏，但**别依赖**（演示用 SSH/网页） |
| 烧录 | TF 卡 + 官方镜像；RDK Studio（Windows）一键烧录 | **现场不要重刷系统**，风险极高；赛前刷好并备份 TF 卡 |
| 远程 | 默认用户 `sunrise`；SSH 可用；调试串口 115200 | 现场用 SSH + VSCode Remote 改代码最快 |
| 包管理 | apt + pip；预装 Python 接口 | `apt install mosquitto mosquitto-clients python3-opencv` |
| 工具 | `srpi-config`（全屏终端）配 40PIN 复用 | 改 I2C/PWM/UART 功能必须用它，改完重启 |
| 社区 | NodeHub（应用中心）、论坛、B 站教程 | 抄示例比自己从零写快 |

**烧录/备份流程（赛前做，现场只读）**：

```bash
# 在 x86 电脑上用 RDK Studio 烧录 TF 卡（选 RDK X5 镜像）
# 首次启动：接 HDMI + 键鼠，或 SSH（网线直连，默认 DHCP）
ssh sunrise@<板子IP>          # 默认密码见官方文档
sudo apt update && sudo apt upgrade -y

# 装我们需要的
sudo apt install -y mosquitto mosquitto-clients python3-opencv python3-pip
pip3 install paho-mqtt fastapi uvicorn

# 备份整卡（赛前，x86 上）
# Win32DiskImager / balenaEtcher 读卡成 .img，存两份
```

---

## 4. 40PIN 怎么用（本次硬件扩展的核心）

### 4.1 电气规格（重要）

| 项 | 官方值 | 来源 |
|---|---|---|
| 逻辑电平 | **3.3V**，最大耐压 3.46V | 40PIN 文档 |
| 3.3V 输出能力 | **≤800mA** | 40PIN 文档 |
| 5V 输出能力 | **≤500mA** | 40PIN 文档 |
| 适配器要求 | **≥25W（5V/5A）** | 40PIN 文档 |
| 复用 | 5×UART / 8×PWM / 3×I2C / 2×SPI / 1×I2S | 产品页 |

> ⚠️ 注意：另一页"接口电源负载能力"写的是 1A@3.3V/1A@5V，与 40PIN 专页的 800mA/500mA 不一致。**按保守值设计**（我们的 P0 不从 40PIN 取电，只留风扇/状态灯）。

### 4.2 引脚复用与配置

- 40PIN 默认使能 UART/SPI/I2C/I2S 等专用功能；要当普通 GPIO 用，得先 `sudo srpi-config` → `3 Interface Options` → `I3 Peripheral bus config`，把对应功能 `disabled`，**重启生效**。
- 复用组内"只能开一个"：例如 `pwm0/spi2`、`i2c0/pwm2` 等。
- 丝印在 40PIN 座旁边，PIN1/PIN40 有标记；接线前断电。

### 4.3 软件接口：Hobot.GPIO（Python）

```python
import Hobot.GPIO as GPIO
GPIO.setmode(GPIO.BOARD)        # 推荐：用物理引脚号，和丝印一致
GPIO.setup(37, GPIO.IN)
GPIO.setup(31, GPIO.OUT, initial=GPIO.LOW)
GPIO.output(31, GPIO.input(37))
GPIO.cleanup()
```

- 库版本 0.0.2，支持 `BOARD/BCM/CVM/SOC` 四种编码；**我们用 BOARD**。
- 支持 `wait_for_edge / add_event_detect` 中断、PWM（`GPIO.PWM`）。
- 板端预置示例：`/app/40pin_samples/`（`button_led.py`、`pwm.py`、`i2c.py` 等），直接改。

### 4.4 我们项目用到的 40PIN 引脚（P0 极少）

| 用途 | 引脚 | 说明 |
|---|---|---|
| 状态灯（可选） | 3.3V + GND + GPIO | 演示时指示中枢状态；也可用板载 LED |
| 风扇 | 5V + GND | X5 满载 10W 级，散热片/风扇必装 |
| 备用 UART | UART3 | 如果 Wi-Fi 挂了，用串口接 ESP32 调试（P1） |

> 单元（ESP32）与中枢之间走 **Wi-Fi/MQTT**，不拉线——这是"套挂式"的前提。

---

## 5. 相机怎么接

| 方式 | 事实 | 我们的用法 |
|---|---|---|
| **USB 摄像头（UVC）** | 插上自动出现 `/dev/video0`，免驱 | **P0 主方案**：1080p USB 相机 + 三脚架 |
| MIPI CSI | 2 路 22pin，支持 **IMX219（800W）/ OV5647（500W）/ IMX477（1230W）**；I2C 地址 0x10 | P1：第二视角/双目；**严禁带电插拔**（会烧模组） |
| 深度相机 | 现场提供奥比中光（USB） | P1：衣物体积/拥塞；驱动风险高，不进 P0 |

USB 相机注意事项：

- 4 路 USB3 总带宽够，但**供电**：单口 1A，相机 0.2—0.4A，没问题。
- 用 `v4l2-ctl --list-devices` 确认设备；Python 用 `cv2.VideoCapture(0)`。
- 曝光/白平衡手动锁定（`v4l2-ctl -c exposure_auto=1`），否则视觉读数会漂。
- 相机不要对着强逆光；展台补一盏 4000K 灯。

---

## 6. BPU 与 Model Zoo（"AI 能力"到底怎么用）

### 6.1 事实

- X5 BPU：**10 TOPS（INT8 等效）**，支持 Transformer/RWKV/检测/分割等。
- 模型不是"直接跑 ONNX"：需要 **x86 上用 OpenExplorer 工具链量化编译成 `.bin`**，板端用 `hobot_dnn`（Python 包 `pyeasy_dnn`）加载。
- X5 对应工具链：**OpenExplorer 1.2.8**（Docker 镜像 `openexplorer/ai_toolchain_ubuntu_20_x5_cpu:v1.2.8`），或 pip 安装 `rdkx5-yolo-mapper`（Ubuntu 22.04 + Python 3.10）。
- 官方 Model Zoo 提供 YOLO 系列（含 Ultralytics YOLOv8/YOLO11）的导出、校准、编译脚本。

来源：[RDK Model Zoo · ultralytics_yolo 转换指南](https://github.com/D-Robotics/rdk_model_zoo/blob/rdk_x5/samples/vision/ultralytics_yolo/conversion/README_cn.md)。

### 6.2 典型流程（P2 才做，赛前评估）

```bash
# x86 Ubuntu 22.04 + Python 3.10
conda create -n rdk_env python=3.10 -y && conda activate rdk_env
pip install rdkx5-yolo-mapper
# 1) 导出 ONNX（Ultralytics）
# 2) 准备 100—300 张校准图（我们场景的衣物/杆）
# 3) hb_mapper 量化编译 → *.bin
# 4) 拷到板端，hobot_dnn 加载推理
```

**48 小时判断**：模型训练/量化/调精度至少 1—2 天，且需要数据集。**P0 不用 BPU**，用 OpenCV ArUco（CPU 足够）；BPU 留给"下一版衣物识别"，答辩时讲路线图，不吹已实现。

---

## 7. TROS / ROS2 要不要用

- RDK 提供 **TogetheROS.Bot（TROS）**，基于 ROS2，提供相机、检测、语音等节点（`hobot_usb_cam`、`mipi_cam`、`hobot_dnn` 等），可 apt 安装。
- **我们的取舍**：48h 内**不用 ROS2 全栈**。原因：DDS 发现/QoS/跨机配置在陌生现场是纯风险；我们的系统只有 5 个线程 + MQTT，一个人能看懂。
- **保留迁移路径**：话题命名（`vision`/`cmd`/`state`）按 ROS2 风格设计，产品化时封装成节点即可。

> 答辩话术：*"我们用 RDK 的算力和接口，但没被中间件绑架；48 小时要的是能跑，不是架构漂亮。"*

---

## 8. 供电与散热（现场最容易翻车）

| 项 | 要求 | 做法 |
|---|---|---|
| X5 供电 | **5V/5A（25W）**，必须用官方/支持 5A 的适配器 | 自带 65W PD 充电宝 + 5A 线；**多数充电宝只有 5V/3A**，会掉压重启（见 docs/05 §9） |
| 散热 | 满载 10W 级 | 散热片 + 风扇（40PIN 5V），竖放垫高 10mm |
| 断电保护 | 演示不能因踢线中断 | 插排固定、线走桌下、胶带标记 |
| 单元供电 | 18650 ×4（+4 备用） | 每晚充满；现场带 2 个充电器 |

---

## 9. 现场开发流程（贴墙版）

```bash
# 0. 开箱检查
cat /etc/os-release            # 确认 Ubuntu 22.04
python3 --version              # 3.10.x
ls /dev/video*                 # 相机
ip a                           # 网络

# 1. 连网（现场 Wi-Fi 或手机热点）
nmcli dev wifi list
nmcli dev wifi connect "SSID" password "PASS"

# 2. 起热点给单元/手机（NetworkManager）
sudo nmcli dev wifi hotspot ifname wlan0 ssid HangFlow-01 password hangflow2026

# 3. 起 MQTT
sudo systemctl enable --now mosquitto
mosquitto_sub -t 'hangflow/#' -v

# 4. 跑中枢（赛前打成 systemd）
cd ~/hangflow && python3 -m software.hub.main --mock   # 先 mock
python3 -m software.hub.main                            # 再真机

# 5. 网页
# 手机连 HangFlow-01 → http://192.168.4.1:8000
```

---

## 10. 常见坑（按踩坑概率排序）

1. **40PIN 5V 只有 500mA**：别拿它给电机/大功率外设供电，会掉压重启。
2. **MIPI 相机带电插拔会烧**：插拔前必须断电。
3. **GPIO 复用没关**：直接 `GPIO.setup` 会报"pin already in use"，先 `srpi-config` 关掉专用功能。
4. **GPIO 编号模式**：BOARD/BCM/SOC 三套编号，接错线不报错但动作全错；统一 BOARD。
5. **5V/5A 电源**：用 5V/3A 充电宝 → 相机+Wi-Fi 峰值时重启，误判为"代码 bug"。
6. **Wi-Fi 热点**：`nmcli` 建的热点默认可能 5G/2.4G 混，ESP32 只支持 2.4G；显式设 `band bg`。
7. **Python 版本**：系统 3.10，pip 装包可能装到用户目录；用 venv 隔离。
8. **OpenCV 版本**：apt 的 `python3-opencv` 够用（ArUco 在 contrib 里，确认 `cv2.aruco` 存在；没有就 pip 装 `opencv-contrib-python`）。
9. **系统时间**：板子没 RTC 电池时时间错乱，MQTT 日志对不上；用中枢时间戳。
10. **现场不要重刷系统**：刷坏 = 项目结束；赛前备份 TF 卡。

---

## 11. 学习资源（赛前 1—2 天刷一遍）

| 资源 | 用途 |
|---|---|
| [RDK X3/X5 用户手册](https://developer.d-robotics.cc/rdk_x_doc/) | 硬件、系统、40PIN、相机、Model Zoo |
| [RDK S100/S600 手册](https://developer.d-robotics.cc/rdk_s_doc/) | 了解异构板（答辩对比用） |
| [RDK Model Zoo](https://github.com/D-Robotics/rdk_model_zoo) | YOLO 转换/部署示例 |
| [TROS 文档](https://developer.d-robotics.cc/tros_doc/) | ROS2 节点、相机、检测 |
| [地瓜开发者社区/论坛](https://forum.d-robotics.cc/) | 踩坑搜索 |
| [RDK Studio](https://developer.d-robotics.cc/) | 烧录/管理（Windows 已装：`E:\RDK Studio`） |
| [黑客松官网](https://hackathon.d-robotics.cc/) | 赛程、资源、FAQ |

---

## 12. 我们项目的"RDK 使用清单"（答辩用）

| RDK 能力 | 用在哪 | 现状 |
|---|---|---|
| 8×A55 CPU | 相机采集、ArUco、规划、Web、MQTT | ✅ P0 |
| 10 TOPS BPU | 衣物检测/材质（P2） | ⏳ 路线图 |
| USB3 ×4 | USB 相机 | ✅ P0 |
| 2×MIPI CSI | 第二视角（P1） | ⏳ |
| Wi-Fi6 | 热点 + 单元连接 | ✅ P0 |
| 40PIN | 风扇/状态灯/备用串口 | ✅ 少量 |
| CAN FD | 未来接升降晾衣架 | ⏳ 路线图 |
| Ubuntu 22.04 | Python/OpenCV/FastAPI/MQTT | ✅ P0 |

> 一句话：**P0 把 RDK 当"视觉 + 规划 + Web 服务器"用，P2 才用它最贵的 BPU。** 这不是浪费，是把不确定性留到有数据的时候。
