"""Interactive GT builder for piano-fingering audit.

Shows pianoplayer + ArLSTM predictions side-by-side per onset; you confirm
or override. Saves after every onset so q-quit at any time is safe.

Usage:
    python build_gt_interactive.py \\
        --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \\
        --hand right \\
        --out  eval_data/canon_rh_full_gt.json \\
        --resume eval_data/canon_rh_gt.json   # optional: pre-fill from old GT
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from evaluate_canon import ONSET_BUCKET_SEC
from webui.realtime.fingering_engine import generate_fingering
from ramoneda_predict import predict as arlstm_predict


def collect_onsets(midi_path: str, hand: str):
    """Return list of bucketed onsets with both predictors' fingers attached.

    Bucketing is driven by pianoplayer's note stream (the same stream
    `evaluate_canon.engine_predictions` uses), so the resulting onset_index
    aligns 1:1 with predictor predictions. ArLSTM fingers are looked up by
    (round(time,4), pitch); a missing key falls back to 0 (=unknown).
    """
    pp_eo = [e for e in generate_fingering(midi_path, source='pianoplayer')
             if e.expected_hand == hand]
    pp_eo.sort(key=lambda e: (e.time, e.pitch))

    arlstm_fingers, arlstm_info = arlstm_predict(midi_path, hand=hand, kind='ArLSTM')
    arlstm_lookup = {(round(t, 4), int(p)): int(f)
                     for (t, p), f in zip(arlstm_info, arlstm_fingers)}

    buckets: list[list[dict]] = []
    bucket_start: float | None = None
    for e in pp_eo:
        if bucket_start is None or (e.time - bucket_start) > ONSET_BUCKET_SEC:
            buckets.append([])
            bucket_start = e.time
        buckets[-1].append({
            'time': float(e.time),
            'pitch': int(e.pitch),
            'pp': int(e.expected_finger_idx) + 1,
            'arlstm': arlstm_lookup.get((round(e.time, 4), int(e.pitch)), 0),
        })

    onsets = []
    for idx, bucket in enumerate(buckets):
        bucket.sort(key=lambda x: x['pitch'])
        onsets.append({
            'onset_index': idx,
            'onset_time': bucket[0]['time'],
            'midi_notes': [b['pitch'] for b in bucket],
            'pp_fingering': [b['pp'] for b in bucket],
            'arlstm_fingering': [b['arlstm'] for b in bucket],
        })
    return onsets


def load_existing(out_path: str, resume_path: str | None):
    """Build {onset_index: gt_entry} from existing/resume files, if any."""
    answered: dict[int, dict] = {}
    meta: dict | None = None
    for src in [out_path, resume_path]:
        if not src or not os.path.exists(src):
            continue
        blob = json.loads(Path(src).read_text(encoding='utf-8'))
        if meta is None:
            meta = {k: v for k, v in blob.items() if k != 'ground_truth'}
        for e in blob.get('ground_truth', []):
            answered[int(e['onset_index'])] = {
                'onset_index': int(e['onset_index']),
                'onset_time': float(e.get('onset_time', 0.0)),
                'midi_notes': list(e['midi_notes']),
                'fingering':  list(e['fingering']),
            }
    return answered, meta


def save(out_path: str, meta: dict | None, answered: dict[int, dict]) -> None:
    body = dict(meta) if meta else {}
    body['ground_truth'] = [answered[k] for k in sorted(answered.keys())]
    Path(out_path).write_text(
        json.dumps(body, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )


def prompt_one(onset: dict, n_total: int) -> list[int] | None:
    """Return chosen fingering list, or None to skip / sentinel for quit."""
    idx = onset['onset_index']
    t = onset['onset_time']
    notes = onset['midi_notes']
    pp = onset['pp_fingering']
    arl = onset['arlstm_fingering']

    header = f'[{idx+1:>3}/{n_total:>3}] t={t:7.3f}  pitches={notes}'
    is_chord = len(notes) > 1
    agree = (pp == arl)

    print(header)
    if is_chord:
        print(f'  pp     = {pp}')
        print(f'  arlstm = {arl}')
        hint = '[a=pp, b=arlstm, custom e.g. "1,4", s=skip, q=quit'
        hint += ', ENTER=arlstm' if agree else ''
        hint += ']: '
    else:
        if agree:
            print(f'  pp = arlstm = {pp[0]}   (agree)')
            hint = f'[ENTER={pp[0]}, custom 1-5, s=skip, q=quit]: '
        else:
            print(f'  pp={pp[0]}    arlstm={arl[0]}    (DISAGREE)')
            hint = '[a=pp, b=arlstm, custom 1-5, s=skip, q=quit]: '

    while True:
        try:
            raw = input(hint).strip().lower()
        except EOFError:
            return ['__quit__']  # treat ctrl-D as quit
        if raw == 'q':
            return ['__quit__']
        if raw == 's':
            return None
        if raw == 'a':
            return pp
        if raw == 'b':
            return arl
        if raw == '':
            if agree:
                return arl  # both agree, so == pp
            print('  (no consensus, please pick a/b/custom)')
            continue
        # custom — parse list of ints
        parts = [p for p in raw.replace(',', ' ').split() if p]
        try:
            vals = [int(p) for p in parts]
        except ValueError:
            print('  (parse error, try again)')
            continue
        if not all(1 <= v <= 5 for v in vals):
            print('  (fingers must be 1..5)')
            continue
        if len(vals) != len(notes):
            print(f'  (need {len(notes)} fingers for {notes}, got {len(vals)})')
            continue
        return vals


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--midi', required=True)
    ap.add_argument('--hand', default='right', choices=['right', 'left'])
    ap.add_argument('--out', required=True,
                    help='output GT JSON; also re-read on start for resume')
    ap.add_argument('--resume', default=None,
                    help='optional second GT JSON to seed answers from (e.g. partial)')
    ap.add_argument('--song', default=None,
                    help='song name to write into the GT header')
    args = ap.parse_args()

    print(f'building GT for hand={args.hand}, midi={args.midi}')
    onsets = collect_onsets(args.midi, args.hand)
    n_total = len(onsets)
    print(f'{n_total} {args.hand}-hand onset buckets')

    answered, meta = load_existing(args.out, args.resume)
    if meta is None:
        meta = {
            'song': args.song or os.path.basename(args.midi),
            'midi': args.midi,
            'hand': args.hand,
            'fingering_convention': '1=thumb, 2=index, 3=middle, 4=ring, 5=pinky',
        }
    if answered:
        print(f'resuming — {len(answered)}/{n_total} already answered')

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    quit_now = False
    for o in onsets:
        if quit_now:
            break
        if o['onset_index'] in answered:
            continue
        ans = prompt_one(o, n_total)
        if ans is None:
            continue  # skip — not written
        if ans == ['__quit__']:
            quit_now = True
            break
        answered[o['onset_index']] = {
            'onset_index': o['onset_index'],
            'onset_time':  o['onset_time'],
            'midi_notes':  o['midi_notes'],
            'fingering':   ans,
        }
        save(args.out, meta, answered)

    save(args.out, meta, answered)
    print(f'\nsaved {len(answered)}/{n_total} entries → {args.out}')


if __name__ == '__main__':
    main()
