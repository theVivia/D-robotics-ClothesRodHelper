// MQTT：cmd 解析（set_length / clamp / stop / resume / home）+ state 10Hz + evt
#pragma once

#include <Arduino.h>
#include <PubSubClient.h>
#include <WiFi.h>

#include "config.h"
#include "safety.h"

struct Command {
  char op[16] = {0};
  float setLengthMm = 0;
  float speedMmS = DEFAULT_SPEED_MM_S;
  int seq = 0;
  char clamp[4] = {0};
  char action[12] = {0};
};

class Net {
 public:
  void begin();
  void loop(uint32_t now);

  bool connected();
  bool takeCommand(Command &out);
  void publishState(float lengthMm, ClampState clampState, bool clampA, bool clampB,
                    bool limitMin, bool limitMax, bool estop, uint8_t fault,
                    uint16_t battMv, const char *stateStr, uint32_t uptimeS);
  void publishEvt(const char *code, const char *msg, float lengthMm);

  bool estopBroadcast() const { return estopBroadcast_; }
  void clearEstopBroadcast() { estopBroadcast_ = false; }
  bool resumeBroadcast() const { return resumeBroadcast_; }
  void clearResumeBroadcast() { resumeBroadcast_ = false; }
  void notifyHubAlive(uint32_t now) { lastHubMs_ = now; }
  uint32_t lastHubMs() const { return lastHubMs_; }

 private:
  void ensureWifi();
  void ensureMqtt(uint32_t now);
  static void onMessage(char *topic, uint8_t *payload, unsigned int len);

  WiFiClient wifiClient_;
  PubSubClient mqtt_{wifiClient_};
  uint32_t lastReconnectMs_ = 0;
  uint32_t lastHubMs_ = 0;
  bool estopBroadcast_ = false;
  bool resumeBroadcast_ = false;
};
