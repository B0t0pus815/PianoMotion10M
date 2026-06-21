"""Reusable jitter-generator: warp a clean MIDI into an 'unsteady' performance.

Adds seeded per-note Gaussian timing jitter while preserving pitches and
durations, so note-alignment still pairs each played note to its clean reference
onset — only the TIMING differs. That makes the runner's rhythm hints (rush/drag,
deviation from the running tempo) actually fire, which a clean self-replay never
does. Used to demo / test the rhythm path; reusable as a CLI or by importing
`jitter_midi`.

CLI:
    python -m tests.fixtures.make_warped clean.mid warped.mid --std 0.08 --seed 42
"""
from __future__ import annotations

import argparse

import numpy as np
import pretty_midi


def jitter_midi(src: str, dst: str, std_s: float = 0.08, seed: int = 42) -> int:
    """Write `src` to `dst` with N(0, std_s) jitter added to every note's start
    (end shifted to keep duration; starts clamped at 0 and re-sorted). Returns
    the number of notes written."""
    rng = np.random.default_rng(seed)
    pm = pretty_midi.PrettyMIDI(src)
    for inst in pm.instruments:
        for n in inst.notes:
            dur = n.end - n.start
            n.start = max(0.0, n.start + float(rng.normal(0.0, std_s)))
            n.end = n.start + dur
        inst.notes.sort(key=lambda x: x.start)
    pm.write(dst)
    return sum(len(i.notes) for i in pm.instruments)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('src', help='clean input .mid')
    ap.add_argument('dst', help='warped output .mid')
    ap.add_argument('--std', type=float, default=0.08,
                    help='jitter standard deviation in seconds (default 0.08 = 80ms)')
    ap.add_argument('--seed', type=int, default=42, help='RNG seed (default 42)')
    args = ap.parse_args()
    n = jitter_midi(args.src, args.dst, std_s=args.std, seed=args.seed)
    print(f'wrote {args.dst}: {n} notes (jitter std={args.std * 1000:.0f}ms, seed={args.seed})')


if __name__ == '__main__':
    main()
