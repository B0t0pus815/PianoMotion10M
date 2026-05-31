"""ONNX fingering inference — a torch-free Logic Track source.

Runs the FingeringTransformer (external/piano-fingering-model) via onnxruntime
instead of PyTorch, so the live judge can predict fingerings on an edge device
(Jetson NX) with NO torch/CUDA. The token construction + per-finger state tracking
mirror external/piano-fingering-model/python/inference.py exactly (that is the
model's input contract); only the forward pass is swapped torch -> onnxruntime.

Models: external/piano-fingering-model/js/models/fingering_transformer_{left,right}.onnx
  input  `tokens`  [batch, 26, 5]
  output `logits`  [batch, 5]   -> argmax = finger 0..4

Public:
  predict_fingerings(notes, hand, is_left) -> notes (each with 'finger' 1..5)
    notes: list of {'left': bool, 'note': midi, 'time': ms, 'duration': ms,
                    'finger': 1..5 (optional, treated as fixed)}
"""
from __future__ import annotations

import os

import numpy as np

_MODELS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'external', 'piano-fingering-model', 'js', 'models',
)
BLACK_KEY_NOTES = [1, 4, 6, 9, 11]  # A#, C#, D#, F#, G# (key_index % 12)

_SESSIONS: dict = {}


def _session(hand: str):
    """Lazily load + cache the onnxruntime session for one hand."""
    if hand not in _SESSIONS:
        import onnxruntime as ort  # lazy: only needed when source='onnx'
        path = os.path.join(_MODELS_DIR, f'fingering_transformer_{hand}.onnx')
        if not os.path.exists(path):
            raise FileNotFoundError(f'ONNX model not found: {path}')
        _SESSIONS[hand] = ort.InferenceSession(
            path, providers=['CPUExecutionProvider'])
    return _SESSIONS[hand]


# ── token features (verbatim from inference.py — the model's contract) ──
def is_black_key(midi: int) -> float:
    if midi < 0:
        return -1.0
    return 1.0 if ((midi - 21) % 12) in BLACK_KEY_NOTES else 0.0


def midi_to_pitch_class(midi: int) -> float:
    if midi < 0:
        return -1.0
    return ((midi - 21) % 12) / 11.0


def build_tokens(current_midi, finger_last_midi, finger_last_time,
                 lookahead_notes) -> np.ndarray:
    """Build the 26x5 input tokens for a single note prediction."""
    tokens = np.zeros((26, 5), dtype=np.float32)
    tokens[:, 4] = -1.0
    ref_midi_norm = (current_midi - 21) / 87.0

    for f in range(5):                       # 5 previous (one per finger)
        midi = finger_last_midi[f]
        if midi >= 0:
            tokens[f, 0] = (midi - 21) / 87.0 - ref_midi_norm
        else:
            tokens[f, 0] = -1.0
        if finger_last_time[f] == float('inf'):
            tokens[f, 1] = 1.0
        else:
            tokens[f, 1] = max(0.0, min(finger_last_time[f], 10.0)) / 10.0
        tokens[f, 2] = is_black_key(int(midi)) if midi >= 0 else -1.0
        tokens[f, 3] = 0.0

    tokens[5, 0] = midi_to_pitch_class(current_midi)   # current
    tokens[5, 1] = 0.0
    tokens[5, 2] = is_black_key(current_midi)
    tokens[5, 3] = 0.5

    for j in range(20):                      # 20 lookahead
        if j < len(lookahead_notes):
            ln = lookahead_notes[j]
            midi = ln['midi']
            tokens[6 + j, 0] = (midi - 21) / 87.0 - ref_midi_norm if midi >= 0 else -1.0
            tu = ln['time_until']
            tokens[6 + j, 1] = -1.0 if tu < 0 else min(tu / 1000.0, 10.0) / 10.0
            tokens[6 + j, 2] = is_black_key(midi) if midi >= 0 else -1.0
            tokens[6 + j, 3] = 1.0
            fh = ln.get('finger')
            tokens[6 + j, 4] = fh / 4.0 if (fh is not None and 0 <= fh <= 4) else -1.0
        else:
            tokens[6 + j, :] = -1.0
    return tokens


def predict_fingerings(notes: list[dict], hand: str, is_left: bool) -> list[dict]:
    """Predict fingerings for all notes of one hand (mirrors inference.py;
    forward pass via onnxruntime). Fixed fingers (1..5) are kept and hinted."""
    hand_notes = [n for n in notes if n['left'] == is_left]
    if not hand_notes:
        return []
    sess = _session(hand)
    sorted_notes = sorted(hand_notes, key=lambda n: (n['time'], n['note']))

    finger_last_midi = [-1.0] * 5
    finger_last_time = [float('inf')] * 5
    results = []

    for i, note in enumerate(sorted_notes):
        cur_t, cur_midi = note['time'], note['note']
        lookahead = []
        for fut in sorted_notes[i + 1:i + 21]:
            ff = fut.get('finger')
            hint = (ff - 1) if (ff is not None and 1 <= ff <= 5) else None
            lookahead.append({'midi': fut['note'],
                              'time_until': fut['time'] - cur_t, 'finger': hint})
        tokens = build_tokens(cur_midi, finger_last_midi, finger_last_time, lookahead)
        logits = sess.run(['logits'], {'tokens': tokens[None].astype(np.float32)})[0][0]
        pred = int(np.argmax(logits))

        out = note.copy()
        existing = note.get('finger')
        if existing is not None and 1 <= existing <= 5:
            finger = existing
        else:
            finger = pred + 1
            out['finger'] = finger
        results.append(out)

        fi = finger - 1
        finger_last_midi[fi] = cur_midi
        finger_last_time[fi] = -((note.get('duration') or 100) / 1000.0)
        if i + 1 < len(sorted_notes):
            dt = (sorted_notes[i + 1]['time'] - cur_t) / 1000.0
            for f in range(5):
                if finger_last_time[f] != float('inf'):
                    finger_last_time[f] += dt
    return results
