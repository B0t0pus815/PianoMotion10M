"""note_align.py — sequence alignment between a PLAYED note stream and the
EXPECTED (reference) note stream.

Why this exists
---------------
The live loop in runner.py greedily matches each played note to a nearby
expected onset (±MATCH_WINDOW, same pitch) and SILENTLY DROPS misses and extras.
So "did you play the right notes" is never measured — only finger accuracy on
the notes that happened to line up, which conflates a wrong-note error with a
wrong-finger error.

This module does a global Needleman–Wunsch alignment on the two pitch sequences
(ordered by onset; chords sorted by pitch so both sides order them the same
way). It is TEMPO-INVARIANT — it aligns by note ORDER, not absolute time — so a
user playing the right notes at any tempo scores 100% note accuracy. It surfaces:

  - correct / wrong / missing / extra note counts (note accuracy, decoupled from
    fingering),
  - the matched (played↔expected) pairs the comparator should judge fingering on,
  - a played→expected time warp (matched onset times) → est. tempo scale + offset,
    which the A/V-MIDI sync step can use instead of a manual slate.

Standalone use (grade one MIDI against a reference, no video needed):
    python -m webui.realtime.note_align played.mid results/canon_clean.mid
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Optional

# Needleman–Wunsch scores. MATCH must beat a substitution, and a substitution
# must beat the miss+extra pair (-2) so a single wrong pitch aligns as one
# 'wrong' rather than a spurious missing+extra.
MATCH_SCORE = 2.0
MISMATCH_SCORE = -1.0
GAP_SCORE = -1.0


@dataclass
class AlignOp:
    kind: str                      # 'match' | 'wrong' | 'extra' | 'missing'
    played_idx: Optional[int]
    expected_idx: Optional[int]
    played_pitch: Optional[int] = None
    expected_pitch: Optional[int] = None


@dataclass
class AlignResult:
    ops: list
    n_played: int
    n_expected: int
    correct: int
    wrong: int
    missing: int
    extra: int
    matched_pairs: list            # [(played_idx, expected_idx)] for 'match' ops
    warp: list                     # [(played_time, expected_time)] for matches

    @property
    def note_accuracy(self) -> float:
        """Fraction of the reference's notes the user played correctly."""
        return 1.0 if self.n_expected == 0 else self.correct / self.n_expected


def _pt(note) -> tuple:
    """Accept (time, pitch) tuples/lists or objects with .time/.pitch."""
    if isinstance(note, (tuple, list)):
        return float(note[0]), int(note[1])
    return float(note.time), int(note.pitch)


def align(played, expected) -> AlignResult:
    """Globally align a played note stream to an expected one.

    `played`/`expected` are iterables of (time, pitch) tuples or objects with
    .time/.pitch (e.g. ExpectedOnset). Returns an AlignResult.
    """
    P = sorted((_pt(n) for n in played), key=lambda x: (x[0], x[1]))
    E = sorted((_pt(n) for n in expected), key=lambda x: (x[0], x[1]))
    n, m = len(P), len(E)

    # DP score table; f[i][j] = best score aligning P[:i] with E[:j].
    f = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        f[i][0] = i * GAP_SCORE
    for j in range(1, m + 1):
        f[0][j] = j * GAP_SCORE
    for i in range(1, n + 1):
        pi = P[i - 1][1]
        fi, fim1 = f[i], f[i - 1]
        for j in range(1, m + 1):
            ej = E[j - 1][1]
            diag = fim1[j - 1] + (MATCH_SCORE if pi == ej else MISMATCH_SCORE)
            up = fim1[j] + GAP_SCORE        # P[i-1] is an extra (insertion)
            left = fi[j - 1] + GAP_SCORE    # E[j-1] is missing (deletion)
            fi[j] = diag if (diag >= up and diag >= left) else (up if up >= left else left)

    # Traceback. DP values are exact (sums of ±1, ±2), so == comparisons are safe.
    ops = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            pi, ej = P[i - 1][1], E[j - 1][1]
            diag = f[i - 1][j - 1] + (MATCH_SCORE if pi == ej else MISMATCH_SCORE)
            if f[i][j] == diag:
                kind = 'match' if pi == ej else 'wrong'
                ops.append(AlignOp(kind, i - 1, j - 1, pi, ej))
                i -= 1
                j -= 1
                continue
        if i > 0 and f[i][j] == f[i - 1][j] + GAP_SCORE:
            ops.append(AlignOp('extra', i - 1, None, P[i - 1][1], None))
            i -= 1
            continue
        ops.append(AlignOp('missing', None, j - 1, None, E[j - 1][1]))
        j -= 1
    ops.reverse()

    correct = wrong = missing = extra = 0
    matched_pairs, warp = [], []
    for op in ops:
        if op.kind == 'match':
            correct += 1
            matched_pairs.append((op.played_idx, op.expected_idx))
            warp.append((P[op.played_idx][0], E[op.expected_idx][0]))
        elif op.kind == 'wrong':
            wrong += 1
        elif op.kind == 'extra':
            extra += 1
        else:
            missing += 1

    return AlignResult(ops=ops, n_played=n, n_expected=m,
                       correct=correct, wrong=wrong, missing=missing, extra=extra,
                       matched_pairs=matched_pairs, warp=warp)


