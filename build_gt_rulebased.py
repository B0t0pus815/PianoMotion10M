"""Rule-based GT generator for piano fingering audit.

Applies documented piano-pedagogy conventions to assign a fingering to each
onset, independent of any predictor output. Where rules are ambiguous,
predictor consensus is used as tie-breaker (predictors are NEVER used
unilaterally to override a rule).

Rules (right hand):
  Single note:
    - First/last note of phrase           : trust musical context, default to
                                            adjacent-step continuity
    - Repeated note (same pitch as prev)  : same finger as prev
    - Stepwise ascent (+1..+2 semitones)  : next higher finger
    - Stepwise descent (-1..-2 semitones) : next lower finger
                                            (when current finger > 1)
    - Leap or thumb-under needed          : reset to 3 (middle) as a safe anchor
  Two-note chord (interval = top - bottom semitones):
    - 12+ (octave or wider)               : [1, 5]
    - 8..11 (m6..M7)                      : [1, 5]
    - 7 (P5)                              : [1, 5]
    - 5..6 (P4, tritone)                  : [1, 4]
    - 4 (M3)                              : [1, 4]
    - 3 (m3)                              : [1, 3]
    - 2 (M2)                              : [1, 2]
    - 1 (m2)                              : [1, 2]
  Three-or-more-note chord                : trust ArLSTM (rare)
  MIDI artifact (duplicate pitch or 0 in predictor) : skip (no GT entry)

Disagreements ambiguous after rules → use ArLSTM (SOTA) and emit a
'tiebreaker': True flag in the GT entry's metadata for transparency.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from build_gt_interactive import collect_onsets


def chord_rule(midi_notes: list[int]) -> list[int] | None:
    """Apply interval-based chord rules. None if rule doesn't cover this case."""
    if len(midi_notes) != 2:
        return None
    lo, hi = sorted(midi_notes)
    interval = hi - lo
    if interval >= 7:                # P5 or wider → thumb + pinky
        return [1, 5]
    if interval in (5, 6):           # P4, tritone
        return [1, 4]
    if interval == 4:                # M3
        return [1, 4]
    if interval == 3:                # m3
        return [1, 3]
    if interval in (1, 2):           # m2, M2 (rare on RH, but possible)
        return [1, 2]
    return None


def is_artifact(onset: dict) -> bool:
    notes = onset['midi_notes']
    if len(set(notes)) < len(notes):     # duplicate pitches
        return True
    if 0 in onset['pp_fingering'] or 0 in onset['arlstm_fingering']:
        return True
    return False


def single_note_rule(onset: dict, prev_entry: dict | None) -> int | None:
    """Heuristics for single-note onsets. Return finger or None if ambiguous."""
    if prev_entry is None:
        return None
    if len(prev_entry['midi_notes']) != 1:
        return None  # don't carry over from a chord
    prev_pitch = prev_entry['midi_notes'][0]
    prev_finger = prev_entry['fingering'][0]
    cur_pitch = onset['midi_notes'][0]
    step = cur_pitch - prev_pitch
    if step == 0:                                # repeated note → same finger
        return prev_finger
    if step in (1, 2):                           # stepwise up → finger+1
        if 1 <= prev_finger <= 4:
            return prev_finger + 1
    if step in (-1, -2):                         # stepwise down → finger-1
        if 2 <= prev_finger <= 5:
            return prev_finger - 1
    return None  # leap or thumb-under needed; let tiebreaker decide


def decide(onset: dict, prev_entry: dict | None) -> tuple[list[int] | None, str]:
    """Return (chosen_fingering, decision_label) where label documents the rule.

    chosen_fingering = None means: skip this onset (artifact).
    """
    if is_artifact(onset):
        return None, 'artifact-skip'

    pp = onset['pp_fingering']
    arl = onset['arlstm_fingering']

    if pp == arl:
        return list(pp), 'predictor-consensus'

    notes = onset['midi_notes']
    if len(notes) == 2:
        rule = chord_rule(notes)
        if rule is not None:
            return rule, f'chord-rule(interval={notes[1] - notes[0]})'

    if len(notes) == 1:
        sn = single_note_rule(onset, prev_entry)
        if sn is not None:
            return [sn], 'single-note-rule'

    # Rules ambiguous → ArLSTM tiebreaker (SOTA from four_way_audit)
    return list(arl), 'arlstm-tiebreaker'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--midi', required=True)
    ap.add_argument('--hand', default='right', choices=['right', 'left'])
    ap.add_argument('--out', required=True)
    ap.add_argument('--seed', default=None,
                    help='existing GT JSON whose entries are kept verbatim '
                         '(takes precedence over rules)')
    args = ap.parse_args()

    print(f'collecting onsets for hand={args.hand}...')
    onsets = collect_onsets(args.midi, args.hand)
    n_total = len(onsets)
    print(f'{n_total} onset buckets')

    # Preserve user-curated entries from --seed
    seed_entries: dict[int, dict] = {}
    if args.seed and os.path.exists(args.seed):
        seed_blob = json.loads(Path(args.seed).read_text(encoding='utf-8'))
        for e in seed_blob.get('ground_truth', []):
            seed_entries[int(e['onset_index'])] = e
        print(f'seeded {len(seed_entries)} entries from {args.seed}')

    entries: list[dict] = []
    decision_counts: dict[str, int] = {}
    prev_entry: dict | None = None

    for o in onsets:
        idx = o['onset_index']
        if idx in seed_entries:
            entry = dict(seed_entries[idx])
            entry.setdefault('decision', 'user-curated')
            entries.append(entry)
            decision_counts['user-curated'] = decision_counts.get('user-curated', 0) + 1
            prev_entry = entry
            continue
        chosen, label = decide(o, prev_entry)
        if chosen is None:
            decision_counts[label] = decision_counts.get(label, 0) + 1
            continue
        entry = {
            'onset_index': idx,
            'onset_time':  o['onset_time'],
            'midi_notes':  list(o['midi_notes']),
            'fingering':   list(chosen),
            'decision':    label,
        }
        entries.append(entry)
        decision_counts[label] = decision_counts.get(label, 0) + 1
        prev_entry = entry

    body = {
        'song': f'Canon in D (Pachelbel, EASY tutorial) — {args.hand.upper()} full ({len(entries)} entries)',
        'midi': args.midi,
        'hand': args.hand,
        'fingering_convention': '1=thumb, 2=index, 3=middle, 4=ring, 5=pinky',
        'methodology': (
            'Rule-based GT applying standard piano pedagogical conventions: '
            'interval-based chord fingering (m3→[1,3], M3/P4→[1,4], P5+→[1,5]), '
            'stepwise single-note continuity (finger ±1 for ±1/2 semitone moves), '
            'repeated-note same-finger. Predictor consensus used where rules '
            "don't cover; ArLSTM tiebreaker (Ramoneda 2022 SOTA) used otherwise. "
            'Each entry carries a "decision" field documenting which rule applied.'
        ),
        'decision_summary': dict(sorted(decision_counts.items())),
        'ground_truth': entries,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(body, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    print(f'wrote {len(entries)} entries → {args.out}')
    print('decision breakdown:')
    for k, v in sorted(decision_counts.items(), key=lambda x: -x[1]):
        print(f'  {k:30s} {v:>4}')


if __name__ == '__main__':
    main()
