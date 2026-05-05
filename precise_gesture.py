# DEPRECATED: This script uses basic_pitch which is no longer recommended.
# Please use extract_piano_midi.py (ByteDance High-Resolution Piano Transcription) instead.
"""
precise_gesture.py
==================
精确钢琴手势生成：MIDI 驱动 + 数据集手势检索 + IK 对齐

输入: MP3 (或已有 MIDI)
输出: 逐帧手势 → 渲染 + 键盘叠加影片

核心思路:
  1. MIDI 告诉我们每帧哪些键被按 → 精确的目标
  2. 从数据集中检索相似音符组合的真实手势 → 自然的手指角度
  3. IK 调整手腕位置 → 指尖精确对齐目标键
  4. Savgol 平滑 → 丝滑过渡
"""
import os, sys, argparse, pickle, json
import numpy as np
import torch
from scipy.signal import savgol_filter
from tqdm import tqdm

sys.path.insert(0, '.')

FPS = 30
HAND_SPLIT = 60  # Middle C: <=60 左手, >60 右手

# MANO 指尖 vertex
TIP_IDS = {'thumb': 744, 'index': 320, 'middle': 443, 'ring': 555, 'pinky': 672}

# MANO hand_pose 45 维中每根手指的关节索引
FINGER_SLICE = {
    'index': (0, 9), 'middle': (9, 18), 'ring': (18, 27),
    'pinky': (27, 36), 'thumb': (36, 45),
}

# 白键索引
def white_key_index(pitch):
    wo = [0,0,1,2,2,3,3,4,5,5,6,6]
    return (pitch-21)//12*7 + wo[(pitch-21)%12]

def pitch_to_pixel(pitch, width=1920):
    wi = white_key_index(pitch)
    return wi * (width/52.0) + (width/52.0)/2

def is_black_key(pitch):
    return (pitch % 12) in [1, 3, 6, 8, 10]

# ─── 指法分配 ────────────────────────────────────────────────
def assign_fingers(pitches, is_right):
    """
    给一组同时按下的音符分配手指。
    右手: 低→高 = 拇指→小指
    左手: 高→低 = 拇指→小指
    """
    fingers = ['thumb', 'index', 'middle', 'ring', 'pinky']
    sorted_pitches = sorted(pitches, reverse=(not is_right))
    assignment = {}
    for i, p in enumerate(sorted_pitches):
        if i < 5:
            assignment[p] = fingers[i]
        else:
            assignment[p] = fingers[4]  # 超过 5 个音归小指
    return assignment

# ─── 手势检索 ────────────────────────────────────────────────
class GestureRetriever:
    def __init__(self, index_path='results/gesture_index.pkl'):
        with open(index_path, 'rb') as f:
            self.samples = pickle.load(f)
        # 建立 n_notes → samples 的快速查找
        self.by_n = {}
        for s in self.samples:
            n = s['n_notes']
            if n not in self.by_n:
                self.by_n[n] = []
            self.by_n[n].append(s)
        print(f'手势库: {len(self.samples)} 样本')
    
    def query(self, active_pitches, is_right):
        """找最相似的手势模板"""
        n = len(active_pitches)
        # 在相同音符数里找, 找不到就扩大范围
        candidates = self.by_n.get(n, [])
        if not candidates:
            for delta in range(1, 10):
                candidates = self.by_n.get(n+delta, []) + self.by_n.get(max(1,n-delta), [])
                if candidates:
                    break
        if not candidates:
            candidates = self.samples
        
        # 按音域相似度排序
        target_center = np.mean(active_pitches)
        best = None
        best_dist = float('inf')
        for s in candidates:
            s_center = np.mean(s['active_notes'])
            dist = abs(s_center - target_center)
            if dist < best_dist:
                best_dist = dist
                best = s
        
        if is_right:
            return np.array(best['right_pose'], dtype=np.float32)
        else:
            return np.array(best['left_pose'], dtype=np.float32)

