// ============================================================================
// 衣序 HangFlow 套挂单元固件 —— 配置（现场只改这一段）
// 目标板：ESP32-C3 SuperMini（4MB Flash）
// 引脚与 docs/05 §5.1 引脚分配总表一致；接线见 hardware/wiring/wiring-clipunit.md
//
// 设计要点（来自 docs/05 §6）：
//   * 位置反馈用 AS5600 磁编码（绝对角），N20 自带编码器不接（P1 再说）
//   * DRV8833 模块没有采样电阻 → 堵转只能靠"PWM 在给但 AS5600 不转"判断
//   * nSLEEP 上电默认低（输出高阻），必须 MCU 主动拉高才可能动
// ============================================================================
#pragma once

// ---------- 身份 ----------
#define UNIT_ID            "01"          // 每个单元改成 01/02/03/04
#define FW_VERSION         "0.2.0"

// ---------- Wi-Fi / MQTT ----------
#define WIFI_SSID          "HangFlow-01" // RDK 热点（2.4G）
#define WIFI_PASS          "hangflow2026"
#define MQTT_HOST          "192.168.4.1" // RDK 热点网关
#define MQTT_PORT          1883
#define MQTT_USER          ""
#define MQTT_PASS          ""
#define TOPIC_CMD          "hangflow/unit/" UNIT_ID "/cmd"
#define TOPIC_STATE        "hangflow/unit/" UNIT_ID "/state"
#define TOPIC_EVT          "hangflow/unit/" UNIT_ID "/evt"
#define TOPIC_ESTOP        "hangflow/sys/estop"

// ---------- 引脚（ESP32-C3 SuperMini）----------
#define PIN_BAT_SENSE      0    // ADC1_CH0，100k/100k 分压（电池 3.0—4.2V → 1.5—2.1V）
#define PIN_BUTTON         1    // 按键，内部上拉，低有效
#define PIN_TOF_XSHUT      2    // VL53L1X 复位，外部 10k 上拉（strapping 脚，注意）
#define PIN_LED            3    // WS2812B 数据，串 330Ω
#define PIN_MOTOR_AIN1     4    // DRV8833 AIN1（LEDC ch0）
#define PIN_MOTOR_AIN2     5    // DRV8833 AIN2（LEDC ch1）
#define PIN_I2C_SDA        6    // AS5600 + VL53L1X 共用
#define PIN_I2C_SCL        7    // 400kHz
#define PIN_MOTOR_NSLEEP   10   // DRV8833 nSLEEP，低=休眠/高阻；外部 10k 下拉

// I2C 地址
#define AS5600_ADDR        0x36
#define AS5600_RAW_ANGLE   0x0E
#define TOF_I2C_ADDR       0x29

// ---------- 机械参数（与 docs/04 一致）----------
#define WHEEL_DIAMETER_MM  28.0f
#define AS5600_CPR         4096.0f   // 12 位
#define MM_PER_COUNT       (3.1415926f * WHEEL_DIAMETER_MM / AS5600_CPR)

// ---------- 运动参数 ----------
#define MAX_SPEED_MM_S     60.0f
#define DEFAULT_SPEED_MM_S 45.0f
#define MAX_ACCEL_MM_S2    200.0f
#define POS_DEADBAND_MM    2.0f
#define MOVE_TIMEOUT_MS    12000
#define HOMING_DUTY        (-0.45f)   // 归零：低速向左

// ---------- 安全阈值 ----------
// 堵转：PWM 足够大，但 300ms 内 AS5600 角度几乎不变
#define STALL_DUTY_MIN     0.35f
#define STALL_WINDOW_MS    300
#define STALL_ANGLE_MIN    3       // LSB，约 0.026°（≈0.006mm，轮子基本没动）
#define STALL_CONFIRM      2       // 连续 2 次 → 判堵转（约 0.6s）
#define BATT_LOW_MV        3400
#define BATT_CRITICAL_MV   3300
#define HEARTBEAT_TIMEOUT_MS 500   // 中枢失联 → 停
#define TOF_OBSTACLE_MM    60
#define TOF_MAX_MM         2000

// ---------- 控制周期 ----------
#define CONTROL_HZ         50
#define STATE_HZ           10
