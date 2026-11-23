"""MQTT / REST 协议（v2）。不依赖 paho；只做校验与编解码。"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

PROTO_VERSION = 2
TOPIC_CMD = "hangflow/unit/{uid}/cmd"
TOPIC_STATE = "hangflow/unit/{uid}/state"
TOPIC_EVT = "hangflow/unit/{uid}/evt"
TOPIC_ESTOP = "hangflow/sys/estop"

EVENTS = {
    "E01": "Wi-Fi 断开",
    "E02": "MQTT 断开",
    "E03": "丝杆卡死",
    "E04": "超行程",
    "E05": "低电",
    "E06": "长度超时",
    "E07": "非法指令",
    "E09": "标定缺失",
    "E10": "夹持未锁/夹持失败",
    "E13": "夹持未锁禁止运动",
    "E14": "运动中夹持状态变化",
}

CLAMP = {"lock", "free"}


class ProtocolError(ValueError):
    pass


@dataclass
class Command:
    seq: int
    op: str
    target_mm: float
    speed_mm_s: float = 7.0
    clamp_left: str = "lock"
    clamp_right: str = "free"
    timeout_ms: int = 30000
    v: int = PROTO_VERSION

    def to_json(self) -> str:
        d = asdict(self)
        d["clamp"] = {"left": d.pop("clamp_left"), "right": d.pop("clamp_right")}
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "Command":
        try:
            d: Dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ProtocolError(f"bad json: {e}") from e
        if d.get("v") != PROTO_VERSION:
            raise ProtocolError(f"unsupported version: {d.get('v')}")
        if d.get("op") not in {"set_length", "stop", "home", "ping"}:
            raise ProtocolError(f"bad op: {d.get('op')}")
        if not isinstance(d.get("seq"), int) or d["seq"] < 0:
            raise ProtocolError("bad seq")
        if d["op"] == "set_length":
            if not isinstance(d.get("target_mm"), (int, float)):
                raise ProtocolError("bad target_mm")
            clamp = d.get("clamp") or {}
            left = clamp.get("left", "lock")
            right = clamp.get("right", "free")
            if left not in CLAMP or right not in CLAMP:
                raise ProtocolError("bad clamp")
            if left == "free" and right == "free":
                raise ProtocolError("E13: both clamps free, refuse motion")
            return cls(
                seq=d["seq"],
                op="set_length",
                target_mm=float(d["target_mm"]),
                speed_mm_s=float(d.get("speed_mm_s", 7.0)),
                clamp_left=left,
                clamp_right=right,
                timeout_ms=int(d.get("timeout_ms", 30000)),
            )
        return cls(seq=d["seq"], op=d["op"], target_mm=0.0)


@dataclass
class State:
    uid: str
    seq: int
    length_mm: float
    target_mm: float
    clamp_l: str
    clamp_r: str
    i_ma: int = 0
    batt_mv: int = 3900
    moving: bool = False
    fault: int = 0

    def to_json(self) -> str:
        d = asdict(self)
        d["v"] = PROTO_VERSION
        d["flags"] = {"moving": d.pop("moving")}
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))


def cmd_topic(uid: str) -> str:
    return TOPIC_CMD.format(uid=uid)


def state_topic(uid: str) -> str:
    return TOPIC_STATE.format(uid=uid)


def evt_topic(uid: str) -> str:
    return TOPIC_EVT.format(uid=uid)
