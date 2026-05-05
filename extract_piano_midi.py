"""高精度钢琴 MIDI 转录脚本.

吃 MP3/WAV → ByteDance High-Resolution Piano Transcription → 输出同名 .mid 檔.

用法:
    python extract_piano_midi.py --mp3 input_songs/canon.mp3
    # → input_songs/canon.mid

    python extract_piano_midi.py --mp3 song.mp3 --out custom/path.mid
    python extract_piano_midi.py --mp3 song.mp3 --device cpu
    python extract_piano_midi.py --mp3 song.mp3 --no-overwrite
"""
import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description='高精度鋼琴 MIDI 轉錄 (ByteDance piano_transcription_inference)')
    parser.add_argument('--mp3', type=str, required=True,
                        help='輸入音檔路徑 (mp3/wav 等 ffmpeg 可解的格式)')
    parser.add_argument('--out', type=str, default=None,
                        help='輸出 MIDI 路徑 (默認: 同目錄, 同 basename, 副檔名改 .mid)')
    parser.add_argument('--device', type=str, default='cuda', choices=['cuda', 'cpu'],
                        help='推論設備 (默認 cuda)')
    parser.add_argument('--no-overwrite', dest='overwrite', action='store_false',
                        help='若輸出 MIDI 已存在則拒絕覆蓋 (默認允許覆蓋)')
    parser.set_defaults(overwrite=True)
    parser.add_argument('--clip_duration', type=float, default=None,
                        help='硬截短: 把每顆 note 的 end 限制在 start+N 秒內, 寫進 .mid 檔. '
                             '默認 None = 不截短 (保留原模型輸出, sustain pedal 延長照舊). '
                             '設例如 0.5 = 寫一份「視覺乾淨版」MIDI, 但會降低 mir_eval offset F1.')
    args = parser.parse_args()

    if not os.path.exists(args.mp3):
        print(f'❌ 找不到音檔: {args.mp3}', file=sys.stderr)
        sys.exit(1)

    out_path = args.out or os.path.splitext(args.mp3)[0] + '.mid'
    if os.path.exists(out_path) and not args.overwrite:
        print(f'❌ 輸出已存在: {out_path} (用 --overwrite 或刪除後再跑)', file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)

    print(f'[1/3] 載入 ByteDance 鋼琴轉錄模型 (device={args.device})...', flush=True)
    from piano_transcription_inference import PianoTranscription, load_audio, sample_rate
    transcriptor = PianoTranscription(device=args.device)

    print(f'[2/3] 讀取音檔 → {args.mp3}', flush=True)
    audio, _ = load_audio(args.mp3, sr=sample_rate, mono=True)

    print(f'[3/3] 轉錄中 → {out_path}', flush=True)
    transcriptor.transcribe(audio, out_path)

    import pretty_midi
    midi = pretty_midi.PrettyMIDI(out_path)
    n_notes = sum(len(i.notes) for i in midi.instruments if not i.is_drum)

    if args.clip_duration is not None:
        clipped = 0
        for inst in midi.instruments:
            if inst.is_drum:
                continue
            for n in inst.notes:
                new_end = min(n.end, n.start + args.clip_duration)
                if new_end < n.end:
                    clipped += 1
                    n.end = new_end
        midi.write(out_path)
        print(f'✂️  截短: {clipped}/{n_notes} 顆 note 的 duration 被 cap 在 {args.clip_duration}s 內')

    print(f'✅ 完成: {n_notes} 個音符, 時長 {midi.get_end_time():.1f}s')
    print(f'   MIDI: {out_path}')


if __name__ == '__main__':
    main()
