# DEPRECATED: This script uses basic_pitch which is no longer recommended.
# Please use extract_piano_midi.py (ByteDance High-Resolution Piano Transcription) instead.
"""
simple_natural.py
=================
自然手势 + 正确键位。
手指保持数据集中位数姿态（自然展开），
只移动手腕让手到目标区域，按键手指固定下压。
不用梯度优化，不会扭曲。
"""
import os, sys, argparse, json
from typing import Dict, List, Optional, Tuple
import numpy as np
import torch
import glob
from scipy.signal import savgol_filter
from tqdm import tqdm

sys.path.insert(0, '.')

# Route B: biomechanical Viterbi solver (no wrist, pure finger-pair cost)
from biomechanical_fingering import (
    FingeringConfig, BiomechanicalCostCalculator, ViterbiFingeringSolver,
)

FPS = 30
HAND_SPLIT = 60
TIP_IDS = {'thumb': 744, 'index': 320, 'middle': 443, 'ring': 555, 'pinky': 672}
FINGER_LIST = ['thumb','index','middle','ring','pinky']

# 每根手指在 hand_pose 45维中的位置
# index:0-8, middle:9-17, ring:18-26, pinky:27-35, thumb:36-44
FINGER_SLICE = {
    'index': (0,9), 'middle': (9,18), 'ring': (18,27),
    'pinky': (27,36), 'thumb': (36,45),
}

# 按键时各关节的弯曲增量 (自然的按键动作)
# 按键弯曲增量: MCP 弯 ~25度, PIP ~15度, DIP ~10度 (明显的按键动作)
PRESS_DELTA = {
    'thumb':  [0, 0.05, 0,  0, 0.20, 0,  0, 0.15, 0],
    'index':  [0, 0.40, 0,  0, 0.25, 0,  0, 0.15, 0],
    'middle': [0, 0.40, 0,  0, 0.25, 0,  0, 0.15, 0],
    'ring':   [0, 0.40, 0,  0, 0.25, 0,  0, 0.15, 0],
    'pinky':  [0, 0.40, 0,  0, 0.25, 0,  0, 0.15, 0],
}

# 手指张开角度: 每根手指 MCP 的横向展开 (axis-angle 的第一个分量)
# 正值=远离中指方向展开
SPREAD_BASE = {
    'thumb':  -0.15,
    'index':  -0.06,
    'middle':  0.00,
    'ring':    0.06,
    'pinky':   0.12,
}

def pitch_to_pixel(pitch, width=1920, key_width=51.87):
    """琴键中心的 screen X.
    与 add_keyboard_overlay.pitch_key_center_x 一致:
      - key_width=51.87 是物理投影 (FX*0.023m/Z @ Z=16.62) 让 IK 目标跟 overlay 键对齐
      - 黑键放在两白键之间 (而非白键中心)
      - key_width=None 则填满 frame_width (旧行为)
    """
    wo = [0, 0, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6]
    rem = (pitch - 21) % 12
    octave = (pitch - 21) // 12
    wi = octave * 7 + wo[rem]
    is_black = rem in (1, 4, 6, 9, 11)
    total_white = 52

    if key_width is None:
        white_w = width / total_white
        x_offset = 0.0
    else:
        white_w = key_width
        x_offset = (width - white_w * total_white) / 2.0

    if is_black:
        return x_offset + (wi + 1) * white_w
    return x_offset + (wi + 0.5) * white_w

def assign_fingers(pitches, is_right):
    """根據相鄰音的半音距估算合理跨指.
    - 1-2 半音 (一鍵內): 相鄰指
    - 3-4 半音 (約二度~三度): 隔一個指
    - 5+ 半音 (四度以上): 跨更遠
    這樣 {C4, G4} 會被指派到 (thumb, ring/pinky) 而不是 (thumb, index).
    """
    fingers = ['thumb','index','middle','ring','pinky']
    sorted_p = sorted(pitches, reverse=(not is_right))
    n = len(sorted_p)
    if n == 0:
        return {}
    if n > 5:
        # 超過 5 顆音不可能用單手, 保留舊邏輯避免崩潰
        return {p: fingers[min(i, 4)] for i, p in enumerate(sorted_p)}

    # 從第 0 根指 (thumb) 開始, 根據半音距遞推 finger slot
    slots = [0]
    for i in range(1, n):
        interval = abs(sorted_p[i] - sorted_p[i-1])
        # 半音距 → 跨指數: 1-2→1, 3-4→2, 5-7→3, 8+→4
        if interval <= 2:
            step = 1
        elif interval <= 4:
            step = 2
        elif interval <= 7:
            step = 3
        else:
            step = 4
        slots.append(min(slots[-1] + step, 4))
    # 若整體 slot 範圍超過 4 (5 根指上限), 再壓縮回 [0, 4]
    if slots[-1] > 4:
        scale = 4 / slots[-1]
        slots = [int(round(s * scale)) for s in slots]
    return {p: fingers[s] for p, s in zip(sorted_p, slots)}


