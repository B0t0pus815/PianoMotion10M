"""calibrate.py — measure the "blind" thresholds against a real recording.

Why this exists
---------------
The realtime grader gates user input on absolute-pixel constants tuned for the
1920×1080 biomech-v4 renders:

  - MIN_PRESS_VELOCITY = 80 px/s   (comparator: is this a real key press?)
  - WRIST_*_THRESHOLD  = 25 px     (comparator: arched / collapsed wrist?)
  - min_detection_confidence = 0.3 (hand_tracker: was a hand found at all?)

On a real webcam recording these are SILENTLY wrong: a different resolution and
framing change the pixels-per-press, and real-photo hands detect at a different
rate than MANO renders. Nothing in the pipeline reports whether a press cleared
the velocity bar or whether the hand was even tracked — a low-velocity legato
press and a tracking dropout both just become "no clear motion → lowest finger",
indistinguishable from a real result.

This tool runs the SAME tracking + history + A/V-sync machinery as runner.py
over a recording, but instead of GRADING it reports the DISTRIBUTIONS each
threshold gates on, plus data-driven recommended values. So "tune the
thresholds" stops being a guess and becomes a measurement: drop a recording in,
run one command, read off what the constants should be (and whether the
recording is even usable).

CLI
---
    python -m webui.realtime.calibrate recording.mp4 played.mid
    python -m webui.realtime.calibrate recording.mp4 played.mid \\
        --max-seconds 8 --mirror --out user_recordings/calib.json

Negative-control check (MANO render → expect LOW detection, warning fires):
    python -m webui.realtime.calibrate results/canon_biomech_v4_kb.mp4 \\
        results/canon_clean.mid --max-seconds 8 --no-sync
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict

import numpy as np

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Defaults the live pipeline actually uses — we measure against THESE so the
# report says how the current constants behave on this recording.
from webui.realtime.comparator import (
    PRESS_WINDOW, MIN_PRESS_VELOCITY,
    WRIST_ARCHED_THRESHOLD, WRIST_REFERENCE_WINDOW,
)
# Note: the arched/collapsed thresholds are symmetric (both 25 px); we report
# against WRIST_ARCHED_THRESHOLD and treat |deviation| beyond it as a flag.

BASELINE_HEIGHT = 1080   # the resolution the absolute-pixel defaults were tuned at


# ─── Pure statistics helpers (unit-tested without video / MediaPipe) ──────

def percentile(values, p: float):
    """p-th percentile (0–100) by linear interpolation. None for empty input."""
    a = np.asarray([v for v in values if v is not None], dtype=float)
    if a.size == 0:
        return None
    return float(np.percentile(a, p))


def pct_summary(values, ps=(10, 50, 90)) -> dict:
    """{'p10':…, 'p50':…, 'p90':…, 'n':…}; values None when empty."""
    out = {f'p{int(p)}': percentile(values, p) for p in ps}
    out['n'] = int(sum(1 for v in values if v is not None))
    return out


def fraction_below(values, threshold: float) -> float:
    """Fraction of (non-None) values strictly below threshold. 0.0 for empty."""
    a = [v for v in values if v is not None]
    if not a:
        return 0.0
    return sum(1 for v in a if v < threshold) / len(a)


def fraction_above(values, threshold: float) -> float:
    """Fraction of (non-None) values strictly above threshold. 0.0 for empty."""
    a = [v for v in values if v is not None]
    if not a:
        return 0.0
    return sum(1 for v in a if v > threshold) / len(a)


def recommend_min_press_velocity(onset_max_vels, target_fallback: float = 0.10,
                                 floor: float = 20.0):
    """Velocity bar that leaves at most `target_fallback` of onsets below it
    (i.e. silently hitting the lowest-finger fallback). That is the
    (target_fallback*100)-th percentile of the per-onset max finger velocity,
    floored so sensor noise can't drive it to ~0. None if no data."""
    p = percentile(onset_max_vels, target_fallback * 100.0)
    if p is None:
        return None
    return max(floor, p)


