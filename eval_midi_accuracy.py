"""用 PianoMotion10M test split 当 ground truth, 评估 MIDI 转录准确率.

策略: 每首 BV 取 seq_0000 (0-30s) audio + 同窗口的 ground-truth MIDI, 跑
extract_piano_midi.py 的转录, 用 mir_eval 标准指标比对.

输出指标 (mir_eval.transcription):
  Onset F1: onset+pitch 都对 (默认 onset_tolerance=50ms, pitch_tolerance=50 cents)
  Note F1 (no offset): 只看 onset+pitch (offset_ratio=None)
  Note F1 (with offset): onset+pitch+offset 都对 (offset_ratio=0.2)

用法:
    python eval_midi_accuracy.py                # N=5 (默认)
    python eval_midi_accuracy.py --n 10         # 多跑几首
    python eval_midi_accuracy.py --seed 42      # 指定 random seed
"""
import argparse
import json
import os
import random
import sys
import tempfile

import numpy as np
import pretty_midi
import mir_eval

DATASET = '/home/dex/PianoMotion10M/PianoMotion10M_Dataset'
SEG_DURATION = 30.0   # seq_0000 永远是 0-30s
ONSET_TOL = 0.05      # 50ms (mir_eval 默认)


def slice_midi_to_arrays(midi_path, t_start=0.0, t_end=SEG_DURATION):
    """读取 MIDI, 抽出 [t_start, t_end] 内的音符 → (intervals, pitches in Hz)."""
    midi = pretty_midi.PrettyMIDI(midi_path)
    intervals, pitches = [], []
    for inst in midi.instruments:
        if inst.is_drum:
            continue
        for n in inst.notes:
            if n.end <= t_start or n.start >= t_end:
                continue
            s = max(n.start, t_start) - t_start
            e = min(n.end, t_end) - t_start
            if e <= s:
                continue
            intervals.append([s, e])
            pitches.append(pretty_midi.note_number_to_hz(n.pitch))
    if not intervals:
        return np.zeros((0, 2)), np.zeros(0)
    return np.array(intervals), np.array(pitches)


