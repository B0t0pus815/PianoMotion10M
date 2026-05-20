"""Dual-Track Cross-Audit: score Logic Track (pianoplayer) AND Visual Track
(motion-based reference) against the same Teacher's Answer-Key GT.

This is the thesis-defensible variant of the v0 24.4% agreement audit — instead
of asking "do they agree?", it asks "which one agrees with the teacher?".

Usage:
    python cross_audit_canon.py \
        --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \
        --gt   eval_data/canon_rh_gt.json \
        --fingertips results/canon_biomech_v4_fingertips.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluate_template import evaluate, load_ground_truth
from evaluate_canon import engine_predictions, ONSET_BUCKET_SEC
from webui.realtime.reference import build_reference


def motion_predictions(midi_path: str,
                       fingertips_path: str,
                       hand: str,
                       frame_width: int = 1920) -> dict[int, list[int]]:
    """Same onset bucketing as engine_predictions, but using motion-based reference."""
    onsets = build_reference(midi_path, fingertips_path, frame_width=frame_width)
    onsets = [e for e in onsets if e.expected_hand == hand]
    onsets.sort(key=lambda e: (e.time, e.pitch))

    buckets: list[list] = []
    bucket_start: float | None = None
    for e in onsets:
        if bucket_start is None or (e.time - bucket_start) > ONSET_BUCKET_SEC:
            buckets.append([e])
            bucket_start = e.time
        else:
            buckets[-1].append(e)

    predictions: dict[int, list[int]] = {}
    for idx, group in enumerate(buckets):
        group.sort(key=lambda e: e.pitch)
        predictions[idx] = [int(e.expected_finger_idx) + 1 for e in group]
    return predictions


def _disagreement_rate(a: dict[int, list[int]],
                       b: dict[int, list[int]],
                       n: int) -> tuple[float, int]:
    """Return (% of GT-covered onsets where a and b disagree, raw count)."""
    diffs = 0
    for i in range(n):
        if a.get(i) != b.get(i):
            diffs += 1
    return diffs / n if n else 0.0, diffs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--midi', required=True)
    ap.add_argument('--gt', required=True)
    ap.add_argument('--fingertips', required=True)
    ap.add_argument('--frame-width', type=int, default=1920)
    ap.add_argument('--hand', default=None)
    args = ap.parse_args()

    gt_blob = json.loads(Path(args.gt).read_text(encoding='utf-8'))
    hand = args.hand or gt_blob.get('hand', 'right')

    gt_entries = load_ground_truth(args.gt)

    logic_pred = engine_predictions(args.midi, hand=hand)
    motion_pred = motion_predictions(args.midi, args.fingertips,
                                     hand=hand, frame_width=args.frame_width)

    logic_per, logic_sum = evaluate(gt_entries, logic_pred)
    motion_per, motion_sum = evaluate(gt_entries, motion_pred)

    n = len(gt_entries)
    dis_rate, dis_n = _disagreement_rate(logic_pred, motion_pred, n)

    print(f"song: {gt_blob.get('song')}")
    print(f"hand: {hand}   gt_entries: {n}")
    print()
    header = f"{'idx':>3}  {'t':>6}  {'pitches':<14}  {'GT':<10}  " \
             f"{'LOGIC':<10}  {'MOTION':<10}  {'L.h/s':>9}  {'M.h/s':>9}"
    print(header)
    print('-' * len(header))
    for ls, ms in zip(logic_per, motion_per):
        t = next((e.get('onset_time') for e in gt_entries
                  if e['onset_index'] == ls.onset_index), None)
        t_str = f'{t:6.2f}' if t is not None else '   -- '
        print(f"{ls.onset_index:>3}  {t_str}  "
              f"{str(ls.midi_notes):<14}  {str(ls.gt_fingering):<10}  "
              f"{str(ls.pred_fingering):<10}  {str(ms.pred_fingering):<10}  "
              f"{ls.hard:.2f}/{ls.soft:.2f}  {ms.hard:.2f}/{ms.soft:.2f}")
    print()
    print('aggregate vs Teacher GT:')
    print(f"  Logic  (pianoplayer)  Hard={logic_sum['hard_accuracy']:.3f}  "
          f"Soft={logic_sum['soft_accuracy']:.3f}")
    print(f"  Motion (biomech v4)   Hard={motion_sum['hard_accuracy']:.3f}  "
          f"Soft={motion_sum['soft_accuracy']:.3f}")
    print()
    print(f"Logic vs Motion disagreement on GT-covered range: "
          f"{dis_n}/{n} = {dis_rate*100:.1f}%")


if __name__ == '__main__':
    main()
