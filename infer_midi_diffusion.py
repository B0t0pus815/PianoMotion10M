# DEPRECATED: This script uses basic_pitch which is no longer recommended.
# Please use extract_piano_midi.py (ByteDance High-Resolution Piano Transcription) instead.
"""
infer_midi_diffusion.py
=======================
用训练好的 MIDI 扩散模型生成手势影片。

使用方式：
    python infer_midi_diffusion.py \
        --mp3 "./input_songs/summer.mp3" \
        --encoder_ckpt ./logs/midi_encoder_v2/best_encoder.ckpt \
        --diffusion_ckpt ./logs/midi_diffusion_v1/iter_50000.ckpt
"""

import os
import sys
import argparse
import json
import numpy as np
import torch
import librosa
from tqdm import tqdm

sys.path.insert(0, '.')
from models.midi_encoder import MidiEncoderWithGuide
from models.denoise_diffusion import GaussianDiffusion1D_piano2pose, Unet1D

MIDI_NOTE_MIN   = 21
MIDI_NOTE_MAX   = 108
MIDI_NOTE_RANGE = MIDI_NOTE_MAX - MIDI_NOTE_MIN + 1
FPS = 30
SEG_SEC = 4   # 每次推论 4 秒（和训练一致）


def extract_piano_roll(mp3_path: str, duration: float) -> np.ndarray:
    print('[1/4] 提取 MIDI...')
    from basic_pitch.inference import predict
    _, midi_data, _ = predict(mp3_path)

    HAND_SPLIT = 65
    frame_num  = int(duration * FPS)
    roll_r = np.zeros((frame_num, MIDI_NOTE_RANGE), dtype=np.float32)
    roll_l = np.zeros((frame_num, MIDI_NOTE_RANGE), dtype=np.float32)

    for inst in midi_data.instruments:
        if inst.is_drum: continue
        for note in inst.notes:
            fs  = max(0, int(note.start * FPS))
            fe  = min(frame_num, int(note.end * FPS) + 1)
            idx = note.pitch - MIDI_NOTE_MIN
            if 0 <= idx < MIDI_NOTE_RANGE:
                vel = note.velocity / 127.0
                if note.pitch > HAND_SPLIT:
                    roll_r[fs:fe, idx] = vel
                else:
                    roll_l[fs:fe, idx] = vel

    piano_roll = np.concatenate([roll_r, roll_l], axis=-1)  # (T, 176)
    print(f'      {frame_num} 帧')
    return piano_roll


def load_models(encoder_ckpt: str, diffusion_ckpt: str):
    print('[2/4] 载入模型...')

    # 编码器
    encoder = MidiEncoderWithGuide(
        d_model=512, nhead=8, num_layers=6, dim_feedforward=2048
    ).cuda()
    enc_ckpt = torch.load(encoder_ckpt, map_location='cpu', weights_only=False)
    encoder.load_state_dict(enc_ckpt['model_state'])
    encoder.eval()
    print(f'      编码器: val_loss={enc_ckpt["val_loss"]:.4f}')

    # 扩散模型
    unet = Unet1D(
        dim=128,
        dim_mults=(1, 2, 4, 8),
        channels=122,
        remap_noise=True,
        condition=True,
        guide=True,
        guide_dim=122,
        condition_dim=768,
        encoder_type='none',
        num_layer=16,
    ).cuda()

    diff_ckpt = torch.load(diffusion_ckpt, map_location='cpu', weights_only=False)
    unet.load_state_dict(diff_ckpt['model_state'])

    diffusion = GaussianDiffusion1D_piano2pose(
        unet,
        encoder,
        seq_length=SEG_SEC * FPS,
        timesteps=1000,
    ).cuda()
    diffusion.eval()
    print(f'      扩散模型: iter={diff_ckpt["iteration"]}')

    return diffusion


