"""
add_keyboard_overlay.py
=======================
在已渲染的手势图片上叠加钢琴键盘，
并根据 MIDI 高亮正在弹奏的琴键。

注意：本脚本不再做 MIDI 提取，必须传入 --midi 参数指向已转录好的 .mid 檔。
请先用 extract_piano_midi.py 产生 MIDI:
    python extract_piano_midi.py --mp3 input_songs/song.mp3
    # → input_songs/song.mid

使用方式：
    python add_keyboard_overlay.py \
        --frames_dir ./results/ik_teacher \
        --mp3 "./input_songs/summer.mp3" \
        --midi "./input_songs/summer.mid" \
        --out_dir ./results/ik_teacher_with_keyboard \
        --out_video ./results/ik_teacher_keyboard.mp4
"""

import math
import os
import sys
import argparse
import numpy as np
import cv2
from tqdm import tqdm

FPS = 30
MIDI_NOTE_MIN = 21   # A0（钢琴最低音）
MIDI_NOTE_MAX = 108  # C8（钢琴最高音）
HAND_SPLIT = 60

# 视觉指数衰减参数 (模拟钢琴弦的物理残响)
T_FULL_DEFAULT = 0.4    # 前 0.4s 全亮 (按下瞬间)
TAU_DEFAULT    = 0.5    # 之后指数衰减时间常数 (越大衰得越慢)
ALPHA_THRESHOLD = 0.03  # 低于此值视为完全熄灭


def compute_alpha(t_since_onset: float,
                  t_full: float = T_FULL_DEFAULT,
                  tau: float = TAU_DEFAULT) -> float:
    """指数衰减: 前 t_full 秒全亮 1.0, 之后 alpha = exp(-(t-t_full)/τ)."""
    if t_since_onset < 0:
        return 0.0
    if t_since_onset <= t_full:
        return 1.0
    return math.exp(-(t_since_onset - t_full) / tau)

# 手指编号: 拇指=1, 食指=2, 中指=3, 无名指=4, 小指=5
FINGER_NUM = {'thumb': '1', 'index': '2', 'middle': '3', 'ring': '4', 'pinky': '5'}
FINGER_ORDER = ['thumb', 'index', 'middle', 'ring', 'pinky']

# 键盘显示参数
KEYBOARD_HEIGHT = 200     # 键盘区域高度（像素）
WHITE_KEY_COLOR  = (240, 240, 240)
BLACK_KEY_COLOR  = (30, 30, 30)
HIGHLIGHT_RIGHT  = (100, 200, 255)  # 右手按键颜色（蓝）
HIGHLIGHT_LEFT   = (100, 255, 150)  # 左手按键颜色（绿）
GHOST_GRAY       = (130, 130, 130)  # 踏板余响 / 无人按 的中性灰
KEY_BORDER_COLOR = (80, 80, 80)

# 手指 X 距离阈值 (像素)
FINGER_NEAR_PX  = 30  # < 30px: 確認有指在上, 正常 label
FINGER_FAR_PX   = 60  # 30~60px: 邊緣狀態, label 加 '?' debug
                       # > 60px: 沒有手指真的在那, 不標 label, 改 ghost 灰


def assign_finger_labels(pitch_hand_map: dict) -> dict:
    """镜像 simple_natural.py 的 assign_fingers:
    右手: 升序 thumb→pinky; 左手: 降序 thumb→pinky。
    回传 {pitch: 'L1'|'2'|...}。"""
    out = {}
    for hand in ('right', 'left'):
        pitches = sorted(
            [p for p, h in pitch_hand_map.items() if h == hand],
            reverse=(hand == 'left'),
        )
        prefix = '' if hand == 'right' else 'L'
        for i, p in enumerate(pitches):
            finger = FINGER_ORDER[min(i, 4)]
            out[p] = prefix + FINGER_NUM[finger]
    return out


def is_black_key(midi_note: int) -> bool:
    return (midi_note % 12) in [1, 3, 6, 8, 10]


def get_white_key_index(midi_note: int) -> int:
    """该音符是第几个白键（从 A0 开始计）"""
    note_in_octave = (midi_note - 21) % 12
    octave = (midi_note - 21) // 12
    white_offset = [0, 0, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6]
    return octave * 7 + white_offset[note_in_octave]


def count_white_keys() -> int:
    """钢琴总白键数"""
    return get_white_key_index(MIDI_NOTE_MAX) + 1  # 52个


