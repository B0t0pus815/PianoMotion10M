"""
gentle_fix.py
=============
官方扩散模型生成自然手势 + 轻度 IK 修正对齐目标键。

大部分动作保持扩散模型原样（自然丝滑），
只对按键帧做小幅手腕平移 + 按键手指轻微下压。
"""
import os, sys, json, copy, argparse
import numpy as np
import torch
from scipy.signal import savgol_filter
from tqdm import tqdm

sys.path.insert(0, '.')

FPS = 30
HAND_SPLIT = 60
TIP_IDS = {'thumb': 744, 'index': 320, 'middle': 443, 'ring': 555, 'pinky': 672}

def pitch_to_pixel(pitch, width=1920):
    wo = [0,0,1,2,2,3,3,4,5,5,6,6]
    wi = (pitch-21)//12*7 + wo[(pitch-21)%12]
    return wi * (width/52.0) + (width/52.0)/2

def assign_fingers(pitches, is_right):
    fingers = ['thumb', 'index', 'middle', 'ring', 'pinky']
    sorted_p = sorted(pitches, reverse=(not is_right))
    return {p: fingers[min(i, 4)] for i, p in enumerate(sorted_p)}


# ─── 阶段 1: 官方模型推论，输出 MANO 参数 ────────────────────
def run_official_model(mp3_path):
    """用官方 Piano2Posi + Diffusion 生成手势参数"""
    print("[1/4] 官方模型推论...")
    
    import librosa
    audio_raw, _ = librosa.load(mp3_path, sr=16000)
    duration = len(audio_raw) / 16000
    
    # 加载官方模型
    from models.piano2posi import Piano2Posi
    from models.denoise_diffusion import GaussianDiffusion1D_piano2pose, Unet1D
    
    exp_path = 'logs/diffusion_posiguide_hubertbase_tf2'
    
    with open(f'{exp_path}/args.txt') as f:
        args = json.load(f)
    
    # Piano2Posi
    with open(f'{exp_path}/args_posi.txt') as f:
        args_posi = json.load(f)
    
    class A: pass
    ap = A()
    ap.__dict__ = args_posi
    # 本地 HuBERT 路径
    if 'hubert-base' in ap.wav2vec_path:
        ap.wav2vec_path = './checkpoints/hubert-base-ls960'
    elif 'hubert-large' in ap.wav2vec_path:
        ap.wav2vec_path = './checkpoints/hubert-large-ls960-ft'
    if not hasattr(ap, 'hidden_type'):
        ap.hidden_type = 'audio_f'
    
    piano2posi = Piano2Posi(ap)
    
    # UNet + Diffusion
    if 'hidden_type' in args:
        if args['hidden_type'] == 'audio_f':
            cond_dim = 768 if 'base' in args_posi.get('wav2vec_path','base') else 1024
        elif args['hidden_type'] == 'hidden_f':
            cond_dim = args_posi['feature_dim']
        elif args['hidden_type'] == 'both':
            cond_dim = args_posi['feature_dim'] + (768 if 'base' in args_posi.get('wav2vec_path','base') else 1024)
    else:
        cond_dim = 768

    unet = Unet1D(
        dim=args['unet_dim'],
        dim_mults=(1, 2, 4, 8),
        channels=args['bs_dim'],
        remap_noise=args.get('remap_noise', True),
        condition=True,
        guide=args['xyz_guide'],
        guide_dim=6 if args['xyz_guide'] else 0,
        condition_dim=cond_dim,
        encoder_type=args.get('encoder_type', 'none'),
        num_layer=args.get('num_layer', None)
    )
    
    model = GaussianDiffusion1D_piano2pose(
        unet, piano2posi,
        seq_length=args['train_sec'] * 30,
        timesteps=args['timesteps'],
        objective='pred_v',
    )
    
    # 加载权重
    ckpt_files = sorted([f for f in os.listdir(exp_path) if f.endswith('.ckpt')])
    ckpt_path = os.path.join(exp_path, ckpt_files[-1])
    state = torch.load(ckpt_path, map_location='cpu', weights_only=False)['state_dict']
    model.load_state_dict(state)
    model.cuda().eval()
    print(f'  模型加载: {ckpt_path}')
    
    # 分段推论
    seg_sec = args['train_sec']  # 8
    seg_samples = seg_sec * 16000
    seg_frames = seg_sec * FPS
    scale = torch.tensor([1.5, 1.5, 25.0]).cuda()
    
    all_right = []
    all_left = []
    
    with torch.no_grad():
        for start in tqdm(range(0, len(audio_raw), seg_samples), desc='  推论'):
            chunk = audio_raw[start:start+seg_samples]
            if len(chunk) < seg_samples:
                chunk = np.pad(chunk, (0, seg_samples - len(chunk)))
            
            audio_t = torch.FloatTensor(chunk).unsqueeze(0).cuda()
            pose_hat, guide = model.sample(audio_t, seg_frames, 1)
            
            pose_hat = pose_hat.permute(0, 2, 1)[0].cpu().numpy() * np.pi  # (T, 96)
            guide = (guide.permute(0, 2, 1) * scale.repeat(2))[0].cpu().numpy()  # (T, 6)
            
            # 平滑
            for i in range(pose_hat.shape[1]):
                pose_hat[:, i] = savgol_filter(pose_hat[:, i], 5, 2)
            for i in range(guide.shape[1]):
                guide[:, i] = savgol_filter(guide[:, i], 5, 2)
            
            # 组装: guide[:3] + pose[:48] = 右手, guide[3:] + pose[48:] = 左手
            right = np.concatenate([guide[:, :3], pose_hat[:, :48]], axis=1)  # (T, 51)
            left  = np.concatenate([guide[:, 3:], pose_hat[:, 48:]], axis=1)  # (T, 51)
            
            actual = min(seg_frames, int((len(audio_raw) - start) / 16000 * FPS))
            all_right.append(right[:actual])
            all_left.append(left[:actual])
    
    right_poses = np.concatenate(all_right, axis=0)
    left_poses  = np.concatenate(all_left, axis=0)
    print(f'  生成 {right_poses.shape[0]} 帧')
    return right_poses, left_poses, duration


