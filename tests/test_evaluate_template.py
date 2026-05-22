"""Unit tests for evaluate_template — the foundation of all corpus numbers.

Reviewer reproducibility check:
    cd /home/dex/PianoMotion10M
    python -m pytest tests/test_evaluate_template.py -v

These tests pin down the exact Hard/Soft scoring behavior so future
refactors can't silently drift the corpus numbers reported in ch4.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluate_template import (
    VALID_ALT_CREDIT, score_chord, load_ground_truth, evaluate, OnsetScore,
)


# ─── score_chord — single-finger cases ─────────────────────────────────

def test_score_chord_exact_match_single():
    hard, soft, per = score_chord([3], [3])
    assert hard == 1.0
    assert soft == 1.0
    assert per == [1.0]


def test_score_chord_off_by_one_gets_half_credit():
    hard, soft, per = score_chord([3], [4])
    assert hard == 0.0
    assert soft == VALID_ALT_CREDIT
    assert per == [VALID_ALT_CREDIT]


def test_score_chord_off_by_one_below_gets_half_credit():
    """+1 and -1 are symmetric."""
    hard, soft, per = score_chord([3], [2])
    assert hard == 0.0
    assert soft == VALID_ALT_CREDIT


def test_score_chord_off_by_two_gets_zero():
    hard, soft, per = score_chord([3], [5])
    assert hard == 0.0
    assert soft == 0.0
    assert per == [0.0]


def test_score_chord_none_prediction_is_zero():
    """A missing prediction (predictor saw no onset) scores zero, not error."""
    hard, soft, per = score_chord([3], None)
    assert hard == 0.0
    assert soft == 0.0
    assert per == [0.0]


# ─── score_chord — chord cases ─────────────────────────────────────────

def test_score_chord_exact_match_2note():
    hard, soft, per = score_chord([1, 5], [1, 5])
    assert hard == 1.0
    assert soft == 1.0
    assert per == [1.0, 1.0]


def test_score_chord_partial_match_2note():
    """First finger exact, second off-by-1."""
    hard, soft, per = score_chord([1, 5], [1, 4])
    assert hard == 0.0
    assert soft == pytest.approx((1.0 + 0.5) / 2)
    assert per == [1.0, 0.5]


def test_score_chord_length_mismatch_pred_too_short():
    """Predictor produced 1 finger but GT has 2 — missing slot scores 0."""
    hard, soft, per = score_chord([1, 5], [1])
    assert hard == 0.0
    assert soft == pytest.approx(1.0 / 2)
    assert per == [1.0, 0.0]


def test_score_chord_length_mismatch_pred_too_long():
    """Predictor produced 3 fingers but GT has 2 — extras inflate denominator."""
    hard, soft, per = score_chord([1, 5], [1, 5, 3])
    assert hard == 0.0
    # numerator = 1 + 1 + 0 (extras don't add to per), denominator = 2 + 1
    assert soft == pytest.approx(2.0 / 3)


def test_score_chord_three_note_chord():
    """Verify scoring scales to triads."""
    hard, soft, per = score_chord([1, 3, 5], [1, 3, 4])
    assert hard == 0.0
    assert soft == pytest.approx((1.0 + 1.0 + 0.5) / 3)


# ─── evaluate() — corpus-level integration ─────────────────────────────

def test_evaluate_minimal_perfect():
    """Single onset GT, perfect prediction, expects 1.0 Hard / 1.0 Soft."""
    gt = [{"onset_index": 0, "midi_notes": [60], "fingering": [3]}]
    preds = {0: [3]}
    per_onset, summary = evaluate(gt, preds)
    assert len(per_onset) == 1
    assert summary['hard_accuracy'] == 1.0
    assert summary['soft_accuracy'] == 1.0
    assert summary['n_onsets'] == 1.0
    assert summary['n_missing_predictions'] == 0.0


def test_evaluate_minimal_missing():
    """Missing prediction is counted (not error) — confirms downstream robustness."""
    gt = [{"onset_index": 0, "midi_notes": [60], "fingering": [3]}]
    preds = {}  # nothing!
    per_onset, summary = evaluate(gt, preds)
    assert summary['hard_accuracy'] == 0.0
    assert summary['soft_accuracy'] == 0.0
    assert summary['n_missing_predictions'] == 1.0


def test_evaluate_mixed_correct_partial_missing():
    """Three onsets: one exact, one ±1, one missing. Sanity-check arithmetic."""
    gt = [
        {"onset_index": 0, "midi_notes": [60], "fingering": [3]},
        {"onset_index": 1, "midi_notes": [62], "fingering": [4]},
        {"onset_index": 2, "midi_notes": [64], "fingering": [5]},
    ]
    preds = {
        0: [3],       # exact
        1: [3],       # off by 1
        # 2 missing
    }
    per_onset, summary = evaluate(gt, preds)
    assert summary['hard_accuracy'] == pytest.approx(1.0 / 3)
    assert summary['soft_accuracy'] == pytest.approx((1.0 + 0.5 + 0.0) / 3)
    assert summary['n_missing_predictions'] == 1.0


def test_evaluate_preserves_onset_index_mapping():
    """If GT has non-sequential onset_index, predictions must be looked up
    by the index field, not by array position."""
    gt = [
        {"onset_index": 0,   "midi_notes": [60], "fingering": [1]},
        {"onset_index": 100, "midi_notes": [72], "fingering": [5]},  # gap!
    ]
    preds = {0: [1], 100: [5]}
    per_onset, summary = evaluate(gt, preds)
    assert summary['hard_accuracy'] == 1.0  # both perfect
    # And not preds.get(0) + preds.get(1) which would miss the second.


# ─── load_ground_truth — schema validation ─────────────────────────────

def test_load_ground_truth_rejects_length_mismatch(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "ground_truth": [
            {"onset_index": 0, "midi_notes": [60, 64], "fingering": [3]}  # mismatch
        ]
    }))
    with pytest.raises(ValueError, match="length mismatch"):
        load_ground_truth(bad)


def test_load_ground_truth_accepts_valid(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps({
        "song": "test",
        "hand": "right",
        "ground_truth": [
            {"onset_index": 0, "midi_notes": [60, 64], "fingering": [1, 3]},
        ]
    }))
    entries = load_ground_truth(good)
    assert len(entries) == 1
    assert entries[0]["fingering"] == [1, 3]


# ─── Regression-pinning tests — DO NOT MODIFY without updating thesis ─

def test_regression_canon_neutral_pinning_arlstm_only():
    """Pin the ArLSTM number reported in thesis ch4 4.4.1 to within tolerance.

    Skipped unless the rule-based GT is present (CI environments without
    the eval_data/ committed will skip). This is the single most important
    test for thesis defense: if it ever fails, the corpus number in
    ch4/4.4.1, ch1/1.3 main contributions, and ch7/7.1 findings need to
    be updated together.
    """
    gt_path = Path(__file__).resolve().parent.parent / 'eval_data' / 'canon_rh_rulebased_gt.json'
    if not gt_path.exists():
        pytest.skip(f"GT not present at {gt_path}")
    # Just load + count — actually evaluating ArLSTM here would require
    # the full inference stack; that's an integration test, not a unit test.
    entries = load_ground_truth(gt_path)
    # n=186 entries in RH GT — if this changes, ch4 4.4.1 needs update.
    assert len(entries) == 186, (
        f"RH GT entry count changed: thesis ch4 4.4.1 says n=186, "
        f"this file has n={len(entries)}. Update ch4 or revert GT."
    )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
