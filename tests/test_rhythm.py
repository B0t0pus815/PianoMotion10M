"""Tests for rhythm-hint v1 — the rush/drag tracker, the faithful reference-time
bridge, and the additive OnsetResult/Thresholds fields the runner relies on.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webui.realtime.rhythm import RhythmTracker, RhythmResult
from webui.realtime.note_align import ref_time_by_onset
from webui.realtime.comparator import OnsetResult, DEFAULT_THRESHOLDS
from webui.realtime.reference import ExpectedOnset, FINGER_ORDER


def _exp(time: float, pitch: int) -> ExpectedOnset:
    return ExpectedOnset(
        time=time, pitch=pitch, velocity=80,
        expected_hand='right', expected_finger='thumb',
        expected_finger_idx=FINGER_ORDER.index('thumb'), duration=0.5,
    )


# ─── RhythmTracker.update ──────────────────────────────────────────────

def test_first_onset_is_unknown_and_zero_detrended():
    """No baseline yet → can't judge steadiness; raw offset still reported."""
    t = RhythmTracker()
    r = t.update(played_t=1.2, reference_t=1.0)
    assert isinstance(r, RhythmResult)
    assert r.offset_s == pytest.approx(0.2)
    assert r.detrended_s == 0.0
    assert r.status == 'unknown'


def test_steady_lateness_reads_as_even():
    """A constant +200ms lag is absorbed by the baseline → on_time (even),
    while the RAW offset stays +200ms (the report card's drag tendency)."""
    t = RhythmTracker()
    statuses, offsets = [], []
    for k in range(6):
        r = t.update(played_t=k + 0.2, reference_t=float(k))
        statuses.append(r.status)
        offsets.append(r.offset_s)
    assert statuses[0] == 'unknown'
    assert all(s == 'on_time' for s in statuses[1:])
    assert all(o == pytest.approx(0.2) for o in offsets)


def test_single_late_spike_after_steady_play_is_drag():
    t = RhythmTracker()
    for k in range(4):
        t.update(played_t=float(k), reference_t=float(k))   # dead-on
    r = t.update(played_t=4 + 0.3, reference_t=4.0)
    assert r.status == 'drag'
    assert r.detrended_s == pytest.approx(0.3, abs=1e-6)


def test_single_early_spike_after_steady_play_is_rush():
    t = RhythmTracker()
    for k in range(4):
        t.update(played_t=float(k), reference_t=float(k))
    r = t.update(played_t=4 - 0.3, reference_t=4.0)
    assert r.status == 'rush'
    assert r.detrended_s == pytest.approx(-0.3, abs=1e-6)


def test_tolerance_boundary():
    """Just inside ±tol → on_time; just outside → rush/drag. Fresh trackers so
    the EMA baseline doesn't carry between assertions."""
    tol = 0.06
    inside = RhythmTracker(tolerance_s=tol)
    inside.update(0.0, 0.0)
    assert inside.update(played_t=0.05, reference_t=0.0).status == 'on_time'

    late = RhythmTracker(tolerance_s=tol)
    late.update(0.0, 0.0)
    assert late.update(played_t=0.07, reference_t=0.0).status == 'drag'

    early = RhythmTracker(tolerance_s=tol)
    early.update(0.0, 0.0)
    assert early.update(played_t=-0.07, reference_t=0.0).status == 'rush'


# ─── ref_time_by_onset (faithful reference time bridge) ────────────────

def test_ref_time_by_onset_recovers_faithful_time_under_uniform_offset():
    """expected .time carries a uniform +0.5 offset; the rank bridge still
    pairs each onset to its raw reference time."""
    expected = [_exp(0.5, 60), _exp(1.5, 62), _exp(2.5, 64)]
    reference = [(0.0, 60), (1.0, 62), (2.0, 64)]
    assert ref_time_by_onset(expected, reference) == pytest.approx([0.0, 1.0, 2.0])


def test_ref_time_by_onset_same_pitch_ranks_in_order():
    expected = [_exp(0.5, 60), _exp(1.5, 60)]
    reference = [(0.0, 60), (1.0, 60)]
    assert ref_time_by_onset(expected, reference) == pytest.approx([0.0, 1.0])


def test_ref_time_by_onset_falls_back_to_own_time_when_unmatched():
    """An expected onset whose pitch has no reference match keeps its own time."""
    expected = [_exp(0.5, 60), _exp(1.5, 99)]   # 99 absent from reference
    reference = [(0.0, 60)]
    out = ref_time_by_onset(expected, reference)
    assert out[0] == pytest.approx(0.0)
    assert out[1] == pytest.approx(1.5)   # fallback to .time


# ─── Additive-field guards (backwards compat) ─────────────────────────

def test_onsetresult_default_rhythm_fields():
    r = OnsetResult(
        time=1.0, pitch=60, expected_hand='right', expected_finger='thumb',
        detected_finger='thumb', correct=True, confidence=0.9,
    )
    assert r.timing_offset_s == 0.0
    assert r.timing_detrended_s == 0.0
    assert r.rhythm_status == 'unknown'


def test_default_thresholds_has_rhythm_tolerance():
    assert DEFAULT_THRESHOLDS.rhythm_tolerance_s == 0.06


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