# ─── IK 定位 ─────────────────────────────────────────────────
def solve_multi_finger_ik(mano_layer, pose, finger_targets, is_right, steps=60):
    """
    Per-finger IK: 优化手腕位置 + 各手指关节角度，
    让多根指尖同时到达各自目标键。
    
    finger_targets: {finger_name: target_pixel_x}
    """
    FX = 37500.0; cx = 960.0
    
    # 阶段1: 手腕粗定位到目标中心
    target_center = np.mean(list(finger_targets.values()))
    transl = pose[0:3].copy()
    orient = pose[3:6].copy()
    hp = pose[6:51].copy()
    
    with torch.no_grad():
        output = mano_layer['right'](
            global_orient=torch.tensor(orient).float().unsqueeze(0).cuda(),
            hand_pose=torch.tensor(hp).float().unsqueeze(0).cuda(),
            betas=torch.zeros(1,10).float().cuda(),
            transl=torch.tensor(transl).float().unsqueeze(0).cuda()
        )
        verts = output.vertices[0]
        if not is_right:
            verts = verts.clone()
            verts[:, 0] *= -1
        mid_tip = verts[TIP_IDS['middle']].cpu().numpy()
        mid_px = FX * mid_tip[0] / mid_tip[2] + cx
        error = target_center - mid_px
        if is_right:
            transl[0] += error * mid_tip[2] / FX
        else:
            transl[0] -= error * mid_tip[2] / FX
    
    # 阶段2: 梯度优化手指角度
    hand_pose_t = torch.tensor(hp, dtype=torch.float32, device='cuda', requires_grad=True)
    transl_t = torch.tensor(transl, dtype=torch.float32, device='cuda', requires_grad=True)
    orient_t = torch.tensor(orient, dtype=torch.float32, device='cuda')
    orig_hp = hand_pose_t.clone().detach()
    
    optimizer = torch.optim.Adam([transl_t, hand_pose_t], lr=0.003)
    
    for _ in range(steps):
        optimizer.zero_grad()
        output = mano_layer['right'](
            global_orient=orient_t.unsqueeze(0),
            hand_pose=hand_pose_t.unsqueeze(0),
            betas=torch.zeros(1,10).float().cuda(),
            transl=transl_t.unsqueeze(0)
        )
        verts = output.vertices[0]
        if not is_right:
            verts = verts.clone()
            verts[:, 0] *= -1
        
        loss = torch.tensor(0.0, device='cuda')
        for fname, tgt_px in finger_targets.items():
            vi = TIP_IDS[fname]
            tip = verts[vi]
            px = FX * tip[0] / tip[2] + cx
            loss = loss + (px - tgt_px) ** 2
        
        for fname, (s, e) in FINGER_SLICE.items():
            if fname not in finger_targets:
                loss = loss + 5.0 * ((hand_pose_t[s:e] - orig_hp[s:e]) ** 2).sum()
            else:
                loss = loss + 0.1 * ((hand_pose_t[s:e] - orig_hp[s:e]) ** 2).sum()
        
        loss.backward()
        optimizer.step()
    
    pose[0:3] = transl_t.detach().cpu().numpy()
    pose[6:51] = hand_pose_t.detach().cpu().numpy()
    return pose

# ─── 主流程 ───────────────────────────────────────────────────
def extract_midi(mp3_path):
    print("[1/5] 提取 MIDI...")
    from basic_pitch.inference import predict
    _, midi_data, _ = predict(mp3_path)
    return midi_data

def get_per_frame_notes(midi_data, frame_num):
    """每帧的活跃音符，分左右手"""
    frames = [{'right': set(), 'left': set()} for _ in range(frame_num)]
    for inst in midi_data.instruments:
        if inst.is_drum: continue
        for note in inst.notes:
            fs = max(0, int(note.start * FPS))
            fe = min(frame_num, int(note.end * FPS) + 1)
            hand = 'right' if note.pitch > HAND_SPLIT else 'left'
            for f in range(fs, fe):
                frames[f][hand].add(note.pitch)
    return frames

