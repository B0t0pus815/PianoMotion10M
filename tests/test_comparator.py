"""Tests for the comparator — locks in wrist_status v1 behavior and
HandHistory data flow. Thesis ch6 §6.2 + ch7 §7.3.3 claim wrist v1
is shipped; these tests assert the contract holds.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webui.realtime.comparator import (
    HandHistory, wrist_status, compare_onset, OnsetResult,
    WRIST_ARCHED_THRESHOLD, WRIST_COLLAPSED_THRESHOLD,
)
from webui.realtime.hand_tracker import HandPose
from webui.realtime.reference import ExpectedOnset


# ─── Test fixtures ─────────────────────────────────────────────────────

def make_pose(wrist_y: float, finger_y: float = 500.0,
              handedness: str = 'right') -> HandPose:
    """Build a HandPose with 21 landmarks, wrist + fingertips set."""
    landmarks = np.zeros((21, 3), dtype=np.float32)
    landmarks[0] = [400, wrist_y, 0]  # wrist landmark
    # Fingertip indices from hand_tracker
    from webui.realtime.hand_tracker import TIP_INDICES, TIP_ORDER
    for i, name in enumerate(TIP_ORDER):
        landmarks[TIP_INDICES[name]] = [300 + i * 30, finger_y, 0]
    return HandPose(landmarks=landmarks, handedness=handedness, score=0.9)


def make_expected(time: float = 1.0, pitch: int = 60,
                  hand: str = 'right', finger: str = 'thumb') -> ExpectedOnset:
    from webui.realtime.reference import FINGER_ORDER
    finger_idx = FINGER_ORDER.index(finger)
    return ExpectedOnset(
        time=time, pitch=pitch, velocity=80,
        expected_hand=hand, expected_finger=finger, expected_finger_idx=finger_idx,
        duration=0.5,
    )


# ─── HandHistory wrist tracking ────────────────────────────────────────

def test_handhistory_wrist_buf_separately_tracked():
    """wrist_buf is its own deque, not derived from fingertip buf."""
    h = HandHistory(capacity=10)
    pose = make_pose(wrist_y=500.0)
    h.push(1.0, {'right': pose})
    assert len(h.wrist_buf['right']) == 1
    assert len(h.buf['right']) == 1
    # Wrist Y stored as float, not array
    t, y = h.wrist_buf['right'][0]
    assert t == 1.0
    assert y == 500.0


def test_handhistory_recent_wrist_y_filters_by_window():
    h = HandHistory(capacity=20)
    for i in range(10):
        h.push(float(i), {'right': make_pose(wrist_y=500.0 + i)})
    # Window [5, 7] should pick up i=5,6,7 → 3 samples
    ys = h.recent_wrist_y('right', target_t=7.0, window=2.0)
    assert len(ys) == 3
    assert ys == [505.0, 506.0, 507.0]


def test_handhistory_recent_wrist_y_empty_for_unseen_hand():
    h = HandHistory()
    h.push(1.0, {'right': make_pose(500.0)})
    assert h.recent_wrist_y('left', 1.0, 2.0) == []


# ─── wrist_status() classification ─────────────────────────────────────

def test_wrist_status_returns_unknown_with_no_history():
    h = HandHistory()
    status, dev = wrist_status(h, 'right', onset_time=1.0)
    assert status == 'unknown'
    assert dev == 0.0


def test_wrist_status_returns_unknown_with_too_few_samples():
    h = HandHistory()
    # Only 3 samples — wrist_status needs ≥ 4 for stable median
    for i in range(3):
        h.push(float(i), {'right': make_pose(wrist_y=500.0)})
    status, _ = wrist_status(h, 'right', onset_time=2.5)
    assert status == 'unknown'


def test_wrist_status_good_when_current_near_baseline():
    """Wrist stays at ~500 for whole window → status 'good' regardless of
    arbitrary baseline."""
    h = HandHistory()
    for i in range(20):
        h.push(float(i) * 0.1, {'right': make_pose(wrist_y=500.0)})
    status, dev = wrist_status(h, 'right', onset_time=1.9)
    assert status == 'good'
    assert abs(dev) < 1.0


def test_wrist_status_arched_when_current_above_baseline():
    """Wrist sits at 500 then jumps UP (lower y in image) by > threshold
    → 'arched'."""
    h = HandHistory()
    # Baseline 4 seconds of wrist y=500
    for i in range(40):
        h.push(float(i) * 0.1, {'right': make_pose(wrist_y=500.0)})
    # Most recent frame (within PRESS_WINDOW = 0.12s of onset) has wrist
    # well above baseline (low y in image)
    h.push(3.95, {'right': make_pose(wrist_y=500.0 - WRIST_ARCHED_THRESHOLD - 10)})
    status, dev = wrist_status(h, 'right', onset_time=4.0)
    assert status == 'arched'
    assert dev < 0  # negative = above median in image space


def test_wrist_status_collapsed_when_current_below_baseline():
    h = HandHistory()
    for i in range(40):
        h.push(float(i) * 0.1, {'right': make_pose(wrist_y=500.0)})
    h.push(3.95, {'right': make_pose(wrist_y=500.0 + WRIST_COLLAPSED_THRESHOLD + 10)})
    status, dev = wrist_status(h, 'right', onset_time=4.0)
    assert status == 'collapsed'
    assert dev > 0


def test_wrist_status_per_hand_independent():
    """Right hand 'arched' shouldn't leak into left hand classification."""
    h = HandHistory()
    for i in range(40):
        h.push(float(i) * 0.1, {
            'right': make_pose(wrist_y=500.0),
            'left':  make_pose(wrist_y=600.0),
        })
    # Right hand spikes arched
    h.push(3.95, {'right': make_pose(wrist_y=400.0),  # arched
                  'left':  make_pose(wrist_y=600.0)})  # stable
    r_status, _ = wrist_status(h, 'right', onset_time=4.0)
    l_status, _ = wrist_status(h, 'left',  onset_time=4.0)
    assert r_status == 'arched'
    assert l_status == 'good'


