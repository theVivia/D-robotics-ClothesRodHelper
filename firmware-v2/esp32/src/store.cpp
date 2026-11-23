#include "store.h"\n\n#include <stddef.h>

namespace {
constexpr uint32_t kMagic = 0x48465231UL;  // "HFR1"
struct Record {
  uint32_t magic;
  int32_t counts;
  uint16_t crc;
};

uint16_t crc16(const uint8_t *data, size_t len) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < len; i++) {
    crc ^= static_cast<uint16_t>(data[i]) << 8;
    for (uint8_t b = 0; b < 8; b++) {
      crc = (crc & 0x8000) ? static_cast<uint16_t>((crc << 1) ^ 0x1021)
                           : static_cast<uint16_t>(crc << 1);
    }
  }
  return crc;
}
}  // namespace

bool EncoderStore::begin() {
  opened_ = prefs_.begin("hangflow", false);
  return opened_;
}

bool EncoderStore::load(int32_t &counts) {
  if (!opened_) return false;
  Record rec{};
  const size_t n = prefs_.getBytes("enc", &rec, sizeof(rec));
  if (n != sizeof(rec) || rec.magic != kMagic) return false;
  if (rec.crc != crc16(reinterpret_cast<const uint8_t *>(&rec), offsetof(Record, crc))) {
    return false;
  }
  counts = rec.counts;
  return true;
}

bool EncoderStore::save(int32_t counts) {
  if (!opened_) return false;
  Record rec{};
  rec.magic = kMagic;
  rec.counts = counts;
  rec.crc = crc16(reinterpret_cast<const uint8_t *>(&rec), offsetof(Record, crc));
  const bool ok = prefs_.putBytes("enc", &rec, sizeof(rec)) == sizeof(rec);
  if (ok) lastSaveMs_ = millis();
  return ok;
}

bool EncoderStore::clear() {
  if (!opened_) return false;
  return prefs_.remove("enc");
}