def generate(mp3_path, out_dir, out_video):
    import librosa
    audio, sr = librosa.load(mp3_path, sr=16000)
    duration = len(audio) / 16000
    frame_num = int(duration * FPS)
    print(f"音频: {duration:.1f}s, {frame_num} 帧")
    
    # 1. MIDI
    midi_data = extract_midi(mp3_path)
    per_frame = get_per_frame_notes(midi_data, frame_num)
    
    # 2. 手势基准 (用中位数，不用检索)
    print("[2/5] 准备手势基准...")
    
    # 3. 加载 MANO
    print("[3/5] 加载 MANO + 生成手势...")
    from models.mano import build_mano
    mano = build_mano()
    mano['right'] = mano['right'].cuda()
    
    # 从数据集计算中位数手指角度（最自然的弹琴姿态）
    import glob as _glob
    _annos = sorted(_glob.glob('./PianoMotion10M_Dataset/annotation/*/*/*.json'))[:50]
    _all_r_hp = []
    _all_l_hp = []
    _all_r_orient = []
    _all_l_orient = []
    for _jf in _annos:
        with open(_jf) as _f:
            _d = json.load(_f)
        _r = np.array(_d['right'])[:, 1:52].astype(np.float32)
        _l = np.array(_d['left'])[:, 1:52].astype(np.float32)
        for _i in range(0, len(_r), 30):
            _all_r_hp.append(_r[_i, 6:51])
            _all_l_hp.append(_l[_i, 6:51])
            _all_r_orient.append(_r[_i, 3:6])
            _all_l_orient.append(_l[_i, 3:6])
    median_r_hp = np.median(_all_r_hp, axis=0).astype(np.float32)
    median_l_hp = np.median(_all_l_hp, axis=0).astype(np.float32)
    median_r_orient = np.median(_all_r_orient, axis=0).astype(np.float32)
    median_l_orient = np.median(_all_l_orient, axis=0).astype(np.float32)
    print(f'  中位数手指角度计算完成 ({len(_all_r_hp)} 样本)')
    
    # 构建默认静止姿态
    rest_right = np.zeros(51, dtype=np.float32)
    rest_right[0] = -0.085346  # X
    rest_right[1] = 0.289      # Y
    rest_right[2] = 24.5       # Z
    rest_right[3:6] = median_r_orient
    rest_right[6:51] = median_r_hp
    
    rest_left = np.zeros(51, dtype=np.float32)
    rest_left[0] = 0.009605
    rest_left[1] = 0.281
    rest_left[2] = 24.8
    rest_left[3:6] = median_l_orient
    rest_left[6:51] = median_l_hp
    
    right_poses = np.tile(rest_right, (frame_num, 1))
    left_poses  = np.tile(rest_left,  (frame_num, 1))
    prev_right = rest_right.copy()
    prev_left  = rest_left.copy()
    
    # 4. 逐帧: 检索模板 + IK 对齐
    for frame in tqdm(range(frame_num), desc="生成手势"):
        for hand, is_right, poses in [
            ('right', True, right_poses), 
            ('left', False, left_poses)
        ]:
            pitches = per_frame[frame][hand]
            prev = prev_right if is_right else prev_left
            if not pitches:
                next_pitches = None
                frames_until = 15
                for look in range(frame+1, min(frame + 15, frame_num)):
                    if per_frame[look][hand]:
                        next_pitches = sorted(per_frame[look][hand])
                        frames_until = look - frame
                        break
                pose = prev.copy()
                if next_pitches is not None:
                    next_center_px = np.mean([pitch_to_pixel(p) for p in next_pitches])
                    target_x = (next_center_px - 960.0) * prev[2] / 37500.0
                    if not is_right:
                        target_x = -target_x
                    alpha = min(0.3, 1.0 / max(frames_until, 1))
                    pose[0] = prev[0] + alpha * (target_x - prev[0])
                else:
                    rest = rest_right if is_right else rest_left
                    decay = 0.05
                    pose[0] = prev[0] + decay * (rest[0] - prev[0])
                    pose[6:51] = prev[6:51] + decay * (rest[6:51] - prev[6:51])
                poses[frame] = pose
                if is_right: prev_right = pose.copy()
                else: prev_left = pose.copy()
                continue
            
            pitches = sorted(pitches)
            pose = prev.copy()
            pose[1] = 0.289 if is_right else 0.281
            pose[2] = 24.5 if is_right else 24.8
            
            # 分配指法
            finger_map = assign_fingers(pitches, is_right)
            
            # 给所有活跃手指建立目标像素
            finger_targets = {}
            for p, fname in finger_map.items():
                finger_targets[fname] = pitch_to_pixel(p)
            # 如果多个音符分配给同一手指，取中间值
            merged = {}
            for fname, px in finger_targets.items():
                if fname not in merged:
                    merged[fname] = []
                merged[fname].append(px)
            finger_targets = {f: np.mean(pxs) for f, pxs in merged.items()}
            
            # Per-finger IK: 每根活跃手指独立对齐目标键
            pose = solve_multi_finger_ik(mano, pose, finger_targets, is_right)
            
            poses[frame] = pose
            if is_right: prev_right = pose.copy()
            else: prev_left = pose.copy()
    
    # 5. Savgol 平滑
    print("[4/5] 平滑...")
    for dim in range(51):
        right_poses[:, dim] = savgol_filter(right_poses[:, dim], 7, 2)
        left_poses[:, dim]  = savgol_filter(left_poses[:, dim], 7, 2)
    
    # 6. 渲染
    print("[5/5] 渲染...")
    os.makedirs(out_dir, exist_ok=True)
    from datasets.show import render_result
    render_result(out_dir, None, right_poses, left_poses, video=False)
    
    # 键盘叠加
    os.system(f'python add_keyboard_overlay.py '
              f'--frames_dir {out_dir} '
              f'--mp3 "{mp3_path}" '
              f'--out_dir {out_dir}_kb '
              f'--out_video {out_video}')
    
    print(f"\n{'='*60}")
    print(f"✅ 完成! {out_video}")
    print(f"{'='*60}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mp3', type=str, required=True)
    parser.add_argument('--out_dir', type=str, default='./results/ik_output')
    parser.add_argument('--out_video', type=str, default='./results/ik_output_kb.mp4')
    args = parser.parse_args()
    generate(args.mp3, args.out_dir, args.out_video)