def fingertip_screen_x(mano_layer, pose, is_right, fx=37500.0, cx=960.0):
    """单 pose forward, 回传 5 根指尖的 screen X (按 FINGER_LIST 顺序)"""
    p = torch.tensor(pose).float().cuda().unsqueeze(0)
    with torch.no_grad():
        out = mano_layer['right'](
            global_orient=p[:, 3:6],
            hand_pose=p[:, 6:51],
            betas=torch.zeros(1, 10, device='cuda'),
            transl=p[:, 0:3],
        )
    verts = out.vertices[0]
    if not is_right:
        verts = verts.clone()
        verts[:, 0] *= -1
    xs = np.zeros(5, dtype=np.float32)
    for i, fname in enumerate(FINGER_LIST):
        tip = verts[TIP_IDS[fname]]
        xs[i] = (fx * tip[0] / tip[2] + cx).item()
    return xs


def nearest_finger_assign(pitches, ref_xs):
    """每个 pitch 选离 ref_xs[i] 最近的可用指; greedy 先锁'最确定'的对子.
    ref_xs 是该手 5 根指尖在某基准位置的 screen X (通常 = wrist_screen + 自然 offsets)."""
    targets = [(p, pitch_to_pixel(p)) for p in pitches]
    targets.sort(key=lambda pt: min(abs(ref_xs[i] - pt[1]) for i in range(5)))
    available = set(range(5))
    finger_map = {}
    for pitch, tx in targets:
        best = min(available, key=lambda i: abs(ref_xs[i] - tx))
        finger_map[pitch] = FINGER_LIST[best]
        available.discard(best)
    return finger_map


def wrist_screen_x(pose, is_right, fx=37500.0, cx=960.0):
    """从 pose transl 算 wrist 投影到 screen 的 X (左手做镜像)."""
    if is_right:
        return fx * float(pose[0]) / float(pose[2]) + cx
    return fx * (-float(pose[0])) / float(pose[2]) + cx


def all_in_reach(natural_xs, pitches, tol=15.0):
    """目标键中心 X 都落在自然手指跨度 (±tol) 内."""
    lo, hi = float(min(natural_xs)) - tol, float(max(natural_xs)) + tol
    return all(lo <= pitch_to_pixel(p) <= hi for p in pitches)


def extract_events(per_frame, hand_key, total_frames):
    """该手的事件序列 (start_frame, frozenset(pitches)).
    pitch 集合改变时新增 event."""
    events = []
    last_pitches = frozenset()
    for f in range(total_frames):
        pitches = frozenset(per_frame[f][hand_key])
        if pitches and pitches != last_pitches:
            events.append((f, pitches))
        last_pitches = pitches
    return events