def recommend_wrist_threshold(abs_devs, target_flag_rate: float = 0.05):
    """Symmetric ±px wrist threshold that flags only the most extreme
    `target_flag_rate` of onsets — i.e. the (1-rate) percentile of the absolute
    deviation from the rolling median. None if no data."""
    return percentile(abs_devs, (1.0 - target_flag_rate) * 100.0)


def resolution_scale(frame_h: int, baseline_h: int = BASELINE_HEIGHT) -> float:
    """Factor to rescale a baseline absolute-pixel threshold to this frame
    height (a 720p frame needs ~0.667× the 1080p pixel thresholds)."""
    if not frame_h:
        return 1.0
    return frame_h / float(baseline_h)


# ─── Report container ─────────────────────────────────────────────────────

@dataclass
class CalibrationReport:
    video: str
    midi: str
    frames: int = 0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    duration_s: float = 0.0
    sync_offset_s: float = 0.0
    sync_norm: float = 0.0
    onsets_sampled: int = 0

    # tracking quality
    detect_rate: dict = field(default_factory=dict)      # hand → fraction of frames
    score: dict = field(default_factory=dict)            # hand → pct_summary
    hand_span_px: dict = field(default_factory=dict)     # hand → pct_summary

    # press detection
    onset_velocity: dict = field(default_factory=dict)   # pct_summary px/s
    press_fallback_fraction: float = 0.0                 # at current MIN_PRESS_VELOCITY

    # wrist posture
    wrist_abs_dev: dict = field(default_factory=dict)    # pct_summary px
    wrist_flag_fraction: float = 0.0                     # at current ±25px

    # recommendations
    recommended: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Video pass (needs MediaPipe + cv2) ───────────────────────────────────

def _onset_max_velocity(snaps) -> float | None:
    """Max mean-downward fingertip velocity (px/s) over `snaps`
    (list of (t, tips(5,2))). Mirrors comparator.detect_press_finger so the
    number this reports is exactly what MIN_PRESS_VELOCITY is compared against."""
    if len(snaps) < 2:
        return None
    vel = np.zeros(5, dtype=float)
    for i in range(1, len(snaps)):
        t0, p0 = snaps[i - 1]
        t1, p1 = snaps[i]
        dt = max(t1 - t0, 1e-3)
        vel += (p1[:, 1] - p0[:, 1]) / dt
    vel /= max(len(snaps) - 1, 1)
    return float(np.max(vel))


