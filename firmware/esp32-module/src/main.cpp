// ============================================================================
// 衣序 HangFlow · 套挂单元固件（v0.2 骨架）
// ----------------------------------------------------------------------------
// 硬件依据：
//   - 引脚表 / 安全策略：docs/05-硬件与电控设计.md §5、§11
//   - 机械参数：docs/04-机械结构设计.md（轮 Ø28、杆 Ø20—35）
//   - 通信协议：docs/07-软件架构与通信协议.md §3
//
// 职责：
//   1) 连 Wi-Fi / MQTT，收 move/stop/home/ping
//   2) AS5600 绝对角 → 里程；速度环 + 位置环把模块走到 target_mm
//   3) 堵转（角度不变）、ToF 遮挡、心跳丢失、低电 四道保护
//   4) 10Hz 上报状态，事件上报
//
// 状态：骨架，未在真机编译验证（标 TODO(verify) 的都要实测）。
// ============================================================================
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_NeoPixel.h>
#include <VL53L1X.h>
#include "config.h"

// ---------------- 全局对象 ----------------
WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);
Adafruit_NeoPixel led(1, PIN_LED, NEO_GRB + NEO_KHZ800);
VL53L1X tof;

// ---------------- 状态 ----------------
enum State { ST_BOOT, ST_IDLE, ST_MOVING, ST_HOMING, ST_ESTOP, ST_FAULT };
State state = ST_BOOT;

float posMm = 0.0f;          // AS5600 累计的绝对位置（mm，向右为正）
float targetMm = 0.0f;
float cmdSpeed = DEFAULT_SPEED_MM_S;
float velMmS = 0.0f;
float dutyOut = 0.0f;

uint16_t lastRawAngle = 0;
bool     angleInited = false;
uint32_t lastSeq = 0;
uint32_t lastCmdMs = 0;
uint32_t lastStateMs = 0;
uint32_t lastCtrlMs = 0;
uint32_t lastStallCheckMs = 0;
uint32_t bootMs = 0;
uint32_t buttonDownMs = 0;
uint8_t  faultCode = 0;
uint8_t  stallCount = 0;
float    stallRefPos = 0.0f;
bool     homed = false;

// ---------------- 基础 IO ----------------
void setMotorRaw(float duty) {          // duty ∈ [-1, 1]；带 nSLEEP 使能
  duty = constrain(duty, -1.0f, 1.0f);
  dutyOut = duty;
  digitalWrite(PIN_MOTOR_NSLEEP, HIGH); // 先使能
  int pwm = (int)(fabsf(duty) * 255);
  if (duty >= 0) { digitalWrite(PIN_MOTOR_AIN2, LOW);  analogWrite(PIN_MOTOR_AIN1, pwm); }
  else           { digitalWrite(PIN_MOTOR_AIN1, LOW);  analogWrite(PIN_MOTOR_AIN2, pwm); }
}

void stopMotor() {
  analogWrite(PIN_MOTOR_AIN1, 0);
  analogWrite(PIN_MOTOR_AIN2, 0);
  digitalWrite(PIN_MOTOR_NSLEEP, LOW);  // 高阻，断电即停
  dutyOut = 0.0f;
}

void setLed(uint8_t r, uint8_t g, uint8_t b) {
  led.setPixelColor(0, led.Color(r, g, b)); led.show();
}

uint16_t readBattMv() {
  // 100k/100k 分压：ADC 电压 × 2；analogReadMilliVolts 已做校准
  uint32_t mv = analogReadMilliVolts(PIN_BAT_SENSE);
  return (uint16_t)(mv * 2);
}

uint16_t readTofMm() {
  if (tof.timeoutOccurred()) return TOF_MAX_MM;
  uint16_t d = tof.read();
  return (d == 0 || d > TOF_MAX_MM) ? TOF_MAX_MM : d;
}

// ---------------- AS5600 ----------------
uint16_t readAs5600Raw() {
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(AS5600_RAW_ANGLE);
  if (Wire.endTransmission(false) != 0) return lastRawAngle;
  if (Wire.requestFrom((uint8_t)AS5600_ADDR, (uint8_t)2) != 2) return lastRawAngle;
  uint8_t hi = Wire.read(), lo = Wire.read();
  return ((uint16_t)(hi << 8) | lo) & 0x0FFF;
}

// 读取角度增量并累加到 posMm；返回本次增量（counts，带符号）
int32_t updatePosFromAs5600() {
  uint16_t raw = readAs5600Raw();
  if (!angleInited) { lastRawAngle = raw; angleInited = true; return 0; }
  int16_t delta = (int16_t)raw - (int16_t)lastRawAngle;
  if (delta > 2048) delta -= 4096;
  if (delta < -2048) delta += 4096;
  lastRawAngle = raw;
  posMm += delta * MM_PER_COUNT;
  return delta;
}

