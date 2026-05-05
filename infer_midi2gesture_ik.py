# DEPRECATED: This script uses basic_pitch which is no longer recommended.
# Please use extract_piano_midi.py (ByteDance High-Resolution Piano Transcription) instead.
"""
infer_midi2gesture_ik.py
========================
方案 C: Transformer 生成粗略手势 + IK 后处理精确对齐。

使用:
    python infer_midi2gesture_ik.py \
        --mp3 ./PianoMotion10M_Dataset/audio/470175873/BV1Rv411879H/BV1Rv411879H_seq_0000.mp3 \
        --ckpt ./logs/midi2gesture_c/best.ckpt
"""
import os, sys, argparse, json, math
import numpy as np
import torch
import pretty_midi
from tqdm import tqdm

# 项目模块
sys.path.insert(0, '.')
from train_midi2gesture import MidiToGestureTransformer, MIDI_NOTE_RANGE, POSE_DIM, FPS, SEQ_LEN, MIDI_NOTE_MIN, MIDI_NOTE_MAX
from midi_to_gesture import solve_wrist_x_ik, TIP_VERTEX_IDS, _middle_c_mano_x, HAND_SPLIT_NOTE

def load_model(ckpt_path):
    ckpt = torch.load(ckpt_path, map_location='cpu', weights_only=False)
    args = ckpt.get('args', {})
    model = MidiToGestureTransformer(
        d_model=args.get('d_model', 256),
        nhead=args.get('nhead', 8),
        num_layers=args.get('num_layers', 6),
        dim_feedforward=args.get('dim_feedforward', 1024),
    ).cuda()
    model.load_state_dict(ckpt['model_state'])
    model.eval()
    print(f"模型载入: {ckpt_path} (epoch {ckpt.get('epoch', '?')}, val_loss {ckpt.get('val_loss', '?'):.4f})")
    return model


def audio_to_midi(mp3_path):
    """用 basic-pitch 从 MP3 提取 MIDI"""
    print("[1/5] 提取 MIDI...")
    from basic_pitch.inference import predict
    _, midi_data, _ = predict(mp3_path)
    return midi_data


def midi_to_piano_roll(midi_data, duration):
    """把 MIDI 转成逐帧 piano roll"""
    frame_num = int(duration * FPS)
    roll = np.zeros((frame_num, MIDI_NOTE_RANGE), dtype=np.float32)
    for inst in midi_data.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            fs = max(0, int(note.start * FPS))
            fe = min(frame_num, int(note.end * FPS) + 1)
            idx = note.pitch - MIDI_NOTE_MIN
            if 0 <= idx < MIDI_NOTE_RANGE:
                roll[fs:fe, idx] = note.velocity / 127.0
    return roll


def get_active_notes_per_frame(midi_data, frame_num):
    """每帧的活跃音符: [{pitch: 'right'|'left'}, ...]"""
    per_frame = [dict() for _ in range(frame_num)]
    for inst in midi_data.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            fs = max(0, int(note.start * FPS))
            fe = min(frame_num, int(note.end * FPS) + 1)
            hand = 'right' if note.pitch > HAND_SPLIT_NOTE else 'left'
            for f in range(fs, fe):
                per_frame[f][note.pitch] = hand
    return per_frame


