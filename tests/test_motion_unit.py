"""Pure-logic unit tests for the motion/deadman decision functions.

These touch no server and no dimos transport — they pin the exact arithmetic the
HTTP layer relies on (clamp envelope, direction mapping, deadman window).
"""

from __future__ import annotations

import pytest

from yugo.controllers.MotionController import (
    clamp,
    deadman_adjust,
    direction_to_velocity,
)


# --- clamp -------------------------------------------------------------------

def test_clamp_within_range_unchanged():
    assert clamp(0.3, -0.2, 0.5, 0.6, 1.2) == (0.3, -0.2, 0.5)


def test_clamp_limits_linear_and_angular():
    assert clamp(5.0, -9.0, 99.0, 0.6, 1.2) == (0.6, -0.6, 1.2)
    assert clamp(-5.0, 9.0, -99.0, 0.6, 1.2) == (-0.6, 0.6, -1.2)


# --- direction mapping -------------------------------------------------------

def test_directions_map_to_expected_axes():
    assert direction_to_velocity("up", 0.4, 0.8) == (0.4, 0.0, 0.0)
    assert direction_to_velocity("down", 0.4, 0.8) == (-0.4, 0.0, 0.0)
    assert direction_to_velocity("left", 0.4, 0.8) == (0.0, 0.0, 0.8)
    assert direction_to_velocity("right", 0.4, 0.8) == (0.0, 0.0, -0.8)


def test_unknown_direction_raises():
    with pytest.raises(ValueError):
        direction_to_velocity("diagonal", 0.4, 0.8)


# --- deadman decision --------------------------------------------------------

def test_deadman_holds_fresh_command():
    assert deadman_adjust((0.4, 0.0, 0.0), cmd_ts=10.0, now=10.2, timeout=0.5) == (
        0.4,
        0.0,
        0.0,
    )


def test_deadman_zeroes_stale_command():
    assert deadman_adjust((0.4, 0.0, 0.0), cmd_ts=10.0, now=10.7, timeout=0.5) == (
        0.0,
        0.0,
        0.0,
    )


def test_deadman_zeroes_when_never_commanded():
    assert deadman_adjust((0.4, 0.0, 0.0), cmd_ts=None, now=10.0, timeout=0.5) == (
        0.0,
        0.0,
        0.0,
    )


def test_deadman_boundary_is_inclusive_of_window():
    # exactly at the window edge is still "fresh" (not stale)
    assert deadman_adjust((0.4, 0.0, 0.0), cmd_ts=10.0, now=10.5, timeout=0.5) == (
        0.4,
        0.0,
        0.0,
    )
