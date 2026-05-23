"""Convert a MIDI file to MusicXML, optionally annotated with ArLSTM fingerings.

For thesis Stage D — OSMD (OpenSheetMusicDisplay) in PracticeScreen needs
a MusicXML file per song. This script generates one from the MIDI,
optionally adding <fingering> tags from the same ArLSTM model the system's
Logic Track uses.

Usage:
    python midi_to_musicxml.py --midi input_songs/Canon....mid \\
        --out songs/canon.musicxml

    # with ArLSTM fingerings annotated into the score
    python midi_to_musicxml.py --midi input_songs/Canon....mid \\
        --out songs/canon.musicxml --annotate-fingering
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import music21


def _annotate_fingerings(score, midi_path: str):
    """Walk each note in the score and attach an ArLSTM-prescribed fingering
    via music21's Fingering articulation. Best-effort: notes ArLSTM doesn't
    cover (rare 6+ chord) are skipped."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from ramoneda_predict import predict
    except ImportError as e:
        print(f'[warn] cannot import ramoneda_predict: {e}; skipping fingering', file=sys.stderr)
        return

    # Get ArLSTM predictions for both hands
    lookup: dict[tuple[int, int], int] = {}
    for hand in ('right', 'left'):
        try:
            fingers, info = predict(midi_path, hand=hand, kind='ArLSTM')
        except RuntimeError:
            continue  # no notes for this hand
        for (t, p), f in zip(info, fingers):
            # round time to 2 decimals to align with score note start times
            lookup[(round(float(t), 2), int(p))] = int(f)

    # Annotation by position: align Nth score-note-of-pitch-P with
    # ArLSTM's Nth (time, pitch=P) prediction. Robust to tempo/offset
    # quirks of music21's MIDI re-quantization.
    from collections import defaultdict

    # Build position-indexed ArLSTM prediction: pitch → [(time, finger), ...]
    pred_by_pitch = defaultdict(list)
    for (t, p), f in sorted(lookup.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        pred_by_pitch[p].append(f)

    # Walk score in time order, track per-pitch position counter
    flat = score.flatten()
    score_pitch_cursor = defaultdict(int)
    n_annotated = 0
    n_seen = 0
    for el in sorted(flat.notes, key=lambda n: float(n.offset)):
        if not hasattr(el, 'pitch'):
            continue
        n_seen += 1
        p = int(el.pitch.midi)
        idx = score_pitch_cursor[p]
        score_pitch_cursor[p] += 1
        if idx < len(pred_by_pitch[p]):
            f = pred_by_pitch[p][idx]
            fg = music21.articulations.Fingering(f)
            el.articulations.append(fg)
            n_annotated += 1

    print(f'[annotate] attached {n_annotated}/{n_seen} fingering tags '
          f'(position-indexed)')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--midi', required=True)
    ap.add_argument('--out', required=True, help='output .musicxml path')
    ap.add_argument('--annotate-fingering', action='store_true',
                    help='also attach ArLSTM-prescribed fingerings to the score')
    args = ap.parse_args()

    print(f'reading {args.midi}')
    score = music21.converter.parse(args.midi)
    print(f'score: {len(score.parts)} parts, '
          f'{sum(len(p.flatten().notes) for p in score.parts)} notes total')

    if args.annotate_fingering:
        _annotate_fingerings(score, args.midi)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    score.write('musicxml', fp=args.out)
    print(f'✓ wrote {args.out} ({os.path.getsize(args.out)} bytes)')


if __name__ == '__main__':
    main()
