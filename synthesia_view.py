"""
synthesia_view.py — no-hand, Synthesia/flowkey-style falling-note renderer.
====================================================================

为什么有这支脚本
----------------
渲染手部动作的视频有个 ~33% 的「指尖落键不对」瑕疵 (动作保真度问题, 要重训
GPU 才有可能压下去, 见 reference_route_a / reference_landing_eval)。这支脚本
**完全丢弃手部姿态**, 改用业界 (Synthesia / flowkey) 的学习辅助范式:
带手指号的音条从上方落下, 落到底部高亮的琴键上。

关键: 音条上的手指号直接来自 Logic Track (`generate_fingering`), 也就是
**100% 的推荐指法** —— 没有手, 就没有「手指落错键」的问题。整条管线纯 CPU
(numpy / cv2 + ffmpeg), 不需要 torch GPU 渲染。

几何与配色复用 add_keyboard_overlay.py, 底部琴键直接调它的 build_keyboard_image,
所以亮键 + 键上数字的外观与既有 *_LABELED.mp4 一致。

用法:
    python synthesia_view.py \
        --midi results/canon_clean.mid \
        --mp3 "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mp3" \
        --out results/canon_synthesia.mp4
"""

import argparse
import math
import os
import subprocess
import sys
import wave

import numpy as np
import cv2
import pretty_midi
from tqdm import tqdm

from add_keyboard_overlay import (
    FPS, MIDI_NOTE_MIN, MIDI_NOTE_MAX, HAND_SPLIT,
    FINGER_NUM, HIGHLIGHT_RIGHT, HIGHLIGHT_LEFT, KEY_BORDER_COLOR,
    is_black_key, get_white_key_index, count_white_keys,
    pitch_key_center_x, build_keyboard_image, draw_labels,
)

FFMPEG = '/usr/bin/ffmpeg'   # conda 自带的 ffmpeg 关了 libx264, 一律用系统的 (见 reference_compute)

# ── 画布 / 布局 ──
WHITE_W = 32          # 白键像素宽 (无手, 不需要对齐 IK 投影, 取一个看着舒服的宽度)
ROLL_H = 760          # 上方落音区高度
KB_H = 200            # 底部键盘高度 (与 add_keyboard_overlay 默认一致)
LEAD = 3.0            # 提前量(秒): 音条从顶端落到击键线要 LEAD 秒
TAIL = 1.5            # 结尾留白(秒)
BG_COLOR = (24, 24, 28)
HITLINE_COLOR = (90, 90, 110)
GUIDE_COLOR = (44, 44, 52)   # 八度 C 的竖向参考线


def _frame_width() -> int:
    return int(WHITE_W * count_white_keys())   # 52 白键 → 1664px


def load_note_events(midi_path: str, source: str):
    """合并 pretty_midi 的 (onset, dur, pitch) 与 Logic Track 的推荐指法。

    回传 list[dict]: {onset, dur, pitch, hand, fnum, is_black}
        fnum: '1'..'5' 字符串, 没有推荐时 None。
    """
    from webui.realtime.fingering_engine import generate_fingering

    pm = pretty_midi.PrettyMIDI(midi_path)
    notes = []
    for inst in pm.instruments:
        if not inst.is_drum:
            notes.extend(inst.notes)

    # Logic Track 推荐: {(round(onset,2), pitch) -> (hand, finger_name)}
    onsets = generate_fingering(midi_path, source=source, use_override=True)
    rec = {(round(e.time, 2), int(e.pitch)): (e.expected_hand, e.expected_finger)
           for e in onsets}

    events = []
    for n in notes:
        hand_split = 'right' if n.pitch >= HAND_SPLIT else 'left'
        r = rec.get((round(n.start, 2), int(n.pitch)))
        if r is not None:
            hand, finger_name = r
            fnum = FINGER_NUM.get(finger_name)
        else:
            hand, fnum = hand_split, None
        events.append(dict(
            onset=float(n.start),
            dur=max(0.08, float(n.end - n.start)),
            pitch=int(n.pitch),
            hand=hand or hand_split,
            fnum=fnum,
            is_black=is_black_key(n.pitch),
        ))
    events.sort(key=lambda e: e['onset'])
    return events, pm.get_end_time()