def _lerp_color(base, highlight, alpha):
    """alpha=0 → base, alpha=1 → highlight, 中间线性混合."""
    return tuple(int(base[i] * (1 - alpha) + highlight[i] * alpha) for i in range(3))


def build_keyboard_image(frame_width: int, active_notes: dict,
                          key_width: float = None, kb_height: int = None) -> np.ndarray:
    """
    建立钢琴键盘图片。

    参数：
        frame_width : 画布宽度（像素）
        active_notes: dict[midi_note -> (hand, label, alpha)]
                      hand: 'right' | 'left'
                      label: '1'..'5' (右手) / 'L1'..'L5' (左手)
                      alpha: 0.0~1.0 高亮强度 (0=不亮, 1=全亮, 中间=渐隐中)
        key_width   : 每个白键的像素宽度；None = 自动铺满 frame_width
        kb_height   : 键盘高度；None = 使用 KEYBOARD_HEIGHT 常数

    回传：
        keyboard: (kb_height, frame_width, 3) BGR 图片
    """
    LABEL_ALPHA_THRESHOLD = 0.95  # alpha 衰减后就不再显示手指编号 (避免文字跳动)

    def _unpack(entry):
        # 兼容 3-tuple (旧) / 4-tuple (新带 is_ghost)
        if len(entry) == 4:
            return entry
        hand, finger_label, alpha = entry
        return hand, finger_label, alpha, False

    def _highlight_for(hand, is_ghost):
        if is_ghost:
            return GHOST_GRAY
        return HIGHLIGHT_RIGHT if hand == 'right' else HIGHLIGHT_LEFT
    total_white = count_white_keys()
    kh = kb_height if kb_height is not None else KEYBOARD_HEIGHT

    if key_width is None:
        white_w = frame_width / total_white
        x_offset = 0
    else:
        white_w = key_width
        # 让整个键盘水平居中
        total_px = white_w * total_white
        x_offset = (frame_width - total_px) / 2

    black_w = white_w * 0.6
    black_h = kh * 0.62

    img = np.ones((kh, frame_width, 3), dtype=np.uint8) * 60  # 深灰背景
    label_ops = []  # 延后绘制, 在手势叠加后再画, 免得被手盖住

    # ── 先画白键 ──
    for note in range(MIDI_NOTE_MIN, MIDI_NOTE_MAX + 1):
        if is_black_key(note):
            continue
        wi = get_white_key_index(note)
        x1 = int(x_offset + wi * white_w)
        x2 = int(x_offset + (wi + 1) * white_w) - 1
        if x2 < 0 or x1 >= frame_width:
            continue

        color = WHITE_KEY_COLOR
        label = None
        if note in active_notes:
            hand, finger_label, alpha, is_ghost = _unpack(active_notes[note])
            color = _lerp_color(WHITE_KEY_COLOR, _highlight_for(hand, is_ghost), alpha)
            # ghost 状态本来 finger_label 就是 None, 这里再加一道 alpha 阈值
            if alpha >= LABEL_ALPHA_THRESHOLD and finger_label is not None:
                label = finger_label

        cv2.rectangle(img, (max(x1, 0), 0), (min(x2, frame_width-1), kh - 1), color, -1)
        cv2.rectangle(img, (max(x1, 0), 0), (min(x2, frame_width-1), kh - 1), KEY_BORDER_COLOR, 1)

        if label is not None:
            label_ops.append((
                (max(x1, 0) + min(x2, frame_width-1)) // 2,
                32,  # 顶部, 手一般不会盖到这么高
                label,
                min(0.8, white_w / 55.0),
            ))

    # ── 再画黑键 ──
    for note in range(MIDI_NOTE_MIN, MIDI_NOTE_MAX + 1):
        if not is_black_key(note):
            continue
        wi = get_white_key_index(note)
        cx_px = int(x_offset + (wi + 1) * white_w)
        x1 = int(cx_px - black_w / 2)
        x2 = int(cx_px + black_w / 2)
        y2 = int(black_h)
        if x2 < 0 or x1 >= frame_width:
            continue

        color = BLACK_KEY_COLOR
        label = None
        if note in active_notes:
            hand, finger_label, alpha, is_ghost = _unpack(active_notes[note])
            color = _lerp_color(BLACK_KEY_COLOR, _highlight_for(hand, is_ghost), alpha)
            if alpha >= LABEL_ALPHA_THRESHOLD and finger_label is not None:
                label = finger_label

        cv2.rectangle(img, (max(x1, 0), 0), (min(x2, frame_width-1), y2), color, -1)
        cv2.rectangle(img, (max(x1, 0), 0), (min(x2, frame_width-1), y2), KEY_BORDER_COLOR, 1)

        if label is not None:
            label_ops.append((
                (max(x1, 0) + min(x2, frame_width-1)) // 2,
                32,  # 顶部, 黑键内
                label,
                min(0.55, black_w / 45.0),
            ))

    cv2.putText(img, 'RIGHT', (5, kh - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, HIGHLIGHT_RIGHT, 1)
    cv2.putText(img, 'LEFT', (70, kh - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, HIGHLIGHT_LEFT, 1)

    return img, label_ops


def draw_labels(frame_img, label_ops, x_offset, y_offset):
    """在已合成的帧上画手指编号, 强制盖在手的上面"""
    font = cv2.FONT_HERSHEY_SIMPLEX
    for cx, cy, text, scale in label_ops:
        thick = 2
        (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
        tx = int(x_offset + cx - tw / 2)
        ty = int(y_offset + cy + th / 2)
        cv2.putText(frame_img, text, (tx, ty), font, scale, (255, 255, 255), thick + 2, cv2.LINE_AA)
        cv2.putText(frame_img, text, (tx, ty), font, scale, (0, 0, 0), thick, cv2.LINE_AA)


def pitch_key_center_x(pitch, frame_width, key_width=None):
    """琴键中心的像素 X, 与 build_keyboard_image 的几何一致"""
    total_white = count_white_keys()
    if key_width is None:
        white_w = frame_width / total_white
        x_offset = 0
    else:
        white_w = key_width
        x_offset = (frame_width - white_w * total_white) / 2
    wi = get_white_key_index(pitch)
    if is_black_key(pitch):
        return x_offset + (wi + 1) * white_w
    return x_offset + (wi + 0.5) * white_w


def label_by_nearest_fingertip(raw_per_frame, fingertips_data, frame_width, key_width):
    """几何最近邻 + 距离合理性检查.

    Input  raw[f]: dict[pitch -> (hand, alpha)]
    Output     :   dict[pitch -> (hand, label, alpha, is_ghost)]

    距离分级 (基于 X-pixel):
        < FINGER_NEAR_PX (30):  確認有指在按 → 正常 label, is_ghost=False
        FINGER_NEAR_PX ~ FINGER_FAR_PX (30~60): 邊緣狀態 → label 加 '?', is_ghost=False
        > FINGER_FAR_PX (60):  沒有手指在那 → label=None, is_ghost=True (灰高光)
    """
    finger_order = fingertips_data['finger_order']
    right_tips = np.array(fingertips_data['right'], dtype=np.float32)  # (n, 5, 2)
    left_tips  = np.array(fingertips_data['left'],  dtype=np.float32)

    per_frame = []
    for i, pm in enumerate(raw_per_frame):
        labels = {}
        for pitch, (hand, alpha) in pm.items():
            key_x = pitch_key_center_x(pitch, frame_width, key_width)
            tips = right_tips[i] if hand == 'right' else left_tips[i]
            # 只比 X (Y 在 simple_natural 渲染下不带按下/抬起信息)
            x_dists = np.abs(tips[:, 0] - key_x)
            finger_idx = int(np.argmin(x_dists))
            min_dist = float(x_dists[finger_idx])

            if min_dist > FINGER_FAR_PX:
                # 沒有手指真的在按 → ghost 灰, 不標 label
                labels[pitch] = (hand, None, alpha, True)
            else:
                finger = finger_order[finger_idx]
                prefix = '' if hand == 'right' else 'L'
                base = prefix + FINGER_NUM[finger]
                # 邊緣狀態加 '?' 方便 debug
                label = base if min_dist < FINGER_NEAR_PX else (base + '?')
                labels[pitch] = (hand, label, alpha, False)
        per_frame.append(labels)
    return per_frame


def extract_active_notes_per_frame(midi_path: str, total_frames: int,
                                   fingertips_path: str = None,
                                   frame_width: int = 1920,
                                   key_width: float = None,
                                   t_full: float = T_FULL_DEFAULT,
                                   tau: float = TAU_DEFAULT) -> list:
    """取得每帧正在弹奏的音符, 并贴上手指 label + alpha.

    每个 note 的视觉生命周期 (相對於 onset):
        [0, t_full]  alpha=1.0   全亮 (按下瞬间)
        (t_full, ∞)  alpha=exp(-(t-t_full)/τ)  指数衰减
        alpha < 0.03 视为完全熄灭, 不再写入 frame.

    Returns:
        per_frame: list, len=total_frames.
            每个元素 = dict[pitch -> (hand, label, alpha)].
    """
    import pretty_midi

    if not midi_path or not os.path.exists(midi_path):
        raise FileNotFoundError(
            f'MIDI 檔不存在: {midi_path!r}. '
            f'请先用 extract_piano_midi.py 產生 MIDI 後再呼叫本腳本.')
    print(f'[1/3] 讀取 MIDI: {midi_path} (decay t_full={t_full}s, τ={tau}s)')
    midi_data = pretty_midi.PrettyMIDI(midi_path)

    # 收集所有音符, 按 onset 排序; 同一 pitch 的後者覆寫前者 = 模拟 re-strike
    notes = []
    for inst in midi_data.instruments:
        if not inst.is_drum:
            notes.extend(inst.notes)
    notes.sort(key=lambda n: n.start)

    # 算 alpha 衰减到 ALPHA_THRESHOLD 时的最大 frame 数 (限制 inner loop)
    max_decay_secs = t_full + tau * math.log(1.0 / ALPHA_THRESHOLD)
    max_decay_frames = int(max_decay_secs * FPS) + 1

    raw = [dict() for _ in range(total_frames)]
    for note in notes:
        onset_frame = int(note.start * FPS)
        end_frame = onset_frame + max_decay_frames
        hand = 'right' if note.pitch > HAND_SPLIT else 'left'
        for f in range(max(0, onset_frame), min(total_frames, end_frame)):
            t_since = (f - onset_frame) / FPS
            alpha = compute_alpha(t_since, t_full, tau)
            if alpha < ALPHA_THRESHOLD:
                break  # alpha 单调递减, 后续帧也不会过关
            raw[f][note.pitch] = (hand, alpha)

    if fingertips_path and os.path.exists(fingertips_path):
        print(f'      用指尖数据定 label: {fingertips_path}')
        import json
        with open(fingertips_path) as f:
            ft = json.load(f)
        per_frame = label_by_nearest_fingertip(raw, ft, frame_width, key_width)
    else:
        # 没有指尖数据就退回音高排序
        print('      未提供指尖数据, 用 pitch 排序分配 (label 可能与视觉不一致)')
        per_frame = []
        for pm in raw:
            simple_pm = {p: h for p, (h, _alpha) in pm.items()}
            labels = assign_finger_labels(simple_pm)
            # 没有指尖数据无法判 ghost, 一律视为「在按」
            per_frame.append({p: (h, labels[p], a, False) for p, (h, a) in pm.items()})

    print(f'      共 {len(notes)} 个音符')
    return per_frame


def process_frames(frames_dir: str, active_notes_per_frame: list,
                   out_dir: str, keyboard_y: int = 710, keyboard_height: int = None,
                   keyboard_scale: float = 1.0, key_width: float = None):
    """把键盘叠加到每一帧图片上"""
    print('[2/3] 叠加键盘...')
    os.makedirs(out_dir, exist_ok=True)

    frame_files = sorted(
        [f for f in os.listdir(frames_dir) if f.endswith('.png')],
        key=lambda x: int(x.replace('frame_', '').replace('.png', ''))
    )

    kb_h = keyboard_height if keyboard_height is not None else KEYBOARD_HEIGHT

    for i, fname in enumerate(tqdm(frame_files)):
        img = cv2.imread(os.path.join(frames_dir, fname))
        if img is None:
            continue

        h, w = img.shape[:2]

        # 键盘宽度可缩放（scale < 1 = 缩小，让按键与手指比例更匹配）
        kb_w = int(w * keyboard_scale)
        x_off = (w - kb_w) // 2

        active = active_notes_per_frame[i] if i < len(active_notes_per_frame) else {}
        keyboard, label_ops = build_keyboard_image(
            w, active,
            key_width=key_width if keyboard_scale == 1.0 else None,
            kb_height=kb_h,
        )

        y_start = keyboard_y
        y_end = min(h, y_start + kb_h)
        actual_h = y_end - y_start

        # 贴键盘
        img[y_start:y_end, x_off:x_off + kb_w] = keyboard[:actual_h]

        # 手的部分：非黑色像素覆盖回来（整行）
        original = cv2.imread(os.path.join(frames_dir, fname))
        if original is not None:
            hand_mask = original[y_start:y_end, :].sum(axis=2) > 30
            img[y_start:y_end, :][hand_mask] = original[y_start:y_end, :][hand_mask]

        # 手指标签放最后, 确保不被手盖住
        draw_labels(img, label_ops, x_off, y_start)

        cv2.imwrite(os.path.join(out_dir, fname), img)


def make_video(out_dir: str, mp3_path: str, out_video: str):
    """合成含音乐的影片"""
    print('[3/3] 合成影片...')

    frames = sorted(
        [f for f in os.listdir(out_dir) if f.endswith('.png')],
        key=lambda x: int(x.replace('frame_', '').replace('.png', ''))
    )

    list_file = '/tmp/keyboard_frames.txt'
    with open(list_file, 'w') as f:
        for fr in frames:
            f.write(f"file '{os.path.abspath(out_dir)}/{fr}'\n")

    cmd = (f'ffmpeg -y -r {FPS} -f concat -safe 0 -i {list_file} '
           f'-i "{mp3_path}" -c:v libopenh264 -c:a aac -pix_fmt yuv420p '
           f'-shortest "{out_video}"')
    ret = os.system(cmd)
    if ret != 0:
        raise RuntimeError(f'ffmpeg failed (exit {ret})')
    print(f'✅ 完成！影片：{out_video}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--frames_dir', type=str, required=True,
                        help='渲染好的手势图片资料夹')
    parser.add_argument('--mp3', type=str, required=True,
                        help='原始 MP3（用于提取 MIDI 和音轨）')
    parser.add_argument('--out_dir', type=str,
                        default='./results/with_keyboard')
    parser.add_argument('--midi', type=str, required=True,
                        help='已轉錄好的 MIDI 檔路徑 (必填; 用 extract_piano_midi.py 產出)')
    parser.add_argument('--out_video', type=str,
                        default='./results/with_keyboard.mp4')
    parser.add_argument('--keyboard_y', type=int, default=710,
                        help='键盘顶部的像素行位置（默认 710）')
    parser.add_argument('--keyboard_height', type=int, default=None,
                        help='键盘高度（像素，默认 200）')
    parser.add_argument('--keyboard_scale', type=float, default=1.0,
                        help='键盘横向缩放比例，< 1 让琴键变窄（默认 1.0）')
    parser.add_argument('--key_width', type=float, default=51.87,
                        help='每个白键的像素宽度（默认 51.87，与 IK 物理投影对齐；填满全屏用 None）')
    parser.add_argument('--fingertips', type=str, default=None,
                        help='指尖投影 JSON (simple_natural.py 输出的 *_fingertips.json)')
    parser.add_argument('--decay_t_full', type=float, default=T_FULL_DEFAULT,
                        help=f'指數衰減: 前 N 秒保持全亮 (默認 {T_FULL_DEFAULT}s).')
    parser.add_argument('--decay_tau', type=float, default=TAU_DEFAULT,
                        help=f'指數衰減時間常數 τ (默認 {TAU_DEFAULT}s; 越大殘響越長; '
                             f'設超大值如 100 ≈ 完全不衰減).')
    args = parser.parse_args()

    frame_files = [f for f in os.listdir(args.frames_dir) if f.endswith('.png')]
    total_frames = len(frame_files)
    print(f'总帧数: {total_frames}')

    # 读一帧拿画布宽度, 用于后续几何换算
    sample = cv2.imread(os.path.join(args.frames_dir, frame_files[0]))
    frame_w = sample.shape[1] if sample is not None else 1920
    # overlay 与 build_keyboard_image 的 key_width 逻辑一致: scale!=1.0 时填满
    kw = args.key_width if args.keyboard_scale == 1.0 else None

    active_notes = extract_active_notes_per_frame(
        args.midi, total_frames,
        fingertips_path=args.fingertips,
        frame_width=frame_w,
        key_width=kw,
        t_full=args.decay_t_full,
        tau=args.decay_tau,
    )

    process_frames(args.frames_dir, active_notes, args.out_dir,
                   keyboard_y=args.keyboard_y,
                   keyboard_height=args.keyboard_height,
                   keyboard_scale=args.keyboard_scale,
                   key_width=args.key_width)

    make_video(args.out_dir, args.mp3, args.out_video)


if __name__ == '__main__':
    main()
