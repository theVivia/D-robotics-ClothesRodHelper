#include "safety.h"

#include "config.h"

namespace {
struct Debounce {
  bool stable = false;
  uint8_t count = 0;
};
Debounce dbA, dbB, dbMin, dbMax;

bool debounceRead(uint8_t pin, Debounce &db) {
  const bool raw = (digitalRead(pin) == LOW);  // 所有安全开关：低=触发/锁
  if (raw == db.stable) {
    db.count = 0;
  } else if (++db.count >= 3) {
    db.stable = raw;
    db.count = 0;
  }
  return db.stable;
}
}  // namespace

void Safety::begin() {
  pinMode(PIN_LOCK_A, INPUT_PULLUP);
  pinMode(PIN_LOCK_B, INPUT_PULLUP);
  pinMode(PIN_LIM_MIN, INPUT_PULLUP);
  pinMode(PIN_LIM_MAX, INPUT_PULLUP);
  pinMode(PIN_KEY, INPUT_PULLUP);
  pinMode(PIN_BAT_SENSE, INPUT);
  analogReadResolution(12);

  dbA = dbB = dbMin = dbMax = Debounce{};
  clampA_ = debounceRead(PIN_LOCK_A, dbA);
  clampB_ = debounceRead(PIN_LOCK_B, dbB);
  limitMin_ = debounceRead(PIN_LIM_MIN, dbMin);
  limitMax_ = debounceRead(PIN_LIM_MAX, dbMax);
  updateButton(millis());
}

bool Safety::readActiveLow(uint8_t pin) { return digitalRead(pin) == LOW; }

void Safety::update(uint32_t now) {
  clampA_ = debounceRead(PIN_LOCK_A, dbA);
  clampB_ = debounceRead(PIN_LOCK_B, dbB);
  limitMin_ = debounceRead(PIN_LIM_MIN, dbMin);
  limitMax_ = debounceRead(PIN_LIM_MAX, dbMax);

#if UNIT_ROLE_END
  // 端部：外端(A)必须锚定；内端(B)锁上=长度固定
  if (!clampA_) {
    clampState_ = ClampState::FREE;
  } else if (clampB_) {
    clampState_ = ClampState::FIXED;
  } else {
    clampState_ = ClampState::REF_A;
  }
#else
  if (clampA_ && clampB_) {
    clampState_ = ClampState::FIXED;
  } else if (clampA_) {
    clampState_ = ClampState::REF_A;
  } else if (clampB_) {
    clampState_ = ClampState::REF_B;
  } else {
    clampState_ = ClampState::FREE;
  }
#endif

  if (now - lastBattMs_ >= 1000) {
    lastBattMs_ = now;
    const uint32_t mv = static_cast<uint32_t>(analogReadMilliVolts(PIN_BAT_SENSE));
    // 100k/100k 分压 → ×2；简单滑动平均
    const uint16_t v = static_cast<uint16_t>(mv * 2);
    battMv_ = battMv_ == 0 ? v : static_cast<uint16_t>((battMv_ * 3 + v) / 4);
  }

  updateButton(now);
}

bool Safety::motionAllowed() const {
#if UNIT_ROLE_END
  return clampState_ == ClampState::REF_A;  // 外端锁、内端自由
#else
  return clampState_ == ClampState::REF_A || clampState_ == ClampState::REF_B;
#endif
}

void Safety::updateButton(uint32_t now) {
  const bool down = readActiveLow(PIN_KEY);
  if (down && !buttonRaw_) {
    buttonRaw_ = true;
    buttonDownMs_ = now;
    longFired_ = false;
  } else if (down && buttonRaw_) {
    if (!longFired_ && now - buttonDownMs_ >= 3000) {
      longFired_ = true;
      longPress_ = true;
    }
  } else if (!down && buttonRaw_) {
    buttonRaw_ = false;
    if (!longFired_ && now - buttonDownMs_ < 1000) shortPress_ = true;
  }
}

bool Safety::takeShortPress() {
  const bool v = shortPress_;
  shortPress_ = false;
  return v;
}

bool Safety::takeLongPress() {
  const bool v = longPress_;
  longPress_ = false;
  return v;
}

void Safety::resetStall(int32_t counts) {
  stallWindowMs_ = millis();
  stallCounts_ = counts;
  stallHits_ = 0;
}

bool Safety::checkStall(int32_t counts, float duty, uint32_t now) {
  if (now - stallWindowMs_ < STALL_WINDOW_MS) return false;
  const int32_t delta = counts - stallCounts_;
  stallCounts_ = counts;
  stallWindowMs_ = now;

  if (fabsf(duty) < STALL_DUTY_MIN) {
    stallHits_ = 0;
    return false;
  }
  if (abs(delta) < STALL_COUNTS_MIN) {
    if (++stallHits_ >= STALL_CONFIRM) {
      stallHits_ = 0;
      return true;
    }
  } else {
    stallHits_ = 0;
  }
  return false;
}