def _bar_x_bounds(pitch: int, frame_width: int):
    """音条的左右像素边界, 与底部琴键几何对齐 (key_width=WHITE_W, 居中 offset=0)。"""
    cx = pitch_key_center_x(pitch, frame_width, key_width=WHITE_W)
    if is_black_key(pitch):
        half = WHITE_W * 0.6 * 0.5 * 0.86
    else:
        half = WHITE_W * 0.5 * 0.82
    return int(cx - half), int(cx + half), cx


def _draw_roll(canvas, events, t_now, frame_width):
    """在 canvas 的上半部 (0..ROLL_H) 画下落音条。"""
    pps = ROLL_H / LEAD          # 每秒像素
    # 八度参考线 (每个 C)
    for pitch in range(MIDI_NOTE_MIN, MIDI_NOTE_MAX + 1):
        if pitch % 12 == 0:      # C
            x = int(pitch_key_center_x(pitch, frame_width, key_width=WHITE_W))
            cv2.line(canvas, (x, 0), (x, ROLL_H), GUIDE_COLOR, 1)

    for e in events:
        # onset 边 (下沿) 在 t_now==onset 时落到击键线 y=ROLL_H
        y_onset = ROLL_H - (e['onset'] - t_now) * pps
        y_release = ROLL_H - (e['onset'] + e['dur'] - t_now) * pps
        if y_release >= ROLL_H or y_onset <= 0:
            continue   # 整条都在视野外
        x1, x2, cx = _bar_x_bounds(e['pitch'], frame_width)
        top = int(max(0, y_release))
        bot = int(min(ROLL_H, y_onset))
        if bot - top < 2:
            continue
        base = HIGHLIGHT_RIGHT if e['hand'] == 'right' else HIGHLIGHT_LEFT
        # 越接近击键线越亮 (下沿到线的距离归一)
        prox = 1.0 - min(1.0, abs(ROLL_H - y_onset) / ROLL_H)
        color = tuple(int(c * (0.55 + 0.45 * prox)) for c in base)
        cv2.rectangle(canvas, (x1, top), (x2, bot), color, -1)
        cv2.rectangle(canvas, (x1, top), (x2, bot), KEY_BORDER_COLOR, 1)
        # 手指号: 画在音条下沿附近 (即将触键的那一端), 条够高才画
        if e['fnum'] and (bot - top) >= 16:
            ty = min(bot - 6, ROLL_H - 6)
            scale = 0.7 if not e['is_black'] else 0.5
            (tw, th), _ = cv2.getTextSize(e['fnum'], cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
            tx = int(cx - tw / 2)
            ty = int(min(ty, bot - 4))
            cv2.putText(canvas, e['fnum'], (tx, ty), cv2.FONT_HERSHEY_SIMPLEX,
                        scale, (255, 255, 255), 3, cv2.LINE_AA)
            cv2.putText(canvas, e['fnum'], (tx, ty), cv2.FONT_HERSHEY_SIMPLEX,
                        scale, (0, 0, 0), 1, cv2.LINE_AA)

    # 击键线
    cv2.line(canvas, (0, ROLL_H), (frame_width, ROLL_H), HITLINE_COLOR, 2)


def _active_keyboard_notes(events, t_now):
    """当前正在发声的音 → build_keyboard_image 需要的 active_notes dict。
    {pitch -> (hand, label, alpha, is_ghost)}。"""
    active = {}
    for e in events:
        if e['onset'] <= t_now <= e['onset'] + e['dur'] + 0.05:
            label = (('' if e['hand'] == 'right' else 'L') + e['fnum']) if e['fnum'] else None
            active[e['pitch']] = (e['hand'], label, 1.0, label is None)
    return active


def synth_audio_from_midi(midi_path: str, out_wav: str, fs: int = 44100) -> str:
    """MIDI-only 曲目没有录音时, 用 pretty_midi 直接合成音轨 (纯正弦波, 无需
    soundfont / fluidsynth)。画面与音轨同源于一份 MIDI, 故音画天然完全同步。
    音色偏单薄但音高/时值清楚, 作为指法学习辅助足够。"""
    pm = pretty_midi.PrettyMIDI(midi_path)
    audio = pm.synthesize(fs=fs)                      # float64 单声道
    peak = float(np.max(np.abs(audio))) if audio.size else 1.0
    audio = (audio / (peak + 1e-9) * 0.89 * 32767.0).astype(np.int16)
    with wave.open(out_wav, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(audio.tobytes())
    print(f'      合成音轨: {out_wav} ({len(audio) / fs:.1f}s)')
    return out_wav


def render(midi_path, audio_path, out_path, source='arlstm'):
    frame_width = _frame_width()
    events, end_time = load_note_events(midi_path, source)
    if not events:
        raise SystemExit(f'MIDI 无音符: {midi_path}')

    total_secs = end_time + TAIL
    total_frames = int(total_secs * FPS)
    canvas_h = ROLL_H + KB_H
    print(f'[synthesia] {os.path.basename(midi_path)}  '
          f'{len(events)} 音符  {end_time:.1f}s  '
          f'{frame_width}x{canvas_h}  {total_frames} 帧  source={source}')

    # 直接把原始 BGR 帧 pipe 给 ffmpeg, 不落盘 PNG (快且省磁盘)。
    # 关键: 画面帧 t=0 == 乐曲 t=0 == 音轨 t=0, 与 *_LABELED.mp4 一致。
    # app 内是「静音 <video> + 独立 <audio> 同放」, 不能给音轨加偏移, 否则落键会比
    # 声音早 LEAD 秒。开头乐曲一般有前奏静音, 首音自然会从顶端落入, 不需要额外入场。
    cmd = [
        FFMPEG, '-y',
        '-f', 'rawvideo', '-pix_fmt', 'bgr24',
        '-s', f'{frame_width}x{canvas_h}', '-r', str(FPS), '-i', 'pipe:0',
        '-i', audio_path,
        '-map', '0:v', '-map', '1:a',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
        '-c:a', 'aac', '-pix_fmt', 'yuv420p', '-shortest',
        out_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    try:
        for f in tqdm(range(total_frames), desc='render'):
            t_now = f / FPS           # 画面 t=0 对齐乐曲 t=0
            canvas = np.empty((canvas_h, frame_width, 3), dtype=np.uint8)
            canvas[:] = BG_COLOR

            _draw_roll(canvas, events, t_now, frame_width)

            active = _active_keyboard_notes(events, t_now)
            keyboard, label_ops = build_keyboard_image(
                frame_width, active, key_width=WHITE_W, kb_height=KB_H)
            canvas[ROLL_H:ROLL_H + KB_H, :] = keyboard
            draw_labels(canvas, label_ops, 0, ROLL_H)

            proc.stdin.write(canvas.tobytes())
    finally:
        proc.stdin.close()
        ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f'ffmpeg 退出码 {ret}')
    print(f'✅ 完成: {out_path}')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--midi', required=True, help='已转录/清洗好的 .mid')
    ap.add_argument('--mp3', default=None,
                    help='配乐音轨; 省略则用 pretty_midi 从 --midi 合成 '
                         '(适合无录音的 MIDI-only 曲目, 音画完全同步)')
    ap.add_argument('--out', required=True, help='输出 mp4')
    ap.add_argument('--source', default='arlstm',
                    choices=['arlstm', 'pianoplayer', 'onnx'],
                    help='指法来源 (默认 arlstm = Logic Track 推荐指法)')
    args = ap.parse_args()

    if not os.path.exists(args.midi):
        sys.exit(f'找不到 MIDI: {args.midi}')
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    if args.mp3:
        if not os.path.exists(args.mp3):
            sys.exit(f'找不到音轨: {args.mp3}')
        audio_path = args.mp3
    else:
        audio_path = os.path.splitext(os.path.abspath(args.out))[0] + '_synth.wav'
        print('[synthesia] 未提供 --mp3 → 用 pretty_midi 合成音轨 (MIDI-only 曲目)')
        synth_audio_from_midi(args.midi, audio_path)

    render(args.midi, audio_path, args.out, source=args.source)


if __name__ == '__main__':
    main()
