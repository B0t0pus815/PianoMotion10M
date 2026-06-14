"""Tests for calibrate.py — the threshold-measurement instrument.

Cover the pure statistics + recommendation helpers (no video / MediaPipe), and
the CalibrationReport JSON contract. The video pass (run_calibration) needs
MediaPipe + a recording and is exercised by a manual run, not here.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from webui.realtime.calibrate import (
    percentile, pct_summary, fraction_below, fraction_above,
    recommend_min_press_velocity, recommend_wrist_threshold, resolution_scale,
    CalibrationReport, format_report, _onset_max_velocity,
)


# ─── percentile / summaries ────────────────────────────────────────────

def test_percentile_basic():
    vals = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert percentile(vals, 0) == 0.0
    assert percentile(vals, 100) == 100.0
    assert percentile(vals, 50) == 50.0


def test_percentile_empty_is_none():
    assert percentile([], 50) is None
    assert percentile([None, None], 50) is None


def test_percentile_ignores_none():
    assert percentile([None, 10, None, 20], 50) == 15.0


def test_pct_summary_shape_and_count():
    s = pct_summary([1, 2, 3, 4], ps=(10, 50, 90))
    assert set(s) == {'p10', 'p50', 'p90', 'n'}
    assert s['n'] == 4
    assert s['p50'] == 2.5


def test_pct_summary_empty():
    s = pct_summary([])
    assert s['n'] == 0
    assert s['p50'] is None


# ─── fraction_below / fraction_above ───────────────────────────────────

def test_fraction_below():
    assert fraction_below([10, 20, 30, 40], 25) == 0.5
    assert fraction_below([10, 20], 5) == 0.0
    assert fraction_below([], 5) == 0.0          # empty → 0, no div-by-zero


def test_fraction_above():
    assert fraction_above([10, 20, 30, 40], 25) == 0.5
    assert fraction_above([10, 20], 50) == 0.0
    assert fraction_above([], 5) == 0.0


def test_fraction_strict_at_boundary():
    # strictly below / above — the boundary value counts for neither
    assert fraction_below([25, 25, 25], 25) == 0.0
    assert fraction_above([25, 25, 25], 25) == 0.0


# ─── recommendations ───────────────────────────────────────────────────

def test_recommend_min_press_velocity_targets_fallback_rate():
    # 100 onsets 1..100 px/s; want ≤10% below the bar → ~10th percentile.
    vels = list(range(1, 101))
    rec = recommend_min_press_velocity(vels, target_fallback=0.10, floor=0.0)
    assert fraction_below(vels, rec) <= 0.11


def test_recommend_min_press_velocity_respects_floor():
    # All tiny velocities → percentile near 0, floor must win.
    rec = recommend_min_press_velocity([0.0, 0.1, 0.2, 0.3], floor=20.0)
    assert rec == 20.0


def test_recommend_min_press_velocity_empty_is_none():
    assert recommend_min_press_velocity([]) is None


def test_recommend_wrist_threshold_flags_only_tail():
    # 100 deviations 1..100; flag worst 5% → ~95th percentile, leaving ≤5%.
    devs = list(range(1, 101))
    thr = recommend_wrist_threshold(devs, target_flag_rate=0.05)
    assert fraction_above(devs, thr) <= 0.06


def test_recommend_wrist_threshold_empty_is_none():
    assert recommend_wrist_threshold([]) is None


# ─── _onset_max_velocity (mirrors comparator.detect_press_finger) ──────

def _tips(ys) -> np.ndarray:
    """(5,2) fingertip array with the given per-finger y values, x fixed."""
    a = np.zeros((5, 2), dtype=float)
    a[:, 0] = [100, 130, 160, 190, 220]
    a[:, 1] = ys
    return a


def test_onset_max_velocity_picks_fastest_downward_finger():
    # finger 2 (index) drops 30px in 0.1s → 300 px/s; others still.
    snaps = [
        (0.00, _tips([200, 200, 200, 200, 200])),
        (0.10, _tips([200, 230, 200, 200, 200])),
    ]
    assert _onset_max_velocity(snaps) == pytest.approx(300.0)


def test_onset_max_velocity_none_when_too_few_snaps():
    assert _onset_max_velocity([]) is None
    assert _onset_max_velocity([(0.0, _tips([0]*5))]) is None


def test_onset_max_velocity_upward_motion_is_negative_max():
    # all fingers move UP (y decreases) → max velocity is negative (no press).
    snaps = [
        (0.00, _tips([200]*5)),
        (0.10, _tips([170]*5)),
    ]
    assert _onset_max_velocity(snaps) == pytest.approx(-300.0)


# ─── resolution scaling ────────────────────────────────────────────────

def test_resolution_scale_720p_is_two_thirds():
    assert math.isclose(resolution_scale(720, baseline_h=1080), 720 / 1080)


def test_resolution_scale_1080p_is_identity():
    assert resolution_scale(1080) == 1.0


def test_resolution_scale_zero_height_safe():
    assert resolution_scale(0) == 1.0


# ─── report JSON contract ──────────────────────────────────────────────

def test_calibration_report_roundtrips_through_json():
    rep = CalibrationReport(video='v.mp4', midi='m.mid', frames=10, height=720)
    rep.detect_rate = {'left': 0.9, 'right': 0.95}
    blob = json.dumps(rep.to_dict())
    back = json.loads(blob)
    assert back['video'] == 'v.mp4'
    assert back['height'] == 720
    assert back['detect_rate']['right'] == 0.95


# ─── format_report (positive + degenerate paths, no video needed) ───────

def _healthy_report() -> CalibrationReport:
    rep = CalibrationReport(video='rec.mp4', midi='played.mid',
                            frames=300, fps=30.0, width=1280, height=720,
                            duration_s=10.0, onsets_sampled=200)
    rep.detect_rate = {'left': 0.92, 'right': 0.95}
    rep.score = {'left': pct_summary([0.8, 0.9, 0.95]),
                 'right': pct_summary([0.85, 0.92, 0.97])}
    rep.hand_span_px = {'left': pct_summary([180, 190, 200]),
                        'right': pct_summary([185, 195, 205])}
    rep.onset_velocity = pct_summary([40, 120, 300])
    rep.press_fallback_fraction = 0.30          # > 0.25 → ⚠
    rep.wrist_abs_dev = pct_summary([5, 15, 40])
    rep.wrist_flag_fraction = 0.10
    rep.recommended = {
        'resolution_scale_vs_1080p': 0.6667,
        'min_press_velocity': 48.0,
        'min_press_velocity_scaled_default': 53.3,
        'wrist_threshold_px': 38.0,
        'wrist_threshold_scaled_default': 16.7,
    }
    return rep


def test_format_report_data_path_shows_recommendations_and_flag():
    txt = format_report(_healthy_report())
    assert 'blind presses' in txt
    assert 'MIN_PRESS_VELOCITY ≈ 48' in txt
    assert '⚠ 30.0% of onsets fall BELOW' in txt   # fallback > 25% → warned
    assert 'wrist threshold ≈ 38' in txt
    # 720p ≠ 1080p baseline → resolution mismatch called out
    assert 'off by 0.67' in txt


def test_format_report_zero_samples_has_no_false_checkmark():
    rep = CalibrationReport(video='blank.mp4', midi='m.mid', frames=100,
                            fps=30.0, width=1920, height=1080, onsets_sampled=50)
    rep.detect_rate = {'left': 0.0, 'right': 0.0}
    rep.score = {'left': pct_summary([]), 'right': pct_summary([])}
    rep.hand_span_px = {'left': pct_summary([]), 'right': pct_summary([])}
    rep.onset_velocity = pct_summary([])         # n == 0
    rep.wrist_abs_dev = pct_summary([])          # n == 0
    txt = format_report(rep)
    assert '⚠ LOW detection' in txt              # tracking warning fires
    assert 'nothing to measure' in txt           # press section: honest
    assert 'enough wrist history' in txt         # wrist section: honest
    # the misleading "✓ 0.0% ... blind presses" verdict must NOT appear
    assert 'blind presses' not in txt


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