def infer_transformer(model, piano_roll):
    """Transformer 推论: 分段处理长序列"""
    print("[2/5] Transformer 推论...")
    frame_num = piano_roll.shape[0]
    right_all = np.zeros((frame_num, POSE_DIM), dtype=np.float32)
    left_all  = np.zeros((frame_num, POSE_DIM), dtype=np.float32)

    # 分段推论 (overlap 50% 取中间段避免边界效应)
    step = SEQ_LEN // 2  # 120 帧步进
    with torch.no_grad():
        for start in range(0, frame_num, step):
            end = min(start + SEQ_LEN, frame_num)
            seg = piano_roll[start:end]

            # 补齐到 SEQ_LEN
            if seg.shape[0] < SEQ_LEN:
                pad = np.zeros((SEQ_LEN - seg.shape[0], MIDI_NOTE_RANGE), dtype=np.float32)
                seg = np.concatenate([seg, pad], axis=0)

            midi_t = torch.FloatTensor(seg).unsqueeze(0).cuda()
            pred_r, pred_l = model(midi_t)
            pred_r = pred_r[0].cpu().numpy()
            pred_l = pred_l[0].cpu().numpy()

            # 反归一化 Z
            pred_r[:, 2] = pred_r[:, 2] * 10.0 + 14.0
            pred_l[:, 2] = pred_l[:, 2] * 10.0 + 14.0

            # 写入结果 (overlap 区域取后半段)
            actual_len = end - start
            if start == 0:
                write_start = 0
                write_len = min(actual_len, step + step // 2)
            else:
                write_start = step // 2  # 跳过前 1/4
                write_len = min(actual_len - write_start, step)

            dst_start = start + write_start
            dst_end = min(dst_start + write_len, frame_num)
            src_end = write_start + (dst_end - dst_start)

            right_all[dst_start:dst_end] = pred_r[write_start:src_end]
            left_all[dst_start:dst_end]  = pred_l[write_start:src_end]

    return right_all, left_all


def ik_postprocess(right_poses, left_poses, active_notes):
    """IK 后处理: 修正手腕位置让指尖对齐目标键"""
    print("[3/5] IK 后处理...")
    from models.mano import build_mano
    mano = build_mano()
    mano['right'] = mano['right'].cuda()

    wo = [0,0,1,2,2,3,3,4,5,5,6,6]
    frame_num = len(right_poses)

    def pitch_to_pixel(p):
        wi = (p-21)//12*7 + wo[(p-21)%12]
        return wi * (1920.0/52) + (1920.0/52)/2

    # 简单指法分配
    def assign_finger(pitch, is_right):
        if is_right:
            rel = max(0, min(36, pitch - 60))
            fi = int(rel / 36 * 4)
        else:
            rel = max(0, min(38, pitch - 21))
            fi = int(rel / 38 * 4)
            fi = 4 - fi
        return ['thumb','index','middle','ring','pinky'][fi]

    for frame in tqdm(range(frame_num)):
        notes = active_notes[frame]
        if not notes:
            continue

        # 分左右手音符
        right_notes = {p: h for p, h in notes.items() if h == 'right'}
        left_notes  = {p: h for p, h in notes.items() if h == 'left'}

        # 右手: 取最高权重音符做 IK
        if right_notes:
            dom_pitch = max(right_notes.keys())  # 最高音
            finger = assign_finger(dom_pitch, True)
            target_px = pitch_to_pixel(dom_pitch)
            right_poses[frame] = solve_wrist_x_ik(
                mano, right_poses[frame], finger, target_px, is_right=True)
            # Middle C boundary
            mc_x = _middle_c_mano_x(True)
            right_poses[frame, 0] = max(right_poses[frame, 0], mc_x)

        # 左手
        if left_notes:
            dom_pitch = min(left_notes.keys())  # 最低音
            finger = assign_finger(dom_pitch, False)
            target_px = pitch_to_pixel(dom_pitch)
            left_poses[frame] = solve_wrist_x_ik(
                mano, left_poses[frame], finger, target_px, is_right=False)
            mc_x = _middle_c_mano_x(False)
            left_poses[frame, 0] = max(left_poses[frame, 0], mc_x)

    return right_poses, left_poses


def render(right_poses, left_poses, out_dir):
    """渲染帧"""
    print("[4/5] 渲染...")
    os.makedirs(out_dir, exist_ok=True)
    from datasets.show import render_result
    render_result(out_dir, None, right_poses, left_poses, video=False)


def overlay_and_video(frames_dir, mp3_path, out_dir, out_video):
    """叠加键盘 + 合成影片"""
    print("[5/5] 叠加键盘并合成影片...")
    os.system(f'python add_keyboard_overlay.py '
              f'--frames_dir {frames_dir} '
              f'--mp3 "{mp3_path}" '
              f'--out_dir {out_dir} '
              f'--out_video {out_video}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mp3', type=str, required=True)
    parser.add_argument('--ckpt', type=str, default='./logs/midi2gesture_c/best.ckpt')
    parser.add_argument('--out_dir', type=str, default='./results/ik_output')
    parser.add_argument('--out_video', type=str, default='./results/ik_output_kb.mp4')
    parser.add_argument('--skip_ik', action='store_true', help='跳过 IK 后处理 (只看 Transformer 原始输出)')
    args = parser.parse_args()

    import librosa
    audio, sr = librosa.load(args.mp3, sr=16000)
    duration = len(audio) / 16000
    print(f"音频时长: {duration:.2f}s")

    # 1. 提取 MIDI
    midi_data = audio_to_midi(args.mp3)

    # 2. Transformer 推论
    model = load_model(args.ckpt)
    piano_roll = midi_to_piano_roll(midi_data, duration)
    right_poses, left_poses = infer_transformer(model, piano_roll)

    # 3. IK 后处理
    if not args.skip_ik:
        frame_num = int(duration * FPS)
        active_notes = get_active_notes_per_frame(midi_data, frame_num)
        right_poses, left_poses = ik_postprocess(right_poses, left_poses, active_notes)

    # 4. 渲染
    render_dir = args.out_dir
    render(right_poses, left_poses, render_dir)

    # 5. 键盘叠加 + 影片
    kb_dir = render_dir + '_kb'
    overlay_and_video(render_dir, args.mp3, kb_dir, args.out_video)

    print(f"\n{'='*60}")
    print(f"✅ 完成! 影片: {args.out_video}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
