"""Per-note agreement: pianoplayer (Logic Track) vs motion-based (current).

For each MIDI note, get the expected_finger from:
  A. fingering_engine.generate_fingering (deterministic DP)
  B. reference.build_reference (motion-based on biomech v4 fingertips)

Then report agreement %, by hand, and dump the disagreements so you can sanity-
check by ear: was pianoplayer's choice closer to what a teacher would say?

Usage:
    python -m webui.realtime.compare_fingerings \\
        --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \\
        --fingertips results/canon_biomech_v4_fingertips.json
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from webui.realtime.fingering_engine import generate_fingering
from webui.realtime.reference import build_reference, FINGER_ORDER


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--midi', required=True)
    p.add_argument('--fingertips', required=True)
    p.add_argument('--ref-width', type=int, default=1920)
    p.add_argument('--show-diffs', type=int, default=20,
                   help='print first N disagreements')
    args = p.parse_args()

    logic = generate_fingering(args.midi)
    motion = build_reference(args.midi, args.fingertips, frame_width=args.ref_width)

    if len(logic) != len(motion):
        print(f'WARN: count mismatch  logic={len(logic)}  motion={len(motion)}')
        n = min(len(logic), len(motion))
        logic, motion = logic[:n], motion[:n]
    else:
        n = len(logic)
    print(f'Comparing {n} notes\n')

    # Per-note finger agreement (hand should already match — both use HAND_SPLIT=60)
    matches = 0
    hand_mismatch = 0
    confusion = Counter()  # (logic_finger, motion_finger) -> count
    by_hand = defaultdict(lambda: [0, 0])  # hand -> [matches, total]
    diffs = []

    for a, b in zip(logic, motion):
        if a.pitch != b.pitch or abs(a.time - b.time) > 0.05:
            print(f'  ! time/pitch drift at t={a.time:.2f}: {a.pitch} vs {b.pitch}')
            continue
        if a.expected_hand != b.expected_hand:
            hand_mismatch += 1
            continue
        by_hand[a.expected_hand][1] += 1
        if a.expected_finger == b.expected_finger:
            matches += 1
            by_hand[a.expected_hand][0] += 1
        else:
            confusion[(a.expected_finger, b.expected_finger)] += 1
            diffs.append((a, b))

    print(f'=== Agreement (Logic Track vs Motion-based) ===')
    print(f'  Total compared:    {n}')
    print(f'  Same finger:       {matches}  ({100 * matches / max(n, 1):.1f}%)')
    print(f'  Different finger:  {n - matches - hand_mismatch}')
    print(f'  Different hand:    {hand_mismatch}')
    print()
    print('  By hand:')
    for h, (m, t) in by_hand.items():
        print(f'    {h:5s}:  {m:3d}/{t:3d}  ({100 * m / max(t, 1):.1f}%)')
    print()

    print('  Top confusion pairs (logic → motion):')
    for (lg, mt), c in confusion.most_common(8):
        idx_l = FINGER_ORDER.index(lg) + 1
        idx_m = FINGER_ORDER.index(mt) + 1
        delta = idx_l - idx_m
        print(f'    {lg:7s}({idx_l}) → {mt:7s}({idx_m})  delta={delta:+d}  count={c}')

    print()
    print(f'  First {args.show_diffs} disagreements:')
    for a, b in diffs[:args.show_diffs]:
        h = a.expected_hand[0].upper()
        print(f'    t={a.time:6.2f}  pitch={a.pitch:3d}  {h}  '
              f'logic={a.expected_finger:7s}  motion={b.expected_finger}')


if __name__ == '__main__':
    main()
