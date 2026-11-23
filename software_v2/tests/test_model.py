from __future__ import annotations

import pytest

from software_v2.model import ChainError, demo_chain


def lengths(chain):
    return [round(u.length, 1) for u in chain.units]


def test_demo_total_and_anchors():
    c = demo_chain()
    assert lengths(c) == [60, 100, 100, 100, 60]
    assert c.total == 460
    assert c.outer_positions() == (0.0, 460.0)


def test_equalize_wider_uses_end_stroke():
    c = demo_chain().equalize(120)
    c.check()
    assert lengths(c) == [30, 120, 120, 120, 30]
    assert c.total == 460


def test_equalize_below_powered_min_is_rejected():
    with pytest.raises(ChainError):
        demo_chain().equalize(80)


def test_collect_returns_to_min_powered():
    c = demo_chain().equalize(120).collect(100)
    c.check()
    assert lengths(c) == [60, 100, 100, 100, 60]
    assert c.total == 460


def test_equalize_too_wide_is_rejected():
    with pytest.raises(ChainError):
        demo_chain().equalize(150)


def test_outer_anchors_do_not_move():
    for target in (100, 110, 120):
        c = demo_chain().equalize(target)
        assert c.outer_positions() == (0.0, 460.0)
        assert c.total == 460


def test_set_lengths_cannot_change_total():
    c = demo_chain()
    with pytest.raises(ChainError):
        c.set_lengths([60, 120, 100, 100, 60])
