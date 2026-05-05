# DEPRECATED: This script uses basic_pitch which is no longer recommended.
# Please use extract_piano_midi.py (ByteDance High-Resolution Piano Transcription) instead.
"""
infer_midi2gesture.py
=====================
用训练好的 MIDI→手势 模型，从任意 MP3 生成精确手势影片。

使用方式：
    python infer_midi2gesture.py \
        --mp3 ./input_songs/summer.mp3 \
        --ckpt ./logs/midi2gesture_v1/best.ckpt
"""

import os
import sys
import argparse
import json
import numpy as np
import torch
import librosa
from tqdm import tqdm

# 复用训练脚本里的模型定义
sys.path.insert(0, '.')
from train_midi2gesture import MidiToGestureTransformer, MIDI_NOTE_MIN, MIDI_NOTE_RANGE, FPS


def extract_piano_roll(mp3_path: str, duration: float) -> np.ndarray:
    """从 MP3 提取 piano roll"""
    print('[1/4] 提取 MIDI 音符...')
    try:
        from basic_pitch.inference import predict
        _, midi_data, _ = predict(mp3_path)
    except Exception as e:
        print(f'❌ basic-pitch 失败: {e}')
        sys.exit(1)

    frame_num = int(duration * FPS)
    piano_roll = np.zeros((frame_num, MIDI_NOTE_RANGE), dtype=np.float32)

    for instrument in midi_data.instruments:
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            frame_start = max(0, int(note.start * FPS))
            frame_end   = min(frame_num, int(note.end * FPS) + 1)
            note_idx    = note.pitch - MIDI_NOTE_MIN
            if 0 <= note_idx < MIDI_NOTE_RANGE:
                piano_roll[frame_start:frame_end, note_idx] = note.velocity / 127.0

    print(f'      共 {len([n for inst in midi_data.instruments for n in inst.notes])} 个音符')
    return piano_roll


def generate_gestures(piano_roll: np.ndarray, ckpt_path: str,
                       batch_sec: int = 8) -> tuple:
    """分批推论，生成完整手势序列"""
    print('[2/4] 载入模型...')

    ckpt = torch.load(ckpt_path, map_location='cpu', weights_only=False)
    args = ckpt['args']

    model = MidiToGestureTransformer(
        d_model=args['d_model'],
        nhead=args['nhead'],
        num_layers=args['num_layers'],
        dim_feedforward=args['dim_feedforward'],
    ).cuda()
    model.load_state_dict(ckpt['model_state'])
    model.eval()
    print(f'      载入: {ckpt_path} (val_loss={ckpt["val_loss"]:.4f})')

    print('[3/4] 生成手势...')
    batch_frames = batch_sec * FPS
    frame_num = len(piano_roll)

    right_all = np.zeros((frame_num, 51), dtype=np.float32)
    left_all  = np.zeros((frame_num, 51), dtype=np.float32)

    with torch.no_grad():
        for start in tqdm(range(0, frame_num, batch_frames)):
            end   = min(start + batch_frames, frame_num)
            chunk = piano_roll[start:end]

            # 补齐到 batch_frames
            if len(chunk) < batch_frames:
                pad = np.zeros((batch_frames - len(chunk), MIDI_NOTE_RANGE), dtype=np.float32)
                chunk = np.concatenate([chunk, pad], axis=0)

            midi_tensor = torch.FloatTensor(chunk).unsqueeze(0).cuda()
            pred_right, pred_left = model(midi_tensor)

            pred_right = pred_right[0].cpu().numpy()
            pred_left  = pred_left[0].cpu().numpy()

            actual_len = end - start
            right_all[start:end] = pred_right[:actual_len]
            left_all[start:end]  = pred_left[:actual_len]

    # 反归一化 Z 轴
    right_all[:, 2] = right_all[:, 2] * 10.0 + 14.0
    left_all[:, 2]  = left_all[:, 2]  * 10.0 + 14.0

    return right_all, left_all


def render_and_save(right_poses, left_poses, mp3_path, out_dir, out_video):
    """渲染成影片"""
    print('[4/4] 渲染影片...')
    from datasets.show import render_result

    os.makedirs(out_dir, exist_ok=True)
    render_result(out_dir, None, right_poses, left_poses, video=False)

    # 合成影片
    frames = sorted(
        [f for f in os.listdir(out_dir) if f.endswith('.png')],
        key=lambda x: int(x.replace('frame_', '').replace('.png', ''))
    )
    list_file = '/tmp/midi2gesture_frames.txt'
    with open(list_file, 'w') as f:
        for fr in frames:
            f.write(f"file '{os.path.abspath(out_dir)}/{fr}'\n")

    os.makedirs(os.path.dirname(out_video) or '.', exist_ok=True)
    cmd = (f'ffmpeg -y -r {FPS} -f concat -safe 0 -i {list_file} '
           f'-i "{mp3_path}" -c:v libx264 -c:a aac -pix_fmt yuv420p '
           f'-shortest "{out_video}"')
    os.system(cmd)
    print(f'✅ 完成！影片：{out_video}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mp3',  type=str, required=True)
    parser.add_argument('--ckpt', type=str, default='./logs/midi2gesture_v1/best.ckpt')
    parser.add_argument('--out_dir',   type=str, default='./results/midi2gesture')
    parser.add_argument('--out_video', type=str, default='./results/midi2gesture.mp4')
    args = parser.parse_args()

    audio, sr = librosa.load(args.mp3, sr=16000)
    duration = len(audio) / 16000
    print(f'音频时长: {duration:.2f} 秒')

    piano_roll = extract_piano_roll(args.mp3, duration)
    right_poses, left_poses = generate_gestures(piano_roll, args.ckpt)
    render_and_save(right_poses, left_poses, args.mp3, args.out_dir, args.out_video)


if __name__ == '__main__':
    main()