// ---------------- 事件与状态上报 ----------------
void publishEvt(const char* code, const char* msg) {
  StaticJsonDocument<256> doc;
  doc["v"] = 1; doc["id"] = UNIT_ID; doc["code"] = code;
  doc["msg"] = msg; doc["x_mm"] = posMm; doc["ts"] = millis();
  char buf[256]; serializeJson(doc, buf, sizeof(buf));
  mqtt.publish(TOPIC_EVT, buf);
}

void publishState() {
  StaticJsonDocument<384> doc;
  doc["v"] = 1; doc["id"] = UNIT_ID; doc["seq"] = lastSeq;
  doc["x_mm"] = posMm; doc["v_mm_s"] = velMmS;
  doc["batt_mv"] = readBattMv();
  doc["tof_f_mm"] = readTofMm();
  JsonObject f = doc.createNestedObject("flags");
  f["homing"] = (state == ST_HOMING);
  f["moving"] = (state == ST_MOVING);
  f["estop"]  = (state == ST_ESTOP);
  f["fault"]  = faultCode;
  doc["uptime_s"] = (millis() - bootMs) / 1000;
  char buf[384]; serializeJson(doc, buf, sizeof(buf));
  mqtt.publish(TOPIC_STATE, buf);
}

// ---------------- 安全 ----------------
void enterFault(uint8_t code, const char* msg) {
  stopMotor();
  state = ST_FAULT;
  faultCode = code;
  setLed(80, 0, 0);
  publishEvt(msg, "fault");   // msg 同时作为事件码
}

// 堵转：PWM 在给，但固定窗口内 AS5600 几乎没动
bool checkStall() {
  if (state != ST_MOVING || fabsf(dutyOut) < STALL_DUTY_MIN) {
    stallCount = 0; stallRefPos = posMm; lastStallCheckMs = millis();
    return false;
  }
  if (millis() - lastStallCheckMs < STALL_WINDOW_MS) return false;

  float moved = fabsf(posMm - stallRefPos);
  stallRefPos = posMm;
  lastStallCheckMs = millis();
  // 1 count ≈ 0.0215mm；STALL_ANGLE_MIN=3 → 0.065mm/300ms
  if (moved < STALL_ANGLE_MIN * MM_PER_COUNT * 4) {
    if (++stallCount >= STALL_CONFIRM) return true;
  } else {
    stallCount = 0;
  }
  return false;
}

bool safetyCheck() {
  // 1) 堵转
  if (checkStall()) {
    if (state == ST_HOMING) {          // 归零时撞到挡块是正常现象
      stopMotor(); posMm = 0; lastRawAngle = readAs5600Raw(); homed = true;
      state = ST_IDLE; publishEvt("HOMED", "homing done");
      return false;
    }
    enterFault(3, "E03");              // E03 stall
    return false;
  }
  // 2) ToF 前方遮挡（只挡前进方向）
  if (state == ST_MOVING && dutyOut > 0.1f && readTofMm() < TOF_OBSTACLE_MM) {
    enterFault(4, "E04");              // E04 tof obstacle
    return false;
  }
  // 3) 低电
  if (readBattMv() < BATT_CRITICAL_MV && state != ST_ESTOP) {
    enterFault(5, "E05");              // E05 battery critical
    return false;
  }
  // 4) 心跳丢失（运动中）
  if (state == ST_MOVING && millis() - lastCmdMs > HEARTBEAT_TIMEOUT_MS) {
    enterFault(2, "E02");              // E02 hub heartbeat lost
    return false;
  }
  return true;
}

// ---------------- 运动控制（50Hz） ----------------
void controlTick() {
  uint32_t now = millis();
  float dt = (now - lastCtrlMs) / 1000.0f;
  lastCtrlMs = now;
  if (dt <= 0 || dt > 0.2f) return;

  int32_t dCounts = updatePosFromAs5600();
  velMmS = dCounts * MM_PER_COUNT / dt;

  if (!safetyCheck()) return;

  if (state == ST_HOMING) {
    setMotorRaw(HOMING_DUTY);
    if (posMm < -30.0f) {              // 超程保护
      stopMotor(); posMm = 0; lastRawAngle = readAs5600Raw();
      homed = true; state = ST_IDLE; publishEvt("HOMED", "homing by limit");
    }
    return;
  }

  if (state == ST_MOVING) {
    float err = targetMm - posMm;
    if (fabsf(err) < POS_DEADBAND_MM) {
      stopMotor(); state = ST_IDLE; publishEvt("DONE", "arrived");
      return;
    }
    if (now - lastCmdMs > MOVE_TIMEOUT_MS) {   // 超时
      stopMotor(); state = ST_IDLE; publishEvt("E08", "move timeout");
      return;
    }
    // 位置环 → 速度指令；速度环 P → 占空比（TODO(verify) 整定）
    float vWant = constrain(err * 3.0f, -cmdSpeed, cmdSpeed);
    float vErr = vWant - velMmS;
    setMotorRaw(constrain(vErr * 0.02f, -0.85f, 0.85f));
  } else {
    stopMotor();
  }
}

