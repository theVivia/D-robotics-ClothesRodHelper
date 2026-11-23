// AS5600（I2C 0x36）单圈绝对角 + 固件多圈累计
// L_mm = LENGTH_MIN_MM + counts / COUNTS_PER_MM
#pragma once

#include <Arduino.h>

class As5600 {
 public:
  bool begin();
  bool update();                 // 200Hz 调用；返回本次 I2C 是否成功
  bool healthy() const { return ok_ && (millis() - lastOkMs_ < 100); }
  int32_t counts() const { return counts_; }
  float lengthMm() const;
  void setCounts(int32_t c);
  void zero();

 private:
  bool readRawAngle(uint16_t &raw);
  uint16_t lastRaw_ = 0;
  int32_t counts_ = 0;
  bool hasLast_ = false;
  bool ok_ = false;
  uint32_t lastOkMs_ = 0;
};
