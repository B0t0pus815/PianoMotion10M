"""Four-way fingering audit on a Teacher's Answer-Key GT.

Compares against the same GT JSON:
  - Logic Track:   pianoplayer DP (Parncutt cost)
  - Visual Track:  biomech v4 motion-derived
  - Ramoneda 2022: ArLSTM
  - Ramoneda 2022: ArGNN

Usage:
    python four_way_audit.py \\
        --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \\
        --gt   eval_data/canon_rh_gt.json \\
        --fingertips results/canon_biomech_v4_fingertips.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from evaluate_template import evaluate, load_ground_truth
from evaluate_canon import engine_predictions, ONSET_BUCKET_SEC
from cross_audit_canon import motion_predictions
from ramoneda_predict import predict as ramoneda_predict


def ramoneda_bucketed(midi_path: str, hand: str, kind: str) -> dict[int, list[int]]:
    """Run Ramoneda model, then bucket per-note outputs by onset time (same
    rule as engine_predictions / motion_predictions) so onset indices align."""
    fingers, info = ramoneda_predict(midi_path, hand, kind)
    paired = sorted(zip(info, fingers), key=lambda x: (x[0][0], x[0][1]))

    buckets: list[list] = []
    bucket_start: float | None = None
    for (t, p), f in paired:
        if bucket_start is None or (t - bucket_start) > ONSET_BUCKET_SEC:
            buckets.append([])
            bucket_start = t
        buckets[-1].append((t, p, int(f)))

    predictions: dict[int, list[int]] = {}
    for idx, group in enumerate(buckets):
        group.sort(key=lambda x: x[1])  # by pitch
        predictions[idx] = [g[2] for g in group]
    return predictions


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--midi', required=True)
    ap.add_argument('--gt', required=True)
    ap.add_argument('--fingertips', required=True,
                    help='Motion track fingertip JSON for biomech v4')
    ap.add_argument('--frame-width', type=int, default=1920)
    ap.add_argument('--hand', default=None)
    ap.add_argument('--exclude-tiebreakers', action='store_true',
                    help='Drop GT entries whose decision=="arlstm-tiebreaker" '
                         'before scoring — gives a predictor-neutral subset that '
                         'does NOT trivially favor ArLSTM.')
    args = ap.parse_args()

    gt_blob = json.loads(Path(args.gt).read_text(encoding='utf-8'))
    hand = args.hand or gt_blob.get('hand', 'right')

    gt_entries = load_ground_truth(args.gt)
    n_gt = len(gt_entries)
    if args.exclude_tiebreakers:
        before = n_gt
        gt_entries = [e for e in gt_entries
                      if e.get('decision') != 'arlstm-tiebreaker']
        n_gt = len(gt_entries)
        print(f'[mask] dropped {before - n_gt} arlstm-tiebreaker entries; '
              f'evaluating on {n_gt} predictor-neutral entries')

    # Run all four predictors.
    preds = {
        'pianoplayer': engine_predictions(args.midi, hand=hand),
        'motion_v4':   motion_predictions(args.midi, args.fingertips,
                                          hand=hand, frame_width=args.frame_width),
        'ArLSTM':      ramoneda_bucketed(args.midi, hand, 'ArLSTM'),
        'ArGNN':       ramoneda_bucketed(args.midi, hand, 'ArGNN'),
    }

    # Score each.
    scored = {name: evaluate(gt_entries, p) for name, p in preds.items()}

    # Per-onset side-by-side.
    print(f"song: {gt_blob.get('song')}")
    print(f"hand: {hand}   gt_entries: {n_gt}")
    print()
    header_cols = ['idx', 't', 'pitches', 'GT',
                   'pianoplayer', 'motion_v4', 'ArLSTM', 'ArGNN']
    print(f"{'idx':>3}  {'t':>6}  {'pitches':<12}  {'GT':<10}  "
          f"{'pianoplayer':<11}  {'motion_v4':<11}  "
          f"{'ArLSTM':<11}  {'ArGNN':<11}")
    print('-' * 100)
    for i in range(n_gt):
        e = gt_entries[i]
        idx = e['onset_index']  # NOT array position — predictors are keyed by onset_index
        t = e.get('onset_time')
        t_str = f'{t:6.2f}' if t is not None else '   -- '
        cells = [str(preds[name].get(idx)) for name in
                 ['pianoplayer', 'motion_v4', 'ArLSTM', 'ArGNN']]
        print(f"{idx:>3}  {t_str}  {str(e['midi_notes']):<12}  "
              f"{str(e['fingering']):<10}  "
              f"{cells[0]:<11}  {cells[1]:<11}  {cells[2]:<11}  {cells[3]:<11}")

    print()
    print('Aggregate accuracy vs Teacher GT:')
    print(f"  {'Track':<14}  {'Hard':>5}  {'Soft':>5}")
    print('  ' + '-' * 30)
    for name in ['pianoplayer', 'motion_v4', 'ArLSTM', 'ArGNN']:
        _, summary = scored[name]
        print(f"  {name:<14}  {summary['hard_accuracy']:>5.3f}  {summary['soft_accuracy']:>5.3f}")


if __name__ == '__main__':
    main()
