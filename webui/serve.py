#!/usr/bin/env python3
"""Serve HandKeys AI webui + PianoMotion10M results/ + input_songs/.

The webui's songs.json references `../results/*.mp4` and `../input_songs/*.mp3`,
so this script launches the HTTP server from the *project root* (one level above
this file) and opens the browser at `/webui/`.

Usage:
    python webui/serve.py [port]

Default port is 8765.
"""
from __future__ import annotations

import http.server
import os
import socketserver
import sys
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 8765


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".mp4": "video/mp4",
        ".mp3": "audio/mpeg",
        ".json": "application/json",
        ".js": "application/javascript",
        ".jsx": "application/javascript",
    }

    def end_headers(self):
        # Helpful for big media files
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def log_message(self, fmt, *args):
        # Only log non-200/206 so console isn't flooded by video range requests
        try:
            status = int(args[1])
            if status not in (200, 206, 304):
                super().log_message(fmt, *args)
        except (IndexError, ValueError):
            super().log_message(fmt, *args)


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    os.chdir(PROJECT_ROOT)
    with socketserver.ThreadingTCPServer(("", port), Handler) as httpd:
        url = f"http://localhost:{port}/webui/"
        print(f"HandKeys AI serving from {PROJECT_ROOT}")
        print(f"  → {url}")
        print("  (Ctrl-C to stop)")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