def run_calibration(video_path: str, midi_path: str, *,
                    max_seconds: float | None = None, mirror: bool = False,
                    sync: bool = True) -> CalibrationReport:
    """Decode `video_path`, track hands, and sample the threshold distributions
    at the onsets of `midi_path`. Returns a CalibrationReport."""
    from add_keyboard_overlay import HAND_SPLIT
    from webui.realtime.sources import VideoSource
    from webui.realtime.hand_tracker import HandTracker
    from webui.realtime.comparator import HandHistory, wrist_status
    from webui.realtime.note_align import notes_from_midi

    rep = CalibrationReport(video=video_path, midi=midi_path)

    # A/V offset so onset times land on the video clock (same convention as the
    # runner: history is pushed at eff_t = frame_ts − δ, MIDI onsets sampled at
    # their own time). Skippable for already-aligned renders.
    offset = 0.0
    if sync:
        try:
            from webui.realtime.av_sync import estimate_offset_xcorr
            offset, _peak, norm = estimate_offset_xcorr(video_path, midi_path)
            rep.sync_offset_s, rep.sync_norm = float(offset), float(norm)
        except Exception as exc:  # noqa: BLE001 — sync must never abort calibration
            print(f'[calib] auto-sync failed ({exc}); offset 0.')

    video = VideoSource(video_path, realtime=False)
    tracker = HandTracker(mirror=mirror)
    history = HandHistory(capacity=512)
    rep.fps = float(video.fps)

    det = {'left': 0, 'right': 0}
    scores = {'left': [], 'right': []}
    spans = {'left': [], 'right': []}
    n_frames = 0
    try:
        for frame in video:
            if max_seconds is not None and frame.timestamp > max_seconds:
                break
            if rep.width == 0:
                rep.height, rep.width = frame.image.shape[:2]
            eff_t = frame.timestamp - offset
            hands = tracker.process(frame.image, int(frame.timestamp * 1000))
            history.push(eff_t, hands)
            for label, pose in hands.items():
                det[label] += 1
                scores[label].append(float(pose.score))
                wrist = pose.wrist[:2]
                mid_tip = pose.fingertips[2, :2]
                spans[label].append(float(np.linalg.norm(mid_tip - wrist)))
            n_frames += 1
    finally:
        video.close()
        tracker.close()

    rep.frames = n_frames
    rep.duration_s = round(n_frames / rep.fps, 2) if rep.fps else 0.0
    for label in ('left', 'right'):
        rep.detect_rate[label] = round(det[label] / max(n_frames, 1), 4)
        rep.score[label] = pct_summary(scores[label])
        rep.hand_span_px[label] = pct_summary(spans[label])

    # Sample press velocity + wrist deviation at the played onsets.
    onsets = notes_from_midi(midi_path)
    onset_vels, abs_devs = [], []
    for t, pitch in onsets:
        hand = 'right' if pitch >= HAND_SPLIT else 'left'
        snaps = history.recent(hand, t, PRESS_WINDOW)
        v = _onset_max_velocity(snaps)
        if v is not None:
            onset_vels.append(v)
        status, dev = wrist_status(history, hand, t)
        if status != 'unknown':
            abs_devs.append(abs(dev))
    rep.onsets_sampled = len(onsets)
    rep.onset_velocity = pct_summary(onset_vels)
    rep.press_fallback_fraction = round(fraction_below(onset_vels, MIN_PRESS_VELOCITY), 4)
    rep.wrist_abs_dev = pct_summary(abs_devs)
    # abs deviations vs the symmetric ±threshold → a flag fires when |dev| > it.
    rep.wrist_flag_fraction = round(fraction_above(abs_devs, WRIST_ARCHED_THRESHOLD), 4)

    scale = resolution_scale(rep.height)
    rep.recommended = {
        'resolution_scale_vs_1080p': round(scale, 4),
        'min_press_velocity': _round_or_none(recommend_min_press_velocity(onset_vels)),
        'min_press_velocity_scaled_default': round(MIN_PRESS_VELOCITY * scale, 1),
        'wrist_threshold_px': _round_or_none(recommend_wrist_threshold(abs_devs)),
        'wrist_threshold_scaled_default': round(WRIST_ARCHED_THRESHOLD * scale, 1),
    }
    return rep


def _round_or_none(x, nd: int = 1):
    return None if x is None else round(x, nd)


# ─── Human-readable report ────────────────────────────────────────────────

def _fmt_pct(s: dict, unit: str = '') -> str:
    def g(k):
        v = s.get(k)
        return '   n/a' if v is None else f'{v:6.1f}'
    return f'p10/p50/p90 = {g("p10")}/{g("p50")}/{g("p90")}{unit}  (n={s.get("n", 0)})'


