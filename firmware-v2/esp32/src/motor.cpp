#include "motor.h"\n\n#include <math.h>

#include "config.h"

namespace {
constexpr uint8_t kChA = 0;
constexpr uint8_t kChB = 1;
constexpr uint16_t kPwmFreq = 20000;
constexpr uint8_t kPwmBits = 8;
constexpr uint16_t kPwmMax = 255;

int dutyToPwm(float duty) {
  float d = duty;
#if MOTOR_INVERT
  d = -d;
#endif
  if (d < 0) d = -d;
  if (d > MAX_DUTY) d = MAX_DUTY;
  return static_cast<int>(d * kPwmMax + 0.5f);
}
}  // namespace

void Motor::begin() {
  pinMode(PIN_MOTOR_NSLEEP, OUTPUT);
  digitalWrite(PIN_MOTOR_NSLEEP, LOW);  // 先休眠 = 高阻

  ledcSetup(kChA, kPwmFreq, kPwmBits);
  ledcSetup(kChB, kPwmFreq, kPwmBits);
  ledcAttachPin(PIN_MOTOR_AIN1, kChA);
  ledcAttachPin(PIN_MOTOR_AIN2, kChB);
  ledcWrite(kChA, 0);
  ledcWrite(kChB, 0);
  awake_ = false;
}

void Motor::wake() {
  if (awake_) return;
  digitalWrite(PIN_MOTOR_NSLEEP, HIGH);
  delayMicroseconds(200);  // DRV8833 唤醒时间（数据手册 t_wake 约 1ms 内）
  awake_ = true;
}

void Motor::sleep() {
  ledcWrite(kChA, 0);
  ledcWrite(kChB, 0);
  digitalWrite(PIN_MOTOR_NSLEEP, LOW);
  awake_ = false;
}

void Motor::setDuty(float duty) {
  float d = duty;
#if MOTOR_INVERT
  d = -d;
#endif
  if (d > MAX_DUTY) d = MAX_DUTY;
  if (d < -MAX_DUTY) d = -MAX_DUTY;

  if (fabsf(d) < 0.01f) {
    stop();
    return;
  }
  wake();
  const int pwm = static_cast<int>(fabsf(d) * kPwmMax + 0.5f);
  if (d > 0) {
    ledcWrite(kChB, 0);
    ledcWrite(kChA, pwm);
  } else {
    ledcWrite(kChA, 0);
    ledcWrite(kChB, pwm);
  }
}

void Motor::stop() {
  ledcWrite(kChA, 0);
  ledcWrite(kChB, 0);  // IN1=IN2=0 → coast
}

void Motor::brake(uint16_t ms) {
  if (!awake_) return;
  ledcWrite(kChA, kPwmMax);
  ledcWrite(kChB, kPwmMax);  // IN1=IN2=1 → 动态刹车
  delay(ms);
  stop();
}

