"""Tests for build_gt_rulebased — the GT generator that thesis depends on.

These tests pin down the rule-application behavior so future refactors
can't silently drift the GT, which would invalidate every audit number
reported in ch4.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build_gt_rulebased import chord_rule, is_artifact, single_note_rule, decide


# ─── chord_rule — interval-based 2-note rules ───────────────────────────

@pytest.mark.parametrize('notes,expected', [
    # (low_pitch, high_pitch)  → expected [low_finger, high_finger]
    ([60, 61], [1, 2]),     # m2 → [1, 2]
    ([60, 62], [1, 2]),     # M2 → [1, 2]
    ([60, 63], [1, 3]),     # m3 → [1, 3]
    ([60, 64], [1, 4]),     # M3 → [1, 4]
    ([60, 65], [1, 4]),     # P4 → [1, 4]
    ([60, 66], [1, 4]),     # 三全音 → [1, 4]
    ([60, 67], [1, 5]),     # P5 → [1, 5]
    ([60, 69], [1, 5]),     # M6 → [1, 5]
    ([60, 70], [1, 5]),     # m7 → [1, 5]
    ([60, 71], [1, 5]),     # M7 → [1, 5]
    ([60, 72], [1, 5]),     # 八度 → [1, 5]
    ([60, 79], [1, 5]),     # >octave → [1, 5]
])
def test_chord_rule_interval_table(notes, expected):
    """All standard interval cases produce textbook fingerings."""
    assert chord_rule(notes) == expected


def test_chord_rule_returns_none_for_non_chord():
    """Single note → None (no chord rule applies)."""
    assert chord_rule([60]) is None


def test_chord_rule_returns_none_for_unison():
    """Same pitch twice → interval 0, no rule covers this case."""
    assert chord_rule([60, 60]) is None


def test_chord_rule_returns_none_for_3plus_notes():
    """3+ note chord — current implementation only handles 2-note chords."""
    assert chord_rule([60, 64, 67]) is None
    assert chord_rule([60, 63, 67, 70]) is None


def test_chord_rule_sorts_input_pitches():
    """Caller may pass descending pitches; rule sorts ascending internally."""
    # 60 + 64 (M3) → [1, 4] regardless of input order
    assert chord_rule([64, 60]) == [1, 4]


# ─── is_artifact — MIDI artifact detection ──────────────────────────────

def test_is_artifact_duplicate_pitch():
    """[71, 71] is a MIDI artifact (same pitch in same onset)."""
    o = {'midi_notes': [71, 71], 'pp_fingering': [1, 2], 'arlstm_fingering': [2, 3]}
    assert is_artifact(o) is True


def test_is_artifact_zero_in_pp():
    """pianoplayer outputting 0 (unassigned) → artifact."""
    o = {'midi_notes': [60, 67], 'pp_fingering': [1, 0], 'arlstm_fingering': [1, 5]}
    assert is_artifact(o) is True


def test_is_artifact_zero_in_arlstm():
    """ArLSTM outputting 0 → artifact."""
    o = {'midi_notes': [60, 67], 'pp_fingering': [1, 5], 'arlstm_fingering': [0, 5]}
    assert is_artifact(o) is True


def test_is_artifact_normal_case():
    """Normal 2-note chord with valid fingers from both predictors → not artifact."""
    o = {'midi_notes': [60, 64], 'pp_fingering': [1, 3], 'arlstm_fingering': [1, 4]}
    assert is_artifact(o) is False


# ─── single_note_rule — stepwise continuity ─────────────────────────────

def test_single_note_rule_no_prev_returns_none():
    """First onset has no prev_entry; rule can't apply."""
    onset = {'midi_notes': [60]}
    assert single_note_rule(onset, None) is None


def test_single_note_rule_after_chord_returns_none():
    """Don't carry over from a chord (state mismatch)."""
    onset = {'midi_notes': [60]}
    prev = {'midi_notes': [60, 64], 'fingering': [1, 3]}  # was a chord
    assert single_note_rule(onset, prev) is None


def test_single_note_rule_repeated_note():
    """Same pitch as prev → same finger."""
    onset = {'midi_notes': [60]}
    prev = {'midi_notes': [60], 'fingering': [3]}
    assert single_note_rule(onset, prev) == 3


def test_single_note_rule_step_up():
    """+1 semitone → finger + 1."""
    onset = {'midi_notes': [61]}
    prev = {'midi_notes': [60], 'fingering': [2]}
    assert single_note_rule(onset, prev) == 3  # index → middle


def test_single_note_rule_step_up_from_pinky_returns_none():
    """+1 semitone but already at pinky (5) → can't go to 6, rule fails."""
    onset = {'midi_notes': [61]}
    prev = {'midi_notes': [60], 'fingering': [5]}
    assert single_note_rule(onset, prev) is None


def test_single_note_rule_step_down():
    """-1 semitone → finger - 1."""
    onset = {'midi_notes': [59]}
    prev = {'midi_notes': [60], 'fingering': [3]}
    assert single_note_rule(onset, prev) == 2  # middle → index


def test_single_note_rule_step_down_from_thumb_returns_none():
    """-1 semitone from thumb (1) → can't go to 0, rule fails."""
    onset = {'midi_notes': [59]}
    prev = {'midi_notes': [60], 'fingering': [1]}
    assert single_note_rule(onset, prev) is None


def test_single_note_rule_leap_returns_none():
    """+3 semitone leap → rule doesn't apply, defer to tiebreaker."""
    onset = {'midi_notes': [63]}
    prev = {'midi_notes': [60], 'fingering': [2]}
    assert single_note_rule(onset, prev) is None


# ─── decide — full decision dispatch ────────────────────────────────────

def test_decide_artifact_returns_none_with_label():
    """Artifact onset → (None, 'artifact-skip')."""
    o = {'midi_notes': [60, 60], 'pp_fingering': [1, 2], 'arlstm_fingering': [2, 3]}
    chosen, label = decide(o, None)
    assert chosen is None
    assert label == 'artifact-skip'


def test_decide_consensus_returns_consensus_value():
    """Both predictors agree → use that, label = 'predictor-consensus'."""
    o = {'midi_notes': [60], 'pp_fingering': [3], 'arlstm_fingering': [3]}
    chosen, label = decide(o, None)
    assert chosen == [3]
    assert label == 'predictor-consensus'


def test_decide_chord_rule_overrides_predictors():
    """When chord rule applies, it wins regardless of predictor output."""
    # m3 → [1, 3] rule, even if pianoplayer disagrees
    o = {'midi_notes': [60, 63], 'pp_fingering': [2, 5], 'arlstm_fingering': [1, 3]}
    chosen, label = decide(o, None)
    assert chosen == [1, 3]
    assert label.startswith('chord-rule')


def test_decide_falls_through_to_arlstm_when_rules_fail():
    """Leap single note → no rule applies → arlstm-tiebreaker."""
    o = {'midi_notes': [63], 'pp_fingering': [1], 'arlstm_fingering': [4]}
    prev = {'midi_notes': [60], 'fingering': [2]}  # leap from 60 to 63
    chosen, label = decide(o, prev)
    assert chosen == [4]
    assert label == 'arlstm-tiebreaker'


def test_decide_single_note_stepwise_rule_applies():
    """Stepwise +1 should use rule, not predictor."""
    o = {'midi_notes': [61], 'pp_fingering': [5], 'arlstm_fingering': [1]}  # both wrong
    prev = {'midi_notes': [60], 'fingering': [2]}
    chosen, label = decide(o, prev)
    assert chosen == [3]  # rule = 2 + 1 = 3
    assert label == 'single-note-rule'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
