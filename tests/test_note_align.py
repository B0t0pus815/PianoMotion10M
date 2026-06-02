"""Tests for note_align — the played↔expected sequence aligner that decouples
note accuracy (wrong/missing/extra) from fingering accuracy and is tempo-
invariant. See webui/realtime/note_align.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webui.realtime.note_align import align, estimate_offset_scale, build_match_map


def seq(pitches, t0=0.0, dt=0.5):
    """Build a simple monophonic (time, pitch) stream."""
    return [(t0 + i * dt, p) for i, p in enumerate(pitches)]


REF = [60, 62, 64, 65, 67, 65, 64, 62, 60]


def test_identical_is_perfect():
    r = align(seq(REF), seq(REF))
    assert r.correct == len(REF)
    assert r.wrong == r.missing == r.extra == 0
    assert r.note_accuracy == 1.0


def test_tempo_invariance():
    # Same notes, played 1.7x faster and shifted — sequence alignment ignores time.
    fast = seq(REF, t0=3.0, dt=0.5 / 1.7)
    r = align(fast, seq(REF))
    assert r.correct == len(REF)
    assert r.note_accuracy == 1.0


def test_missing_note():
    played = seq(REF[:4] + REF[5:])      # dropped index 4 (the 67)
    r = align(played, seq(REF))
    assert r.missing == 1
    assert r.extra == 0
    assert r.correct == len(REF) - 1
    miss = [o for o in r.ops if o.kind == 'missing']
    assert miss and miss[0].expected_pitch == 67


def test_extra_note():
    played = seq(REF[:4] + [99] + REF[4:])   # inserted a stray 99
    r = align(played, seq(REF))
    assert r.extra == 1
    assert r.missing == 0
    assert r.correct == len(REF)
    extra = [o for o in r.ops if o.kind == 'extra']
    assert extra and extra[0].played_pitch == 99


def test_wrong_note_is_substitution_not_miss_plus_extra():
    wrong = list(REF)
    wrong[4] = 66                         # played 66 instead of 67
    r = align(seq(wrong), seq(REF))
    assert r.wrong == 1
    assert r.missing == 0 and r.extra == 0
    assert r.correct == len(REF) - 1


def test_accuracy_drops_for_unrelated_sequence():
    r = align(seq([40, 41, 42, 43]), seq(REF))
    assert r.note_accuracy < 0.2


def test_empty_played_all_missing():
    r = align([], seq(REF))
    assert r.missing == len(REF)
    assert r.correct == 0
    assert r.note_accuracy == 0.0


def test_chord_order_independent():
    # A chord = simultaneous notes; input order should not matter (sorted by pitch).
    a = [(0.0, 64), (0.0, 60), (0.0, 67)]
    b = [(0.0, 60), (0.0, 67), (0.0, 64)]
    r = align(a, b)
    assert r.correct == 3 and r.wrong == 0


def test_build_match_map_identity():
    p = seq(REF)
    mm = build_match_map(p, seq(REF))
    assert len(mm) == len(REF)
    for i, (t, pitch) in enumerate(p):
        assert mm[(t, pitch)] == i      # i-th played note → i-th expected onset


def test_build_match_map_skips_extra_and_shifts_correctly():
    # extra stray note at t=2.0; the real notes must still map to the right
    # expected indices (greedy ±window would mis-attribute after the extra).
    played = seq(REF[:4]) + [(2.0, 99)] + seq(REF[4:], t0=2.5)
    mm = build_match_map(played, seq(REF))
    assert (2.0, 99) not in mm          # extra note not finger-judged
    assert len(mm) == len(REF)
    assert mm[(2.5, REF[4])] == 4       # note after the extra still maps to expected idx 4


class _Exp:
    """Minimal expected-onset stand-in with .time/.pitch."""
    def __init__(self, t, p):
        self.time = t
        self.pitch = p


def test_build_match_map_bridges_time_shifted_expected():
    # 'expected' = same notes as the faithful reference but with a -50ms offset
    # on alternate notes (mimics generate_fingering). The (pitch,rank) bridge
    # must still map each played note to the correct expected index.
    ref = seq(REF)
    expected = [_Exp(t - (0.05 if i % 2 else 0.0), p) for i, (t, p) in enumerate(ref)]
    mm = build_match_map(ref, ref, expected=expected)   # played == faithful ref
    assert len(mm) == len(REF)
    for i, (t, p) in enumerate(ref):
        assert mm[(t, p)] == i      # correct expected index despite the shifts


def test_warp_recovers_tempo_scale_and_offset():
    # expected_t = scale*played_t + offset; here ref is 2x slower, +5s.
    played = seq(REF, t0=0.0, dt=0.3)
    expected = [(5.0 + 2.0 * t, p) for (t, p) in played]
    r = align(played, expected)
    scale, offset, rms = estimate_offset_scale(r.warp)
    assert scale == pytest.approx(2.0, abs=1e-6)
    assert offset == pytest.approx(5.0, abs=1e-6)
    assert rms < 1e-6