# ─── 阶段 2: 轻度 IK 修正 ────────────────────────────────────
def gentle_ik_fix(right_poses, left_poses, midi_data, frame_num):
    """只对按键帧做小幅手腕平移，保持手指自然"""
    print("[2/4] 轻度 IK 修正...")
    
    from models.mano import build_mano
    mano = build_mano()
    mano['right'] = mano['right'].cuda()
    
    FX = 37500.0; cx = 960.0
    
    # 收集每帧活跃音符
    per_frame = [{'right': set(), 'left': set()} for _ in range(frame_num)]
    for inst in midi_data.instruments:
        if inst.is_drum: continue
        for note in inst.notes:
            fs = max(0, int(note.start * FPS))
            fe = min(frame_num, int(note.end * FPS) + 1)
            hand = 'right' if note.pitch > HAND_SPLIT else 'left'
            for f in range(fs, fe):
                per_frame[f][hand].add(note.pitch)
    
    # 对每帧: 算手中指当前像素位置 vs 目标像素，做小幅修正
    for frame in tqdm(range(frame_num), desc='  修正'):
        for hand, is_right, poses in [
            ('right', True, right_poses),
            ('left', False, left_poses),
        ]:
            pitches = per_frame[frame][hand]
            if not pitches:
                continue
            
            pitches = sorted(pitches)
            target_center_px = np.mean([pitch_to_pixel(p) for p in pitches])
            
            pose = poses[frame]
            
            # 用 MANO forward 算当前中指位置
            with torch.no_grad():
                output = mano['right'](
                    global_orient=torch.tensor(pose[3:6]).float().unsqueeze(0).cuda(),
                    hand_pose=torch.tensor(pose[6:51]).float().unsqueeze(0).cuda(),
                    betas=torch.zeros(1,10).float().cuda(),
                    transl=torch.tensor(pose[0:3]).float().unsqueeze(0).cuda()
                )
                verts = output.vertices[0]
                if not is_right:
                    verts = verts.clone()
                    verts[:, 0] *= -1
                
                mid_tip = verts[TIP_IDS['middle']].cpu().numpy()
                current_px = FX * mid_tip[0] / mid_tip[2] + cx
            
            error_px = target_center_px - current_px
            
            # 限制修正量: 最多移动 3 个白键 (约 111px)
            max_shift_px = 111.0
            error_px = np.clip(error_px, -max_shift_px, max_shift_px)
            
            # 只修正 50% 的误差 (保持自然感，不完全对齐)
            correction = error_px * 0.5
            
            if is_right:
                pose[0] += correction * mid_tip[2] / FX
            else:
                pose[0] -= correction * mid_tip[2] / FX
            
            # 按键手指轻微下压 (MCP +0.1 rad ≈ 6度)
            finger_map = assign_fingers(pitches, is_right)
            finger_list = ['thumb','index','middle','ring','pinky']
            for p, fname in finger_map.items():
                fi = finger_list.index(fname)
                base = 6 + fi * 9
                pose[base + 1] += 0.08  # MCP 轻微弯
            
            poses[frame] = pose
    
    # 再做一次平滑消除修正带来的跳变
    print("  平滑...")
    for dim in range(51):
        right_poses[:, dim] = savgol_filter(right_poses[:, dim], 7, 2)
        left_poses[:, dim]  = savgol_filter(left_poses[:, dim], 7, 2)
    
    return right_poses, left_poses


