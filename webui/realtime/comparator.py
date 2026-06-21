"""Compare user hand pose vs expected fingering at MIDI onsets.

Heuristic: the "pressing finger" is the fingertip with the largest mean
downward velocity in the PRESS_WINDOW seconds before the onset. If no
fingertip moved more than MIN_PRESS_VELOCITY pixels/sec, fall back to the
lowest fingertip (highest y in image coordinates) — covers legato and held
chord cases where the press already happened.

Wrist feedback (v1, added 2026-05-24): in addition to per-onset finger
correctness, the comparator emits a `wrist_status` field — 'arched'
(wrist held too high above keys) / 'collapsed' (wrist sagging below
keys) / 'good'. The reference is the student's OWN rolling-median wrist
y over WRIST_REFERENCE_WINDOW seconds, so the feedback is calibrated
per-student per-session rather than absolute pixel thresholds (different
camera angles / hand sizes need different baselines).
"""
from __future__ import annotations

import collections
import json
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from webui.realtime.hand_tracker import HandPose, TIP_ORDER
from webui.realtime.reference import ExpectedOnset


PRESS_WINDOW = 0.12
MIN_PRESS_VELOCITY = 80.0

# Wrist-feedback v1 — rolling-median calibrated thresholds.
# Deviation from rolling-median wrist y, in PIXELS at frame native resolution.
# Tuned for 1920×1080 biomech v4 renders; scales OK to 1280×720 webcam.
WRIST_REFERENCE_WINDOW = 4.0     # seconds of recent history → rolling median
WRIST_ARCHED_THRESHOLD = 25.0    # current_y < median - this → 'arched' (上抬)
WRIST_COLLAPSED_THRESHOLD = 25.0 # current_y > median + this → 'collapsed' (下沉)


@dataclass(frozen=True)
class Thresholds:
    """Injectable copies of the press/wrist thresholds.

    Every field defaults to the module constant above, so `Thresholds()` (and
    therefore any call that doesn't pass `thr=`) reproduces today's behavior
    exactly — the change is additive. Use `Thresholds.from_calibration(...)` to
    apply calibrate.py's per-recording recommendations to grading WITHOUT
    editing source (the whole point: the pixel thresholds were baked for 1080p
    biomech renders and are wrong on a real webcam at a different scale).
    """
    press_window: float = PRESS_WINDOW
    min_press_velocity: float = MIN_PRESS_VELOCITY
    wrist_reference_window: float = WRIST_REFERENCE_WINDOW
    wrist_arched: float = WRIST_ARCHED_THRESHOLD
    wrist_collapsed: float = WRIST_COLLAPSED_THRESHOLD
    # Rhythm-hint v1 (2026-06-21): on-time half-window applied to the
    # tempo-detrended onset offset (see rhythm.RhythmTracker).
    rhythm_tolerance_s: float = 0.06

    @classmethod
    def from_calibration(cls, data: dict) -> 'Thresholds':
        """Build from a calibrate.py CalibrationReport dict, applying the
        `recommended` values that are present. A missing/None recommendation
        keeps that field's default (e.g. a recording with no tracked hands
        yields no recommendation → defaults stay).

        Maps: recommended.min_press_velocity → min_press_velocity;
              recommended.wrist_threshold_px → wrist_arched & wrist_collapsed.
        """
        rec = (data or {}).get('recommended', {}) or {}
        kw: dict = {}
        mpv = rec.get('min_press_velocity')
        if mpv is not None:
            kw['min_press_velocity'] = float(mpv)
        wt = rec.get('wrist_threshold_px')
        if wt is not None:
            kw['wrist_arched'] = float(wt)
            kw['wrist_collapsed'] = float(wt)
        return cls(**kw)

    @classmethod
    def from_json(cls, path: str) -> 'Thresholds':
        with open(path) as f:
            return cls.from_calibration(json.load(f))


DEFAULT_THRESHOLDS = Thresholds()


@dataclass
class OnsetResult:
    time: float
    pitch: int
    expected_hand: str
    expected_finger: str
    detected_finger: Optional[str]
    correct: bool
    confidence: float
    # Wrist feedback v1 (2026-05-24). 'good' / 'arched' / 'collapsed' /
    # 'unknown' (when no recent history to compute baseline).
    wrist_status: str = 'unknown'
    wrist_deviation_px: float = 0.0   # signed pixels from rolling median; +ve = below
    # Rhythm-hint v1 (2026-06-21). Set by the runner (which owns both the played
    # and reference times); see rhythm.RhythmTracker. +ve offset = drag/late.
    timing_offset_s: float = 0.0      # raw: played - reference
    timing_detrended_s: float = 0.0   # raw minus running tempo baseline
    rhythm_status: str = 'unknown'    # 'rush' / 'drag' / 'on_time' / 'unknown'


class HandHistory:
    def __init__(self, capacity: int = 240):
        self.buf: dict[str, collections.deque] = {
            'left': collections.deque(maxlen=capacity),
            'right': collections.deque(maxlen=capacity),
        }
        # Separate per-hand wrist Y buffer (capacity wider — for rolling median)
        self.wrist_buf: dict[str, collections.deque] = {
            'left': collections.deque(maxlen=capacity),
            'right': collections.deque(maxlen=capacity),
        }

    def push(self, t: float, hands: dict[str, HandPose]):
        for label in ('left', 'right'):
            if label in hands:
                pose = hands[label]
                self.buf[label].append((t, pose.fingertips[:, :2].copy()))
                # Wrist Y in image pixel space (y axis points down)
                self.wrist_buf[label].append((t, float(pose.wrist[1])))

    def recent(self, label: str, target_t: float, window: float):
        return [(t, x) for (t, x) in self.buf[label]
                if target_t - window <= t <= target_t]

    def recent_wrist_y(self, label: str, target_t: float, window: float):
        """Return list of wrist y values in [target_t - window, target_t]."""
        return [y for (t, y) in self.wrist_buf[label]
                if target_t - window <= t <= target_t]