# ─── compare_onset emits wrist fields ──────────────────────────────────

def test_compare_onset_attaches_wrist_status_even_when_no_finger_history():
    """Wrist evaluation runs independently of finger detection."""
    h = HandHistory()
    # Populate wrist history but no fingertip presses → finger detection
    # falls back to 'lowest finger'
    for i in range(40):
        h.push(float(i) * 0.1, {'right': make_pose(wrist_y=500.0)})
    result = compare_onset(h, make_expected(time=4.0))
    # Wrist should report 'good' even though there's no actual press motion
    assert result.wrist_status == 'good'


def test_compare_onset_wrist_status_unknown_for_unseen_hand():
    h = HandHistory()
    for i in range(40):
        h.push(float(i) * 0.1, {'right': make_pose(wrist_y=500.0)})
    # Expected is left hand → no history for left → wrist_status 'unknown'
    result = compare_onset(h, make_expected(time=4.0, hand='left'))
    assert result.wrist_status == 'unknown'


def test_compare_onset_wrist_status_carries_through_when_finger_detected():
    h = HandHistory()
    # Build a session where wrist arched at moment of press
    for i in range(40):
        h.push(float(i) * 0.1, {'right': make_pose(wrist_y=500.0)})
    h.push(3.95, {'right': make_pose(wrist_y=400.0)})  # arched
    result = compare_onset(h, make_expected(time=4.0))
    assert result.wrist_status == 'arched'
    assert result.wrist_deviation_px < 0


# ─── Backwards compat — old code paths shouldn't break ────────────────

def test_onsetresult_default_wrist_fields():
    """OnsetResult must be constructible without wrist fields for any
    code path that wasn't updated."""
    r = OnsetResult(
        time=1.0, pitch=60,
        expected_hand='right', expected_finger='thumb',
        detected_finger='thumb', correct=True, confidence=0.9,
    )
    assert r.wrist_status == 'unknown'
    assert r.wrist_deviation_px == 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
