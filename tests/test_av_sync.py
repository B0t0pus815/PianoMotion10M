"""Tests for av_sync.estimate_offset — the audio↔MIDI offset voter. Uses
synthetic onset trains (no audio decoding) so the fast suite stays fast.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webui.realtime.av_sync import estimate_offset


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
