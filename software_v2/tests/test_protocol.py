from __future__ import annotations

import json

import pytest

from software_v2.protocol import Command, ProtocolError, cmd_topic, state_topic


def test_command_roundtrip():
    raw = ('{"v":2,"seq":7,"op":"set_length","target_mm":120,'
           '"speed_mm_s":7,"clamp":{"left":"lock","right":"free"}}')
    c = Command.from_json(raw)
    assert c.target_mm == 120
    assert c.clamp_left == "lock"
    d = json.loads(c.to_json())
    assert d["clamp"] == {"left": "lock", "right": "free"}


def test_both_free_refused():
    raw = ('{"v":2,"seq":1,"op":"set_length","target_mm":100,'
           '"clamp":{"left":"free","right":"free"}}')
    with pytest.raises(ProtocolError):
        Command.from_json(raw)


def test_bad_version():
    with pytest.raises(ProtocolError):
        Command.from_json('{"v":1,"seq":1,"op":"stop"}')


def test_topics():
    assert cmd_topic("02") == "hangflow/unit/02/cmd"
    assert state_topic("05") == "hangflow/unit/05/state"
