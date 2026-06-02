"""Tiny WS client for testing the runner's broadcast feed.

Connects to ws://localhost:<port>, prints each JSON message, and exits when
the server closes or after --max-msgs messages.

Usage:
    python -m webui.realtime.ws_smoketest --port 8766 --max-msgs 50
"""
from __future__ import annotations

import argparse
import asyncio
import json

import websockets


async def consume(url: str, max_msgs: int | None, retry_seconds: float = 0.0):
    deadline = asyncio.get_event_loop().time() + retry_seconds
    while True:
        try:
            ws_ctx = websockets.connect(url, max_size=2**20)
            ws = await ws_ctx.__aenter__()
            break
        except (OSError, ConnectionRefusedError) as e:
            if asyncio.get_event_loop().time() >= deadline:
                print(f'[ws] cannot connect after {retry_seconds:.1f}s: {e}')
                return
            print(f'[ws] retrying... ({e})')
            await asyncio.sleep(0.5)
    try:
            print(f'[ws] connected → {url}')
            n = 0
            async for raw in ws:
                n += 1
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    print(f'  raw: {raw[:200]}')
                    continue
                t = data.get('type')
                if t == 'ready':
                    print(f'  ready: expected={data.get("expected_count")} '
                          f'video={data.get("video")}')
                elif t == 'onset':
                    tag = 'OK ' if data['correct'] else (
                        '-- ' if data.get('detected_finger') is None else 'X  ')
                    print(f'  [{tag}] t={data["time"]:.2f} '
                          f'note={data["pitch"]}  '
                          f'exp={data["expected_hand"][0].upper()}/{data["expected_finger"]}  '
                          f'got={data.get("detected_finger") or "-"}  '
                          f'conf={data["confidence"]:.2f}')
                elif t == 'done':
                    print(f'  done: total={data["total"]} correct={data["correct"]} '
                          f'wrong={data["wrong"]} no_hand={data["no_hand"]}')
                else:
                    print(f'  [{t}] {data}')
                if max_msgs is not None and n >= max_msgs:
                    break
            print(f'[ws] {n} messages received')
    except (websockets.exceptions.ConnectionClosed, OSError) as e:
        print(f'[ws] disconnected: {e}')
    finally:
        await ws_ctx.__aexit__(None, None, None)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=8766)
    p.add_argument('--host', default='localhost')
    p.add_argument('--max-msgs', type=int)
    p.add_argument('--retry-seconds', type=float, default=20.0,
                   help='retry connection for this many seconds before giving up')
    args = p.parse_args()
    url = f'ws://{args.host}:{args.port}'
    asyncio.run(consume(url, args.max_msgs, args.retry_seconds))


if __name__ == '__main__':
    main()