def generate_poses(piano_roll: np.ndarray, diffusion) -> tuple:
    print('[3/4] 生成手势...')

    seg_frames  = SEG_SEC * FPS       # 120 帧
    overlap     = seg_frames // 4     # 30 帧重叠（1 秒）
    stride      = seg_frames - overlap  # 90 帧步进
    frame_num   = len(piano_roll)
    pose_all    = np.zeros((frame_num, 122), dtype=np.float32)
    weight_all  = np.zeros((frame_num, 1),   dtype=np.float32)

    # 建立段边缘的淡入淡出权重（cosine blend）
    blend = np.ones(seg_frames, dtype=np.float32)
    ramp  = (1 - np.cos(np.linspace(0, np.pi, overlap))) / 2
    blend[:overlap]  = ramp
    blend[-overlap:] = ramp[::-1]

    starts = list(range(0, frame_num, stride))

    with torch.no_grad():
        for start in tqdm(starts):
            end   = min(start + seg_frames, frame_num)
            chunk = piano_roll[start:end]

            # 补齐
            if len(chunk) < seg_frames:
                pad   = np.zeros((seg_frames - len(chunk), MIDI_NOTE_RANGE * 2), dtype=np.float32)
                chunk = np.concatenate([chunk, pad], axis=0)

            midi_t = torch.FloatTensor(chunk).unsqueeze(0).cuda()
            samples, _ = diffusion.sample(midi_t, seg_frames, batch_size=1)
            pose_seg = samples[0].permute(1, 0).cpu().numpy()  # (T, 122)

            actual  = end - start
            w       = blend[:actual].reshape(-1, 1)
            pose_all[start:end]   += pose_seg[:actual] * w
            weight_all[start:end] += w

    # 归一化（加权平均）
    weight_all = np.maximum(weight_all, 1e-6)
    pose_all  /= weight_all

    # 拆分左右手（各 51 维）
    right_poses = pose_all[:, :51]
    left_poses  = pose_all[:, 51:102]

    # 反归一化：模型输出 [0,1]，映射回真实范围
    def denorm_right(p):
        r = p.copy()
        r[:, 0] = r[:, 0] * 0.196 - 0.121   # X: -0.121~0.075
        r[:, 1] = r[:, 1] * 0.138 + 0.181   # Y: 0.181~0.319
        r[:, 2] = 16.5                        # Z 固定（消除段间大小跳动）
        r[:, 3] = r[:, 3] * 1.044 - 1.466   # or_x
        r[:, 4] = r[:, 4] * 1.037 - 2.013   # or_y
        r[:, 5] = r[:, 5] * 0.982 + 0.090   # or_z
        r[:, 6:] = r[:, 6:] * 1.746 - 0.740 # finger: [0,1] → [-0.74,1.0]
        return r

    def denorm_left(p):
        l = p.copy()
        l[:, 0] = l[:, 0] * 0.301 - 0.040   # X: -0.04~0.26
        l[:, 1] = l[:, 1] * 0.289 + 0.181   # Y
        l[:, 2] = 19.0                        # Z 固定（左手比右手稍远）
        l[:, 3] = l[:, 3] * 1.044 - 1.466   # or_x
        l[:, 4] = l[:, 4] * 1.037 - 2.013   # or_y
        l[:, 5] = l[:, 5] * 0.982 + 0.090   # or_z
        l[:, 6:] = l[:, 6:] * 1.746 - 0.740 # finger
        return l

    right_poses = denorm_right(right_poses)
    left_poses  = denorm_left(left_poses)

    return right_poses, left_poses


def render_video(right_poses, left_poses, mp3_path, out_dir, out_video):
    print('[4/4] 渲染影片...')
    from datasets.show import render_result

    os.makedirs(out_dir, exist_ok=True)
    render_result(out_dir, None, right_poses, left_poses, video=False)

    frames = sorted(
        [f for f in os.listdir(out_dir) if f.endswith('.png')],
        key=lambda x: int(x.replace('frame_', '').replace('.png', ''))
    )
    list_file = '/tmp/midi_diff_frames.txt'
    with open(list_file, 'w') as f:
        for fr in frames:
            f.write(f"file '{os.path.abspath(out_dir)}/{fr}'\n")

    os.makedirs(os.path.dirname(out_video) or '.', exist_ok=True)
    cmd = (f'ffmpeg -y -r {FPS} -f concat -safe 0 -i {list_file} '
           f'-i "{mp3_path}" -c:v libx264 -c:a aac -pix_fmt yuv420p '
           f'-shortest "{out_video}"')
    os.system(cmd)
    print(f'✅ 完成：{out_video}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mp3',            type=str, required=True)
    parser.add_argument('--encoder_ckpt',   type=str,
                        default='./logs/midi_encoder_v2/best_encoder.ckpt')
    parser.add_argument('--diffusion_ckpt', type=str,
                        default='./logs/midi_diffusion_v1/iter_50000.ckpt')
    parser.add_argument('--out_dir',   type=str, default='./results/midi_diffusion')
    parser.add_argument('--out_video', type=str, default='./results/midi_diffusion.mp4')
    args = parser.parse_args()

    audio, _ = librosa.load(args.mp3, sr=16000)
    duration  = len(audio) / 16000
    print(f'音频时长: {duration:.1f} 秒')

    piano_roll          = extract_piano_roll(args.mp3, duration)
    diffusion           = load_models(args.encoder_ckpt, args.diffusion_ckpt)
    right_poses, left_poses = generate_poses(piano_roll, diffusion)
    render_video(right_poses, left_poses, args.mp3, args.out_dir, args.out_video)


if __name__ == '__main__':
    main()