# ─── 主流程 ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='Gentle IK 修正 + 鍵盤疊加 (需先用 extract_piano_midi.py 產 MIDI)')
    parser.add_argument('--mp3', type=str, required=True)
    parser.add_argument('--midi', type=str, required=True,
                        help='已轉錄好的 MIDI 檔 (必填; 用 extract_piano_midi.py 產出)')
    parser.add_argument('--out_dir', type=str, default='./results/ik_output')
    parser.add_argument('--out_video', type=str, default='./results/ik_output_kb.mp4')
    args = parser.parse_args()

    if not os.path.exists(args.midi):
        raise FileNotFoundError(
            f'MIDI 檔不存在: {args.midi!r}. '
            f'请先用 extract_piano_midi.py 產生 MIDI 後再呼叫本腳本.')

    # 1. 官方模型推论
    right_poses, left_poses, duration = run_official_model(args.mp3)
    frame_num = right_poses.shape[0]

    # 2. 讀取 MIDI
    print(f"[MIDI] 讀取 → {args.midi}")
    import pretty_midi
    midi_data = pretty_midi.PrettyMIDI(args.midi)

    # 3. 轻度修正
    right_poses, left_poses = gentle_ik_fix(right_poses, left_poses, midi_data, frame_num)

    # 4. 渲染
    print("[3/4] 渲染...")
    os.makedirs(args.out_dir, exist_ok=True)
    from datasets.show import render_result
    render_result(args.out_dir, None, right_poses, left_poses, video=False)

    # 5. 键盘叠加 (传同一份 MIDI)
    print("[4/4] 叠加键盘...")
    kb_dir = args.out_dir + '_kb'
    os.system(f'python add_keyboard_overlay.py '
              f'--frames_dir {args.out_dir} '
              f'--mp3 "{args.mp3}" '
              f'--midi "{args.midi}" '
              f'--out_dir {kb_dir} '
              f'--out_video {args.out_video}')
    
    print(f"\n{'='*60}")
    print(f"✅ 完成! {args.out_video}")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