// ---------------- MQTT ----------------
void onCommand(char* topic, byte* payload, unsigned int len) {
  StaticJsonDocument<384> doc;
  if (deserializeJson(doc, payload, len)) { publishEvt("E07", "bad json"); return; }
  unsigned int v = doc["v"] | 1;
  uint32_t seq = doc["seq"] | 0;
  const char* op = doc["op"] | "";
  if (v != 1) { publishEvt("E07", "bad version"); return; }
  if (seq != 0 && seq <= lastSeq) return;      // 旧指令丢弃
  lastSeq = seq;
  lastCmdMs = millis();

  if (!strcmp(op, "move")) {
    if (state == ST_ESTOP || state == ST_FAULT) return;
    targetMm = doc["target_mm"] | posMm;
    cmdSpeed = doc["speed_mm_s"] | DEFAULT_SPEED_MM_S;
    if (!homed) { state = ST_HOMING; return; }
    state = ST_MOVING;
  } else if (!strcmp(op, "stop")) {
    stopMotor(); state = ST_IDLE;
  } else if (!strcmp(op, "home")) {
    homed = false; state = ST_HOMING;
  } else if (!strcmp(op, "ping")) {
    publishState();
  } else {
    publishEvt("E07", "unknown op");
  }
}

void onEstop(char* topic, byte* payload, unsigned int len) {
  stopMotor(); state = ST_ESTOP;
  publishEvt("ESTOP", "emergency stop");
}

void mqttEnsure() {
  if (mqtt.connected()) return;
  static uint32_t lastTry = 0;
  if (millis() - lastTry < 3000) return;
  lastTry = millis();
  if (mqtt.connect(("hangflow-unit-" UNIT_ID), MQTT_USER, MQTT_PASS,
                   TOPIC_STATE, 1, true, "{\"online\":false}")) {
    mqtt.subscribe(TOPIC_CMD, 1);
    mqtt.subscribe(TOPIC_ESTOP, 1);
    mqtt.publish(TOPIC_STATE, "{\"online\":true}", true);
  }
}

// ---------------- setup / loop ----------------
void setup() {
  Serial.begin(115200);
  bootMs = millis();

  pinMode(PIN_MOTOR_AIN1, OUTPUT); pinMode(PIN_MOTOR_AIN2, OUTPUT);
  pinMode(PIN_MOTOR_NSLEEP, OUTPUT);
  digitalWrite(PIN_MOTOR_NSLEEP, LOW);       // 上电默认电机高阻
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  pinMode(PIN_TOF_XSHUT, OUTPUT);
  digitalWrite(PIN_TOF_XSHUT, HIGH);         // 释放 ToF 复位

  led.begin(); led.setBrightness(40); setLed(30, 30, 30);

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(400000);

  // AS5600 自检
  Wire.beginTransmission(AS5600_ADDR);
  if (Wire.endTransmission() != 0) Serial.println("AS5600 not found");
  lastRawAngle = readAs5600Raw(); angleInited = true;

  tof.setTimeout(50);
  if (!tof.init()) Serial.println("VL53L1X not found");
  else { tof.setDistanceMode(VL53L1X::Short); tof.startContinuous(50); }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onCommand);
  mqtt.setBufferSize(512);

  state = ST_HOMING;   // 上电自动归零
}

void loop() {
  // Wi-Fi / MQTT
  if (WiFi.status() != WL_CONNECTED) {
    static uint32_t lastWifiTry = 0;
    if (millis() - lastWifiTry > 5000) { lastWifiTry = millis(); WiFi.begin(WIFI_SSID, WIFI_PASS); }
  } else {
    mqttEnsure(); mqtt.loop();
  }

  // 按键：短按暂停，长按 3s 急停（松开生效）
  if (digitalRead(PIN_BUTTON) == LOW) {
    if (buttonDownMs == 0) buttonDownMs = millis();
    if (millis() - buttonDownMs > 3000 && state != ST_ESTOP) {
      stopMotor(); state = ST_ESTOP; publishEvt("ESTOP", "button long press");
    }
  } else {
    if (buttonDownMs && millis() - buttonDownMs < 800) {   // 短按
      if (state == ST_MOVING) { stopMotor(); state = ST_IDLE; }
    }
    buttonDownMs = 0;
  }

  // 50Hz 控制
  if (millis() - lastCtrlMs >= 1000 / CONTROL_HZ) controlTick();

  // 10Hz 状态 + LED 语义
  if (millis() - lastStateMs >= 1000 / STATE_HZ) {
    lastStateMs = millis();
    if (mqtt.connected()) publishState();
    switch (state) {
      case ST_IDLE:   setLed(20, 20, 20); break;   // 白：待机
      case ST_HOMING: setLed(0, 60, 60);  break;   // 青：归零
      case ST_MOVING: setLed(0, 80, 0);   break;   // 绿：移动
      case ST_FAULT:  setLed(80, 0, 0);   break;   // 红：故障
      case ST_ESTOP:  setLed(80, 0, 0);   break;   // 红：急停
      default:        setLed(20, 20, 20); break;
    }
  }
}
