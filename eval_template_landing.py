"""Finger-on-Key Landing Accuracy — goal-aligned eval for the "correct template".

Unlike benchmark_pose_distance.py (which measures L1 distance to PianoMotion10M
GT pose — the metric that wrongly favored diffusion v7), this measures the thing
the deployment actually cares about: at each MIDI onset, does the rendered hand
land the RIGHT finger on the lit key?

Two metrics, reported side by side:

  ★ RECOMMENDED-finger landing  (the deployment-true reference fidelity)
      Does the fingertip of the finger the system *recommends* (the Logic-Track
      judge: ArLSTM by default, or pianoplayer) land on the lit key (<30px)?
      This is the number that says "the demo video is a faithful fingering
      reference" — when it's low, the hand shows a DIFFERENT finger than the one
      the user is told to use. Requires running the Logic Track (--fingering-source).

    nearest-finger landing  (loose visual proxy — kept for sanity)
      Does ANY fingertip of the correct hand land on the key? Says "a hand is
      roughly in the right place" but NOT that the right finger is there. This is
      the original metric; it needs no torch and runs in <1s.

CRITICAL geometry: both metrics use --key-width (default DEFAULT_KEY_WIDTH=51.87,
shared with the render in add_keyboard_overlay). Passing the wrong key width moves
every key center and fakes a ~0.71 "outward gain" on the hands — see git history /
memory. The render and this eval MUST agree on key width.

    # full (recommended-finger, uses deployed ArLSTM judge):
    python eval_template_landing.py \
        --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \
        --fingering-source arlstm \
        results/canon_biomech_v4_fingertips.json \
        results/canon_arlstm_fingertips.json

    # fast nearest-only (no torch, no Logic Track):
    python eval_template_landing.py --midi ... --fingering-source none \
        results/canon_biomech_v4_fingertips.json
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile

import numpy as np
import pretty_midi

from add_keyboard_overlay import (
    pitch_key_center_x, HAND_SPLIT, DEFAULT_KEY_WIDTH, FINGER_ORDER,
)

NEAR_PX = 30.0   # <30px  → confirmed finger-on-key   (codebase FINGER_NEAR_PX)
FAR_PX = 60.0    # 30-60  → borderline; >60 → miss     (codebase FINGER_FAR_PX)


def _band(d):
    """X-pixel distance → landing band."""
    return 'land' if d < NEAR_PX else ('edge' if d < FAR_PX else 'miss')


def clean_midi_like_render(src_path, merge_gap=0.15):
    """Reproduce simple_natural.py's MIDI cleaning (merge same-pitch notes whose
    gap < merge_gap) and write a temp cleaned .mid; return its path.

    WHY this matters for the gate: the render only places a hand for the cleaned
    note set, and its Logic Track (apply_arlstm_fingering) runs ArLSTM on THIS
    cleaned MIDI. Scoring against the raw MIDI instead invents ~14% extra
    repeated-note onsets the render never positioned a finger for (pure miss
    inflation) AND feeds the judge a different note sequence than the render saw
    (fake render↔judge divergence). On Canon this gap is 53.5% (raw) vs 61.5%
    (cleaned). Keep this in lockstep with simple_natural.py:716.
    """
    pm = pretty_midi.PrettyMIDI(src_path)
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        by_pitch = {}
        for n in inst.notes:
            by_pitch.setdefault(n.pitch, []).append(n)
        new_notes = []
        for _pitch, notes in by_pitch.items():
            notes.sort(key=lambda x: x.start)
            merged = [copy.copy(notes[0])]
            for n in notes[1:]:
                prev = merged[-1]
                if n.start - prev.end < merge_gap:
                    prev.end = max(prev.end, n.end)
                else:
                    merged.append(copy.copy(n))
            new_notes.extend(merged)
        inst.notes = new_notes
    fd, path = tempfile.mkstemp(suffix='.cleaned.mid', prefix='eval_landing_')
    os.close(fd)
    pm.write(path)
    return path


def load_onsets(midi_path):
    """Flatten non-drum notes → list of (time, pitch). Hand via HAND_SPLIT."""
    pm = pretty_midi.PrettyMIDI(midi_path)
    notes = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        notes.extend(inst.notes)
    notes.sort(key=lambda n: n.start)
    return [(float(n.start), int(n.pitch)) for n in notes]


def build_assigned_lookup(midi_path, source, use_override=True, time_tol=0.05):
    """Return a callable (time, pitch) -> recommended finger NAME, using the
    deployed Logic Track. `source='none'` (or an import/run failure) returns None,
    which makes the eval fall back to nearest-finger only.

    Lazy import keeps `none` mode free of torch *and* pianoplayer.
    """
    if source == 'none':
        return None
    try:
        from webui.realtime.fingering_engine import generate_fingering
        onsets = generate_fingering(midi_path, source=source,
                                    use_override=use_override)
    except Exception as exc:  # noqa: BLE001 — degrade, never crash the eval
        print(f'[warn] Logic Track ({source}) unavailable → '
              f'recommended-finger metric skipped: {exc}')
        return None

    by_pitch = {}
    for e in onsets:
        by_pitch.setdefault(e.pitch, []).append((e.time, e.expected_finger))
    for p in by_pitch:
        by_pitch[p].sort()

    def lookup(t, pitch):
        cands = by_pitch.get(pitch)
        if not cands:
            return None
        best = min(cands, key=lambda c: abs(c[0] - t))
        return best[1] if abs(best[0] - t) <= time_tol else None

    return lookup


def eval_template(fingertips_path, onsets, frame_width=1920,
                  key_width=DEFAULT_KEY_WIDTH, assigned_lookup=None):
    data = json.load(open(fingertips_path))
    fps = data.get('fps', 30)
    right = np.array(data['right'], dtype=np.float64)   # (T, 5, 2)
    left = np.array(data['left'], dtype=np.float64)
    # Fingertip array column order — respect the JSON's own ordering if present.
    finger_order = data.get('finger_order', FINGER_ORDER)
    name_to_col = {n: i for i, n in enumerate(finger_order)}
    n_frames = right.shape[0]

    rows = []
    for t, pitch in onsets:
        frame = int(round(t * fps))
        if frame >= n_frames:
            continue
        # '>' (not '>=') to match the render's split in add_keyboard_overlay —
        # pitch == HAND_SPLIT is a LEFT-hand note there.
        hand = 'right' if pitch > HAND_SPLIT else 'left'
        tips = right[frame] if hand == 'right' else left[frame]   # (5, 2)
        # key_width MUST match the render geometry (see module docstring).
        key_x = pitch_key_center_x(pitch, frame_width, key_width)
        dx = np.abs(tips[:, 0] - key_x)        # X distance per finger

        nf = int(np.argmin(dx))                # nearest fingertip
        row = dict(pitch=pitch, hand=hand, d_near=float(dx[nf]),
                   nf=nf, band_near=_band(float(dx[nf])),
                   assigned_col=None, d_assigned=None, band_assigned=None)

        if assigned_lookup is not None:
            fin_name = assigned_lookup(t, pitch)
            col = name_to_col.get(fin_name) if fin_name is not None else None
            if col is not None:
                row['assigned_col'] = col
                row['d_assigned'] = float(dx[col])
                row['band_assigned'] = _band(float(dx[col]))
        rows.append(row)
    return rows, fps, n_frames


def _hand_rate(rows, hand, band_key):
    hr = [r for r in rows if r['hand'] == hand and r[band_key] is not None]
    if not hr:
        return 0.0, 0
    return 100 * sum(1 for r in hr if r[band_key] == 'land') / len(hr), len(hr)


def summarize(rows, label, has_assigned):
    n = len(rows)
    if n == 0:
        print(f'{label}: no onsets in range')
        return None
    out = dict(n=n)
    print(f'\n=== {label}  (n={n} onsets) ===')

    if has_assigned:
        scored = [r for r in rows if r['band_assigned'] is not None]
        ns = len(scored)
        if ns:
            a_land = sum(1 for r in scored if r['band_assigned'] == 'land')
            disagree = sum(1 for r in scored if r['assigned_col'] != r['nf'])
            rl, rn = _hand_rate(rows, 'right', 'band_assigned')
            ll, ln = _hand_rate(rows, 'left', 'band_assigned')
            out.update(rec_land_pct=100 * a_land / ns, rec_n=ns,
                       rec_rh=rl, rec_lh=ll)
            print(f'  ★ RECOMMENDED-finger landing (<{NEAR_PX:.0f}px): '
                  f'{a_land:4d}/{ns}  ({100 * a_land / ns:5.1f}%)   '
                  f'[deployment-true reference fidelity]')
            print(f'      RH {rl:5.1f}% (n={rn})   LH {ll:5.1f}% (n={ln})   '
                  f'coverage {ns}/{n}')
            print(f'      recommended ≠ nearest finger: '
                  f'{100 * disagree / ns:5.1f}%')
        else:
            print('  ★ RECOMMENDED-finger landing: no notes matched the '
                  'Logic Track (check --fingering-source / time alignment)')

    land = sum(1 for r in rows if r['band_near'] == 'land')
    edge = sum(1 for r in rows if r['band_near'] == 'edge')
    miss = sum(1 for r in rows if r['band_near'] == 'miss')
    mean_dx = np.mean([r['d_near'] for r in rows])
    rl, rn = _hand_rate(rows, 'right', 'band_near')
    ll, ln = _hand_rate(rows, 'left', 'band_near')
    out.update(near_land_pct=100 * land / n, near_mean_dx=float(mean_dx),
               near_rh=rl, near_lh=ll)
    tag = '  nearest-finger landing (any finger on key):' if has_assigned \
        else f'  Landing (<{NEAR_PX:.0f}px):'
    print(f'{tag} {land:4d}  ({100 * land / n:5.1f}%)   '
          f'RH {rl:.0f}% / LH {ll:.0f}%')
    if not has_assigned:
        print(f'  Borderline (30-60):   {edge:4d}  ({100 * edge / n:5.1f}%)')
        print(f'  Miss (>{FAR_PX:.0f}px):       {miss:4d}  ({100 * miss / n:5.1f}%)')
    print(f'  mean |Δx| (nearest) = {mean_dx:5.1f}px')
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('fingertips', nargs='+', help='one or more *_fingertips.json')
    p.add_argument('--midi', required=True)
    p.add_argument('--frame-width', type=int, default=1920)
    p.add_argument('--key-width', type=float, default=DEFAULT_KEY_WIDTH,
                   help=f'white-key pixel width; MUST match the render geometry '
                        f'(default {DEFAULT_KEY_WIDTH}). Same value as '
                        f'add_keyboard_overlay --key_width.')
    p.add_argument('--fingering-source', default='arlstm',
                   choices=['arlstm', 'pianoplayer', 'none'],
                   help='Logic Track for the recommended-finger metric. '
                        '"arlstm" = deployed default judge (loads Ramoneda/torch); '
                        '"pianoplayer" = fast DP proxy; "none" = nearest-finger only.')
    p.add_argument('--no-override', action='store_true',
                   help='ignore songs/<name>_fingering.json manual overrides '
                        '(default: apply them, matching deployment).')
    p.add_argument('--merge-gap', type=float, default=0.15,
                   help='same-pitch merge gap (s) reproducing the render cleaning '
                        '(simple_natural.py:716). Default 0.15 matches the render.')
    p.add_argument('--no-clean', action='store_true',
                   help='score the RAW MIDI instead of reproducing the render '
                        'cleaning. Inflates misses with phantom repeated-note '
                        'onsets the render never positioned a finger for.')
    args = p.parse_args()

    raw_n = len(load_onsets(args.midi))
    if args.no_clean:
        midi_for_eval = args.midi
        clean_note = '(raw MIDI; render cleaning OFF)'
    else:
        midi_for_eval = clean_midi_like_render(args.midi, args.merge_gap)
        clean_note = f'(render cleaning ON, merge_gap={args.merge_gap}; raw={raw_n})'

    onsets = load_onsets(midi_for_eval)
    print(f'[midi] {len(onsets)} onsets from {os.path.basename(args.midi)} '
          f'{clean_note} (key_width={args.key_width}, '
          f'fingering={args.fingering_source})')

    assigned_lookup = build_assigned_lookup(
        midi_for_eval, args.fingering_source, use_override=not args.no_override)
    has_assigned = assigned_lookup is not None

    summary = {}
    for fp in args.fingertips:
        rows, fps, nf = eval_template(fp, onsets, args.frame_width,
                                      args.key_width, assigned_lookup)
        label = os.path.basename(fp).replace('_fingertips.json', '')
        summary[label] = summarize(rows, label, has_assigned)

    if len(summary) > 1:
        key = 'rec_land_pct' if has_assigned else 'near_land_pct'
        title = ('recommended-finger landing'
                 if has_assigned else 'nearest-finger landing')
        print(f'\n────────── version comparison ({title}, higher = better) ──────────')
        for k, v in sorted(summary.items(), key=lambda kv: -(kv[1] or {}).get(key, 0)):
            if not v:
                continue
            if has_assigned and 'rec_land_pct' in v:
                print(f'  {k:28s} {v["rec_land_pct"]:5.1f}%   '
                      f'(RH {v["rec_rh"]:.0f}% / LH {v["rec_lh"]:.0f}%; '
                      f'nearest {v["near_land_pct"]:.0f}%)')
            else:
                print(f'  {k:28s} {v["near_land_pct"]:5.1f}%   '
                      f'(RH {v["near_rh"]:.0f}% / LH {v["near_lh"]:.0f}%, '
                      f'mean Δx {v["near_mean_dx"]:.0f}px)')


if __name__ == '__main__':
    main()
