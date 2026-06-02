"""Error-triggered video clip recorder for Phase B teaching feedback.

Watches a sliding window of recent onset results; when error rate exceeds the
threshold, snapshots the rolling pre-buffer of camera frames, keeps recording
for `post_seconds` more, then splices a side-by-side video (user vs reference
biomech) via ffmpeg hstack.

Designed for live mode (webcam user vs reference biomech video). In replay
mode the "user" frames are themselves the biomech video, so left and right
panes are identical — still useful for verifying trigger / splicing logic.

Output: clips/<song>_<YYYYMMDD-HHMMSS>_err<rate>.mp4
"""
from __future__ import annotations

import collections
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import cv2
import numpy as np


@dataclass
class ClipConfig:
    pre_seconds: float = 5.0
    post_seconds: float = 5.0
    window_size: int = 8
    trigger_threshold: float = 0.6
    min_window_for_trigger: int = 4
    cooldown_seconds: float = 8.0
    output_dir: str = 'clips'
    fps: int = 30
    ffmpeg_bin: str = '/usr/bin/ffmpeg'
    # Downsize for the saved clip to keep file + memory cost sane.
    target_width: int = 640
    target_height: int = 360


class ClipRecorder:
    def __init__(self,
                 cfg: ClipConfig,
                 song_name: str,
                 reference_video_path: Optional[str] = None,
                 on_event: Optional[Callable[[dict], None]] = None):
        self.cfg = cfg
        self.song = song_name
        self.ref_video = reference_video_path
        self.on_event = on_event or (lambda e: None)

        self._pre_buf: collections.deque = collections.deque()
        self._results_win: collections.deque = collections.deque(maxlen=cfg.window_size)

        self._recording = False
        self._record_trigger_time = 0.0
        self._record_trigger_rate = 0.0
        self._record_post: list = []
        self._record_pre_snapshot: list = []
        self._next_trigger_after = 0.0  # video-time domain

        os.makedirs(cfg.output_dir, exist_ok=True)

    def _downscale(self, frame: np.ndarray) -> np.ndarray:
        if frame.shape[1] == self.cfg.target_width and frame.shape[0] == self.cfg.target_height:
            return frame
        return cv2.resize(frame, (self.cfg.target_width, self.cfg.target_height),
                          interpolation=cv2.INTER_AREA)

    def push_frame(self, timestamp: float, frame: Optional[np.ndarray]):
        if frame is None:
            return
        small = self._downscale(frame)

        # Always maintain rolling pre-buffer
        self._pre_buf.append((timestamp, small))
        cutoff = timestamp - self.cfg.pre_seconds
        while self._pre_buf and self._pre_buf[0][0] < cutoff:
            self._pre_buf.popleft()

        if self._recording:
            self._record_post.append((timestamp, small))
            if timestamp - self._record_trigger_time >= self.cfg.post_seconds:
                self._finalize_clip()

    def push_result(self, timestamp: float, ok: bool, has_hand: bool):
        """Called once per evaluated onset.
        ok: r.correct
        has_hand: r.detected_finger is not None
        """
        if self._recording:
            return
        if timestamp < self._next_trigger_after:
            return
        is_error = not ok  # both wrong-finger and no-hand count as error
        self._results_win.append((timestamp, is_error))

        if len(self._results_win) < self.cfg.min_window_for_trigger:
            return
        err_count = sum(1 for (_, e) in self._results_win if e)
        err_rate = err_count / len(self._results_win)
        if err_rate >= self.cfg.trigger_threshold:
            self._fire_trigger(timestamp, err_rate)

    def _fire_trigger(self, t: float, err_rate: float):
        self._recording = True
        self._record_trigger_time = t
        self._record_trigger_rate = err_rate
        # Snapshot pre-buffer so subsequent push_frame doesn't mutate it.
        self._record_pre_snapshot = list(self._pre_buf)
        self._record_post = []
        self.on_event({
            'type': 'clip_trigger',
            'time': round(t, 3),
            'error_rate': round(err_rate, 3),
            'window_size': len(self._results_win),
        })

    def _finalize_clip(self):
        if not self._recording:
            return
        pre_frames = self._record_pre_snapshot[:]
        post_frames = self._record_post[:]
        trigger_time = self._record_trigger_time
        err_rate = self._record_trigger_rate

        self._recording = False
        self._record_pre_snapshot = []
        self._record_post = []
        self._next_trigger_after = trigger_time + self.cfg.cooldown_seconds
        self._results_win.clear()

        # Render off the main loop so we don't stall the runner.
        t = threading.Thread(
            target=self._render_clip,
            args=(pre_frames, post_frames, trigger_time, err_rate),
            daemon=True,
        )
        t.start()

    def _safe_song_name(self) -> str:
        return ''.join(c if c.isalnum() or c in '-_' else '_' for c in self.song)[:48]

    def _render_clip(self, pre_frames, post_frames, trigger_time, err_rate):
        all_frames = pre_frames + post_frames
        if not all_frames:
            return

        timestamp_str = time.strftime('%Y%m%d-%H%M%S')
        base = os.path.join(
            self.cfg.output_dir,
            f'{self._safe_song_name()}_{timestamp_str}_err{int(err_rate * 100)}',
        )
        user_path = f'{base}_user.mp4'
        ref_path = f'{base}_ref.mp4'
        out_path = f'{base}.mp4'

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(
            user_path, fourcc, self.cfg.fps,
            (self.cfg.target_width, self.cfg.target_height),
        )
        for _, f in all_frames:
            writer.write(f)
        writer.release()

        composed = False
        if self.ref_video and os.path.exists(self.ref_video):
            ref_start = max(0.0, trigger_time - self.cfg.pre_seconds)
            duration = self.cfg.pre_seconds + self.cfg.post_seconds
            try:
                subprocess.run(
                    [self.cfg.ffmpeg_bin, '-y',
                     '-ss', f'{ref_start:.2f}',
                     '-i', self.ref_video,
                     '-t', f'{duration:.2f}',
                     '-vf', f'scale={self.cfg.target_width}:{self.cfg.target_height}',
                     '-an',
                     '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                     ref_path],
                    check=True, capture_output=True, timeout=30,
                )
                subprocess.run(
                    [self.cfg.ffmpeg_bin, '-y',
                     '-i', user_path, '-i', ref_path,
                     '-filter_complex',
                     '[0:v]drawtext=text=USER:x=10:y=10:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5[u];'
                     '[1:v]drawtext=text=REFERENCE:x=10:y=10:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5[r];'
                     '[u][r]hstack=inputs=2[out]',
                     '-map', '[out]',
                     '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                     out_path],
                    check=True, capture_output=True, timeout=60,
                )
                os.remove(user_path)
                os.remove(ref_path)
                composed = True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                err_msg = ''
                if hasattr(e, 'stderr') and e.stderr:
                    err_msg = e.stderr.decode(errors='ignore')[:300]
                print(f'[clip] ffmpeg failed, keeping user-only: {err_msg}')

        if not composed:
            # Fallback: just rename user_path → out_path
            if os.path.exists(user_path):
                os.replace(user_path, out_path)

        self.on_event({
            'type': 'clip_done',
            'path': out_path,
            'duration': round(len(all_frames) / self.cfg.fps, 2),
            'time': round(trigger_time, 3),
            'error_rate': round(err_rate, 3),
            'song': self.song,
            'composed': composed,
        })
        print(f'[clip] saved → {out_path}  '
              f'(err={err_rate * 100:.0f}%  {len(all_frames)} frames)')
