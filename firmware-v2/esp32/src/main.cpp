// ============================================================================
// HangFlow v2 · 伸缩圆柱固件主程序（ESP32-C3 SuperMini）
//
// 闭环：AS5600 多圈计数 → 长度 mm → 位置控制 DRV8833
// 安全：夹持联锁（free/fixed 禁动）、卡死 300ms、上下限位、低压、急停
// 通信：MQTT cmd(set_length/clamp/stop/resume/home)、state 10Hz、evt
//
// 未在真机验证（README 已注明）；按 docs/v2/02-电控与BOM.md 的引脚/协议实现。
// ============================================================================
#include <Adafruit_NeoPixel.h>
#include <Arduino.h>
#include <math.h>

#include "as5600.h"
#include "config.h"
#include "motor.h"
#include "net.h"
#include "safety.h"
#include "store.h"

namespace {

enum class RunState : uint8_t { IDLE, MOVING, HOMING, FAULT, ESTOP };

As5600 encoder;
Motor motor;
Safety safety;
EncoderStore store;
Net net;
Adafruit_NeoPixel pixel(1, PIN_LED, NEO_GRB + NEO_KHZ800);

RunState state = RunState::IDLE;
FaultCode fault = FaultCode::NONE;
ClampState lastClampState = ClampState::FREE;

float targetMm = LENGTH_MIN_MM;
float speedMmS = DEFAULT_SPEED_MM_S;
bool needHome = false;
bool homed = false;

uint32_t lastEncMs = 0;
uint32_t lastSafetyMs = 0;
uint32_t lastControlMs = 0;
uint32_t lastStateMs = 0;
uint32_t lastLedMs = 0;
uint32_t lastSaveMs = 0;
uint32_t idleSinceMs = 0;
uint32_t moveStartMs = 0;
uint32_t homingStartMs = 0;
uint32_t lastSensorRetryMs = 0;
int32_t savedCounts = 0;

const char *stateName(RunState s) {
  switch (s) {
    case RunState::MOVING: return "moving";
    case RunState::HOMING: return "online";  // 归零中，state 仍报 online，evt 区分
    case RunState::FAULT: return "fault";
    case RunState::ESTOP: return "estop";
    default: return "idle";
  }
}

const char *clampName(ClampState c) {
  switch (c) {
    case ClampState::REF_A: return "referenced_a";
    case ClampState::REF_B: return "referenced_b";
    case ClampState::FIXED: return "fixed";
    default: return "free";
  }
}

void setLed(uint8_t r, uint8_t g, uint8_t b) {
  pixel.setPixelColor(0, pixel.Color(r, g, b));
  pixel.show();
}

void ledOff() {
  pixel.setPixelColor(0, 0);
  pixel.show();
}

void updateLed(uint32_t now) {
  if (now - lastLedMs < LED_PERIOD_MS) return;
  lastLedMs = now;
  switch (state) {
    case RunState::ESTOP:
    case RunState::FAULT:
      setLed((now / 200) % 2 ? 80 : 0, 0, 0);  // 红闪
      break;
    case RunState::MOVING:
      setLed(0, 0, 40);  // 蓝
      break;
    case RunState::HOMING:
      setLed(40, 40, 40);  // 白
      break;
    default:
      if (safety.battLow()) {
        setLed(60, 30, 0);  // 黄
      } else if (!safety.motionAllowed()) {
        setLed((now / 500) % 2 ? 60 : 0, (now / 500) % 2 ? 60 : 0, 0);  // 黄闪：未锁
      } else {
        setLed(0, 20, 0);  // 绿
      }
      break;
  }
}

void stopAll(const char *evtCode, FaultCode f) {
  motor.stop();
  motor.brake(200);  // 动态刹车 200ms
  motor.sleep();     // 高阻，减速箱保持
  if (f != FaultCode::NONE) {
    fault = f;
    state = (f == FaultCode::ESTOP) ? RunState::ESTOP : RunState::FAULT;
  } else if (state == RunState::MOVING || state == RunState::HOMING) {
    state = RunState::IDLE;
  }
  if (evtCode != nullptr) {
    net.publishEvt(evtCode, "stopped", encoder.lengthMm());
  }
}

bool isFaultLike() {
  return state == RunState::FAULT || state == RunState::ESTOP;
}

bool targetInRange(float mm) {
  return mm >= LENGTH_MIN_MM && mm <= LENGTH_MAX_MM;
}

uint32_t maxCounts() {
  return static_cast<uint32_t>((LENGTH_MAX_MM - LENGTH_MIN_MM) * COUNTS_PER_MM) + 200;
}

void startHoming(uint32_t now) {
  if (!safety.motionAllowed()) {
    net.publishEvt("E13", "clamp not referenced; cannot home", encoder.lengthMm());
    return;
  }
  state = RunState::HOMING;
  fault = FaultCode::NONE;
  homingStartMs = now;
  targetMm = LENGTH_MIN_MM;
  motor.wake();
  net.publishEvt("OK", "homing start", encoder.lengthMm());
}

void handleCommand(const Command &c, uint32_t now) {
  if (strcmp(c.op, "stop") == 0) {
    stopAll("E00", FaultCode::NONE);
    net.publishEvt("OK", "stop", encoder.lengthMm());
    return;
  }
  if (strcmp(c.op, "resume") == 0) {
    if (fault == FaultCode::ESTOP || fault == FaultCode::STALL) {
      fault = FaultCode::NONE;
      state = RunState::IDLE;
      safety.setEstop(false);
      net.publishEvt("OK", "resume", encoder.lengthMm());
    } else if (fault == FaultCode::SENSOR) {
      net.publishEvt("E09", "sensor still unhealthy", encoder.lengthMm());
    } else {
      fault = FaultCode::NONE;
      state = RunState::IDLE;
      net.publishEvt("OK", "resume", encoder.lengthMm());
    }
    return;
  }
  if (strcmp(c.op, "home") == 0) {
    startHoming(now);
    return;
  }
  if (strcmp(c.op, "clamp") == 0) {
    if (strcmp(c.action, "status") == 0) {
      net.publishEvt("OK", clampName(safety.clampState()), encoder.lengthMm());
    } else {
      // P0 手动夹头没有执行器；lock/release 留给 P1 电动推套筒
      net.publishEvt("E15", "manual clamp; actuator only in P1", encoder.lengthMm());
    }
    return;
  }
  if (strcmp(c.op, "set_length") != 0) {
    net.publishEvt("E07", "unknown op", encoder.lengthMm());
    return;
  }

  if (safety.estop() || state == RunState::ESTOP) {
    net.publishEvt("E10", "estop latched", encoder.lengthMm());
    return;
  }
  if (!safety.motionAllowed()) {
    net.publishEvt("E13", "clamp not referenced", encoder.lengthMm());
    return;
  }
  if (!homed || needHome) {
    net.publishEvt("E06", "not homed; send home first", encoder.lengthMm());
    return;
  }
  if (!targetInRange(c.setLengthMm)) {
    net.publishEvt("E07", "target out of role range", encoder.lengthMm());
    return;
  }
  if (safety.battLow()) {
    net.publishEvt("E05", "low battery", encoder.lengthMm());
    fault = FaultCode::LOW_BAT;
    state = RunState::FAULT;
    return;
  }

  targetMm = c.setLengthMm;
  speedMmS = constrain(c.speedMmS, 1.0f, MAX_SPEED_MM_S);
  state = RunState::MOVING;
  fault = FaultCode::NONE;
  moveStartMs = now;
  motor.wake();
  safety.resetStall(encoder.counts());
  net.publishEvt("OK", "move start", encoder.lengthMm());
}

void controlTick(uint32_t now) {
  // 急停优先
  if (safety.estop() && state != RunState::ESTOP) {
    stopAll("E10", FaultCode::ESTOP);
  }
  if (state == RunState::ESTOP) {
    motor.sleep();
    return;
  }

  // 夹持状态变化：运动中立即停（E14）
  const ClampState cs = safety.clampState();
  if (cs != lastClampState) {
    lastClampState = cs;
    if (state == RunState::MOVING || state == RunState::HOMING) {
      stopAll("E14", FaultCode::CLAMP_CHANGED);
      return;
    }
  }

  if (state == RunState::FAULT) {
    motor.sleep();
    return;
  }

  if (state == RunState::HOMING) {
    if (!safety.motionAllowed()) {
      stopAll("E13", FaultCode::CLAMP);
      return;
    }
    if (safety.limitMin()) {
      motor.stop();
      motor.brake(200);
      motor.sleep();
      encoder.zero();
      homed = true;
      needHome = false;
      state = RunState::IDLE;
      targetMm = encoder.lengthMm();
      savedCounts = 0;
      store.save(0);
      net.publishEvt("OK", "homed at min", encoder.lengthMm());
      return;
    }
    if (now - homingStartMs > HOMING_TIMEOUT_MS) {
      stopAll("E06", FaultCode::HOMING_TIMEOUT);
      return;
    }
    motor.setDuty(HOMING_DUTY);
    return;
  }

  if (state != RunState::MOVING) return;

  // 传感器/夹持/电池/超时
  if (!encoder.healthy()) {
    stopAll("E09", FaultCode::SENSOR);
    return;
  }
  if (!safety.motionAllowed()) {
    stopAll("E13", FaultCode::CLAMP);
    return;
  }
  if (safety.battLow()) {
    stopAll("E05", FaultCode::LOW_BAT);
    return;
  }
  if (now - moveStartMs > MOVE_TIMEOUT_MS) {
    stopAll("E08", FaultCode::MOVE_TIMEOUT);
    return;
  }

  const float len = encoder.lengthMm();
  const float err = targetMm - len;

  // 限位：到端即停；下限顺带把计数清零（标定基准）
  if (safety.limitMax() && err > 0) {
    stopAll("E04", FaultCode::LIMIT);
    return;
  }
  if (safety.limitMin() && err < 0) {
    encoder.zero();
    stopAll("E04", FaultCode::LIMIT);
    return;
  }

  // 到位
  if (fabsf(err) <= POS_DEADBAND_MM) {
    motor.stop();
    motor.brake(200);
    motor.sleep();
    state = RunState::IDLE;
    idleSinceMs = now;
    savedCounts = encoder.counts();
    store.save(savedCounts);
    net.publishEvt("OK", "arrived", len);
    return;
  }

  // 简单 P 控制（骨架；算法同学可换成速度梯形/PI）
  float duty = MIN_DUTY + fabsf(err) * 0.06f;
  if (duty > MAX_DUTY) duty = MAX_DUTY;
  duty *= (speedMmS / DEFAULT_SPEED_MM_S);
  duty = constrain(duty, MIN_DUTY, MAX_DUTY);
  const float signedDuty = (err > 0) ? duty : -duty;
  motor.setDuty(signedDuty);

  if (safety.checkStall(encoder.counts(), signedDuty, now)) {
    stopAll("E03", FaultCode::STALL);
  }
}

void publishState(uint32_t now) {
  net.publishState(encoder.lengthMm(), safety.clampState(), safety.clampA(), safety.clampB(),
                   safety.limitMin(), safety.limitMax(), safety.estop(),
                   static_cast<uint8_t>(fault), safety.battMv(), stateName(state),
                   now / 1000);
}

}  // namespace

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.printf("HangFlow unit %s role=%s fw=%s\n", UNIT_ID, UNIT_ROLE_STR, FW_VERSION);

  pixel.begin();
  pixel.setBrightness(30);
  ledOff();

  motor.begin();
  safety.begin();
  store.begin();

  int32_t stored = 0;
  if (store.load(stored) && stored >= -50 &&
      stored <= static_cast<int32_t>(maxCounts())) {
    encoder.setCounts(stored);
    savedCounts = stored;
    homed = true;
    needHome = false;
  } else {
    homed = false;
    needHome = true;
  }

  if (!encoder.begin()) {
    fault = FaultCode::SENSOR;
    state = RunState::FAULT;
    Serial.println("AS5600 not found (0x36)");
  }

  net.begin();
  targetMm = constrain(encoder.lengthMm(), LENGTH_MIN_MM, LENGTH_MAX_MM);
  lastSaveMs = millis();
  idleSinceMs = millis();
}