def transcribe(audio_path, transcriptor):
    """跑 ByteDance 转录, 写到临时 .mid 再读回."""
    from piano_transcription_inference import load_audio, sample_rate
    audio, _ = load_audio(audio_path, sr=sample_rate, mono=True)
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
        tmp = f.name
    try:
        transcriptor.transcribe(audio, tmp)
        return tmp
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def eval_one(up, bv, transcriptor):
    audio_path = f'{DATASET}/audio/{up}/{bv}/{bv}_seq_0000.mp3'
    gt_midi_path = f'{DATASET}/midi/{up}/{bv}.mid'
    if not (os.path.exists(audio_path) and os.path.exists(gt_midi_path)):
        return None

    pred_path = transcribe(audio_path, transcriptor)
    try:
        ref_iv, ref_p = slice_midi_to_arrays(gt_midi_path, 0.0, SEG_DURATION)
        est_iv, est_p = slice_midi_to_arrays(pred_path, 0.0, SEG_DURATION)
    finally:
        if os.path.exists(pred_path):
            os.unlink(pred_path)

    if len(ref_iv) == 0 or len(est_iv) == 0:
        return {'gt_notes': len(ref_iv), 'pred_notes': len(est_iv),
                'note_f1': 0.0, 'note_offset_f1': 0.0,
                'note_p': 0.0, 'note_r': 0.0}

    # Onset + Pitch (no offset constraint) — 这是 ByteDance 论文报告 0.9677 的指标
    p, r, f1, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_iv, ref_p, est_iv, est_p,
        onset_tolerance=ONSET_TOL,
        pitch_tolerance=50.0,
        offset_ratio=None,
    )
    # Onset + Pitch + Offset
    p_o, r_o, f1_o, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_iv, ref_p, est_iv, est_p,
        onset_tolerance=ONSET_TOL,
        pitch_tolerance=50.0,
        offset_ratio=0.2,
    )
    return {
        'gt_notes': len(ref_iv),
        'pred_notes': len(est_iv),
        'note_p': p, 'note_r': r, 'note_f1': f1,
        'note_offset_f1': f1_o,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=5, help='评估样本数 (默认 5)')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--device', type=str, default='cuda')
    parser.add_argument('--split', type=str, default='test', choices=['test', 'valid', 'train'])
    parser.add_argument('--out', type=str, default=None,
                        help='把每首结果写成 CSV (例如 ./results/benchmark_n50.csv)')
    args = parser.parse_args()

    split_path = f'{DATASET}/{args.split}.txt'
    with open(split_path) as f:
        all_samples = [line.strip().split() for line in f if line.strip()]

    rng = random.Random(args.seed)
    rng.shuffle(all_samples)

    print(f'[setup] 載入 ByteDance 模型 (device={args.device})...', flush=True)
    from piano_transcription_inference import PianoTranscription
    transcriptor = PianoTranscription(device=args.device)

    results = []
    n_attempted = 0
    for up, bv in all_samples:
        if len(results) >= args.n:
            break
        n_attempted += 1
        print(f'[{len(results)+1}/{args.n}] {up}/{bv} ...', flush=True)
        try:
            r = eval_one(up, bv, transcriptor)
        except Exception as e:
            print(f'   跳过 (错误: {e})')
            continue
        if r is None:
            print(f'   跳过 (audio 或 midi 缺失)')
            continue
        r['up'], r['bv'] = up, bv
        results.append(r)
        print(f'   GT={r["gt_notes"]:4d}, Pred={r["pred_notes"]:4d}, '
              f'note F1={r["note_f1"]:.3f}, note+offset F1={r["note_offset_f1"]:.3f}')

    if not results:
        print('❌ 没有可用样本')
        sys.exit(1)

    print()
    print('═' * 78)
    print(f'{"BV":<16} {"GT":>5} {"Pred":>5} {"P":>6} {"R":>6} {"F1":>6} {"F1+off":>7}')
    print('─' * 78)
    for r in results:
        print(f'{r["bv"]:<16} {r["gt_notes"]:>5d} {r["pred_notes"]:>5d} '
              f'{r["note_p"]:>6.3f} {r["note_r"]:>6.3f} {r["note_f1"]:>6.3f} '
              f'{r["note_offset_f1"]:>7.3f}')
    print('─' * 78)

    arr = lambda k: np.array([r[k] for r in results])
    print(f'{"mean":<16} {int(arr("gt_notes").mean()):>5d} {int(arr("pred_notes").mean()):>5d} '
          f'{arr("note_p").mean():>6.3f} {arr("note_r").mean():>6.3f} {arr("note_f1").mean():>6.3f} '
          f'{arr("note_offset_f1").mean():>7.3f}')
    print(f'{"median":<16} {int(np.median(arr("gt_notes"))):>5d} {int(np.median(arr("pred_notes"))):>5d} '
          f'{np.median(arr("note_p")):>6.3f} {np.median(arr("note_r")):>6.3f} '
          f'{np.median(arr("note_f1")):>6.3f} {np.median(arr("note_offset_f1")):>7.3f}')
    print('═' * 78)
    print(f'(onset_tol={ONSET_TOL*1000:.0f}ms, pitch_tol=50¢; ByteDance 论文 note F1 ≈ 0.968 on MAESTRO)')

    if args.out:
        import csv
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)
        with open(args.out, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['up', 'bv', 'gt_notes', 'pred_notes',
                        'note_p', 'note_r', 'note_f1', 'note_offset_f1'])
            for r in results:
                w.writerow([r['up'], r['bv'], r['gt_notes'], r['pred_notes'],
                            f'{r["note_p"]:.4f}', f'{r["note_r"]:.4f}',
                            f'{r["note_f1"]:.4f}', f'{r["note_offset_f1"]:.4f}'])
        print(f'\n✅ 已寫入: {args.out} (n={len(results)}, seed={args.seed}, split={args.split})')


if __name__ == '__main__':
    main()
