#include "as5600.h"

#include <Wire.h>

#include "config.h"

bool As5600::readRawAngle(uint16_t &raw) {
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(static_cast<uint8_t>(AS5600_RAW_ANGLE));
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(static_cast<uint8_t>(AS5600_ADDR), static_cast<uint8_t>(2)) != 2) {
    return false;
  }
  const uint8_t hi = Wire.read();
  const uint8_t lo = Wire.read();
  raw = static_cast<uint16_t>(((hi << 8) | lo) & 0x0FFF);
  return true;
}

bool As5600::begin() {
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(400000);
  uint16_t raw = 0;
  if (!readRawAngle(raw)) {
    ok_ = false;
    return false;
  }
  lastRaw_ = raw;
  hasLast_ = true;
  ok_ = true;
  lastOkMs_ = millis();
  return true;
}

bool As5600::update() {
  uint16_t raw = 0;
  if (!readRawAngle(raw)) {
    ok_ = false;
    return false;
  }
  ok_ = true;
  lastOkMs_ = millis();

  if (!hasLast_) {
    lastRaw_ = raw;
    hasLast_ = true;
    return true;
  }

  // int16 差值自动处理 0/4095 跨圈：范围 -2048..2047
  int16_t delta = static_cast<int16_t>(raw - lastRaw_);
  lastRaw_ = raw;
#if ENCODER_INVERT
  delta = static_cast<int16_t>(-delta);
#endif
  counts_ += delta;
  return true;
}

float As5600::lengthMm() const {
  return LENGTH_MIN_MM + static_cast<float>(counts_) / COUNTS_PER_MM;
}

void As5600::setCounts(int32_t c) { counts_ = c; }

void As5600::zero() {
  counts_ = 0;
  hasLast_ = true;  // 保留 lastRaw_，下一帧从当前位置继续累计
}
