"""Run Ramoneda 2022 pretrained ArLSTM / ArGNN models on a piano MIDI.

Loads checkpoints from external/Automatic-Piano-Fingering/models/ and returns
predicted fingering (1..5) per note. Uses greedy decoding from AR_decoder.

Usage:
    python ramoneda_predict.py \\
        --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \\
        --hand right --model ArGNN
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pretty_midi
import torch

_RAM = os.path.join(os.path.dirname(__file__), 'external', 'Automatic-Piano-Fingering')
if _RAM not in sys.path:
    sys.path.insert(0, _RAM)

from nns.common import only_pitch  # type: ignore
from nns.seq2seq_model import (  # type: ignore
    seq2seq, lstm_encoder, gnn_encoder, AR_decoder,
)
from nns.GGCN import edges_to_matrix  # type: ignore

# pianoplayer/PianoMotion convention: middle C separates hands at MIDI 60.
HAND_SPLIT = 60


class _EmbPitchSafe(torch.nn.Module):
    """emb_pitch with bounds-safe indexing (some MIDI files have pitch 0-127)."""
    out_dim = 64
    def __init__(self):
        super().__init__()
        self.emb = torch.nn.Embedding(127, 64)
    def forward(self, notes, onsets, durations, x_lengths):
        idx = (notes * 127).long().clamp(0, 126)
        return torch.squeeze(self.emb(idx), dim=2)


def build_model(kind: str, device: torch.device) -> torch.nn.Module:
    if kind == 'ArLSTM':
        m = seq2seq(only_pitch(), lstm_encoder(input=1), AR_decoder(in_size=64))
    elif kind == 'ArGNN':
        m = seq2seq(_EmbPitchSafe(), gnn_encoder(input_size=64), AR_decoder(in_size=64))
    else:
        raise ValueError(f'unknown kind {kind}')
    return m.to(device)


def load_checkpoint(model: torch.nn.Module, hand: str, kind: str,
                    device: torch.device) -> None:
    path = os.path.join(_RAM, 'models', f'{hand}_{kind}.pth')
    ckpt = torch.load(path, map_location=device, weights_only=False)
    model.load_state_dict(ckpt['model_state_dict'])
    model.eval()


def build_inputs(midi_path: str, hand: str, device: torch.device):
    """Return (notes, onsets, durations, lengths, edges, raw_pitches, raw_onsets)."""
    pm = pretty_midi.PrettyMIDI(midi_path)
    notes_raw = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for n in inst.notes:
            in_hand = (n.pitch >= HAND_SPLIT) if hand == 'right' else (n.pitch < HAND_SPLIT)
            if in_hand:
                notes_raw.append((float(n.start), int(n.pitch),
                                  float(max(0.05, n.end - n.start))))
    notes_raw.sort(key=lambda x: (x[0], x[1]))

    if not notes_raw:
        raise RuntimeError(f'No notes for hand={hand} in {midi_path}')

    onsets_arr = np.array([n[0] for n in notes_raw], dtype=np.float32)
    pitches_arr = np.array([n[1] for n in notes_raw], dtype=np.float32)
    durations_arr = np.array([n[2] for n in notes_raw], dtype=np.float32)

    n_notes = len(notes_raw)
    edges = []
    # onset edges within same-onset bucket; next edges to next-onset bucket
    distinct_onsets = sorted(set(onsets_arr.tolist()))
    for ti, t in enumerate(distinct_onsets):
        same = [i for i, o in enumerate(onsets_arr.tolist()) if o == t]
        for i in same:
            for j in same:
                if i != j:
                    edges.append((i, j, 'onset'))
        if ti + 1 < len(distinct_onsets):
            nxt = [j for j, o in enumerate(onsets_arr.tolist())
                   if o == distinct_onsets[ti + 1]]
            for i in same:
                for j in nxt:
                    edges.append((i, j, 'next'))

    edge_mat = edges_to_matrix(edges, n_notes)  # (4, T, T)
    edge_list = edge_mat.unsqueeze(0).to(device)  # (1, 4, T, T)

    notes = torch.tensor(pitches_arr / 127.0, device=device).view(1, n_notes, 1).float()
    onsets = torch.tensor(onsets_arr / max(onsets_arr.max(), 1.0), device=device).view(1, n_notes, 1).float()
    durations = torch.tensor(durations_arr / max(durations_arr.max(), 1.0), device=device).view(1, n_notes, 1).float()
    lengths = torch.tensor([n_notes], dtype=torch.long, device=device)

    return notes, onsets, durations, lengths, edge_list, pitches_arr, onsets_arr


@torch.no_grad()
def predict(midi_path: str, hand: str, kind: str,
            device: torch.device | None = None):
    """Return per-note fingering 1..5 and a list of (onset_time, pitch) pairs."""
    device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = build_model(kind, device)
    load_checkpoint(model, hand, kind, device)
    notes, onsets, durations, lengths, edge_list, pitches, onset_times = build_inputs(midi_path, hand, device)
    logits = model(notes, onsets, durations, lengths, edge_list, fingers=None)
    # logits: (1, T, 5) — softmax log-probs over fingers 1..5
    fingers = logits.argmax(dim=2).squeeze(0).cpu().numpy() + 1  # to 1..5
    notes_info = list(zip(onset_times.tolist(), pitches.astype(int).tolist()))
    return fingers.tolist(), notes_info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--midi', required=True)
    ap.add_argument('--hand', default='right', choices=['right', 'left'])
    ap.add_argument('--model', default='ArLSTM', choices=['ArLSTM', 'ArGNN'])
    args = ap.parse_args()

    fingers, info = predict(args.midi, args.hand, args.model)
    print(f'{args.model} ({args.hand}) — {len(fingers)} notes')
    for (t, p), f in list(zip(info, fingers))[:20]:
        print(f'  t={t:6.3f}  pitch={p:3d}  finger={f}')


if __name__ == '__main__':
    main()
