#!/usr/bin/env bash
# HandKeys AI — Jetson NX dependency setup (LIVE JUDGING + SERVE; no torch).
#
# ⚠ UNVERIFIED ON REAL JETSON HARDWARE. mediapipe/opencv on aarch64 are the
#   fragile parts — if pip fails, see deploy/README_NX.md §6 / §7.
#
# Usage:  bash deploy/setup_nx.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REQ="$HERE/requirements-nx.txt"

echo "==> [1/4] system packages (apt)"
sudo apt-get update
# v4l2 (webcam), ALSA (MIDI), and JetPack's OpenCV are best via apt on ARM.
sudo apt-get install -y --no-install-recommends \
    python3-pip python3-opencv v4l-utils alsa-utils libasound2-dev || \
    echo "⚠ some apt packages missing — continue, but verify webcam/MIDI access"

echo "==> [2/4] python deps (pip, NO torch)"
# Drop opencv-python from the pip set if the apt python3-opencv is present
# (avoids a heavy/duplicate ARM build).
if python3 -c "import cv2" 2>/dev/null; then
    grep -v '^opencv-python' "$REQ" > /tmp/req-nx.txt
else
    cp "$REQ" /tmp/req-nx.txt
fi
python3 -m pip install --upgrade pip
python3 -m pip install -r /tmp/req-nx.txt || cat <<'EOF'
⚠ pip install failed — most likely mediapipe on aarch64.
  Try NVIDIA's prebuilt wheel, or fall back to the ONNX fingering path
  (deploy/README_NX.md §7). The rest of the stack (numpy/rtmidi/websockets/
  pianoplayer) is pure-python and should install fine.
EOF

echo "==> [3/4] verify imports (torch-free judge path)"
python3 - <<'PY'
ok=True
for m in ("numpy","cv2","pretty_midi","rtmidi","websockets","pianoplayer","mediapipe"):
    try:
        __import__(m); print(f"  ok  {m}")
    except Exception as e:
        ok=False; print(f"  XX  {m}: {e}")
print("ALL GOOD" if ok else "SOME MISSING — see README_NX.md")
PY

echo "==> [4/4] open firewall ports for phone access (best-effort)"
sudo ufw allow 8765,8766/tcp 2>/dev/null || echo "  (ufw not active — skip)"

echo "==> done. Next: smoke test in deploy/README_NX.md §3."
