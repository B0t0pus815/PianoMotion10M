"""Run evaluate_template on the pianoplayer (Logic Track) fingering for Canon RH.

Usage:
    python evaluate_canon.py \
        --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \
        --gt   eval_data/canon_rh_gt.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from evaluate_template import evaluate, load_ground_truth
from webui.realtime.fingering_engine import generate_fingering


# Same bucket size used when building the GT.
ONSET_BUCKET_SEC = 0.05


def engine_predictions(midi_path: str, hand: str) -> dict[int, list[int]]:
    """Run pianoplayer and return {onset_index: [fingers 1..5]} for one hand.

    Onsets are formed by bucketing simultaneous notes within ONSET_BUCKET_SEC.
    Within a bucket, fingerings are ordered by ascending pitch (matches GT).
    Explicitly requests source='pianoplayer' (the default changed to 'arlstm'
    in 2026-05-21).
    """
    onsets = generate_fingering(midi_path, source='pianoplayer')
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--midi', required=True)
    ap.add_argument('--gt', required=True)
    ap.add_argument('--hand', default=None,
                    help='right|left; defaults to the hand declared in the GT JSON')
    args = ap.parse_args()

    gt_blob = json.loads(Path(args.gt).read_text(encoding='utf-8'))
    hand = args.hand or gt_blob.get('hand', 'right')

    gt_entries = load_ground_truth(args.gt)
    predictions = engine_predictions(args.midi, hand=hand)

    per_onset, summary = evaluate(gt_entries, predictions)

    print(f"song: {gt_blob.get('song')}")
    print(f"hand: {hand}   gt_entries: {len(gt_entries)}   "
          f"engine_onsets({hand}): {len(predictions)}")
    print()
    print(f"{'idx':>3}  {'t':>6}  {'pitches':<14}  {'gt':<10}  "
          f"{'pred':<10}  {'hard':>4}  {'soft':>5}")
    print('-' * 72)
    for s in per_onset:
        t = next((e.get('onset_time') for e in gt_entries
                  if e['onset_index'] == s.onset_index), None)
        t_str = f'{t:6.2f}' if t is not None else '   -- '
        print(f"{s.onset_index:>3}  {t_str}  "
              f"{str(s.midi_notes):<14}  {str(s.gt_fingering):<10}  "
              f"{str(s.pred_fingering):<10}  {s.hard:>4.2f}  {s.soft:>5.3f}")
    print()
    print('summary:')
    for k, v in summary.items():
        print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