void loop() {
  const uint32_t now = millis();

  if (now - lastEncMs >= ENCODER_PERIOD_MS) {
    lastEncMs = now;
    encoder.update();
  }
  if (now - lastSafetyMs >= SAFETY_PERIOD_MS) {
    lastSafetyMs = now;
    safety.update(now);
  }

  // 按键：短按停；长按 3s 锁存/解除急停
  if (safety.takeLongPress()) {
    if (safety.estop()) {
      safety.setEstop(false);
      fault = FaultCode::NONE;
      state = RunState::IDLE;
      net.publishEvt("OK", "estop cleared by key", encoder.lengthMm());
    } else {
      safety.setEstop(true);
      stopAll("E10", FaultCode::ESTOP);
    }
  }
  if (safety.takeShortPress() && state == RunState::MOVING) {
    stopAll("E00", FaultCode::NONE);
    net.publishEvt("OK", "paused by key", encoder.lengthMm());
  }

  // MQTT 广播急停/复位
  if (net.estopBroadcast()) {
    net.clearEstopBroadcast();
    safety.setEstop(true);
    stopAll("E10", FaultCode::ESTOP);
  }
  if (net.resumeBroadcast()) {
    net.clearResumeBroadcast();
    safety.setEstop(false);
    if (fault == FaultCode::ESTOP) {
      fault = FaultCode::NONE;
      state = RunState::IDLE;
      net.publishEvt("OK", "resume broadcast", encoder.lengthMm());
    }
  }

  // 断网/断中枢：运动中 500ms 无心跳 → 停 + holding
  if (state == RunState::MOVING && net.connected() &&
      now - net.lastHubMs() > CMD_HEARTBEAT_MS) {
    stopAll("E01", FaultCode::NONE);
    net.publishEvt("OK", "hub silent; hold", encoder.lengthMm());
  }

  // 传感器故障时每 2s 重试
  if (fault == FaultCode::SENSOR && now - lastSensorRetryMs > 2000) {
    lastSensorRetryMs = now;
    if (encoder.begin()) {
      fault = FaultCode::NONE;
      state = RunState::IDLE;
      needHome = true;
    }
  }

  Command cmd;
  if (net.takeCommand(cmd)) handleCommand(cmd, now);

  // 未归零：夹持允许时自动归零
  if (needHome && !homed && state == RunState::IDLE && safety.motionAllowed() &&
      net.connected()) {
    startHoming(now);
  }

  if (now - lastControlMs >= CONTROL_PERIOD_MS) {
    lastControlMs = now;
    controlTick(now);
  }

  const uint32_t statePeriod =
      (state == RunState::MOVING || state == RunState::HOMING) ? STATE_PERIOD_MOVING_MS
                                                              : STATE_PERIOD_IDLE_MS;
  if (now - lastStateMs >= statePeriod) {
    lastStateMs = now;
    publishState(now);
  }

  // NVS 保存：静止 500ms 后，且距上次 ≥5s
  if ((state == RunState::IDLE || state == RunState::FAULT) &&
      now - idleSinceMs > 500 && now - lastSaveMs > NVS_SAVE_MIN_MS &&
      encoder.counts() != savedCounts) {
    savedCounts = encoder.counts();
    lastSaveMs = now;
    store.save(savedCounts);
  }

  net.loop(now);
  updateLed(now);
}