def build_match_map(played, reference, expected=None) -> dict:
    """Map each correctly-played note's (time, pitch) → an onset INDEX it aligns
    to (only 'match' pairs; wrong/extra notes are absent).

    Lets the live judge attribute fingering via the global alignment instead of
    a greedy ±window search — so a missed or extra note no longer shifts every
    later note onto the wrong expected onset. Keys are (float time, int pitch)
    exactly as in `played`, so callers can look up a fired event directly.

    `reference` must be the FAITHFUL reference note times (e.g. raw MIDI), so the
    alignment isn't perturbed by per-note time offsets. If `expected` is given
    (e.g. generate_fingering's ExpectedOnset list — same notes as `reference` but
    with shifted .time), the returned index is into `expected`, bridged by
    (pitch, occurrence-rank) which is stable under those shifts. Otherwise the
    index is into the (time,pitch)-sorted `reference`.
    """
    res = align(played, reference)
    P = sorted((_pt(n) for n in played), key=lambda x: (x[0], x[1]))
    if expected is None:
        return {P[pi]: ri for (pi, ri) in res.matched_pairs}

    # Bridge reference-sorted-index → expected-original-index via (pitch, rank),
    # ranking each side independently in (time, pitch) order so a uniform per-note
    # time offset (which preserves same-pitch ordering) doesn't break the pairing.
    from collections import defaultdict
    R = sorted((_pt(n) for n in reference), key=lambda x: (x[0], x[1]))
    ref_rank, cnt = [], defaultdict(int)
    for _, p in R:
        ref_rank.append((p, cnt[p]))
        cnt[p] += 1
    exp_idx_by_rank, cnt2 = {}, defaultdict(int)
    for oi in sorted(range(len(expected)),
                     key=lambda i: (_pt(expected[i])[0], _pt(expected[i])[1])):
        p = _pt(expected[oi])[1]
        exp_idx_by_rank[(p, cnt2[p])] = oi
        cnt2[p] += 1
    out = {}
    for (pi, ri) in res.matched_pairs:
        ei = exp_idx_by_rank.get(ref_rank[ri])
        if ei is not None:
            out[P[pi]] = ei
    return out


def ref_time_by_onset(expected, reference) -> list:
    """Faithful reference onset time for each `expected` index.

    `generate_fingering`'s ExpectedOnset .time is the note start, but its
    ordering can drift from raw MIDI, so rhythm grading should compare against
    the FAITHFUL reference time. This pairs each expected onset to a reference
    note via the same (pitch, occurrence-rank) bridge `build_match_map` uses —
    both sides ranked independently in (time, pitch) order so a uniform per-note
    time offset on `expected` (which preserves same-pitch ordering) doesn't break
    the pairing. Returns a list aligned to `expected` indices; an unpaired onset
    (count mismatch) falls back to its own .time.
    """
    from collections import defaultdict
    R = sorted((_pt(n) for n in reference), key=lambda x: (x[0], x[1]))
    ref_time_by_rank, cnt = {}, defaultdict(int)
    for t, p in R:
        ref_time_by_rank[(p, cnt[p])] = t
        cnt[p] += 1
    order = sorted(range(len(expected)),
                   key=lambda i: (_pt(expected[i])[0], _pt(expected[i])[1]))
    out = [0.0] * len(expected)
    cnt2 = defaultdict(int)
    for oi in order:
        et, p = _pt(expected[oi])
        out[oi] = ref_time_by_rank.get((p, cnt2[p]), et)
        cnt2[p] += 1
    return out


def estimate_offset_scale(warp) -> tuple:
    """Least-squares fit expected_t ≈ scale * played_t + offset over matched
    pairs. Returns (scale, offset, rms_residual_seconds). scale>1 means the
    reference is slower than the performance (user played faster)."""
    if len(warp) < 2:
        return (1.0, 0.0, 0.0)
    pt = [w[0] for w in warp]
    et = [w[1] for w in warp]
    n = len(pt)
    sx, sy = sum(pt), sum(et)
    sxx = sum(x * x for x in pt)
    sxy = sum(x * y for x, y in zip(pt, et))
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-9:
        return (1.0, (sy - sx) / n, 0.0)
    scale = (n * sxy - sx * sy) / denom
    offset = (sy - scale * sx) / n
    rms = math.sqrt(sum((et[k] - (scale * pt[k] + offset)) ** 2 for k in range(n)) / n)
    return (scale, offset, rms)


def notes_from_midi(path: str) -> list:
    """Load a MIDI as a time/pitch-sorted list of (time, pitch)."""
    import pretty_midi
    if not os.path.exists(path):
        raise FileNotFoundError(f'MIDI not found: {path}')
    pm = pretty_midi.PrettyMIDI(path)
    notes = [(float(nn.start), int(nn.pitch))
             for inst in pm.instruments if not inst.is_drum
             for nn in inst.notes]
    notes.sort(key=lambda x: (x[0], x[1]))
    return notes


def summary(result: AlignResult) -> str:
    scale, offset, rms = estimate_offset_scale(result.warp)
    return (
        f'note accuracy: {result.note_accuracy * 100:5.1f}%  '
        f'({result.correct}/{result.n_expected} correct)\n'
        f'  wrong={result.wrong}  missing={result.missing}  extra={result.extra}  '
        f'played={result.n_played}\n'
        f'  tempo: played→ref scale={scale:.3f}  offset={offset:+.2f}s  '
        f'align_rms={rms:.3f}s'
    )


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description='Grade a played MIDI against a reference MIDI (note accuracy, '
                    'wrong/missing/extra, tempo warp). Tempo-invariant.')
    ap.add_argument('played', help='played .mid')
    ap.add_argument('reference', help='reference .mid')
    args = ap.parse_args()
    P = notes_from_midi(args.played)
    E = notes_from_midi(args.reference)
    print(f'played   {args.played}: {len(P)} notes')
    print(f'reference {args.reference}: {len(E)} notes')
    print(summary(align(P, E)))


if __name__ == '__main__':
    main()