def wrist_status(history: HandHistory, hand: str, onset_time: float,
                 thr: Thresholds = DEFAULT_THRESHOLDS) -> tuple[str, float]:
    """Classify wrist height at onset against the rolling-median baseline.

    Returns (status, deviation_px) where status ∈
    {'good', 'arched', 'collapsed', 'unknown'} and deviation_px is the
    signed pixel offset from the rolling median (+ve = below median, i.e.
    physically lower; -ve = above median, i.e. physically higher / arched).
    """
    ys = history.recent_wrist_y(hand, onset_time, thr.wrist_reference_window)
    if len(ys) < 4:
        return 'unknown', 0.0
    # Current wrist y is the LAST sample within press window
    current_ys = history.recent_wrist_y(hand, onset_time, thr.press_window)
    if not current_ys:
        return 'unknown', 0.0
    current = current_ys[-1]
    baseline = float(np.median(ys))
    deviation = current - baseline   # positive = below median
    if deviation < -thr.wrist_arched:
        return 'arched', deviation
    if deviation > thr.wrist_collapsed:
        return 'collapsed', deviation
    return 'good', deviation


def detect_press_finger(history, min_press_velocity: float = MIN_PRESS_VELOCITY):
    if len(history) < 2:
        return None, 0.0
    velocities = np.zeros(5, dtype=np.float32)
    for i in range(1, len(history)):
        t0, p0 = history[i - 1]
        t1, p1 = history[i]
        dt = max(t1 - t0, 1e-3)
        velocities += (p1[:, 1] - p0[:, 1]) / dt
    velocities /= max(len(history) - 1, 1)

    if np.max(velocities) < min_press_velocity:
        _, last_tips = history[-1]
        finger_idx = int(np.argmax(last_tips[:, 1]))
        return finger_idx, 0.3

    finger_idx = int(np.argmax(velocities))
    sorted_v = np.sort(velocities)[::-1]
    if sorted_v[1] > 0:
        margin = sorted_v[0] / sorted_v[1]
        confidence = float(min(1.0, margin / 2.0))
    else:
        confidence = 1.0
    return finger_idx, confidence


def compare_onset(history: HandHistory, expected: ExpectedOnset,
                  alt_finger_idxs: Optional[set] = None,
                  thr: Thresholds = DEFAULT_THRESHOLDS) -> OnsetResult:
    """Compare user's pressing finger vs the expected finger.

    alt_finger_idxs: if provided, treats ANY index in the set as correct.
    Used for chord clusters where multiple fingers press simultaneously and
    pitch→finger mapping is ambiguous from MIDI alone — accepting any
    chord-member finger removes a false-positive class.

    thr: press/wrist thresholds (defaults to the module constants; pass a
    calibrated Thresholds to grade a real recording at its own scale).
    """
    target_set = alt_finger_idxs or {expected.expected_finger_idx}

    # Wrist status is computed independently of finger correctness, so we
    # always evaluate it (even if finger detection fails).
    w_status, w_dev = wrist_status(history, expected.expected_hand, expected.time, thr)

    snaps = history.recent(expected.expected_hand, expected.time, thr.press_window)
    if not snaps:
        return OnsetResult(
            time=expected.time, pitch=expected.pitch,
            expected_hand=expected.expected_hand,
            expected_finger=expected.expected_finger,
            detected_finger=None, correct=False, confidence=0.0,
            wrist_status=w_status, wrist_deviation_px=w_dev)
    finger_idx, conf = detect_press_finger(snaps, thr.min_press_velocity)
    if finger_idx is None:
        return OnsetResult(
            time=expected.time, pitch=expected.pitch,
            expected_hand=expected.expected_hand,
            expected_finger=expected.expected_finger,
            detected_finger=None, correct=False, confidence=0.0,
            wrist_status=w_status, wrist_deviation_px=w_dev)
    return OnsetResult(
        time=expected.time, pitch=expected.pitch,
        expected_hand=expected.expected_hand,
        expected_finger=expected.expected_finger,
        detected_finger=TIP_ORDER[finger_idx],
        correct=(finger_idx in target_set),
        confidence=conf,
        wrist_status=w_status, wrist_deviation_px=w_dev,
    )


def precompute_chord_finger_sets(expected: list,
                                 cluster_window: float = 0.05) -> dict:
    """For each ExpectedOnset, compute the set of allowable finger indices
    given chord membership (notes within `cluster_window` of the same hand).

    Returns dict keyed by index into `expected` → set[int] of finger indices.
    """
    out = {}
    n = len(expected)
    i = 0
    while i < n:
        j = i
        anchor = expected[i].time
        while j < n and expected[j].time - anchor <= cluster_window:
            j += 1
        members = list(range(i, j))
        for k in members:
            same_hand = {expected[m].expected_finger_idx
                         for m in members
                         if expected[m].expected_hand == expected[k].expected_hand}
            out[k] = same_hand or {expected[k].expected_finger_idx}
        i = j
    return out
