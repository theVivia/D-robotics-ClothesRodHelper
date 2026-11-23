#include "net.h"

#include <ArduinoJson.h>

namespace {
Net *gNet = nullptr;
Command gPending;
bool gHasCmd = false;
uint32_t gLastSeq = 0;
const char kWill[] = "{\"v\":1,\"id\":\"" UNIT_ID "\",\"state\":\"offline\"}";
}  // namespace

void Net::begin() {
  gNet = this;
  WiFi.mode(WIFI_STA);
  mqtt_.setServer(MQTT_HOST, MQTT_PORT);
  mqtt_.setCallback(&Net::onMessage);
  mqtt_.setBufferSize(768);
}

void Net::ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  static uint32_t lastTry = 0;
  const uint32_t now = millis();
  if (now - lastTry < 3000) return;
  lastTry = now;
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

void Net::ensureMqtt(uint32_t now) {
  if (WiFi.status() != WL_CONNECTED) return;
  if (mqtt_.connected()) return;
  if (now - lastReconnectMs_ < 2000) return;
  lastReconnectMs_ = now;

  const String clientId = String("hangflow-unit-") + UNIT_ID;
  if (mqtt_.connect(clientId.c_str(), nullptr, nullptr, TOPIC_STATE, 0, true, kWill)) {
    mqtt_.subscribe(TOPIC_CMD, 1);
    mqtt_.subscribe(TOPIC_ESTOP, 1);
    mqtt_.subscribe(TOPIC_RESUME, 1);
    mqtt_.subscribe(TOPIC_HUB_STATUS, 1);
  }
}

void Net::loop(uint32_t now) {
  ensureWifi();
  ensureMqtt(now);
  if (mqtt_.connected()) mqtt_.loop();
}

bool Net::connected() { return mqtt_.connected(); }

bool Net::takeCommand(Command &out) {
  if (!gHasCmd) return false;
  out = gPending;
  gHasCmd = false;
  return true;
}

void Net::onMessage(char *topic, uint8_t *payload, unsigned int len) {
  if (gNet == nullptr) return;

  if (strcmp(topic, TOPIC_ESTOP) == 0) {
    gNet->estopBroadcast_ = true;
    return;
  }
  if (strcmp(topic, TOPIC_RESUME) == 0) {
    gNet->resumeBroadcast_ = true;
    return;
  }
  if (strcmp(topic, TOPIC_HUB_STATUS) == 0) {
    gNet->notifyHubAlive(millis());
    return;
  }
  if (strcmp(topic, TOPIC_CMD) != 0) return;

  JsonDocument doc;
  const DeserializationError err = deserializeJson(doc, payload, len);
  if (err) return;

  Command c;
  c.seq = doc["seq"] | 0;
  if (c.seq != 0 && c.seq <= static_cast<int>(gLastSeq)) return;  // 丢弃旧指令
  if (c.seq != 0) gLastSeq = static_cast<uint32_t>(c.seq);

  strlcpy(c.op, doc["op"] | "set_length", sizeof(c.op));
  c.setLengthMm = doc["set_length_mm"] | 0.0f;
  c.speedMmS = doc["speed_mm_s"] | DEFAULT_SPEED_MM_S;
  strlcpy(c.clamp, doc["clamp"] | "", sizeof(c.clamp));
  strlcpy(c.action, doc["action"] | "", sizeof(c.action));

  gPending = c;
  gHasCmd = true;
}

void Net::publishState(float lengthMm, ClampState clampState, bool clampA, bool clampB,
                       bool limitMin, bool limitMax, bool estop, uint8_t fault,
                       uint16_t battMv, const char *stateStr, uint32_t uptimeS) {
  if (!mqtt_.connected()) return;

  const char *cs = "free";
  switch (clampState) {
    case ClampState::REF_A: cs = "referenced_a"; break;
    case ClampState::REF_B: cs = "referenced_b"; break;
    case ClampState::FIXED: cs = "fixed"; break;
    default: cs = "free"; break;
  }

  JsonDocument doc;
  doc["v"] = 1;
  doc["id"] = UNIT_ID;
  doc["role"] = UNIT_ROLE_STR;
  doc["length_mm"] = lengthMm;
  doc["length_min_mm"] = LENGTH_MIN_MM;
  doc["length_max_mm"] = LENGTH_MAX_MM;
  doc["state"] = stateStr;
  doc["clamp_a"] = clampA;
  doc["clamp_b"] = clampB;
  doc["clamp_state"] = cs;
  doc["batt_mv"] = battMv;
  doc["current_ma"] = nullptr;  // P0 无电流传感器
  doc["limit_min"] = limitMin;
  doc["limit_max"] = limitMax;
  doc["estop"] = estop;
  doc["fault"] = fault;
  doc["uptime_s"] = uptimeS;
  doc["ts"] = static_cast<uint32_t>(millis());

  char buf[640];
  const size_t n = serializeJson(doc, buf, sizeof(buf));
  if (n > 0) mqtt_.publish(TOPIC_STATE, reinterpret_cast<const uint8_t *>(buf), n, true);
}

void Net::publishEvt(const char *code, const char *msg, float lengthMm) {
  if (!mqtt_.connected()) return;
  JsonDocument doc;
  doc["v"] = 1;
  doc["id"] = UNIT_ID;
  doc["code"] = code;
  doc["msg"] = msg;
  doc["length_mm"] = lengthMm;
  doc["ts"] = static_cast<uint32_t>(millis());
  char buf[384];
  const size_t n = serializeJson(doc, buf, sizeof(buf));
  if (n > 0) mqtt_.publish(TOPIC_EVT, reinterpret_cast<const uint8_t *>(buf), n, false);
}
