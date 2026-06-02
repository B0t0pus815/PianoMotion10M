"""Tests for av_sync.estimate_offset — the audio↔MIDI offset voter. Uses
synthetic onset trains (no audio decoding) so the fast suite stays fast.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from webui.realtime.av_sync import estimate_offset, best_lag_frames


def midi_train(n=40, dt=0.5):
    return [i * dt for i in range(n)]


def test_recovers_clean_offset():
    m = midi_train()
    a = [t + 2.3 for t in m]                 # audio started 2.3s after midi
    off, votes, frac = estimate_offset(a, m)
    assert off == pytest.approx(2.3, abs=0.02)
    assert frac == pytest.approx(1.0, abs=1e-6)


def test_robust_to_missing_and_spurious_onsets():
    import random
    random.seed(0)
    m = midi_train()
    a = [t + 2.3 for t in m if random.random() > 0.2]      # drop ~20% of audio onsets
    a += [random.uniform(0, 25) for _ in range(8)]          # add spurious onsets
    off, votes, frac = estimate_offset(a, m)
    assert off == pytest.approx(2.3, abs=0.03)
    assert frac > 0.6


def test_intro_before_first_note_does_not_bias():
    # audio has 13.75s of intro noise (no midi counterpart) then the aligned piece.
    m = midi_train()
    a = [t + 0.0 for t in m] + [3.1, 7.4, 11.9]            # spurious intro onsets
    off, _, _ = estimate_offset(a, m)
    assert off == pytest.approx(0.0, abs=0.02)


def test_negative_offset():
    m = midi_train()
    a = [t - 1.7 for t in m]                 # audio started before midi
    off, _, _ = estimate_offset(a, m)
    assert off == pytest.approx(-1.7, abs=0.02)


def test_empty_inputs():
    assert estimate_offset([], midi_train()) == (0.0, 0, 0.0)
    assert estimate_offset(midi_train(), []) == (0.0, 0, 0.0)


# ── envelope cross-correlation core (disambiguates periodic onsets) ──

def _bumps(length, positions, height=1.0, width=3):
    sig = np.zeros(length)
    for p, h in positions:
        for d in range(-width, width + 1):
            i = p + d
            if 0 <= i < length:
                sig[i] += h * max(0.0, 1 - abs(d) / (width + 1))
    return sig


def test_best_lag_recovers_known_shift():
    # amplitude pattern (varying heights) shifted by +40 frames
    pos = [(50, 1.0), (90, 0.4), (130, 0.9), (175, 0.5), (210, 1.0)]
    b = _bumps(400, pos)
    a = _bumps(400, [(p + 40, h) for p, h in pos])
    assert best_lag_frames(a, b, max_lag=80) == pytest.approx(40, abs=1)


def test_best_lag_disambiguates_periodic_via_amplitude():
    # near-evenly-spaced events (period 40) but DISTINCT heights — the wrong
    # period-multiple lag must lose to the true lag (the Canon failure mode).
    heights = [1.0, 0.3, 0.8, 0.5, 0.95, 0.35]
    pos = [(40 + 40 * i, h) for i, h in enumerate(heights)]
    b = _bumps(500, pos)
    a = _bumps(500, [(p + 12, h) for p, h in pos])   # true shift +12
    lag = best_lag_frames(a, b, max_lag=120)
    assert lag == pytest.approx(12, abs=1)           # not 12±40, 12±80, ...
