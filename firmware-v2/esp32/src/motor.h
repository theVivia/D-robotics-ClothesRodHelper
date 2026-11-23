// DRV8833 单通道驱动：AIN1/AIN2 PWM + nSLEEP
#pragma once

#include <Arduino.h>

class Motor {
 public:
  void begin();
  void setDuty(float duty);  // -MAX_DUTY..+MAX_DUTY；正=伸出
  void stop();               // 滑行（coast）
  void brake(uint16_t ms);   // 动态刹车，阻塞 ≤ms
  void sleep();              // nSLEEP 低 = 高阻
  void wake();
  bool awake() const { return awake_; }

 private:
  bool awake_ = false;
};
