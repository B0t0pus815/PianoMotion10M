"""Phase B real-time runner.

Pulls synchronized video frames + MIDI events, runs MediaPipe per frame, and
compares the user's fingering against the biomech v4 reference at each MIDI
onset. Displays a cv2 preview with overlay landmarks + rolling feedback.

Replay mode (no hardware needed — uses recorded video + MIDI file):
    python -m webui.realtime.runner \\
        --video results/canon_biomech_v4_kb.mp4 \\
        --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \\
        --reference results/canon_biomech_v4_fingertips.json

Live mode (when webcam + MIDI keyboard are plugged in):
    python -m webui.realtime.runner --video 0 --midi "Piano Keyboard:0" \\
        --reference results/canon_biomech_v4_fingertips.json --mirror
"""
from __future__ import annotations

import argparse
import os
import sys

import cv2
import numpy as np

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from webui.realtime.sources import VideoSource, MidiSource
from webui.realtime.hand_tracker import HandTracker, TIP_INDICES, TIP_ORDER
from webui.realtime.reference import build_reference
from webui.realtime.fingering_engine import generate_fingering
from webui.realtime.comparator import (
    HandHistory, compare_onset, OnsetResult, precompute_chord_finger_sets,
)
from webui.realtime.clip_recorder import ClipConfig, ClipRecorder


HAND_COLORS = {'left': (100, 255, 150), 'right': (100, 200, 255)}
FINGER_NUM = {'thumb': '1', 'index': '2', 'middle': '3', 'ring': '4', 'pinky': '5'}
MATCH_WINDOW = 0.50          # tempo tolerance: ±0.5s for user-MIDI vs expected
CHORD_CLUSTER_WINDOW = 0.05  # expected onsets within 50ms are treated as a chord


