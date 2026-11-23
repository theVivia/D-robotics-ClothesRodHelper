// 安全输入 + 夹持联锁 + 堵转/低压/急停状态
#pragma once

#include <Arduino.h>

#include "config.h"

enum class ClampState : uint8_t {
  FREE = 0,
  REF_A,
  REF_B,
  FIXED,
};

enum class FaultCode : uint8_t {
  NONE = 0,
  STALL = 3,
  LIMIT = 4,
  LOW_BAT = 5,
  HOMING_TIMEOUT = 6,
  MOVE_TIMEOUT = 8,
  SENSOR = 9,
  ESTOP = 10,
  CLAMP = 13,
  CLAMP_CHANGED = 14,
  NO_ACTUATOR = 15,
};

class Safety {
 public:
  void begin();
  void update(uint32_t now);

  bool clampA() const { return clampA_; }
  bool clampB() const { return clampB_; }
  ClampState clampState() const { return clampState_; }
  bool motionAllowed() const;

  bool limitMin() const { return limitMin_; }
  bool limitMax() const { return limitMax_; }
  uint16_t battMv() const { return battMv_; }
  bool battLow() const { return battMv_ > 0 && battMv_ < BATT_LOW_MV; }
  bool battWarn() const { return battMv_ > 0 && battMv_ < BATT_WARN_MV; }

  bool estop() const { return estop_; }
  void setEstop(bool v) { estop_ = v; }

  bool takeShortPress();
  bool takeLongPress();

  // 堵转窗口（调用方在 MOVING 时每 300ms 喂一次 counts 和 duty）
  bool checkStall(int32_t counts, float duty, uint32_t now);
  void resetStall(int32_t counts);

 private:
  static bool readActiveLow(uint8_t pin);
  void updateButton(uint32_t now);

  bool clampA_ = false;
  bool clampB_ = false;
  bool limitMin_ = false;
  bool limitMax_ = false;
  ClampState clampState_ = ClampState::FREE;
  uint16_t battMv_ = 0;
  bool estop_ = false;

  bool shortPress_ = false;
  bool longPress_ = false;
  bool buttonRaw_ = false;
  uint32_t buttonDownMs_ = 0;
  bool longFired_ = false;

  uint32_t lastBattMs_ = 0;
  uint32_t stallWindowMs_ = 0;
  int32_t stallCounts_ = 0;
  uint8_t stallHits_ = 0;
};
