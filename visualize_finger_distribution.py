"""Render finger-distribution comparison bar charts for thesis ch4.

For each hand, plot side-by-side bars of finger usage frequency under
pianoplayer vs ArLSTM (and optionally biomech / arlstm tiebreaker).

Outputs (PNG, 300dpi, ready for thesis insertion):
    figures/finger_dist_rh.png
    figures/finger_dist_lh.png
    figures/finger_dist_combined.png

Usage:
    python visualize_finger_distribution.py \\
        --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid"
"""
from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from webui.realtime.fingering_engine import generate_fingering

FINGER_NAMES = ['thumb', 'index', 'middle', 'ring', 'pinky']
FINGER_NUM = ['1', '2', '3', '4', '5']


def count_fingers(midi_path: str, source: str, hand: str) -> list[int]:
    """Return per-finger counts (length 5) for one source/hand on the MIDI."""
    onsets = generate_fingering(midi_path, source=source)
    counter = Counter()
    for o in onsets:
        if o.expected_hand != hand:
            continue
        counter[o.expected_finger] += 1
    return [counter.get(f, 0) for f in FINGER_NAMES]


def plot_hand(ax, midi_path: str, hand: str, sources: dict[str, str]):
    """Plot grouped bar chart for one hand on the given Axes."""
    counts = {label: count_fingers(midi_path, source, hand)
              for label, source in sources.items()}
    total_notes = sum(next(iter(counts.values())))

    x = np.arange(len(FINGER_NUM))
    width = 0.8 / len(counts)
    colors = ['#3b6db8', '#1a8f4d', '#9f1f1f', '#d4a017']

    for i, (label, vals) in enumerate(counts.items()):
        offset = (i - (len(counts) - 1) / 2) * width
        bars = ax.bar(x + offset, vals, width, label=label, color=colors[i % len(colors)])
        # Annotate ring-finger atrophy if visible
        for j, b in enumerate(bars):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5,
                    str(int(b.get_height())),
                    ha='center', va='bottom', fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels([f'{n}\n{name}' for n, name in zip(FINGER_NUM, FINGER_NAMES)],
                       fontsize=10)
    ax.set_ylabel('count', fontsize=11)
    ax.set_title(f'{hand.upper()} hand (n={total_notes} notes)', fontsize=12)
    ax.legend(loc='upper right', fontsize=9, frameon=True)
    ax.grid(axis='y', alpha=0.3)

    # Mark expected ring atrophy zone
    if hand == 'left':
        ring_pp = counts.get('pianoplayer', [0]*5)[3]
        ring_arlstm = counts.get('ArLSTM', [0]*5)[3]
        if ring_pp < 5 and ring_arlstm > ring_pp:
            ax.annotate(
                f'pp ring atrophy:\n{ring_pp} → {ring_arlstm} ({(ring_arlstm/max(ring_pp,1)-1)*100:+.0f}%)',
                xy=(3, ring_arlstm), xytext=(3.5, ring_arlstm + 8),
                fontsize=9, color='#9f1f1f', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#9f1f1f', lw=1),
            )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--midi', required=True)
    ap.add_argument('--out_dir', default='figures')
    ap.add_argument('--sources', default='pianoplayer,arlstm',
                    help='Comma-separated source list (subset of '
                         "'pianoplayer','arlstm')")
    args = ap.parse_args()

    sources_list = args.sources.split(',')
    sources = {s: s for s in sources_list}  # label = source
    # Pretty labels
    pretty = {'pianoplayer': 'pianoplayer\n(Parncutt DP)',
              'arlstm': 'ArLSTM\n(Ramoneda 22)'}
    sources_pretty = {pretty.get(s, s): s for s in sources_list}

    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    # One figure per hand
    for hand in ['right', 'left']:
        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=120)
        plot_hand(ax, args.midi, hand, sources_pretty)
        plt.tight_layout()
        out = Path(args.out_dir) / f'finger_dist_{hand[0]}h.png'
        plt.savefig(out, dpi=300, bbox_inches='tight')
        print(f'✓ {out}')
        plt.close()

    # Combined (both hands side by side)
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.5), dpi=120)
    for ax, hand in zip(axes, ['right', 'left']):
        plot_hand(ax, args.midi, hand, sources_pretty)
    fig.suptitle(f'Finger usage distribution — {Path(args.midi).stem}',
                 fontsize=13, y=1.02)
    plt.tight_layout()
    out = Path(args.out_dir) / 'finger_dist_combined.png'
    plt.savefig(out, dpi=300, bbox_inches='tight')
    print(f'✓ {out}')
    plt.close()


if __name__ == '__main__':
    main()