def format_report(rep: CalibrationReport) -> str:
    L = []
    L.append(f'=== CALIBRATION REPORT ===')
    L.append(f'  video : {rep.video}')
    L.append(f'  midi  : {rep.midi}')
    L.append(f'  frames: {rep.frames} @ {rep.fps:.1f} fps  {rep.width}x{rep.height}  '
             f'({rep.duration_s:.1f}s)')
    if rep.sync_offset_s or rep.sync_norm:
        weak = '  ⚠ weak' if rep.sync_norm < 0.05 else ''
        L.append(f'  A/V sync δ={rep.sync_offset_s:+.3f}s (norm {rep.sync_norm:.3f}){weak}')
    L.append(f'  onsets: {rep.onsets_sampled} sampled')
    L.append('')

    L.append(f'[ Tracking quality ]   gate: min_detection_confidence=0.30')
    worst = 1.0
    for hand in ('left', 'right'):
        r = rep.detect_rate.get(hand, 0.0)
        worst = min(worst, r)
        L.append(f'  {hand:5s} detected {r*100:5.1f}% of frames   '
                 f'score {_fmt_pct(rep.score.get(hand, {}))}')
    for hand in ('left', 'right'):
        L.append(f'  {hand:5s} hand span (wrist→middle tip): '
                 f'{_fmt_pct(rep.hand_span_px.get(hand, {}), " px")}')
    if worst < 0.5:
        L.append(f'  ⚠ LOW detection ({worst*100:.0f}%): lighting / occlusion / '
                 f'non-photoreal hands. Grades on this recording are unreliable.')
    else:
        L.append(f'  ✓ detection healthy.')
    L.append('')

    L.append(f'[ Press detection ]    gate: MIN_PRESS_VELOCITY={MIN_PRESS_VELOCITY:.0f} px/s, '
             f'PRESS_WINDOW={PRESS_WINDOW:.2f}s')
    L.append(f'  max finger velocity at onsets: {_fmt_pct(rep.onset_velocity, " px/s")}')
    fb = rep.press_fallback_fraction
    n_vel = rep.onset_velocity.get('n', 0)
    if n_vel == 0:
        L.append(f'  — no onset had a tracked hand; nothing to measure '
                 f'(see tracking quality above).')
    else:
        flag = '⚠' if fb > 0.25 else '✓'
        L.append(f'  {flag} {fb*100:.1f}% of onsets fall BELOW the bar → silent '
                 f'lowest-finger fallback (blind presses).')
    rmpv = rep.recommended.get('min_press_velocity')
    if rmpv is not None:
        L.append(f'  → for ≤10% fallback set MIN_PRESS_VELOCITY ≈ {rmpv:.0f} px/s  '
                 f'(resolution-scaled default would be '
                 f'{rep.recommended.get("min_press_velocity_scaled_default")})')
    L.append('')

    L.append(f'[ Wrist posture ]      gate: ±{WRIST_ARCHED_THRESHOLD:.0f} px '
             f'(window {WRIST_REFERENCE_WINDOW:.0f}s)')
    L.append(f'  |deviation from rolling median| at onsets: '
             f'{_fmt_pct(rep.wrist_abs_dev, " px")}')
    wf = rep.wrist_flag_fraction
    n_wrist = rep.wrist_abs_dev.get('n', 0)
    if n_wrist == 0:
        L.append(f'  — no onset had enough wrist history to measure '
                 f'(see tracking quality above).')
    else:
        L.append(f'  {"⚠" if wf > 0.2 else "✓"} {wf*100:.1f}% of onsets would trip an '
                 f'arched/collapsed flag at the current ±{WRIST_ARCHED_THRESHOLD:.0f}px.')
    rwt = rep.recommended.get('wrist_threshold_px')
    if rwt is not None:
        L.append(f'  → to flag only the worst ~5%, set wrist threshold ≈ {rwt:.0f} px  '
                 f'(resolution-scaled default would be '
                 f'{rep.recommended.get("wrist_threshold_scaled_default")})')
    L.append('')

    scale = rep.recommended.get('resolution_scale_vs_1080p', 1.0)
    if abs(scale - 1.0) > 0.02:
        L.append(f'[ Resolution ] this recording is {rep.height}p → the absolute-pixel '
                 f'defaults (tuned at {BASELINE_HEIGHT}p) are off by {scale:.2f}×. '
                 f'Prefer the measured recommendations above.')
    else:
        L.append(f'[ Resolution ] {rep.height}p ≈ {BASELINE_HEIGHT}p baseline; pixel '
                 f'defaults apply at native scale.')
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video', help='the recording (mp4/mov/webm)')
    ap.add_argument('midi', help='the played .mid (exported from the keyboard)')
    ap.add_argument('--max-seconds', type=float, default=None,
                    help='only process the first N seconds (quick check)')
    ap.add_argument('--mirror', action='store_true',
                    help='swap L/R for a user-facing webcam')
    ap.add_argument('--no-sync', action='store_true',
                    help='skip A/V auto-sync (use for already-aligned renders)')
    ap.add_argument('--out', help='also write the report JSON here')
    args = ap.parse_args()

    rep = run_calibration(args.video, args.midi, max_seconds=args.max_seconds,
                          mirror=args.mirror, sync=not args.no_sync)
    print(format_report(rep))
    if args.out:
        with open(args.out, 'w') as f:
            json.dump(rep.to_dict(), f, indent=2)
        print(f'\n  report JSON → {args.out}')


if __name__ == '__main__':
    main()
