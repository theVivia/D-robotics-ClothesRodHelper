"""无硬件 mock 中枢：演示 v2 的端点锚定规划与协议输出。

用法：
    python -m software_v2.mock_hub --demo
    python -m software_v2.mock_hub --equalize 12
"""
from __future__ import annotations

import argparse
import json
from typing import Dict

from .model import Chain, ChainError, demo_chain
from .protocol import Command, State, cmd_topic, state_topic


def snapshot(chain: Chain) -> Dict[str, float]:
    return {u.uid: round(u.length, 1) for u in chain.units}


def run_demo() -> None:
    chain = demo_chain()
    print("初始:", chain, "外端:", chain.outer_positions())
    nxt = chain.equalize(120)
    nxt.check()
    print("等距 12cm:", nxt)
    chain = nxt
    nxt = chain.collect(100)
    nxt.check()
    print("收衣（回 10cm）:", nxt)
    try:
        demo_chain().equalize(80)
    except ChainError as e:
        print("等距 8cm 拒绝:", e)


def run_equalize(target_cm: float) -> None:
    chain = demo_chain()
    try:
        nxt = chain.equalize(target_cm * 10)
        nxt.check()
    except ChainError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return
    cmds = []
    for i, u in enumerate(nxt.units):
        c = Command(seq=i + 1, op="set_length", target_mm=round(u.length, 1),
                    clamp_left="lock" if u.clamp_l else "free",
                    clamp_right="lock" if u.clamp_r else "free")
        cmds.append({"topic": cmd_topic(u.uid), "payload": json.loads(c.to_json())})
    print(json.dumps({"ok": True, "state": snapshot(nxt),
                      "commands": cmds}, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--equalize", type=float, default=None)
    args = ap.parse_args()
    if args.equalize is not None:
        run_equalize(args.equalize)
    else:
        run_demo()


if __name__ == "__main__":
    main()

