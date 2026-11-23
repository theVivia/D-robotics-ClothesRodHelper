// NVS 多圈计数存储：掉电恢复位置（带 magic + CRC16）
#pragma once

#include <Arduino.h>
#include <Preferences.h>

class EncoderStore {
 public:
  bool begin();
  bool load(int32_t &counts);
  bool save(int32_t counts);
  bool clear();

 private:
  Preferences prefs_;
  bool opened_ = false;
  uint32_t lastSaveMs_ = 0;
};
