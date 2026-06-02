"""Self-check: feed the reference fingertips back through the comparator.

This bypasses MediaPipe and the camera entirely — it just confirms that:
  1. reference.build_reference() produces consistent expected_finger labels
  2. comparator.compare_onset() recovers those labels from raw fingertip
     trajectories using the same press-velocity heuristic

A perfect-input → 100% correct result validates the comparator logic.
A real user with a real camera will degrade from that ceiling based on
detection quality + their actual playing.

Usage:
    python -m webui.realtime.selfcheck \\
        --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \\
        --reference results/canon_biomech_v4_fingertips.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from webui.realtime.reference import build_reference
from webui.realtime.comparator import HandHistory, compare_onset, OnsetResult
from webui.realtime.hand_tracker import HandPose, TIP_INDICES


def _make_handpose_from_tips(tips_xy: np.ndarray, handedness: str) -> HandPose:
    """Synthesize a 21-landmark HandPose where only the 5 fingertip slots
    matter — wrist and joints are zeroed, which is fine because the
    comparator only reads fingertips."""
    arr = np.zeros((21, 3), dtype=np.float32)
    for i, name in enumerate(['thumb', 'index', 'middle', 'ring', 'pinky']):
        arr[TIP_INDICES[name], 0] = tips_xy[i, 0]
        arr[TIP_INDICES[name], 1] = tips_xy[i, 1]
    return HandPose(landmarks=arr, handedness=handedness, score=1.0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--midi', required=True)
    p.add_argument('--reference', required=True)
    p.add_argument('--ref-width', type=int, default=1920)
    args = p.parse_args()

    expected = build_reference(args.midi, args.reference, frame_width=args.ref_width)
    print(f'[ref] {len(expected)} expected onsets')

    with open(args.reference) as f:
        ft = json.load(f)
    fps = ft['fps']
    right_tips = np.array(ft['right'], dtype=np.float32)
    left_tips = np.array(ft['left'], dtype=np.float32)
    n_frames = right_tips.shape[0]

    history = HandHistory(capacity=180)
    expected_sorted = sorted(expected, key=lambda x: x.time)
    onset_cursor = 0
    results = []
    for i in range(n_frames):
        t = i / fps
        hands = {
            'right': _make_handpose_from_tips(right_tips[i], 'right'),
            'left':  _make_handpose_from_tips(left_tips[i],  'left'),
        }
        history.push(t, hands)

        # Evaluate any expected onset that has now arrived in real time
        while (onset_cursor < len(expected_sorted)
               and expected_sorted[onset_cursor].time <= t):
            r = compare_onset(history, expected_sorted[onset_cursor])
            results.append(r)
            onset_cursor += 1

    n = len(results)
    correct = sum(1 for r in results if r.correct)
    no_hand = sum(1 for r in results if r.detected_finger is None)
    wrong = n - correct - no_hand
    print('\n=== Self-check ===')
    print(f'  Total:           {n}')
    print(f'  Correct:         {correct}  ({100 * correct / max(n, 1):.1f}%)')
    print(f'  Wrong finger:    {wrong}')
    print(f'  No hand:         {no_hand}')

    by_hand = {'left': [0, 0], 'right': [0, 0]}
    for r in results:
        by_hand[r.expected_hand][1] += 1
        if r.correct:
            by_hand[r.expected_hand][0] += 1
    for h, (c, t) in by_hand.items():
        print(f'  {h:5s}:  {c:3d}/{t:3d}  ({100 * c / max(t, 1):.1f}%)')

    if wrong > 0:
        print('\n  First 5 wrong:')
        for r in [x for x in results if not x.correct and x.detected_finger][:5]:
            print(f'    t={r.time:5.2f}  pitch={r.pitch}  '
                  f'expected={r.expected_hand}/{r.expected_finger}  '
                  f'detected={r.detected_finger}  conf={r.confidence:.2f}')


if __name__ == '__main__':
    main()
