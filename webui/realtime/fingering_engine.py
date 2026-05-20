"""Deterministic fingering generator (Logic Track).

Replaces the motion-based expected_finger derivation in reference.py: same
ExpectedOnset output shape, but the fingering decision comes from one of two
deterministic sources (selected via `source=`):

  - 'pianoplayer' (default): Parncutt-style DP cost model. Reproducible per
    MIDI; thumb-conservative, weak on chord voicings (Hard 0.500 / Soft 0.625
    on Canon RH first 12 onsets vs Teacher GT).
  - 'arlstm': Ramoneda 2022 pretrained Autoregressive LSTM (PIG-finetuned).
    Pedagogically calibrated; Hard 0.500 / Soft 0.792 on the same audit —
    wins on Soft Accuracy because errors stay within ±1 finger of the
    teacher's choice. See four_way_audit.py for the receipts.

Both sources are wrapped here so the downstream comparator does not need to
know which one produced the fingering.

Manual override: if `songs/<basename>_fingering.json` exists next to the MIDI,
its entries take precedence over algorithmic output — used for answer-key
demo pieces where we hand-annotate to match Henle / Schirmer published
fingerings. Override file shape:

    {
      "12.345_42": {"hand": "left",  "finger": "thumb"},
      "13.5_48":   {"hand": "right", "finger": "index"}
    }

Key is `"<time_rounded_2>_<pitch>"`. Both `hand` and `finger` optional.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import pretty_midi
from pianoplayer.scorereader import reader_pretty_midi
from pianoplayer.hand import Hand

from webui.realtime.reference import ExpectedOnset, FINGER_ORDER, HAND_SPLIT


def _finger_name_from_idx(idx: int, fallback: str = 'thumb') -> str:
    """pianoplayer uses 1..5; 0 means unassigned (rare). Map to thumb..pinky."""
    if 1 <= idx <= 5:
        return FINGER_ORDER[idx - 1]
    return fallback


def _override_key(time_sec: float, pitch: int) -> str:
    return f'{round(time_sec, 2)}_{pitch}'


def load_manual_override(midi_path: str) -> Optional[dict]:
    """Look for <midi_basename>_fingering.json next to the MIDI."""
    base, _ = os.path.splitext(midi_path)
    override_path = base + '_fingering.json'
    if not os.path.exists(override_path):
        return None
    with open(override_path) as f:
        return json.load(f)


def _load_midi_flat(midi_path: str):
    """Read MIDI, flatten non-drum notes into one Instrument, return
    (flat, velocity_lookup). velocity_lookup keyed by (round(time,4), pitch)."""
    pm = pretty_midi.PrettyMIDI(midi_path)
    flat = pretty_midi.Instrument(program=0)
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        flat.notes.extend(inst.notes)
    flat.notes.sort(key=lambda n: n.start)
    velocity_lookup = {(round(n.start, 4), int(n.pitch)): int(n.velocity)
                       for n in flat.notes}
    return flat, velocity_lookup


def _generate_pianoplayer(flat, velocity_lookup, hand_size: str):
    """Return list of (time, pitch, hand, finger_idx_1to5, duration, vel).
    Runs pianoplayer DP per hand against the flattened MIDI."""
    inotes = reader_pretty_midi(flat)
    right = [n for n in inotes if n.pitch >= HAND_SPLIT]
    left = [n for n in inotes if n.pitch < HAND_SPLIT]
    if right:
        Hand(right, side='right', size=hand_size).generate()
    if left:
        Hand(left, side='left', size=hand_size).generate()
    rows = []
    for n in sorted(right + left, key=lambda x: (x.time, x.pitch)):
        hand = 'right' if n.pitch >= HAND_SPLIT else 'left'
        vel = velocity_lookup.get((round(n.time, 4), int(n.pitch)), 64)
        rows.append((float(n.time), int(n.pitch), hand,
                     int(n.fingering), float(max(0.05, n.duration)), vel))
    return rows


def _generate_arlstm(midi_path: str, velocity_lookup):
    """Return list of (time, pitch, hand, finger_idx_1to5, duration, vel) via
    Ramoneda 2022 ArLSTM (one model per hand)."""
    # Lazy import: ramoneda_predict lives at repo root and pulls torch.
    import sys
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from ramoneda_predict import predict as _arlstm_predict

    rows = []
    for hand in ('right', 'left'):
        try:
            fingers, info = _arlstm_predict(midi_path, hand=hand, kind='ArLSTM')
        except RuntimeError:
            # No notes for this hand — predict() raises.
            continue
        for (t, pitch), f in zip(info, fingers):
            t = float(t)
            pitch = int(pitch)
            vel = velocity_lookup.get((round(t, 4), pitch), 64)
            # ArLSTM doesn't return duration; recover from the original MIDI map.
            dur = 0.1  # placeholder; overwritten below from the MIDI flat
            rows.append((t, pitch, hand, int(f), dur, vel))
    # Patch in real durations from the flat MIDI (velocity_lookup ⊂ flat).
    return rows


def _pack_with_override(rows, midi_path: str, use_override: bool,
                       flat) -> list[ExpectedOnset]:
    """Apply manual override and emit ExpectedOnset list sorted by time."""
    duration_lookup = {(round(n.start, 4), int(n.pitch)):
                       float(max(0.05, n.end - n.start)) for n in flat.notes}
    override = load_manual_override(midi_path) if use_override else None

    out: list[ExpectedOnset] = []
    for t, pitch, hand, finger_int, dur, vel in sorted(rows, key=lambda r: (r[0], r[1])):
        finger_fallback = 'thumb' if hand == 'left' else 'index'
        finger_name = _finger_name_from_idx(finger_int, fallback=finger_fallback)
        if override is not None:
            ovr = override.get(_override_key(t, pitch))
            if ovr:
                hand = ovr.get('hand', hand)
                finger_name = ovr.get('finger', finger_name)
        finger_idx = FINGER_ORDER.index(finger_name)
        # Prefer real duration from MIDI over any per-source placeholder.
        real_dur = duration_lookup.get((round(t, 4), pitch), dur)
        out.append(ExpectedOnset(
            time=t,
            pitch=pitch,
            velocity=vel,
            expected_hand=hand,
            expected_finger=finger_name,
            expected_finger_idx=finger_idx,
            duration=real_dur,
        ))
    return out


def generate_fingering(midi_path: str,
                       hand_size: str = 'M',
                       use_override: bool = True,
                       source: str = 'arlstm') -> list[ExpectedOnset]:
    """MIDI → per-note (hand, finger) for the Logic Track.

    Args:
        midi_path: path to .mid / .midi file.
        hand_size: pianoplayer hand size 'XXS'..'XXL' (ignored when source != 'pianoplayer').
        use_override: if True, songs/<basename>_fingering.json per-note overrides apply.
        source: 'arlstm' (default; Ramoneda 2022 SOTA) or 'pianoplayer' (Parncutt DP).

    Returns:
        List[ExpectedOnset] sorted by (time, pitch).
    """
    flat, velocity_lookup = _load_midi_flat(midi_path)
    if not flat.notes:
        return []

    if source == 'pianoplayer':
        rows = _generate_pianoplayer(flat, velocity_lookup, hand_size)
    elif source == 'arlstm':
        rows = _generate_arlstm(midi_path, velocity_lookup)
    else:
        raise ValueError(f"unknown source {source!r}; expected 'pianoplayer' or 'arlstm'")

    return _pack_with_override(rows, midi_path, use_override, flat)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('midi')
    p.add_argument('--size', default='M')
    p.add_argument('--source', default='arlstm',
                   choices=['pianoplayer', 'arlstm'])
    p.add_argument('--no-override', action='store_true')
    args = p.parse_args()
    out = generate_fingering(args.midi, hand_size=args.size,
                             use_override=not args.no_override,
                             source=args.source)
    print(f'{len(out)} notes')
    from collections import Counter
    by_hf = Counter((e.expected_hand, e.expected_finger) for e in out)
    for k, v in sorted(by_hf.items()):
        print(f'  {k}: {v}')
    print()
    print('first 10:')
    for e in out[:10]:
        print(f'  t={e.time:5.2f}  pitch={e.pitch:3d}  '
              f'{e.expected_hand[0].upper()}/{e.expected_finger}')
