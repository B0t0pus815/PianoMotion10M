"""Video + MIDI source abstractions for Phase B real-time pipeline.

Each source has two modes:
- live:   webcam (cv2.VideoCapture(int)) / MIDI input port (rtmidi via mido)
- replay: mp4 file / .mid file, paced against a wall clock so the pipeline
          behaves identically to the live case end-to-end.

The runner uses a single clock — replay sources sleep to keep video frames in
sync with their native fps, and MIDI events fire when wall-time crosses each
event's absolute timestamp.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator, Optional

import cv2
import mido
import numpy as np


@dataclass
class Frame:
    timestamp: float
    image: np.ndarray
    frame_idx: int


@dataclass
class MidiEvent:
    timestamp: float
    type: str
    note: int
    velocity: int


class VideoSource:
    def __init__(self, src, realtime: bool = True):
        self.src = src
        self.mode = 'live' if isinstance(src, int) else 'replay'
        self.realtime = realtime
        self.cap = cv2.VideoCapture(src)
        if not self.cap.isOpened():
            raise RuntimeError(f'VideoSource: cannot open {src!r}')
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.start_wall: Optional[float] = None
        self.frame_idx = 0

    def __iter__(self) -> Iterator[Frame]:
        return self

    def __next__(self) -> Frame:
        if self.start_wall is None:
            self.start_wall = time.monotonic()
        ok, img = self.cap.read()
        if not ok:
            raise StopIteration

        if self.mode == 'replay':
            target = self.frame_idx / self.fps
            if self.realtime:
                now = time.monotonic() - self.start_wall
                sleep = target - now
                if sleep > 0:
                    time.sleep(sleep)
            ts = target
        else:
            ts = time.monotonic() - self.start_wall

        f = Frame(timestamp=ts, image=img, frame_idx=self.frame_idx)
        self.frame_idx += 1
        return f

    def close(self):
        self.cap.release()


class MidiSource:
    """Replay or live MIDI source. Use poll(current_time) to consume events
    whose timestamp has been reached."""

    def __init__(self, src: str):
        self.src = src
        self.mode = 'replay' if src.lower().endswith(('.mid', '.midi')) else 'live'
        self._buffer: list[MidiEvent] = []
        self._cursor = 0
        self._port = None
        self._port_open_wall: Optional[float] = None
        if self.mode == 'replay':
            self._load_midi_file(src)
        else:
            self._open_port(src)

    def _load_midi_file(self, path: str):
        mid = mido.MidiFile(path)
        t = 0.0
        events: list[MidiEvent] = []
        for msg in mid:
            t += msg.time
            if msg.is_meta:
                continue
            if msg.type == 'note_on' and msg.velocity > 0:
                events.append(MidiEvent(t, 'note_on', msg.note, msg.velocity))
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                events.append(MidiEvent(t, 'note_off', msg.note, 0))
        events.sort(key=lambda e: e.timestamp)
        self._buffer = events

    def _open_port(self, port_name: str):
        self._port = mido.open_input(port_name, callback=self._on_msg)
        self._port_open_wall = time.monotonic()

    def _on_msg(self, msg):
        if self._port_open_wall is None:
            return
        ts = time.monotonic() - self._port_open_wall
        if msg.type == 'note_on' and msg.velocity > 0:
            self._buffer.append(MidiEvent(ts, 'note_on', msg.note, msg.velocity))
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            self._buffer.append(MidiEvent(ts, 'note_off', msg.note, 0))

    def poll(self, current_time: float) -> list[MidiEvent]:
        if self.mode == 'replay':
            out = []
            while (self._cursor < len(self._buffer)
                   and self._buffer[self._cursor].timestamp <= current_time):
                out.append(self._buffer[self._cursor])
                self._cursor += 1
            return out
        out = self._buffer[:]
        self._buffer.clear()
        return out

    def replay_events(self) -> list:
        """All loaded note events (replay mode only) — for pre-run alignment.
        Empty in live mode, where events arrive incrementally over the port."""
        return list(self._buffer) if self.mode == 'replay' else []

    def close(self):
        if self._port is not None:
            self._port.close()