def plan_fingering_nearest(events, offsets, is_right, lookahead: int = 4):
    """Geometric nearest with windowed hand-center anchor (v2).

    For each event, the wrist anchor is the MEDIAN target pixel of the surrounding
    [-lookahead, +lookahead] events. This decouples the wrist from each individual
    note's finger choice — without it, whichever finger plays first self-reinforces
    (wrist follows that finger → next nearby target is closest to the SAME finger).

    Within a stable phrase (notes close in pitch), the wrist sits in one place and
    all 5 fingers naturally reach their respective ranges:
       thumb (offset_min)  → lowest notes (for right hand)
       index               → low-mid
       middle              → middle of phrase
       ring                → mid-high
       pinky (offset_max)  → highest

    Each note picks the finger whose natural pixel position (wrist_anchor + offset[f])
    is closest to its target → balanced finger usage, especially middle.
    """
    fmaps = []
    if not events:
        return fmaps

    # Pre-compute target pixel for each event (center note of chord, or only note)
    event_targets = []
    for (_, pitches) in events:
        sorted_p = sorted(pitches)
        center_p = sorted_p[len(sorted_p) // 2]
        event_targets.append(pitch_to_pixel(center_p))
    event_targets = np.array(event_targets, dtype=np.float32)

    for i, (frame, pitches) in enumerate(events):
        sorted_p = sorted(pitches)
        center_p = sorted_p[len(sorted_p) // 2]
        target = event_targets[i]

        # Windowed median anchor — robust to outliers, stays in current phrase
        lo, hi = max(0, i - lookahead), min(len(events), i + lookahead + 1)
        wrist_anchor = float(np.median(event_targets[lo:hi]))

        natural_xs = wrist_anchor + offsets  # 5 finger pixel positions
        if len(pitches) > 1:
            # Chord: Hungarian assignment — minimize total finger-to-target distance
            # so each note goes to the closest *available* finger.
            try:
                from scipy.optimize import linear_sum_assignment
                pitch_list = list(pitches)
                cost = np.abs(natural_xs[None, :] - np.array(
                    [pitch_to_pixel(p) for p in pitch_list])[:, None])
                row_ind, col_ind = linear_sum_assignment(cost)
                chord_fmap = {pitch_list[r]: FINGER_LIST[c]
                              for r, c in zip(row_ind, col_ind)}
            except Exception:
                # fallback to musical interval-based assignment
                chord_fmap = assign_fingers(pitches, is_right)
            fmaps.append(chord_fmap)
        else:
            distances = np.abs(natural_xs - target)
            best_idx = int(np.argmin(distances))
            fmaps.append({center_p: FINGER_LIST[best_idx]})
    return fmaps


MAX_HAND_SPAN_SEMITONES = 13   # adult pianist 1↔5 reach: octave + minor 2nd


def _make_feasible_chord(pitches_sorted):
    """Reduce a chord to one a single hand can physically play.

    Two sequential defences:

    [Plan A.1] Count cap — solver has 5 fingers max. If >5 notes, keep min, max,
               and 3 evenly-spaced inner pitches.

    [Plan A.2] Span cap — even ≤5 notes can exceed a single-hand reach when
               sustain-pedal makes consecutive notes appear simultaneous
               (e.g. bass + melody glued together with 16-semitone span).
               Physical limit = MAX_HAND_SPAN_SEMITONES (13). While the
               current span exceeds it, drop the note farthest from the
               median of remaining pitches — simulates a player releasing
               the most outlying ringing note.

    Always returns sorted-ascending; downstream code can rely on order.
    """
    n = len(pitches_sorted)

    # ── A.1: count cap ──
    if n > 5:
        lo_pitch = pitches_sorted[0]
        hi_pitch = pitches_sorted[-1]
        inner = pitches_sorted[1:-1]                   # len = n - 2 (≥ 4 here)
        m = len(inner)
        chosen_inner = [inner[int((i + 0.5) * m / 3)] for i in range(3)]
        kept = [lo_pitch] + chosen_inner + [hi_pitch]
    else:
        kept = list(pitches_sorted)

    # ── A.2: span cap ──
    while len(kept) > 1 and (kept[-1] - kept[0]) > MAX_HAND_SPAN_SEMITONES:
        # median of remaining pitches
        median = kept[len(kept) // 2]
        # drop whichever end is farther from the median (simulates releasing
        # the most-outlying ringing note)
        if abs(kept[0] - median) > abs(kept[-1] - median):
            kept = kept[1:]
        else:
            kept = kept[:-1]

    return kept


def apply_biomech_fingering(events, is_right):
    """Route B integration: run the biomechanical Viterbi solver over `events`
    and return fmaps in the SAME shape as plan_fingering_dp / plan_fingering_nearest
    (list of {pitch: finger_name_str}, one entry per event).

    Pipeline:
      1. Phrase-split: where event[i].start_frame - event[i-1].start_frame > FPS
         (i.e. >1 second between onsets), break the sequence. The solver only
         sees biomechanically-meaningful continuations.
      2. Chord-grouping: each event already encodes simultaneously-active pitches
         as a frozenset → convert to sorted list for the solver.
      3. Solve each phrase independently with FingeringConfig(hand=...).
      4. Unpack each Tuple[int,...] back into {pitch: FINGER_LIST[idx-1]}.
         Solver returns fingers in the same pitch-sorted order it received them,
         so we zip with the sorted pitch list.

    Note: `events` and the offsets/anatomy in this file are no longer needed —
    the biomech solver is wrist-free and uses its own anatomy tables. We keep
    the `events` signature for drop-in compatibility with the existing flow.
    """
    hand = 'right' if is_right else 'left'
    # Client-side override: bias the Viterbi away from single-finger dominance.
    # Defaults in biomechanical_fingering.py are untouched per Route B spec;
    # we inject this tuning ONLY for the simple_natural integration.
    cfg = FingeringConfig(
        hand=hand,
        base_repeated_penalty=150.0,    # 極度懲罰同指換音，強迫輪替手指
        alpha=3.0,                      # 降低二次跨度懲罰，鼓勵手指張開
        thumb_cross_base_penalty=2.0,   # 降低大拇指基礎穿指門檻
        thumb_cross_per_semitone=1.5,   # 降低穿指時的半音距離懲罰
    )
    calc = BiomechanicalCostCalculator(cfg)
    solver = ViterbiFingeringSolver(calc)

    PHRASE_GAP_FRAMES = FPS  # >1 second onset gap → phrase break

    # Group events into phrases
    phrases = []           # list of (start_event_idx, end_event_idx) pairs
    if events:
        cur_start = 0
        for i in range(1, len(events)):
            gap = events[i][0] - events[i - 1][0]
            if gap > PHRASE_GAP_FRAMES:
                phrases.append((cur_start, i))
                cur_start = i
        phrases.append((cur_start, len(events)))

    fmaps = [None] * len(events)
    for (lo, hi) in phrases:
        # ── Plan A: Pre-process — make every event physically feasible ──
        # Real MIDI extraction sometimes glues overlapping notes into chords
        # that no human hand can play (too many notes OR span > one hand).
        # Send the solver a physically-feasible reduction; we'll fill the
        # omitted notes back in post-process by nearest-pitch finger.
        phrase_events_orig = [sorted(events[i][1]) for i in range(lo, hi)]
        phrase_events_kept = [_make_feasible_chord(p) for p in phrase_events_orig]

        try:
            result = solver.solve(phrase_events_kept)   # List[Tuple[int, ...]]
        except ValueError:
            # ── Plan B: Per-event fallback (shrink blast radius) ──
            # The phrase-level solver failed (a transition between two events
            # is infeasible even after Plan A). Don't poison the whole phrase
            # with middle-finger fallback — re-solve each event in isolation
            # so the rest of the phrase keeps its proper Viterbi-decoded
            # fingering. Only events that fail *even alone* get [3]*n.
            result = []
            n_failed = 0
            for ev in phrase_events_kept:
                try:
                    single = solver.solve([ev])           # 1-event "phrase"
                    result.append(single[0])
                except ValueError:
                    result.append(tuple([3] * len(ev)))   # last-resort middle
                    n_failed += 1
            if n_failed:
                print(f'[apply_biomech_fingering] {n_failed}/{len(phrase_events_kept)} '
                      f'event(s) in this phrase fell back to middle finger '
                      f'(per-event fallback, not whole-phrase).')

        # ── Post-process: unpack solver result + fill omitted notes ──
        for offset, finger_tuple in enumerate(result):
            ev_idx = lo + offset
            kept     = phrase_events_kept[offset]
            original = phrase_events_orig[offset]

            # 1) Kept notes → direct solver assignment
            kept_to_finger = {
                p: FINGER_LIST[fi - 1]            # int 1..5 → 'thumb'/'index'/...
                for p, fi in zip(kept, finger_tuple)
            }

            # 2) Omitted notes → copy the finger of the nearest-by-pitch kept note
            #    (physically: one finger straddles two adjacent keys)
            fmap = dict(kept_to_finger)
            for p in original:
                if p in kept_to_finger:
                    continue
                nearest_kept = min(kept_to_finger, key=lambda kp: abs(kp - p))
                fmap[p] = kept_to_finger[nearest_kept]

            fmaps[ev_idx] = fmap

    return fmaps


def apply_arlstm_fingering(events, is_right, midi_path, frame_tol=5):
    """Stage B: replace biomech v4's Viterbi solver with Ramoneda 2022 ArLSTM.

    Drop-in compatible with apply_biomech_fingering — returns list of
    {pitch: finger_name_str}, one entry per event. Alignment between
    ArLSTM's per-note (time_sec, pitch) output and the (frame, pitches)
    events is done via (round(time*FPS), pitch) lookup with ±frame_tol
    slack. Notes for which ArLSTM has no prediction fall back to the
    biomech v4 solver — this matters for the rare 6+ note chord case
    that ArLSTM was not trained on (PIG has at most 5 simultaneous notes).
    """
    hand = 'right' if is_right else 'left'
    try:
        from ramoneda_predict import predict as _arlstm_predict
        fingers, info = _arlstm_predict(midi_path, hand=hand, kind='ArLSTM')
    except (ImportError, RuntimeError, FileNotFoundError):
        # External Ramoneda repo missing OR no notes for this hand — fully delegate.
        return apply_biomech_fingering(events, is_right)

    # (frame_idx, pitch) → finger_name
    lookup: Dict[Tuple[int, int], str] = {}
    pitch_frames: Dict[int, List[Tuple[int, str]]] = {}
    for (t, p), f in zip(info, fingers):
        frame_idx = int(round(float(t) * FPS))
        p = int(p)
        name = FINGER_LIST[int(f) - 1]
        lookup[(frame_idx, p)] = name
        pitch_frames.setdefault(p, []).append((frame_idx, name))

    fmaps: List[Optional[dict]] = [None] * len(events)
    biomech_fallback = None  # lazy — only build if we need fallback

    for ev_idx, (ev_frame, ev_pitches) in enumerate(events):
        fmap: Dict[int, str] = {}
        misses: List[int] = []
        for p in sorted(ev_pitches):
            name = lookup.get((ev_frame, int(p)))
            if name is None:
                # ±frame_tol slack for jitter between MIDI parsers
                cands = pitch_frames.get(int(p), [])
                if cands:
                    nearest = min(cands, key=lambda x: abs(x[0] - ev_frame))
                    if abs(nearest[0] - ev_frame) <= frame_tol:
                        name = nearest[1]
            if name is None:
                misses.append(int(p))
            else:
                fmap[int(p)] = name

        if misses:
            if biomech_fallback is None:
                biomech_fallback = apply_biomech_fingering(events, is_right)
            bm = biomech_fallback[ev_idx] or {}
            for p in misses:
                fmap[p] = bm.get(p, 'middle')

        fmaps[ev_idx] = fmap

    return fmaps


def plan_fingering_dp(events, offsets, is_right,
                     wrist_move_w=1.0, same_finger_pen=40.0,
                     ring_pinky_bonus=-3.0):
    """Viterbi: 给每个 event 选 center finger, 全局最小化
    wrist_move_w * |Δ手腕| + same_finger_pen * (同指换不同 pitch)
    + ring_pinky_bonus * (用 ring/pinky 折抵, 鼓勵走出 thumb/index 舒適圈).

    回传: list of {pitch: finger_name}, 一个 dict 一个 event.
    """
    n = len(events)
    if n == 0:
        return []

    targets = []
    chord_fmaps = [None] * n
    candidates = []
    for i, (frame, pitches) in enumerate(events):
        sorted_p = sorted(pitches)
        center_p = sorted_p[len(sorted_p) // 2]
        targets.append(pitch_to_pixel(center_p))
        if len(pitches) > 1:
            sort_map = assign_fingers(pitches, is_right)
            chord_fmaps[i] = sort_map
            candidates.append([FINGER_LIST.index(sort_map[center_p])])
        else:
            candidates.append(list(range(5)))

    INF = float('inf')
    cost = [[INF] * 5 for _ in range(n)]
    parent = [[-1] * 5 for _ in range(n)]

    for f in candidates[0]:
        # 不加初始指偏好 — 让 wrist 一致性主导, 避免把低音强拉到 ring/middle 的串位
        cost[0][f] = 0.0

    for i in range(1, n):
        target_changed = abs(targets[i] - targets[i-1]) > 1.0
        for f_i in candidates[i]:
            wrist_i = targets[i] - offsets[f_i]
            best = INF
            best_prev = -1
            for f_prev in candidates[i-1]:
                if cost[i-1][f_prev] >= INF:
                    continue
                wrist_prev = targets[i-1] - offsets[f_prev]
                wrist_move = abs(wrist_i - wrist_prev)
                pen = same_finger_pen if (f_prev == f_i and target_changed) else 0.0
                # ring (idx=3) / pinky (idx=4) 加 bonus (负值 = 主动鼓励)
                bonus = ring_pinky_bonus if f_i in (3, 4) else 0.0
                total = cost[i-1][f_prev] + wrist_move_w * wrist_move + pen + bonus
                if total < best:
                    best = total
                    best_prev = f_prev
            cost[i][f_i] = best
            parent[i][f_i] = best_prev

    # backtrack
    valid = [f for f in candidates[n-1] if cost[n-1][f] < INF]
    if not valid:
        # 退路: sort everywhere
        return [chord_fmaps[i] or assign_fingers(events[i][1], is_right) for i in range(n)]

    best_final = min(valid, key=lambda f: cost[n-1][f])
    chosen = [0] * n
    chosen[n-1] = best_final
    for i in range(n-1, 0, -1):
        chosen[i-1] = parent[i][chosen[i]]

    out = []
    for i, (frame, pitches) in enumerate(events):
        if len(pitches) > 1:
            out.append(chord_fmaps[i])
        else:
            p = next(iter(pitches))
            out.append({p: FINGER_LIST[chosen[i]]})
    return out


def build_fmap_lookup(events, fmaps, per_frame, hand_key, total_frames):
    """frame -> finger_map 字典. 仅在 pitches 仍属于该 event 的帧生效."""
    lookup = {}
    for i, (start_frame, pitches) in enumerate(events):
        end_frame = events[i+1][0] if i+1 < len(events) else total_frames
        for f in range(start_frame, end_frame):
            if frozenset(per_frame[f][hand_key]) == pitches:
                lookup[f] = fmaps[i]
    return lookup


def compute_median_pose():
    """从数据集计算中位数姿态"""
    print("  计算数据集中位数姿态...")
    annos = sorted(glob.glob('./PianoMotion10M_Dataset/annotation/*/*/*.json'))[:50]
    r_all, l_all = [], []
    for jf in annos:
        with open(jf) as f:
            d = json.load(f)
        r = np.array(d['right'])[:, 1:52].astype(np.float32)
        l = np.array(d['left'])[:, 1:52].astype(np.float32)
        for i in range(0, len(r), 30):
            if r[i, 2] > 10:  # 过滤无效帧
                r_all.append(r[i])
            if l[i, 2] > 10:
                l_all.append(l[i])
    
    med_r = np.median(r_all, axis=0).astype(np.float32)
    med_l = np.median(l_all, axis=0).astype(np.float32)
    print(f"  {len(r_all)} 右手, {len(l_all)} 左手样本")
    return med_r, med_l


def event_wrist_keyframes(events, fmaps, offsets, is_right):
    """從 (events, fmaps) 提取 [(start_frame, target_wrist_x), ...].

    每個 event 算出: 想讓 center_finger 落在 center_pitch 對應像素位置時,
    wrist 螢幕 X 該在哪 (= key_px - finger_offset).
    """
    kfs = []
    for (sf, pitches), fmap in zip(events, fmaps):
        if not pitches:
            continue
        ps = sorted(pitches)
        center_pitch = ps[len(ps) // 2]
        # DP 結果優先, 退路用 sort 分配 (與主迴圈一致)
        if fmap and center_pitch in fmap:
            center_finger = fmap[center_pitch]
        else:
            fb = assign_fingers(pitches, is_right)
            center_finger = fb.get(center_pitch)
        if center_finger not in FINGER_LIST:
            continue
        finger_idx = FINGER_LIST.index(center_finger)
        wrist_x = pitch_to_pixel(center_pitch) - offsets[finger_idx]
        kfs.append((sf, float(wrist_x)))
    return kfs


def smooth_wrist_x_trajectory(keyframes, total_frames, lookahead_frames=6):
    """把離散 keyframes → per-frame 目標 wrist X, 每個 keyframe 前 lookahead_frames
    幀用 cosine ease-in/out 提前過渡, 模擬鋼琴家的「預備動作」.

    Args:
        keyframes: list of (start_frame, target_wrist_x), 按 start_frame 升序.
        total_frames: 總幀數.
        lookahead_frames: 預備動作時長 (幀; 30fps 下 6 = 0.2s).

    Returns:
        np.ndarray, shape (total_frames,), 每幀目標 wrist X (螢幕像素).
    """
    out = np.zeros(total_frames, dtype=np.float32)
    if not keyframes:
        return out

    # 第一個 keyframe 之前: 凍結在第一個 X
    first_sf, first_x = keyframes[0]
    out[:min(first_sf, total_frames)] = first_x

    n = len(keyframes)
    for i in range(n):
        sf_i, x_i = keyframes[i]
        if i + 1 < n:
            sf_n, x_n = keyframes[i + 1]
        else:
            sf_n, x_n = total_frames, x_i  # 最後一個 event 維持到尾

        # plateau [sf_i, sf_n - lookahead): 持平
        plateau_end = max(sf_i, sf_n - lookahead_frames)
        a, b = min(sf_i, total_frames), min(plateau_end, total_frames)
        out[a:b] = x_i

        # anticipation [sf_n - lookahead, sf_n): cosine ease-in/out
        for f in range(plateau_end, min(sf_n, total_frames)):
            t_to_next = sf_n - f
            a_lin = 1.0 - t_to_next / lookahead_frames
            a_cos = 0.5 - 0.5 * np.cos(a_lin * np.pi)
            out[f] = x_i * (1 - a_cos) + x_n * a_cos
    return out


def wrist_position_for_pixel(mano, pose, target_px, finger_name, is_right, max_iter=5):
    """
    纯解析法: 迭代调整 wrist X 让指定手指到目标像素。
    不改手指角度，不用梯度。
    """
    FX = 37500.0; cx = 960.0
    transl = pose[0:3].copy()
    
    for _ in range(max_iter):
        with torch.no_grad():
            output = mano['right'](
                global_orient=torch.tensor(pose[3:6]).float().unsqueeze(0).cuda(),
                hand_pose=torch.tensor(pose[6:51]).float().unsqueeze(0).cuda(),
                betas=torch.zeros(1,10).float().cuda(),
                transl=torch.tensor(transl).float().unsqueeze(0).cuda()
            )
            verts = output.vertices[0]
            if not is_right:
                verts = verts.clone()
                verts[:, 0] *= -1
            
            tip = verts[TIP_IDS[finger_name]].cpu().numpy()
            actual_px = FX * tip[0] / tip[2] + cx
            error = target_px - actual_px
            
            if abs(error) < 3.0:
                break
            
            if is_right:
                transl[0] += error * tip[2] / FX
            else:
                transl[0] -= error * tip[2] / FX
    
    pose[0:3] = transl
    return pose


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mp3', type=str, required=True)
    parser.add_argument('--midi', type=str, default=None, help='直接用 MIDI 文件 (比 MP3 提取更准)')
    parser.add_argument('--out_dir', type=str, default='./results/ik_output')
    parser.add_argument('--out_video', type=str, default='./results/ik_output_kb.mp4')
    parser.add_argument('--fingering',
                        choices=['dp', 'nearest', 'biomech', 'arlstm'], default='dp',
                        help='dp      = Viterbi minimizing wrist movement (default). '
                             'nearest = greedy by geometric distance — each note goes '
                             '          to the finger whose natural pixel position is '
                             '          closest to the target key. '
                             'biomech = Route B: wrist-free biomechanical Viterbi '
                             '          (stretch + crossing + repeated + terrain cost). '
                             '          Phrase-split at >1s onset gaps. '
                             'arlstm  = Stage B: Ramoneda 2022 SOTA neural model '
                             '          (pretrained ArLSTM, PIG-finetuned). Falls back '
                             '          to biomech for 6+ note chords.')
    args = parser.parse_args()
    
    # 1. 提取 MIDI
    print("[1/4] 提取 MIDI...")
    if args.midi and os.path.exists(args.midi):
        print(f"  使用已有 MIDI: {args.midi}")
        import pretty_midi
        midi_data = pretty_midi.PrettyMIDI(args.midi)
        # 用 ffprobe 读音频长度避免依赖 librosa
        import subprocess
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', args.mp3],
            capture_output=True, text=True)
        duration = float(r.stdout.strip())
    else:
        import librosa
        audio, _ = librosa.load(args.mp3, sr=16000)
        duration = len(audio) / 16000
        from basic_pitch.inference import predict
        _, midi_data, _ = predict(args.mp3, onset_threshold=0.95, frame_threshold=0.85, minimum_note_length=200)
    frame_num = int(duration * FPS)
    
    # 清理 MIDI: 仅合并同音高相邻音符 (不强制最短时长, 让 overlay 高亮贴近真实音长,
    # 避免 basic_pitch 误检的泛音/邻键被强行延长造成"幽灵琴键"叠加)
    merge_gap = 0.15    # 间隔 < 0.15 秒的同音高音符合并

    for inst in midi_data.instruments:
        if inst.is_drum: continue
        by_pitch = {}
        for n in inst.notes:
            if n.pitch not in by_pitch:
                by_pitch[n.pitch] = []
            by_pitch[n.pitch].append(n)

        new_notes = []
        for pitch, notes in by_pitch.items():
            notes.sort(key=lambda x: x.start)
            merged = [notes[0]]
            for n in notes[1:]:
                prev = merged[-1]
                if n.start - prev.end < merge_gap:
                    prev.end = max(prev.end, n.end)
                else:
                    merged.append(n)
            new_notes.extend(merged)

        inst.notes = new_notes
    
    # 保存清理后的 MIDI，让 overlay 也用同一份
    clean_midi_path = os.path.join(os.path.dirname(args.out_dir), 'clean_extracted.mid')
    midi_data.write(clean_midi_path)
    total_notes = sum(len(i.notes) for i in midi_data.instruments if not i.is_drum)
    print(f"  清理后: {total_notes} 个音符")
    
    # 每帧活跃音符
    per_frame = [{'right': set(), 'left': set()} for _ in range(frame_num)]
    for inst in midi_data.instruments:
        if inst.is_drum: continue
        for note in inst.notes:
            fs = max(0, int(note.start * FPS))
            fe = min(frame_num, int(note.end * FPS) + 1)
            hand = 'right' if note.pitch > HAND_SPLIT else 'left'
            for f in range(fs, fe):
                per_frame[f][hand].add(note.pitch)
    
    # 2. 准备基准姿态
    print("[2/4] 准备姿态...")
    med_r, med_l = compute_median_pose()
    
    from models.mano import build_mano
    mano = build_mano()
    mano['right'] = mano['right'].cuda()
    
    right_poses = np.tile(med_r, (frame_num, 1))
    left_poses  = np.tile(med_l, (frame_num, 1))
    
    # 3. 逐帧: 手腕定位 + 按键手指下压
    print("[3/4] 生成手势...")
    # 自然指尖偏移 (median pose, 相对 wrist screen X), 跟弯曲状态脱钩.
    med_r_tip_xs = fingertip_screen_x(mano, med_r, True)
    med_l_tip_xs = fingertip_screen_x(mano, med_l, False)
    OFFSET_R = med_r_tip_xs - wrist_screen_x(med_r, True)
    OFFSET_L = med_l_tip_xs - wrist_screen_x(med_l, False)

    # 全局排指 (DP / 几何最近指)
    print(f"  排指 ({args.fingering})...")
    events_r = extract_events(per_frame, 'right', frame_num)
    events_l = extract_events(per_frame, 'left',  frame_num)
    if args.fingering == 'biomech':
        # Route B: wrist-free biomechanical Viterbi. Hands are processed
        # independently per spec — right hand notes only, then left hand only.
        fmaps_r = apply_biomech_fingering(events_r, is_right=True)
        fmaps_l = apply_biomech_fingering(events_l, is_right=False)
    elif args.fingering == 'arlstm':
        # Stage B: Ramoneda 2022 ArLSTM. clean_midi_path was written above
        # from midi_data so ArLSTM sees the same notes the renderer will.
        fmaps_r = apply_arlstm_fingering(events_r, True, clean_midi_path)
        fmaps_l = apply_arlstm_fingering(events_l, False, clean_midi_path)
    elif args.fingering == 'nearest':
        fmaps_r = plan_fingering_nearest(events_r, OFFSET_R, True)
        fmaps_l = plan_fingering_nearest(events_l, OFFSET_L, False)
    else:
        fmaps_r = plan_fingering_dp(events_r, OFFSET_R, True)
        fmaps_l = plan_fingering_dp(events_l, OFFSET_L, False)
    fmap_lookup_R = build_fmap_lookup(events_r, fmaps_r, per_frame, 'right', frame_num)
    fmap_lookup_L = build_fmap_lookup(events_l, fmaps_l, per_frame, 'left',  frame_num)

    # Wrist trajectory pre-pass: 每個 event 前 0.2s 用 cosine ease-in/out 提前漂移到位.
    # 模擬鋼琴家的「預備動作」── 手腕先到, 手指照 onset 嚴格觸鍵 (per-finger IK 不變).
    print("  Wrist trajectory pre-pass (0.2s anticipation)...")
    LOOKAHEAD_FRAMES = 6  # 0.2s @ 30fps
    wrist_kf_R = event_wrist_keyframes(events_r, fmaps_r, OFFSET_R, is_right=True)
    wrist_kf_L = event_wrist_keyframes(events_l, fmaps_l, OFFSET_L, is_right=False)
    wrist_x_traj_R = smooth_wrist_x_trajectory(wrist_kf_R, frame_num, LOOKAHEAD_FRAMES)
    wrist_x_traj_L = smooth_wrist_x_trajectory(wrist_kf_L, frame_num, LOOKAHEAD_FRAMES)

    prev_right = med_r.copy()
    prev_left  = med_l.copy()

    for frame in tqdm(range(frame_num)):
        for hand, is_right, poses in [
            ('right', True, right_poses),
            ('left', False, left_poses),
        ]:
            prev = prev_right if is_right else prev_left
            offsets = OFFSET_R if is_right else OFFSET_L
            med  = med_r if is_right else med_l
            pitches = per_frame[frame][hand]

            # 自然指尖位置 = 上一帧手腕 screen X + 固定偏移
            natural_xs = wrist_screen_x(prev, is_right) + offsets

            if not pitches:
                # 闲置: 手腕原位冻结, 手指松开. 下个音超出范围才提前预漂.
                pose = prev.copy()
                next_pitches = None
                frames_until = 0
                for look in range(frame+1, min(frame+15, frame_num)):
                    if per_frame[look][hand]:
                        next_pitches = sorted(per_frame[look][hand])
                        frames_until = look - frame
                        break

                if next_pitches is not None and not all_in_reach(natural_xs, next_pitches):
                    target_px = np.mean([pitch_to_pixel(p) for p in next_pitches])
                    target_x = (target_px - 960.0) * prev[2] / 37500.0
                    if not is_right:
                        target_x = -target_x
                    alpha = min(0.3, 1.0 / max(frames_until, 1))
                    pose[0] = prev[0] + alpha * (target_x - prev[0])

                pose[6:51] = prev[6:51] + 0.1 * (med[6:51] - prev[6:51])
                pose[1] = prev[1] + 0.2 * (med[1] - prev[1])

                poses[frame] = pose
                if is_right: prev_right = pose.copy()
                else: prev_left = pose.copy()
                continue

            # 有音符
            pose = med.copy()
            pitches = sorted(pitches)
            # 选指: 优先全局 DP 结果, 否则退路用 sort 分配
            lookup = fmap_lookup_R if is_right else fmap_lookup_L
            finger_map = lookup.get(frame) or assign_fingers(pitches, is_right)

            center_pitch = pitches[len(pitches)//2]
            center_finger = finger_map[center_pitch]
            # 用 pre-pass 算好的 smoothed wrist 軌跡. plateau 期間 == pitch_to_pixel(center_pitch);
            # 在下個 event 前 0.2s 自動 cosine 漂向下個目標, IK 把 center_finger 拉到漂移後的位置,
            # 達成「手腕先到, 觸鍵時間點不變」的預備動作.
            center_finger_idx = FINGER_LIST.index(center_finger)
            target_wrist_x = wrist_x_traj_R[frame] if is_right else wrist_x_traj_L[frame]
            center_px = float(target_wrist_x) + offsets[center_finger_idx]

            if len(pitches) > 1:
                # 多键: 张指 + 选中指弯曲下压
                min_p, max_p = min(pitches), max(pitches)
                min_wi = (min_p-21)//12*7 + [0,0,1,2,2,3,3,4,5,5,6,6][(min_p-21)%12]
                max_wi = (max_p-21)//12*7 + [0,0,1,2,2,3,3,4,5,5,6,6][(max_p-21)%12]
                key_span = max_wi - min_wi
                spread_factor = max(1.0, key_span / 4.0)
                spread_factor = min(spread_factor, 2.5)
                for fname in ('index', 'middle', 'ring', 'pinky'):
                    s, _ = FINGER_SLICE[fname]
                    pose[6+s] = med[6+s] + SPREAD_BASE[fname] * spread_factor

                for p, fname in finger_map.items():
                    s, e = FINGER_SLICE[fname]
                    delta = np.array(PRESS_DELTA[fname], dtype=np.float32)
                    pose[6+s:6+e] = pose[6+s:6+e] + delta
            # 单键: 不弯手指, 只靠 wrist IK 把整只手平移到键正上方

            # 永远 IK: 把选中的指拉到目标键正上方, 不再有"原地伸"
            pose = wrist_position_for_pixel(mano, pose, center_px, center_finger, is_right)

            pose[1] = med[1] - 0.012

            poses[frame] = pose
            if is_right: prev_right = pose.copy()
            else: prev_left = pose.copy()

    # Savgol 平滑
    print("  平滑...")
    for dim in range(51):
        right_poses[:, dim] = savgol_filter(right_poses[:, dim], 7, 2)
        left_poses[:, dim]  = savgol_filter(left_poses[:, dim], 7, 2)

    # 用最终 (smoothed) pose 批量跑 MANO, 拿 10 根指尖的 screen (x, y)
    print("  计算指尖投影...")
    FX = 37500.0; CX = 960.0; CY = 540.0
    TIPS_IDX = [TIP_IDS[f] for f in FINGER_LIST]

    def fingertip_screen(poses_np, is_right, chunk=512):
        n = poses_np.shape[0]
        out = np.zeros((n, 5, 2), dtype=np.float32)
        for s in range(0, n, chunk):
            e = min(s + chunk, n)
            p = torch.tensor(poses_np[s:e]).float().cuda()
            bs = e - s
            with torch.no_grad():
                mo = mano['right'](
                    global_orient=p[:, 3:6],
                    hand_pose=p[:, 6:51],
                    betas=torch.zeros(bs, 10, device='cuda'),
                    transl=p[:, 0:3],
                )
            verts = mo.vertices
            if not is_right:
                verts = verts.clone()
                verts[:, :, 0] *= -1
            tips = verts[:, TIPS_IDX, :]  # (bs, 5, 3)
            sx = FX * tips[:, :, 0] / tips[:, :, 2] + CX
            sy = FX * tips[:, :, 1] / tips[:, :, 2] + CY
            out[s:e] = torch.stack([sx, sy], dim=-1).cpu().numpy()
        return out

    right_tips = fingertip_screen(right_poses, is_right=True)
    left_tips  = fingertip_screen(left_poses,  is_right=False)

    fingertips_path = args.out_dir.rstrip('/') + '_fingertips.json'
    with open(fingertips_path, 'w') as f:
        json.dump({
            'fps': FPS,
            'finger_order': FINGER_LIST,
            'right': right_tips.tolist(),
            'left':  left_tips.tolist(),
        }, f)
    print(f"  ✓ 指尖数据: {fingertips_path}")

    # 4. 渲染
    print("[4/4] 渲染...")
    os.makedirs(args.out_dir, exist_ok=True)
    from datasets.show import render_result
    render_result(args.out_dir, None, right_poses, left_poses, video=False)

    # 键盘叠加
    kb_dir = args.out_dir + '_kb'
    clean_midi_path = os.path.join(os.path.dirname(args.out_dir), 'clean_extracted.mid')
    os.system(f'python add_keyboard_overlay.py '
              f'--frames_dir {args.out_dir} '
              f'--mp3 "{args.mp3}" '
              f'--midi "{clean_midi_path}" '
              f'--fingertips "{fingertips_path}" '
              f'--out_dir {kb_dir} '
              f'--out_video {args.out_video}')
    
    print(f"\n{'='*60}")
    print(f"✅ 完成! {args.out_video}")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
