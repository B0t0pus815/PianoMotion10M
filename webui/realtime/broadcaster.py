"""Async WebSocket broadcaster running in a background thread.

The runner loop is synchronous (cv2 + MediaPipe). This module spins up an
asyncio event loop in a daemon thread and exposes a thread-safe `publish()`
that schedules a broadcast onto it.

Each connected client receives all events published after its connection.
A short history (default 1024) is replayed on connect so a React client that
opens after the runner finished still gets the full event timeline — useful
for the --fast replay demo flow where Python burns through the file in
seconds before the browser is open.
"""
from __future__ import annotations

import asyncio
import collections
import json
import threading
from typing import Optional

import websockets


class Broadcaster:
    def __init__(self, port: int = 8766, host: str = '0.0.0.0',
                 history_size: int = 1024):
        self.host = host
        self.port = port
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server = None
        self._clients: set = set()
        self._history: collections.deque = collections.deque(maxlen=history_size)
        self._ready = threading.Event()
        self._start_error: Optional[Exception] = None

    async def _handler(self, ws):
        self._clients.add(ws)
        try:
            for msg in list(self._history):
                await ws.send(msg)
            async for _ in ws:
                pass
        finally:
            self._clients.discard(ws)

    async def _broadcast_async(self, msg: str):
        self._history.append(msg)
        targets = list(self._clients)
        if not targets:
            return
        await asyncio.gather(
            *(self._safe_send(c, msg) for c in targets),
            return_exceptions=True,
        )

    async def _safe_send(self, c, msg):
        try:
            await c.send(msg)
        except Exception:
            self._clients.discard(c)

    def publish(self, payload: dict):
        """Thread-safe — call from the runner's sync loop."""
        if self._loop is None or not self._loop.is_running():
            return
        msg = json.dumps(payload, separators=(',', ':'))
        asyncio.run_coroutine_threadsafe(self._broadcast_async(msg), self._loop)

    def _run(self):
        async def serve():
            self._server = await websockets.serve(self._handler, self.host, self.port)
            self._ready.set()
            await asyncio.Future()

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(serve())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._start_error = e
            self._ready.set()

    def start(self) -> bool:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            print('[broadcaster] timeout starting server')
            return False
        if self._start_error is not None:
            print(f'[broadcaster] failed to start: {self._start_error}')
            return False
        print(f'[broadcaster] listening on ws://{self.host}:{self.port}'
              f'  (history={self._history.maxlen})')
        return True

    def stop(self):
        if self._loop is None or not self._loop.is_running():
            return

        async def _close_all():
            for c in list(self._clients):
                try:
                    await c.close()
                except Exception:
                    pass
            if self._server is not None:
                self._server.close()
                await self._server.wait_closed()

        fut = asyncio.run_coroutine_threadsafe(_close_all(), self._loop)
        try:
            fut.result(timeout=2.0)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
