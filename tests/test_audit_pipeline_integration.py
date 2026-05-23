"""End-to-end integration tests for the four-way audit pipeline.

Pins down that the corpus numbers reported in thesis/ch4 are reproducible
from a fresh checkout. If any of these tests fail, the corresponding
thesis section MUST be updated to match the new numbers.

These tests are slow (~30s for Canon RH because they actually load
Ramoneda checkpoints and run inference). Skip in fast unit-test runs
with `pytest -m 'not slow'`.

Run:
    python -m pytest tests/test_audit_pipeline_integration.py -v
    python -m pytest tests/ -v -m 'not slow'   # skip these
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# These will only be importable when the env has torch + Ramoneda submodule
torch = pytest.importorskip('torch', reason='torch not installed')

REPO_ROOT = Path(__file__).resolve().parent.parent
CANON_MIDI = REPO_ROOT / 'input_songs' / 'Canon In D - Pachelbel  EASY Piano Tutorial.mid'
CANON_FINGERTIPS = REPO_ROOT / 'results' / 'canon_biomech_v4_fingertips.json'
BACH_MIDI = REPO_ROOT / 'input_songs' / 'Bach_Invention_01_BWV772.mid'

CANON_RH_GT = REPO_ROOT / 'eval_data' / 'canon_rh_rulebased_gt.json'
CANON_LH_GT = REPO_ROOT / 'eval_data' / 'canon_lh_rulebased_gt.json'
BACH_RH_GT = REPO_ROOT / 'eval_data' / 'bach_inv01_rh_rulebased_gt.json'
BACH_LH_GT = REPO_ROOT / 'eval_data' / 'bach_inv01_lh_rulebased_gt.json'
AUDIT_RESULTS = REPO_ROOT / 'eval_data' / 'audit_results.json'

# Tolerance for floating-point comparison of accuracy numbers.
# Models are deterministic (argmax decode) so true zero tolerance would
# work, but ±0.005 buffer guards against trivial pandas/python version
# rounding differences across machines.
TOL = 0.005


# Mark all tests in this module as slow so they're easy to skip
pytestmark = pytest.mark.slow


def _skip_if_missing(*paths):
    for p in paths:
        if not p.exists():
            pytest.skip(f"Required artifact missing: {p}")


def _run_audit(midi_path, gt_path, fingertips_path=None, neutral=False):
    """Programmatic invocation of the audit pipeline. Returns dict
    of track-name → {'hard': X, 'soft': Y}."""
    from evaluate_template import load_ground_truth, evaluate
    from evaluate_canon import engine_predictions
    from four_way_audit import ramoneda_bucketed

    gt_entries = load_ground_truth(gt_path)
    if neutral:
        gt_entries = [e for e in gt_entries
                      if e.get('decision') != 'arlstm-tiebreaker']

    hand_blob = json.loads(Path(gt_path).read_text(encoding='utf-8'))
    hand = hand_blob.get('hand', 'right')

    preds = {
        'pianoplayer': engine_predictions(str(midi_path), hand=hand),
        'ArLSTM':      ramoneda_bucketed(str(midi_path), hand, 'ArLSTM'),
        'ArGNN':       ramoneda_bucketed(str(midi_path), hand, 'ArGNN'),
    }
    if fingertips_path and Path(fingertips_path).exists():
        from cross_audit_canon import motion_predictions
        preds['motion_v4'] = motion_predictions(
            str(midi_path), str(fingertips_path), hand=hand,
        )

    out = {}
    for name, p in preds.items():
        _, summary = evaluate(gt_entries, p)
        out[name] = {'hard': summary['hard_accuracy'],
                     'soft': summary['soft_accuracy']}
    return out


def _load_frozen():
    return json.loads(AUDIT_RESULTS.read_text(encoding='utf-8'))


# ─── Canon RH ───────────────────────────────────────────────────────────

def test_audit_canon_rh_full_matches_frozen():
    _skip_if_missing(CANON_MIDI, CANON_RH_GT, CANON_FINGERTIPS)
    frozen = _load_frozen()['right_hand']['results_full']
    got = _run_audit(CANON_MIDI, CANON_RH_GT, CANON_FINGERTIPS, neutral=False)
    for track in ['pianoplayer', 'ArLSTM', 'ArGNN', 'motion_v4']:
        assert abs(got[track]['hard'] - frozen[track]['hard']) < TOL, \
            f"RH full Hard for {track}: got {got[track]['hard']:.3f}, frozen {frozen[track]['hard']:.3f}"
        assert abs(got[track]['soft'] - frozen[track]['soft']) < TOL, \
            f"RH full Soft for {track}: got {got[track]['soft']:.3f}, frozen {frozen[track]['soft']:.3f}"


def test_audit_canon_rh_neutral_matches_frozen():
    _skip_if_missing(CANON_MIDI, CANON_RH_GT, CANON_FINGERTIPS)
    frozen = _load_frozen()['right_hand']['results_neutral']
    got = _run_audit(CANON_MIDI, CANON_RH_GT, CANON_FINGERTIPS, neutral=True)
    for track in ['pianoplayer', 'ArLSTM', 'ArGNN', 'motion_v4']:
        assert abs(got[track]['hard'] - frozen[track]['hard']) < TOL
        assert abs(got[track]['soft'] - frozen[track]['soft']) < TOL


# ─── Canon LH ───────────────────────────────────────────────────────────

def test_audit_canon_lh_neutral_matches_frozen():
    _skip_if_missing(CANON_MIDI, CANON_LH_GT, CANON_FINGERTIPS)
    frozen = _load_frozen()['left_hand']['results_neutral']
    got = _run_audit(CANON_MIDI, CANON_LH_GT, CANON_FINGERTIPS, neutral=True)
    for track in ['pianoplayer', 'ArLSTM', 'ArGNN']:
        assert abs(got[track]['hard'] - frozen[track]['hard']) < TOL
        assert abs(got[track]['soft'] - frozen[track]['soft']) < TOL


# ─── Bach Invention (no fingertips → no motion column) ──────────────────

def test_audit_bach_rh_neutral_matches_frozen():
    _skip_if_missing(BACH_MIDI, BACH_RH_GT)
    frozen = _load_frozen()['cross_piece_validation']['bach_invention_01']['rh']['results_neutral']
    got = _run_audit(BACH_MIDI, BACH_RH_GT, neutral=True)
    for track in ['pianoplayer', 'ArLSTM', 'ArGNN']:
        assert abs(got[track]['hard'] - frozen[track]['hard']) < TOL, \
            f"Bach RH neutral Hard for {track}: got {got[track]['hard']:.3f}, frozen {frozen[track]['hard']:.3f}"
        assert abs(got[track]['soft'] - frozen[track]['soft']) < TOL, \
            f"Bach RH neutral Soft for {track}: got {got[track]['soft']:.3f}, frozen {frozen[track]['soft']:.3f}"


def test_audit_bach_lh_neutral_matches_frozen():
    _skip_if_missing(BACH_MIDI, BACH_LH_GT)
    frozen = _load_frozen()['cross_piece_validation']['bach_invention_01']['lh']['results_neutral']
    got = _run_audit(BACH_MIDI, BACH_LH_GT, neutral=True)
    for track in ['pianoplayer', 'ArLSTM', 'ArGNN']:
        assert abs(got[track]['hard'] - frozen[track]['hard']) < TOL
        assert abs(got[track]['soft'] - frozen[track]['soft']) < TOL


# ─── Sanity: pp wins Bach RH, ArLSTM wins Bach LH (the key story) ──────

def test_audit_bach_rh_pianoplayer_wins_soft():
    """Headline finding of ch4 §4.6.3: pp Soft > ArLSTM Soft on Bach RH."""
    _skip_if_missing(BACH_MIDI, BACH_RH_GT)
    got = _run_audit(BACH_MIDI, BACH_RH_GT, neutral=True)
    assert got['pianoplayer']['soft'] > got['ArLSTM']['soft'], \
        "ch4 §4.6.3 claims pp wins Bach RH neutral. If this changes, " \
        "ch4 §4.6, ch7 §7.1 RQ2 answer, defense_qa.md Q1.5, and " \
        "defense_slides.md cross-piece slide ALL need updating."


def test_audit_bach_lh_arlstm_wins_soft():
    """Headline finding of ch4 §4.6.3: ArLSTM Soft > pp Soft on Bach LH."""
    _skip_if_missing(BACH_MIDI, BACH_LH_GT)
    got = _run_audit(BACH_MIDI, BACH_LH_GT, neutral=True)
    assert got['ArLSTM']['soft'] > got['pianoplayer']['soft']


def test_audit_canon_arlstm_wins_combined_soft():
    """Headline finding of ch1 §1.3 and ch4 §4.4.3: ArLSTM Soft > pp Soft
    on Canon RH+LH combined neutral subset (the n=183 number 0.792)."""
    _skip_if_missing(CANON_MIDI, CANON_RH_GT, CANON_LH_GT)
    rh = _run_audit(CANON_MIDI, CANON_RH_GT, CANON_FINGERTIPS, neutral=True)
    lh = _run_audit(CANON_MIDI, CANON_LH_GT, CANON_FINGERTIPS, neutral=True)
    # weighted by GT entry count (143 RH + 40 LH = 183)
    arlstm_combined = (rh['ArLSTM']['soft'] * 143 + lh['ArLSTM']['soft'] * 40) / 183
    pp_combined     = (rh['pianoplayer']['soft'] * 143 + lh['pianoplayer']['soft'] * 40) / 183
    assert arlstm_combined > pp_combined
    assert abs(arlstm_combined - 0.792) < 0.01, \
        f"ch4 §4.4.3 reports combined ArLSTM Soft=0.792; got {arlstm_combined:.3f}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
