#!/usr/bin/env bash
# Defense-day demo launcher. Spawns webui http server + realtime runner
# in tmux, then opens the browser at PracticeScreen.
#
# Usage:
#   bin/demo_defense.sh [song_id]   # song_id ∈ {canon, summer}; default: canon
#
# After running:
#   - tmux session 'thesis_demo' has two panes: HTTP server + runner
#   - Browser opens http://localhost:8765/webui/
#   - Stop demo:   tmux kill-session -t thesis_demo
#   - Attach demo: tmux attach -t thesis_demo

set -euo pipefail

SONG="${1:-canon}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

case "$SONG" in
    canon)
        MIDI="input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid"
        USER_VIDEO="results/canon_biomech_v4_kb.mp4"
        REFERENCE="results/canon_arlstm_fingertips.json"
        ;;
    summer)
        MIDI="input_songs/[Piano Cover] 久石讓 Joe Hisaishi - 菊次郎的夏天(Summer)一聽前奏就知道的旋律_extracted.mid"
        USER_VIDEO="results/summer_arlstm_kb.mp4"  # use Stage B render as fake user
        REFERENCE="results/summer_arlstm_fingertips.json"
        ;;
    *)
        echo "Unknown song: $SONG. Use 'canon' or 'summer'." >&2
        exit 1
        ;;
esac

# Sanity checks
command -v tmux >/dev/null || { echo "tmux not installed (sudo apt install tmux)" >&2; exit 1; }
[[ -f "$MIDI" ]]       || { echo "MIDI not found: $MIDI" >&2; exit 1; }
[[ -f "$REFERENCE" ]]  || { echo "Reference fingertips not found: $REFERENCE — run Stage B render first" >&2; exit 1; }

# Kill any old session
tmux kill-session -t thesis_demo 2>/dev/null || true

# Activate conda env path. Adjust if your conda lives elsewhere.
CONDA_INIT='source ~/anaconda3/etc/profile.d/conda.sh && conda activate pianomotion'

# Pane 1: HTTP server
tmux new-session -d -s thesis_demo -n http \
    "$CONDA_INIT && cd '$REPO_ROOT' && python webui/serve.py 8765; bash"

# Pane 2: realtime runner with judge events broadcast on WS 8766
tmux split-window -t thesis_demo:http -h \
    "$CONDA_INIT && cd '$REPO_ROOT' && sleep 2 && \
     python -m webui.realtime.runner \
         --video '$USER_VIDEO' \
         --midi '$MIDI' \
         --reference '$REFERENCE' \
         --fast --no-preview \
         --ws-port 8766 --ws-linger 3600 \
         --clip-record --clip-threshold 0.6 --clip-window 8 \
         --clip-pre 5 --clip-post 5; bash"

# Layout: even split
tmux select-layout -t thesis_demo:http even-horizontal

# Launch browser after small delay
( sleep 3 && xdg-open "http://localhost:8765/webui/" >/dev/null 2>&1 ) &

cat <<EOF

╔═══════════════════════════════════════════════════════════╗
║  Thesis demo session started ($SONG)                       ║
║                                                            ║
║  Browser:   http://localhost:8765/webui/                  ║
║  tmux:      tmux attach -t thesis_demo                    ║
║  WS port:   8766 (broadcaster for FeedbackOverlay events) ║
║  Stop:      tmux kill-session -t thesis_demo              ║
║                                                            ║
║  Demo talking points (see thesis/defense_slides.md):       ║
║    1. Hero video = Stage B ArLSTM render                  ║
║    2. PianoRoll shows falling-keys with status colors     ║
║    3. ScoreRing reflects per-onset accuracy live          ║
║    4. Stage C smoke test: 'Logic Track (Ramoneda ArLSTM)' ║
║       line appears in runner pane on the right            ║
╚═══════════════════════════════════════════════════════════╝
EOF
