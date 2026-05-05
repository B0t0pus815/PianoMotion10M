# DEPRECATED: This script uses basic_pitch which is no longer recommended.
# Please use extract_piano_midi.py (ByteDance High-Resolution Piano Transcription) instead.
"""
infer_encoder_regressor.py
直接用编码器的回归头生成手势，绕过扩散模型。
时序完全对齐，逐帧预测。
"""
import os, sys, argparse, numpy as np, torch, librosa
from tqdm import tqdm
sys.path.insert(0, '.')
from models.midi_encoder import MidiEncoderWithGuide

MIDI_NOTE_MIN   = 21
MIDI_NOTE_MAX   = 108
MIDI_NOTE_RANGE = 88
HAND_SPLIT      = 65
FPS             = 30

def extract_piano_roll(mp3_path, duration):
    print('[1/4] 提取 MIDI...')
    from basic_pitch.inference import predict
    _, midi_data, _ = predict(mp3_path)
    frame_num = int(duration * FPS)
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
    print(f'      {frame_num} 帧')
    return np.concatenate([roll_r, roll_l], axis=-1)

def load_model(encoder_ckpt):
    print('[2/4] 载入模型...')
    ckpt = torch.load(encoder_ckpt, map_location='cpu', weights_only=False)
    
    encoder = MidiEncoderWithGuide(
        d_model=512, nhead=8, num_layers=6, dim_feedforward=2048
    ).cuda()
    encoder.load_state_dict(ckpt['model_state'])
    encoder.eval()

    # pose_head 是训练时单独建立的，需要重新建立并载入
    # 检查 ckpt 里有没有 pose_head
    if 'pose_head_state' in ckpt:
        pose_head = torch.nn.Sequential(
            torch.nn.Linear(768, 512),
            torch.nn.ReLU(),
            torch.nn.Linear(512, 256),
            torch.nn.ReLU(),
            torch.nn.Linear(256, 102),
        ).cuda()
        pose_head.load_state_dict(ckpt['pose_head_state'])
    else:
        print('      ⚠️  ckpt 没有 pose_head，尝试从 encoder.guide_head 预测')
        pose_head = None

    print(f'      val_loss={ckpt["val_loss"]:.4f}')
    return encoder, pose_head

def generate_poses(piano_roll, encoder, pose_head):
    print('[3/4] 生成手势...')
    SEG = 240  # 每次处理 8 秒，减少边界效应
    frame_num = len(piano_roll)
    right_all = np.zeros((frame_num, 51), dtype=np.float32)
    left_all  = np.zeros((frame_num, 51), dtype=np.float32)

    with torch.no_grad():
        for start in tqdm(range(0, frame_num, SEG)):
            end   = min(start + SEG, frame_num)
            chunk = piano_roll[start:end]
            if len(chunk) < SEG:
                pad   = np.zeros((SEG - len(chunk), MIDI_NOTE_RANGE * 2), dtype=np.float32)
                chunk = np.concatenate([chunk, pad], axis=0)

            midi_t = torch.FloatTensor(chunk).unsqueeze(0).cuda()
            _, features = encoder(midi_t)  # (1, T, 768)

            if pose_head is not None:
                pred = pose_head(features)[0].cpu().numpy()  # (T, 102)
            else:
                # fallback: 用 guide_head
                pred = encoder.guide_head(
                    encoder.encoder.transformer(
                        encoder.encoder.pos_enc(
                            encoder.encoder.input_proj(midi_t)
                        )
                    )
                )[0].cpu().numpy()

            actual = end - start
            right_all[start:end] = pred[:actual, :51]
            left_all[start:end]  = pred[:actual, 51:102]

    # pose_head 直接预测原始标注值，不需要反归一化
    # 只需固定 Z 消除段间跳动
    right_all[:, 2] = 16.5
    left_all[:, 2]  = 16.5

    return right_all, left_all

def render_video(right_poses, left_poses, mp3_path, out_dir, out_video):
    print('[4/4] 渲染影片...')
    from datasets.show import render_result
    os.makedirs(out_dir, exist_ok=True)
    render_result(out_dir, None, right_poses, left_poses, video=False)
    frames = sorted(
        [f for f in os.listdir(out_dir) if f.endswith('.png')],
        key=lambda x: int(x.replace('frame_','').replace('.png',''))
    )
    list_file = '/tmp/enc_reg_frames.txt'
    with open(list_file, 'w') as f:
        for fr in frames:
            f.write(f"file '{os.path.abspath(out_dir)}/{fr}'\n")
    os.system(f'ffmpeg -y -r {FPS} -f concat -safe 0 -i {list_file} '
              f'-i "{mp3_path}" -c:v libx264 -c:a aac -pix_fmt yuv420p '
              f'-shortest "{out_video}"')
    print(f'✅ 完成：{out_video}')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mp3',          type=str, required=True)
    parser.add_argument('--encoder_ckpt', type=str,
                        default='./logs/midi_encoder_v4/best_encoder.ckpt')
    parser.add_argument('--out_dir',   type=str, default='./results/enc_regressor')
    parser.add_argument('--out_video', type=str, default='./results/enc_regressor.mp4')
    args = parser.parse_args()

    audio, _ = librosa.load(args.mp3, sr=16000)
    duration  = len(audio) / 16000

    piano_roll          = extract_piano_roll(args.mp3, duration)
    encoder, pose_head  = load_model(args.encoder_ckpt)
    right_poses, left_poses = generate_poses(piano_roll, encoder, pose_head)
    render_video(right_poses, left_poses, args.mp3, args.out_dir, args.out_video)

if __name__ == '__main__':
    main()
