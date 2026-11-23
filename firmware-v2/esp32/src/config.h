// ============================================================================
// HangFlow v2 · 伸缩圆柱电控 —— 编译配置（现场只改这一段）
//
// 板子：ESP32-C3 SuperMini（Arduino framework / PlatformIO）
// 角色：UNIT_ROLE_END 1 = 端部 01/05（外端锚定、内端自由 30—120mm）
//       UNIT_ROLE_END 0 = 内部段 02—04（40—220mm）
// 说明：端部与内部段是同一套硬件；只有限位范围/夹持规则由固件区分。
// ============================================================================
#pragma once

#include <Arduino.h>

// ---------------- 身份 ----------------
#define UNIT_ID            "01"      // 01—05（演示），01/05 端部；最多 07
#define UNIT_ROLE_END      1         // 1=端部；0=内部段
#define FW_VERSION         "0.3.0"

// ---------------- 引脚（与 docs/v2/02 §3 一致） ----------------
#define PIN_BAT_SENSE      0         // ADC1_CH0，100k/100k 分压
#define PIN_LOCK_A         1         // 外端/数字端夹头微动，锁=低
#define PIN_LED            2         // WS2812 DIN（10k 上拉，strapping 脚）
#define PIN_LIM_MIN        3         // 下限位微动，触发=低
#define PIN_MOTOR_AIN1     4         // DRV8833 AIN1（LEDC ch0）
#define PIN_MOTOR_AIN2     5         // DRV8833 AIN2（LEDC ch1）
#define PIN_I2C_SDA        6         // AS5600 SDA
#define PIN_I2C_SCL        7         // AS5600 SCL
#define PIN_KEY            9         // 按键（并板载 BOOT；开机勿按住）
#define PIN_MOTOR_NSLEEP   10        // DRV8833 nSLEEP，10k 下拉
#define PIN_LIM_MAX        20        // 上限位微动，触发=低
#define PIN_LOCK_B         21        // 内端/另一端夹头微动，串 1k，锁=低

// ---------------- AS5600 / 丝杆 ----------------
#define AS5600_ADDR        0x36
#define AS5600_RAW_ANGLE   0x0E
#define ENCODER_CPR        4096.0f   // 12 bit
#define LEAD_MM            8.0f      // T8 导程 8mm
#define COUNTS_PER_MM      (ENCODER_CPR / LEAD_MM)   // 512
#define ENCODER_INVERT     0          // 读数方向反了就改 1
#define MOTOR_INVERT       0          // 伸出方向反了就改 1

// ---------------- 角色限位（mm，软限位） ----------------
#if UNIT_ROLE_END
  #define LENGTH_MIN_MM    30.0f
  #define LENGTH_MAX_MM    120.0f
  #define UNIT_ROLE_STR    "END"
#else
  #define LENGTH_MIN_MM    40.0f
  #define LENGTH_MAX_MM    220.0f
  #define UNIT_ROLE_STR    "MIDDLE"
#endif

// ---------------- 运动 ----------------
#define MAX_DUTY             0.80f    // 限制最大推力
#define MIN_DUTY             0.25f
#define POS_DEADBAND_MM      1.0f
#define ARRIVE_CONFIRM_MS    300
#define HOMING_DUTY          (-0.30f)
#define HOMING_TIMEOUT_MS    90000
#define MOVE_TIMEOUT_MS      120000
#define DEFAULT_SPEED_MM_S   4.0f
#define MAX_SPEED_MM_S       5.0f

// ---------------- 安全 ----------------
#define STALL_DUTY_MIN       0.35f
#define STALL_WINDOW_MS      300
#define STALL_COUNTS_MIN     3
#define STALL_CONFIRM        1     // 1=300ms 单窗口判定；2=600ms
#define BATT_WARN_MV         3500
#define BATT_LOW_MV          3400
#define CLAMP_DEBOUNCE_MS    50
#define CMD_HEARTBEAT_MS     500     // 中枢静默 → 停 + holding
#define NVS_SAVE_MIN_MS      5000

// ---------------- 周期 ----------------
#define ENCODER_PERIOD_MS    5
#define SAFETY_PERIOD_MS     5
#define CONTROL_PERIOD_MS    20
#define STATE_PERIOD_MOVING_MS 100
#define STATE_PERIOD_IDLE_MS   1000
#define LED_PERIOD_MS        100

// ---------------- Wi-Fi / MQTT ----------------
#define WIFI_SSID          "HangFlow"
#define WIFI_PASS          "hangflow2026"
#define MQTT_HOST          "10.42.0.1"
#define MQTT_PORT          1883

#define TOPIC_CMD          "hangflow/unit/" UNIT_ID "/cmd"
#define TOPIC_STATE        "hangflow/unit/" UNIT_ID "/state"
#define TOPIC_EVT          "hangflow/unit/" UNIT_ID "/evt"
#define TOPIC_ESTOP        "hangflow/sys/estop"
#define TOPIC_RESUME       "hangflow/sys/resume"
#define TOPIC_HUB_STATUS   "hangflow/hub/status"