def draw_hand(img, pose):
    color = HAND_COLORS[pose.handedness]
    for name in TIP_ORDER:
        idx = TIP_INDICES[name]
        x, y = int(pose.landmarks[idx, 0]), int(pose.landmarks[idx, 1])
        cv2.circle(img, (x, y), 6, color, -1)
        cv2.putText(img, FINGER_NUM[name], (x + 6, y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
    wx, wy = int(pose.landmarks[0, 0]), int(pose.landmarks[0, 1])
    cv2.circle(img, (wx, wy), 5, color, -1)
    cv2.putText(img, pose.handedness[0].upper(), (wx + 8, wy + 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)


def draw_feedback(img, results: list):
    if not results:
        return
    h, w = img.shape[:2]
    box_h = 30 + 22 * min(len(results), 8)
    overlay = img.copy()
    cv2.rectangle(overlay, (10, 10), (560, 10 + box_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, img, 0.45, 0, img)

    y = 32
    for r in results[-8:]:
        h_letter = r.expected_hand[0].upper()
        exp = FINGER_NUM[r.expected_finger]
        if r.detected_finger is None:
            txt = f't={r.time:5.2f}  N{r.pitch:3d}  {h_letter}/{exp}  no hand'
            color = (180, 180, 180)
        elif r.correct:
            txt = f't={r.time:5.2f}  N{r.pitch:3d}  {h_letter}/{exp}  OK  conf={r.confidence:.2f}'
            color = (120, 255, 150)
        else:
            got = FINGER_NUM[r.detected_finger]
            txt = f't={r.time:5.2f}  N{r.pitch:3d}  {h_letter}/{exp}  WRONG got {got}'
            color = (120, 120, 255)
        cv2.putText(img, txt, (16, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, color, 1, cv2.LINE_AA)
        y += 22


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--video', required=True, help='webcam idx (int) or mp4 path')
    p.add_argument('--midi', required=True, help='MIDI port name or .mid path')
    p.add_argument('--reference', required=True, help='fingertips JSON')
    p.add_argument('--ref-midi', help='reference MIDI (defaults to --midi)')
    p.add_argument('--ref-width', type=int, default=1920,
                   help='reference render width used for key-X geometry')
    p.add_argument('--mirror', action='store_true',
                   help='swap left/right (for user-facing webcam)')
    p.add_argument('--no-preview', action='store_true')
    p.add_argument('--fast', action='store_true',
                   help='replay video as fast as possible (skip realtime pacing)')
    p.add_argument('--max-onsets', type=int,
                   help='stop after evaluating N onsets (testing)')
    p.add_argument('--output-json', help='write per-onset results to this JSON')
    p.add_argument('--ws-port', type=int, default=8766,
                   help='broadcast results over WebSocket on this port (0 to disable)')
    p.add_argument('--ws-linger', type=float, default=2.0,
                   help='seconds to keep WS server alive after the run finishes '
                        '(so a late-connecting browser can backfill from history)')
    p.add_argument('--fingering-source',
                   choices=['pianoplayer', 'arlstm', 'onnx', 'motion'],
                   default='arlstm',
                   help='Logic Track judge. "arlstm" = Ramoneda 2022 SOTA neural '
                        'model (default; best Soft Accuracy in four_way_audit.py). '
                        '"pianoplayer" = Parncutt DP (fast, deterministic, '
                        'thumb-conservative). "onnx" = FingeringTransformer via '
                        'onnxruntime (torch-free, for edge/Jetson). "motion" '
                        'reproduces the v0 biomech-v4 heuristic, thesis comparison only.')
    p.add_argument('--hand-size', default='M',
                   choices=['XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL'],
                   help='User hand size for pianoplayer (default M).')
    p.add_argument('--clip-record', action='store_true',
                   help='Enable error-triggered clip recorder.')
    p.add_argument('--clip-ref-video', default=None,
                   help='Reference biomech video for side-by-side clip '
                        '(defaults to --video; in live mode point this at the '
                        'biomech v4 mp4).')
    p.add_argument('--clip-threshold', type=float, default=0.6,
                   help='Error-rate trigger threshold (default 0.6).')
    p.add_argument('--clip-window', type=int, default=8,
                   help='Sliding window size in onsets (default 8).')
    p.add_argument('--clip-pre', type=float, default=5.0,
                   help='Seconds of pre-trigger buffer (default 5).')
    p.add_argument('--clip-post', type=float, default=5.0,
                   help='Seconds to record after trigger (default 5).')
    p.add_argument('--clip-output-dir', default='clips')
    args = p.parse_args()

    vsrc = int(args.video) if args.video.isdigit() else args.video
    video = VideoSource(vsrc, realtime=not args.fast)
    midi = MidiSource(args.midi)
    tracker = HandTracker(mirror=args.mirror)

    ref_midi = args.ref_midi or args.midi
    if args.fingering_source in ('pianoplayer', 'arlstm', 'onnx'):
        expected = generate_fingering(ref_midi, hand_size=args.hand_size,
                                      source=args.fingering_source)
        src_label = {
            'pianoplayer': 'Logic Track (pianoplayer, hand={})'.format(args.hand_size),
            'arlstm': 'Logic Track (Ramoneda ArLSTM)',
            'onnx': 'Logic Track (ONNX FingeringTransformer, torch-free)',
        }[args.fingering_source]
        print(f'[ref] {len(expected)} expected onsets — {src_label} from {ref_midi}')
    else:
        expected = build_reference(ref_midi, args.reference, frame_width=args.ref_width)
        print(f'[ref] {len(expected)} expected onsets — motion-based (v0) '
              f'from {args.reference}')

    broadcaster = None
    if args.ws_port > 0:
        from webui.realtime.broadcaster import Broadcaster
        broadcaster = Broadcaster(port=args.ws_port)
        if broadcaster.start():
            notes_payload = [
                {
                    'i': i,
                    'pitch': e.pitch,
                    'start': round(e.time, 3),
                    'dur': round(e.duration, 3),
                    'vel': e.velocity,
                    'hand': e.expected_hand,
                    'finger': e.expected_finger,
                }
                for i, e in enumerate(expected)
            ]
            broadcaster.publish({
                'type': 'ready',
                'expected_count': len(expected),
                'video': args.video,
                'midi': args.midi,
                'notes': notes_payload,
            })
        else:
            broadcaster = None

    chord_finger_sets = precompute_chord_finger_sets(expected,
                                                     cluster_window=CHORD_CLUSTER_WINDOW)
    history = HandHistory(capacity=180)
    results: list[OnsetResult] = []
    played_notes: list[tuple] = []   # (time, pitch) of every played note_on, for note-level alignment
    onset_cursor = 0

    clip_recorder = None
    if args.clip_record:
        clip_cfg = ClipConfig(
            pre_seconds=args.clip_pre,
            post_seconds=args.clip_post,
            window_size=args.clip_window,
            trigger_threshold=args.clip_threshold,
            output_dir=args.clip_output_dir,
            fps=int(video.fps),
        )
        ref_for_clip = args.clip_ref_video or (
            args.video if isinstance(vsrc, str) else None
        )
        song_name = os.path.splitext(os.path.basename(args.midi))[0]

        def _emit_clip_event(ev):
            if broadcaster:
                broadcaster.publish(ev)
            tag = ev.get('type')
            if tag == 'clip_trigger':
                print(f'[clip] TRIGGER at t={ev["time"]:.2f} '
                      f'err_rate={ev["error_rate"]*100:.0f}%')
            elif tag == 'clip_done':
                print(f'[clip] DONE → {ev["path"]}')

        clip_recorder = ClipRecorder(
            cfg=clip_cfg, song_name=song_name,
            reference_video_path=ref_for_clip,
            on_event=_emit_clip_event,
        )
        print(f'[clip] recorder ON  threshold={args.clip_threshold:.2f}  '
              f'window={args.clip_window}  pre/post={args.clip_pre:.0f}/{args.clip_post:.0f}s')

    try:
      try:
        for frame in video:
            ts_ms = int(frame.timestamp * 1000)
            hands = tracker.process(frame.image, ts_ms)
            history.push(frame.timestamp, hands)
            if clip_recorder:
                clip_recorder.push_frame(frame.timestamp, frame.image)

            for ev in midi.poll(frame.timestamp):
                if ev.type != 'note_on':
                    continue
                played_notes.append((ev.timestamp, ev.note))
                best_j = None
                best_dt = MATCH_WINDOW
                for j in range(onset_cursor, min(onset_cursor + 30, len(expected))):
                    e = expected[j]
                    dt = abs(e.time - ev.timestamp)
                    if dt < best_dt and e.pitch == ev.note:
                        best_j, best_dt = j, dt
                if best_j is None:
                    continue
                e = expected[best_j]
                r = compare_onset(history, e, alt_finger_idxs=chord_finger_sets.get(best_j))
                results.append(r)
                onset_cursor = max(onset_cursor, best_j + 1)
                if clip_recorder:
                    clip_recorder.push_result(
                        frame.timestamp, r.correct, r.detected_finger is not None,
                    )
                if broadcaster:
                    broadcaster.publish({
                        'type': 'onset',
                        'i': best_j,
                        'time': round(r.time, 3),
                        'pitch': r.pitch,
                        'expected_hand': r.expected_hand,
                        'expected_finger': r.expected_finger,
                        'detected_finger': r.detected_finger,
                        'correct': r.correct,
                        'confidence': round(r.confidence, 3),
                        # Wrist feedback v1 (2026-05-24)
                        'wrist_status': r.wrist_status,
                        'wrist_deviation_px': round(r.wrist_deviation_px, 1),
                    })
                if args.max_onsets and len(results) >= args.max_onsets:
                    raise StopIteration
                tag = 'OK ' if r.correct else ('-- ' if r.detected_finger is None else 'X  ')
                got = (FINGER_NUM[r.detected_finger]
                       if r.detected_finger else '-')
                print(f'[{tag}] t={r.time:5.2f}  note={r.pitch:3d}  '
                      f'exp={r.expected_hand[0].upper()}/{FINGER_NUM[r.expected_finger]}  '
                      f'got={got}  conf={r.confidence:.2f}')

            if not args.no_preview:
                preview = frame.image.copy()
                for pose in hands.values():
                    draw_hand(preview, pose)
                draw_feedback(preview, results)
                cv2.imshow('Phase B', preview)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
      except StopIteration:
        pass
    finally:
        video.close()
        midi.close()
        tracker.close()
        cv2.destroyAllWindows()

    n = len(results)
    correct = sum(1 for r in results if r.correct)
    no_hand = sum(1 for r in results if r.detected_finger is None)
    wrong = n - correct - no_hand
    print('\n=== Summary ===')
    print(f'  Total onsets evaluated: {n} / {len(expected)} reference')
    print(f'  Correct fingering:      {correct}  ({100 * correct / max(n, 1):.1f}%)')
    print(f'  Wrong finger:           {wrong}')
    print(f'  Hand not detected:      {no_hand}')

    # Note-level accuracy, decoupled from fingering: align the played stream to
    # the reference (tempo-invariant) so wrong/missing/extra notes — which the
    # live finger-matching silently drops — get counted. The warp also yields a
    # played→reference tempo scale/offset usable for A/V-MIDI sync.
    from webui.realtime.note_align import align as align_notes, estimate_offset_scale
    na = align_notes(played_notes, [(e.time, e.pitch) for e in expected])
    n_scale, n_offset, n_rms = estimate_offset_scale(na.warp)
    print(f'  Note accuracy:          {na.correct}/{na.n_expected} '
          f'({100 * na.note_accuracy:.1f}%)  '
          f'wrong={na.wrong} missing={na.missing} extra={na.extra}')
    print(f'  Tempo (played→ref):     scale={n_scale:.3f} offset={n_offset:+.2f}s rms={n_rms:.3f}s')

    if args.output_json:
        import json
        with open(args.output_json, 'w') as f:
            json.dump({
                'fingering': {
                    'evaluated': n, 'reference': len(expected),
                    'correct': correct, 'wrong': wrong, 'no_hand': no_hand,
                },
                'notes': {
                    'accuracy': round(na.note_accuracy, 4),
                    'correct': na.correct, 'wrong': na.wrong,
                    'missing': na.missing, 'extra': na.extra,
                    'played': na.n_played, 'reference': na.n_expected,
                    'tempo_scale': round(n_scale, 4),
                    'tempo_offset_s': round(n_offset, 3),
                    'align_rms_s': round(n_rms, 4),
                },
                'onsets': [r.__dict__ for r in results],
            }, f, indent=2)
        print(f'  Results written → {args.output_json}')

    if broadcaster:
        broadcaster.publish({
            'type': 'done',
            'total': n,
            'correct': correct,
            'wrong': wrong,
            'no_hand': no_hand,
            'note_accuracy': round(na.note_accuracy, 4),
            'notes_missing': na.missing,
            'notes_extra': na.extra,
        })
        if args.ws_linger > 0:
            import time
            print(f'[broadcaster] lingering {args.ws_linger}s for late connections '
                  f'(Ctrl-C to exit immediately)')
            try:
                time.sleep(args.ws_linger)
            except KeyboardInterrupt:
                pass
        broadcaster.stop()


if __name__ == '__main__':
    main()
