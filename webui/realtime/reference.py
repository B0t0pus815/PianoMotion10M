"""Load reference fingertips + MIDI → precompute expected fingering per onset.

For each note_on event in the target MIDI, derive the expected finger using
the SAME heuristic the comparator applies at runtime (motion-based: fingertip
with maximum downward velocity in the window before the onset). This keeps
reference-derivation and runtime-detection self-consistent so that perfect
input → 100% correct, and any deviation reflects real user error.

Falls back to closest-X-to-key when the press window contains too few frames
or no significant motion (legato / sustained / chord stacks).
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass

import numpy as np
import pretty_midi

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from add_keyboard_overlay import pitch_key_center_x, FINGER_ORDER, HAND_SPLIT

# Same window the comparator uses, in seconds.
PRESS_WINDOW = 0.12
MIN_PRESS_VELOCITY = 80.0


def _press_finger_at(tips_seq: np.ndarray, frame_idx: int, fps: float,
                     key_x: float) -> int:
    """Pick the most likely pressing fingertip at frame_idx using the same
    rule as the runtime comparator.

    tips_seq: (N, 5, 2) reference fingertip trajectory for one hand.
    """
    window_frames = max(1, int(round(PRESS_WINDOW * fps)))
    lo = max(0, frame_idx - window_frames)
    snaps = tips_seq[lo:frame_idx + 1]  # (k, 5, 2)
    if snaps.shape[0] < 2:
        # not enough history — fall back to closest X at this frame
        return int(np.argmin(np.abs(tips_seq[frame_idx, :, 0] - key_x)))

    # mean downward velocity (dy/dt > 0 = moving down)
    dt = 1.0 / fps
    vy = np.diff(snaps[:, :, 1], axis=0).mean(axis=0) / dt  # (5,)
    if np.max(vy) < MIN_PRESS_VELOCITY:
        # no clear press motion — fall back to lowest fingertip
        return int(np.argmax(snaps[-1, :, 1]))
    return int(np.argmax(vy))


@dataclass
class ExpectedOnset:
    time: float
    pitch: int
    velocity: int
    expected_hand: str
    expected_finger: str
    expected_finger_idx: int
    duration: float = 0.0  # seconds, for piano roll rendering


def build_reference(midi_path: str,
                    fingertips_path: str,
                    frame_width: int = 1920) -> list[ExpectedOnset]:
    if not os.path.exists(midi_path):
        raise FileNotFoundError(f'MIDI not found: {midi_path}')
    if not os.path.exists(fingertips_path):
        raise FileNotFoundError(f'Fingertips JSON not found: {fingertips_path}')

    with open(fingertips_path) as f:
        ft = json.load(f)
    fps = ft['fps']
    right_tips = np.array(ft['right'], dtype=np.float32)
    left_tips = np.array(ft['left'], dtype=np.float32)
    n_frames = right_tips.shape[0]

    midi = pretty_midi.PrettyMIDI(midi_path)

    out: list[ExpectedOnset] = []
    for inst in midi.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            frame_idx = min(int(round(note.start * fps)), n_frames - 1)
            hand = 'right' if note.pitch >= HAND_SPLIT else 'left'
            tips_seq = right_tips if hand == 'right' else left_tips
            key_x = pitch_key_center_x(note.pitch, frame_width)
            finger_idx = _press_finger_at(tips_seq, frame_idx, fps, key_x)
            out.append(ExpectedOnset(
                time=float(note.start),
                pitch=int(note.pitch),
                velocity=int(note.velocity),
                expected_hand=hand,
                expected_finger=FINGER_ORDER[finger_idx],
                expected_finger_idx=finger_idx,
                duration=float(max(0.05, note.end - note.start)),
            ))
    out.sort(key=lambda e: e.time)
    return out
